-- Phase 5: one analyst disposition per alerted transaction (FR-012.3). Idempotent; re-run on every start.
CREATE UNIQUE INDEX IF NOT EXISTS audit_analyst_decided_once ON audit(transaction_id)
    WHERE action='analyst.decided.v1';
