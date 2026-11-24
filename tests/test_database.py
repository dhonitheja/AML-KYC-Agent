import uuid
from datetime import datetime, timezone
import psycopg
from pipeline import DSN, event, record_transaction


def test_replay_is_idempotent_and_multiple_audit_actions_allowed():
    row = event(uuid.uuid4(),0,None,True)
    with psycopg.connect(DSN) as db:
        record_transaction(db,row,{"topic":"test"})
        record_transaction(db,row,{"topic":"test"})
        assert db.execute("SELECT count(*) FROM transactions WHERE id=%s",(row["id"],)).fetchone()[0] == 1
        db.execute("""INSERT INTO audit(actor, action, transaction_id, inputs)
                   VALUES ('pytest','scored.v1',%s,'{}')""",(row["id"],))
        assert db.execute("SELECT count(*) FROM audit WHERE transaction_id=%s",(row["id"],)).fetchone()[0] == 2
        db.rollback()


def test_batch_with_duplicate_message_records_once():
    from pipeline import record_transactions
    rows = [event(uuid.uuid4(), i, datetime.now(timezone.utc)) for i in range(3)]
    with psycopg.connect(DSN) as db:
        new = record_transactions(db, [(r, {"topic": "test"}) for r in rows + [rows[1]]])
        assert new == {r["id"] for r in rows}
        assert record_transactions(db, [(rows[0], {"topic": "test"})]) == set()  # replay inserts nothing
        assert db.execute("SELECT count(*) FROM audit WHERE action='transaction.recorded' AND transaction_id = ANY(%s::uuid[])",
                          ([r["id"] for r in rows],)).fetchone()[0] == 3
        db.rollback()
