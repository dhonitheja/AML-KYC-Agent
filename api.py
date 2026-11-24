from uuid import UUID

import psycopg
from fastapi import FastAPI, HTTPException
from pipeline import DSN

app = FastAPI(title="Synthetic AML scoring")


@app.get("/scores/{transaction_id}")
def score(transaction_id: UUID):
    with psycopg.connect(DSN) as db:
        row = db.execute("SELECT inputs FROM audit WHERE transaction_id=%s AND action='scored.v1'",
                         (transaction_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "No recorded score")
    return row[0]


@app.get("/alerts")
def alerts():
    with psycopg.connect(DSN) as db:
        rows = db.execute("SELECT inputs FROM audit WHERE action='alerted.v1' ORDER BY event_id DESC LIMIT 100")
        return [row[0] for row in rows]


from kyc import Application, audit, review
from psycopg.types.json import Jsonb
from watchlist import active


@app.post("/onboarding")
def onboard(application: Application):
    body=application.model_dump(mode="json")
    with psycopg.connect(DSN) as db:
        result=review(application,active())
        created=db.execute("""INSERT INTO kyc_applications(id,application,result)
            VALUES (%s,%s,%s) ON CONFLICT DO NOTHING RETURNING id""",
            (application.application_id,Jsonb(body),Jsonb(result))).fetchone()
        if not created:
            original,existing=db.execute("SELECT application,result FROM kyc_applications WHERE id=%s",
                                         (application.application_id,)).fetchone()
            if original!=body:
                raise HTTPException(409,"Application ID already belongs to different input")
            return existing
        audit(db,"kyc.reviewed.v1",{k:v for k,v in result.items() if k!="screening"})
        for subject in result["screening"]:
            audit(db,"onboarding.screened.v1",dict(application_id=str(application.application_id),**subject))
    return result


# Phase 5 · analyst console (FR-012, ADR-031). Humans record dispositions; nothing here changes a case.
import hmac
import re
from functools import lru_cache
from pathlib import Path
from typing import Literal

from fastapi import Depends, Request
from fastapi.responses import FileResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel, ConfigDict, Field

ANALYSTS_FILE = "/run/secrets/analysts"
NAME = re.compile(r"[a-z0-9_.-]{1,64}")
basic = HTTPBasic(realm="aml-console")


@lru_cache
def analysts(path=ANALYSTS_FILE):
    """`name:password` per line. Missing file = no analysts = every console request is refused.
    ponytail: plaintext secret file like the DB passwords; swap for an IdP (OIDC) before real use."""
    try:
        lines = Path(path).read_text().splitlines()
    except FileNotFoundError:
        return {}
    users = dict(line.split(":", 1) for line in lines if ":" in line)
    return {name: pw for name, pw in users.items() if NAME.fullmatch(name) and pw}


def analyst(creds: HTTPBasicCredentials = Depends(basic)):
    users = analysts()
    expected = users.get(creds.username, "\0")  # compare even for unknown names
    ok = hmac.compare_digest(creds.password.encode(), expected.encode())
    if not ok or creds.username not in users:
        raise HTTPException(401, "Invalid credentials", headers={"WWW-Authenticate": 'Basic realm="aml-console"'})
    return creds.username


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    transaction_id: UUID
    disposition: Literal["escalate", "close_no_action", "request_information"]
    rationale: str = Field(min_length=10, max_length=2000)
    draft_event_id: int | None  # the draft the analyst was shown; null = none shown (required, so it is explicit)


# ponytail: newest 100 undecided alerts; add paging/filters when one analyst page stops covering the backlog.
QUEUE = """SELECT a.transaction_id, a.case_id, a.inputs, t.account, t.counterparty, t.amount_cents, t.direction,
        t.occurred_at, d.event_id, d.inputs->'draft', d.model_version, d.inputs->'consistency_warning',
        s.inputs->>'reason'
    FROM audit a JOIN transactions t ON t.id=a.transaction_id
    LEFT JOIN audit d ON d.action='investigation.drafted.v1' AND d.transaction_id=a.transaction_id
    LEFT JOIN audit s ON s.action='investigation.skipped.v1' AND s.inputs->>'alert_key'=a.transaction_id::text
    WHERE a.action='alerted.v1' AND NOT EXISTS (SELECT 1 FROM audit x
        WHERE x.action='analyst.decided.v1' AND x.transaction_id=a.transaction_id)
    ORDER BY a.event_id DESC LIMIT 100"""


@app.get("/console", include_in_schema=False)
def console(_: str = Depends(analyst)):
    return FileResponse(Path(__file__).with_name("console.html"))


@app.get("/console/queue")
def queue(_: str = Depends(analyst)):
    with psycopg.connect(DSN) as db:
        rows = db.execute(QUEUE).fetchall()
    keys = ("transaction_id", "case_id", "alert", "account", "counterparty", "amount_cents", "direction",
            "occurred_at", "draft_event_id", "draft", "model_version", "consistency_warning", "skip_reason")
    return [dict(zip(keys, row)) for row in rows]


@app.post("/console/decisions")
def decide(decision: Decision, request: Request, name: str = Depends(analyst)):
    # CSRF: browsers resend Basic credentials cross-site, but cannot send JSON cross-origin without a preflight.
    if request.headers.get("content-type", "").split(";")[0].strip() != "application/json":
        raise HTTPException(415, "application/json required")
    tid = decision.transaction_id
    with psycopg.connect(DSN) as db:
        alert = db.execute("SELECT case_id FROM audit WHERE action='alerted.v1' AND transaction_id=%s", (tid,)).fetchone()
        if alert is None:
            raise HTTPException(404, "No recorded alert")
        if decision.draft_event_id is not None and db.execute("""SELECT 1 FROM audit WHERE event_id=%s
                AND action='investigation.drafted.v1' AND transaction_id=%s""",
                (decision.draft_event_id, tid)).fetchone() is None:
            raise HTTPException(422, "draft_event_id is not this alert's draft")
        inputs = dict(decision.model_dump(mode="json"), analyst=name)
        try:
            db.execute("""INSERT INTO audit(actor,action,inputs,case_id,transaction_id)
                VALUES (%s,'analyst.decided.v1',%s,%s,%s)""", (f"analyst:{name}", Jsonb(inputs), alert[0], tid))
        except psycopg.errors.UniqueViolation:
            raise HTTPException(409, "Alert already has a recorded decision")
    return inputs
