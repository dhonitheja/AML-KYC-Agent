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
