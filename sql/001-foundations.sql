CREATE EXTENSION vector;
CREATE ROLE aml_worker LOGIN PASSWORD 'synthetic-worker';
CREATE TABLE cases (
  id text PRIMARY KEY, customer text NOT NULL, status text NOT NULL DEFAULT 'Open',
  created_at timestamptz NOT NULL DEFAULT now()
);
INSERT INTO cases(id,customer) VALUES ('AML-1042','Northstar Trading');
CREATE TABLE transactions (
  id uuid PRIMARY KEY, run_id uuid NOT NULL, account text NOT NULL,
  case_id text REFERENCES cases, counterparty text NOT NULL, amount_cents bigint NOT NULL CHECK(amount_cents>0),
  direction text NOT NULL CHECK(direction IN ('credit','debit')), channel text NOT NULL,
  occurred_at timestamptz NOT NULL, received_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX ON transactions(run_id);
CREATE TABLE audit (
  event_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  actor text NOT NULL, action text NOT NULL, case_id text REFERENCES cases,
  transaction_id uuid UNIQUE REFERENCES transactions, inputs jsonb NOT NULL, model_version text, prompt_version text
);
INSERT INTO audit(actor,action,case_id,inputs) VALUES ('seed','case.opened','AML-1042','{"customer":"Northstar Trading"}');
GRANT SELECT ON cases,transactions,audit TO aml_worker;
GRANT INSERT ON transactions,audit TO aml_worker;
GRANT USAGE ON SEQUENCE audit_event_id_seq TO aml_worker;
