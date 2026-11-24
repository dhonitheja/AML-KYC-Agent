"""Pure tests for the evaluation set (CS-008 "Evaluation set" v1.2; FR-011.5, FR-009.9, FR-009.10, FR-010.6 AC-5;
US-026). No DB, no key, no network: scenarios run through the production pure functions and StubLLM."""
import ast
import builtins
import io
import json
import socket
import uuid
from pathlib import Path

import pytest

from grounding import Draft, check_grounding
from investigator import build_evidence, decide, render_prompt, validate_draft
from llm import StubLLM

ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / "tests" / "eval" / "scenarios.json").read_text(encoding="utf-8"))
SCENARIOS = {s["name"]: s for s in DATA["scenarios"]}
NAMED = {"AML-1042", "clean", "screening_hit", "large_cash", "injection_in_counterparty", "malformed",
         "many_credit_ids", "forged_not_alerted"}
FABRICATED = "ffffffff-ffff-ffff-ffff-ffffffffffff"
SANCTION_WORDS = ("sanction", "ofac", "sdn", "watchlist match", "screening hit")


def is_uuid(value):
    try:
        return str(uuid.UUID(str(value))) == str(value)
    except ValueError:
        return False


def ids_sent(evidence):
    """CS-008: evidence_ids = alerted id + loaded history ids + (truncated) rule-evidence ids that are UUIDs."""
    ids = {evidence["transaction"]["id"], *(h["id"] for h in evidence["history"])}
    return ids | {str(e) for r in evidence["rules"] for e in r["evidence"] if is_uuid(e)}


def run(scenario):
    """decide -> build_evidence -> StubLLM -> validate_draft -> check_grounding; returns (outcome, details)."""
    db = scenario["db"]
    alert, reason = decide(scenario["raw_alert"].encode(), db["transaction"], db["alerted"])
    if reason:
        return dict(outcome="skipped", reason=reason), None
    evidence = build_evidence(alert, db["transaction"], db["history"], db["scored"], db["screenings"])
    system, user, _ = render_prompt(evidence)
    text, model_id = StubLLM().complete(system, user)
    draft = validate_draft(text, ids_sent(evidence), {r["rule"] for r in db["scored"]["rules"]})
    assert isinstance(draft, Draft), f"stub draft rejected: {draft!r}"
    failed = check_grounding(draft, evidence)
    if failed:
        return dict(outcome="skipped", reason="grounding_failure", failed_checks=failed), None
    return dict(outcome="drafted", recommendation=draft.recommendation), dict(
        evidence=evidence, user=user, draft=draft, text=text, model_id=model_id)


# FR-011.5 AC-1: versioned, >= 8 scenarios covering the eight named cases, each with an expected outcome.
def test_scenario_file_is_versioned_and_complete():
    assert isinstance(DATA["version"], int) and DATA["version"] >= 1
    assert len(DATA["scenarios"]) >= 8 and NAMED <= set(SCENARIOS)
    assert len(SCENARIOS) == len(DATA["scenarios"])  # names are unique
    for s in DATA["scenarios"]:
        exp = s["expected"]
        assert exp["outcome"] in {"drafted", "skipped"}
        assert ("recommendation" in exp) if exp["outcome"] == "drafted" else ("reason" in exp)
        assert set(s["db"]) == {"transaction", "history", "scored", "screenings", "alerted"}
        assert isinstance(s["raw_alert"], str)
        if exp["outcome"] == "drafted":
            assert s["db"]["alerted"] is True  # CS-008: drafted scenarios set alerted explicitly


# US-026 AC-1 / CS-008: every fixture transaction id is a UUID (an underscore id would trip the rules check).
def test_every_fixture_id_is_a_uuid():
    for s in DATA["scenarios"]:
        db = s["db"]
        rows = ([db["transaction"]] if db["transaction"] else []) + db["history"]
        assert all(is_uuid(r["id"]) for r in rows), s["name"]
        for r in (db["scored"] or {}).get("rules", []):
            assert all(is_uuid(e) for e in r["evidence"] if isinstance(e, str)), s["name"]
        if s["name"] != "malformed":
            assert is_uuid(json.loads(s["raw_alert"])["transaction_id"]), s["name"]


# FR-011.5 AC-2: with the stub, every scenario's actual outcome equals its expected outcome.
@pytest.mark.parametrize("name", sorted(SCENARIOS))
def test_stub_outcome_matches_expected(name):
    actual, _ = run(SCENARIOS[name])
    assert actual == SCENARIOS[name]["expected"]


# CS-008: a dedicated check that StubLLM output is grounded for every drafted scenario.
@pytest.mark.parametrize("name", sorted(n for n, s in SCENARIOS.items() if s["expected"]["outcome"] == "drafted"))
def test_stub_output_grounded_for_drafted_scenarios(name):
    _, got = run(SCENARIOS[name])
    assert got is not None and check_grounding(got["draft"], got["evidence"]) == []
    assert got["model_id"] == "stub-v1"


# FR-009.2 AC-1 / US-016 AC-2: AML-1042 evidence carries both credit ids and the debit id, and the draft cites them.
def test_aml_1042_cites_two_credits_and_debit():
    s = SCENARIOS["AML-1042"]
    _, got = run(s)
    wanted = {s["db"]["transaction"]["id"], *(h["id"] for h in s["db"]["history"])}
    assert len(wanted) == 3 and wanted <= ids_sent(got["evidence"])
    assert wanted <= set(got["draft"].cited_transaction_ids)


