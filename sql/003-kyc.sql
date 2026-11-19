BEGIN;
CREATE TABLE IF NOT EXISTS kyc_applications (
    id uuid PRIMARY KEY, application jsonb NOT NULL, result jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS screened_counterparties (
    account text NOT NULL, name_key text NOT NULL, snapshot text NOT NULL,
    PRIMARY KEY(account,name_key,snapshot)
);
GRANT SELECT,INSERT ON kyc_applications,screened_counterparties TO aml_worker;
COMMIT;
