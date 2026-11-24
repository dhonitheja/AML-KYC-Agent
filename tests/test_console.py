"""Phase 5 analyst console (FR-012). `analysts` is pure; the rest needs the running api + postgres.
Alerts are inserted directly as aml_worker (synthetic, fresh uuid4) so no Kafka consumer reacts to them."""
import base64
import json
import uuid
import urllib.error
import urllib.request

import psycopg
from psycopg.types.json import Jsonb

import api
from pipeline import DSN

ANALYST = ("analyst1", "synthetic-analyst-1")  # demo value from secrets/demo/analysts


def call(path, body=None, auth=ANALYST, content_type="application/json"):
    headers = {"Content-Type": content_type} if body is not None else {}
    if auth:
        headers["Authorization"] = "Basic " + base64.b64encode(":".join(auth).encode()).decode()
    data = None if body is None else (body if isinstance(body, bytes) else json.dumps(body).encode())
    req = urllib.request.Request(f"http://api:8000{path}", data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.load(r) if "json" in r.headers.get("content-type", "") else r.read()
    except urllib.error.HTTPError as e:
        return e.code, json.load(e)


def make_alert():
    tid = uuid.uuid4()
    with psycopg.connect(DSN) as db:
        db.execute("""INSERT INTO transactions(id,run_id,account,counterparty,amount_cents,direction,channel,occurred_at)
            VALUES (%s,%s,%s,'Juniper Orchard Services',8090000,'debit','wire',now())""",
                   (tid, uuid.uuid4(), f"ACC-{tid.hex[:8]}"))
        db.execute("""INSERT INTO audit(actor,action,inputs,transaction_id) VALUES ('test','alerted.v1',%s,%s)""",
                   (Jsonb({"transaction_id": str(tid), "score": 65, "alert": True,
                           "rules": [{"rule": "rapid_pass_through", "points": 65, "evidence": {}}]}), tid))
    return str(tid)


def test_analysts_file_parsing(tmp_path):
    f = tmp_path / "analysts"
    f.write_text("alice:pw:with:colons\nBad Name:x\nempty:\nnoseparator\n")
    assert api.analysts.__wrapped__(str(f)) == {"alice": "pw:with:colons"}
    assert api.analysts.__wrapped__(str(tmp_path / "missing")) == {}


def test_console_requires_valid_credentials():
    for path in ("/console", "/console/queue"):
        assert call(path, auth=None)[0] == 401
        assert call(path, auth=("analyst1", "wrong"))[0] == 401
        assert call(path, auth=("nobody", "synthetic-analyst-1"))[0] == 401
    status, page = call("/console")
    assert status == 200 and b"Alert queue" in page


def test_decision_recorded_once_with_analyst_identity():
    tid = make_alert()
    status, queue = call("/console/queue")
    assert status == 200
    item, = [a for a in queue if a["transaction_id"] == tid]
    assert item["draft"] is None and item["alert"]["score"] == 65

    body = {"transaction_id": tid, "disposition": "escalate", "rationale": "Funds out within a day of large credits."}
    status, rec = call("/console/decisions", body)
    assert status == 200 and rec["analyst"] == "analyst1" and rec["draft_event_id"] is None
    assert call("/console/decisions", dict(body, disposition="close_no_action"), auth=("analyst2", "synthetic-analyst-2"))[0] == 409

    with psycopg.connect(DSN) as db:
        rows = db.execute("SELECT actor, inputs FROM audit WHERE action='analyst.decided.v1' AND transaction_id=%s",
                          (tid,)).fetchall()
    assert rows == [("analyst:analyst1", rec)]
    assert tid not in {a["transaction_id"] for a in call("/console/queue")[1]}  # worklist drops decided alerts


def test_decision_rejects_bad_input():
    tid = make_alert()
    ok = {"transaction_id": tid, "disposition": "escalate", "rationale": "Ten or more characters."}
    assert call("/console/decisions", dict(ok, transaction_id=str(uuid.uuid4())))[0] == 404
    assert call("/console/decisions", dict(ok, disposition="clear"))[0] == 422
    assert call("/console/decisions", dict(ok, rationale="short"))[0] == 422
    assert call("/console/decisions", dict(ok, analyst="analyst2"))[0] == 422  # identity comes from auth only
    assert call("/console/decisions", json.dumps(ok).encode(), content_type="text/plain")[0] in (415, 422)
    assert call("/console/decisions", ok, auth=None)[0] == 401
    with psycopg.connect(DSN) as db:
        assert db.execute("SELECT count(*) FROM audit WHERE action='analyst.decided.v1' AND transaction_id=%s",
                          (tid,)).fetchone()[0] == 0