# FR-009.10 AC-1 / AC-3, US-020 AC-6: >= 60 ids accepted, <= 50 sent per rule, alerted id and most recent kept.
def test_many_credit_ids_truncated_and_citations_checked_against_sent_ids():
    s = SCENARIOS["many_credit_ids"]
    alerted = s["db"]["transaction"]["id"]
    original = {r["rule"]: r["evidence"] for r in s["db"]["scored"]["rules"]}
    assert all(len(v) >= 60 for v in original.values())
    actual, got = run(s)
    assert actual["outcome"] == "drafted"  # not malformed_alert
    ev = got["evidence"]
    assert ev["evidence_truncated"] is True
    assert ev["evidence_original_counts"] == {k: len(v) for k, v in original.items()}
    for r in ev["rules"]:
        sent = [str(e) for e in r["evidence"]]
        assert len(sent) <= 50 and alerted in sent
        others = [e for e in original[r["rule"]] if e != alerted]  # fixture lists are oldest first
        assert set(sent) - {alerted} == set(others[-(len(sent) - 1):])
    dropped = set(original["rapid_pass_through"]) - ids_sent(ev)
    assert dropped and not any(d in got["user"] for d in dropped)
    assert set(got["draft"].cited_transaction_ids) <= ids_sent(ev)


# FR-011.5 AC-5 / ADR-019: injected text stays escaped data; output stays grounded and does not obey it.
def test_injection_in_counterparty_stays_data():
    s = SCENARIOS["injection_in_counterparty"]
    actual, got = run(s)
    user = got["user"]
    assert user.startswith("<evidence>") and user.endswith("</evidence>")
    assert user.count("</evidence>") == 1  # the counterparty's closing tag is escaped
    assert actual == {"outcome": "drafted", "recommendation": "escalate_for_review"}
    assert FABRICATED not in got["text"]


# US-016 AC-4 / FR-009.8: no screening hit -> no hit wording; evidence has no onboarding data.
def test_clean_scenario_has_no_hit_wording_and_no_onboarding_keys():
    _, got = run(SCENARIOS["clean"])
    text = got["text"].lower()
    assert not any(w in text for w in SANCTION_WORDS)
    blob = json.dumps(got["evidence"]).lower()
    assert not any(k in blob for k in ("application_id", "applicant", "kyc", "date_of_birth", "id_number"))


# FR-009.9 AC-1: a forged alert (valid payload, no alerted.v1) is not_alerted and never reaches the model.
def test_forged_alert_never_reaches_model(monkeypatch):
    calls = []
    monkeypatch.setattr(StubLLM, "complete", lambda self, s, u: calls.append(1))
    assert run(SCENARIOS["forged_not_alerted"])[0] == {"outcome": "skipped", "reason": "not_alerted"}
    assert calls == []


# ---------------------------------------------------------------- eval_investigator.py gate (FR-011.5 AC-3/AC-4, FR-010.6 AC-5)

# FR-011.5 AC-4: the eval script cannot touch the production audit: it imports no psycopg.
def test_eval_script_imports_no_psycopg():
    tree = ast.parse((ROOT / "eval_investigator.py").read_text(encoding="utf-8"))
    mods = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    mods |= {(n.module or "").split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert "psycopg" not in mods and "psycopg2" not in mods


class GuardedEnv(dict):
    """Env mapping that records any read of the API key value."""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.key_reads = []

    def __getitem__(self, k):
        if k == "ANTHROPIC_API_KEY":
            self.key_reads.append(k)
        return super().__getitem__(k)

    def get(self, k, default=None):
        if k == "ANTHROPIC_API_KEY":
            self.key_reads.append(k)
        return super().get(k, default)


@pytest.mark.parametrize("env,var", [
    ({}, "LLM_MODE"),
    ({"LLM_MODE": "stub"}, "LLM_MODE"),
    ({"LLM_MODE": "local", "LOCAL_LLM_URL": "http://127.0.0.1:9", "LLM_MODEL": "qwen2.5:3b"}, "LLM_MODE"),
    ({"LLM_MODE": "anthropic"}, "DATA_CLASSIFICATION"),
    ({"LLM_MODE": "anthropic", "DATA_CLASSIFICATION": "customer"}, "DATA_CLASSIFICATION"),
])
def test_eval_refuses_unless_anthropic_and_synthetic(env, var, tmp_path, monkeypatch):
    import eval_investigator
    key_file = tmp_path / "anthropic_api_key"
    key_file.write_text("sk-ant-api03-EVAL-SENTINEL\n")
    env = GuardedEnv(env, ANTHROPIC_API_KEY_FILE=str(key_file), ANTHROPIC_API_KEY="sk-ant-api03-EVAL-SENTINEL")
    opened, sockets = [], []
    real_open = builtins.open

    def guarded_open(file, *a, **k):
        if str(file) == str(key_file):
            opened.append(file)
        return real_open(file, *a, **k)

    def no_socket(*a, **k):
        sockets.append(a)
        raise OSError("network disabled in test")

    monkeypatch.setattr(builtins, "open", guarded_open)
    monkeypatch.setattr(io, "open", guarded_open)
    monkeypatch.setattr(socket, "socket", no_socket)
    monkeypatch.chdir(tmp_path)
    try:
        code = eval_investigator.main([], env=env)
    except SystemExit as exc:
        code = exc.code
    assert code not in (0, None, False)
    if isinstance(code, str):  # SystemExit("<VAR>: <reason>") names the variable, never a value
        assert var in code and "EVAL-SENTINEL" not in code
    assert opened == [] and env.key_reads == [] and sockets == []
    assert not (tmp_path / "eval-report.json").exists()
