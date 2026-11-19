BEGIN;
ALTER TABLE audit DROP CONSTRAINT IF EXISTS audit_transaction_id_key;
CREATE UNIQUE INDEX IF NOT EXISTS audit_ingestion_once ON audit(transaction_id) WHERE action='transaction.recorded';
CREATE UNIQUE INDEX IF NOT EXISTS audit_score_once ON audit(transaction_id,action) WHERE action IN ('scored.v1','alerted.v1');
CREATE INDEX IF NOT EXISTS account_event_history ON transactions(account,occurred_at);
COMMIT;
