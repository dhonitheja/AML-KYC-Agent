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
