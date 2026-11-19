import uuid
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
