BEGIN;
SELECT set_config('aml.investigator_password', :'investigator_password', true) IS NOT NULL AS password_set;
DO $$
BEGIN
    -- An unreadable or empty secret must never clear the role's password (ON_ERROR_STOP does not catch it).
    IF current_setting('aml.investigator_password') = '' THEN
        RAISE EXCEPTION 'investigator_password is empty';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='aml_investigator') THEN
        EXECUTE format('CREATE ROLE aml_investigator LOGIN PASSWORD %L', current_setting('aml.investigator_password'));
    ELSE
        EXECUTE format('ALTER ROLE aml_investigator PASSWORD %L', current_setting('aml.investigator_password'));
    END IF;
END $$;
CREATE OR REPLACE VIEW investigator_audit AS
    SELECT event_id, recorded_at, actor, action, case_id, transaction_id, inputs, model_version, prompt_version
    FROM audit
    WHERE action IN ('scored.v1','alerted.v1','payment.screened.v1','investigation.drafted.v1','investigation.skipped.v1');
GRANT SELECT ON transactions, investigator_audit TO aml_investigator;
GRANT INSERT ON audit TO aml_investigator;
GRANT USAGE ON SEQUENCE audit_event_id_seq TO aml_investigator;
CREATE UNIQUE INDEX IF NOT EXISTS audit_investigation_drafted_once ON audit(transaction_id)
    WHERE action='investigation.drafted.v1';
CREATE UNIQUE INDEX IF NOT EXISTS audit_investigation_alert_once ON audit((inputs->>'alert_key'))
    WHERE action IN ('investigation.drafted.v1','investigation.skipped.v1');
CREATE OR REPLACE FUNCTION audit_investigator_guard() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog, public AS $$
BEGIN
    IF current_user = 'aml_investigator' THEN
        IF NEW.actor = 'investigator-v1' AND NEW.action IN ('investigation.drafted.v1','investigation.skipped.v1') THEN
            RETURN NEW;
        END IF;
        RAISE EXCEPTION 'aml_investigator may only append investigator-v1 investigation rows';
    ELSIF NEW.action LIKE 'investigation.%' OR NEW.actor = 'investigator-v1' THEN
        RAISE EXCEPTION 'investigation rows may only be written by aml_investigator';
    END IF;
    RETURN NEW;
END $$;
CREATE OR REPLACE FUNCTION audit_immutable() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog, public AS $$
BEGIN
    RAISE EXCEPTION 'audit is append-only';
END $$;
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgrelid='audit'::regclass AND tgname='audit_investigator_guard_ins') THEN
        CREATE TRIGGER audit_investigator_guard_ins BEFORE INSERT ON audit
            FOR EACH ROW EXECUTE FUNCTION audit_investigator_guard();
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgrelid='audit'::regclass AND tgname='audit_no_update_delete') THEN
        CREATE TRIGGER audit_no_update_delete BEFORE UPDATE OR DELETE ON audit
            FOR EACH ROW EXECUTE FUNCTION audit_immutable();
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgrelid='audit'::regclass AND tgname='audit_no_truncate') THEN
        CREATE TRIGGER audit_no_truncate BEFORE TRUNCATE ON audit
            FOR EACH STATEMENT EXECUTE FUNCTION audit_immutable();
    END IF;
END $$;
COMMIT;
