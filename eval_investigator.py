"""Opt-in evaluation of the real Anthropic backend on the synthetic scenario set (CS-008 "Evaluation set").
Never run in CI, never imported by the service, opens no DB. Refuses unless LLM_MODE=anthropic AND
DATA_CLASSIFICATION=synthetic, through investigator.load_model_config (steps 1-3 only)."""
import argparse
import json
import os
import sys
from pathlib import Path

from investigator import build_evidence, decide, load_model_config, read_secret, run_model
from llm import AnthropicLLM, Failure

SCENARIOS = Path(__file__).parent / "tests" / "eval" / "scenarios.json"
TIMEOUT_SECONDS = 30  # production defaults; the service env (step 4) is not read here
MAX_ATTEMPTS = 3


def main(argv=None, env=os.environ):
    args = argparse.ArgumentParser(description=__doc__)
    args.add_argument("report", nargs="?", default="eval-report.json")
    args.add_argument("--scenarios", default=str(SCENARIOS))
    args = args.parse_args(argv)
    cfg = load_model_config(env, read_secret)  # the synthetic gate runs before any key read
    if cfg.llm_mode != "anthropic":
        raise SystemExit("LLM_MODE: eval_investigator requires anthropic")
    llm = AnthropicLLM(cfg.api_key, cfg.model, TIMEOUT_SECONDS)
    suite = json.loads(Path(args.scenarios).read_text(encoding="utf-8"))
    results, attempts_total, citation_failures = [], 0, 0
    for sc in suite["scenarios"]:
        db, expected = sc["db"], sc["expected"]
        alert, reason = decide(sc["raw_alert"], db.get("transaction"), db.get("alerted"))  # raw Kafka value
        result = {"name": sc["name"], "expected": expected, "attempts": 0, "failed_checks": []}
        if reason:
            result.update(outcome="skipped", reason=reason)
        else:
            evidence = build_evidence(alert, db["transaction"], db.get("history", []), db["scored"],
                                      db.get("screenings", []))
            errors = []
            _, out = run_model(evidence, llm, MAX_ATTEMPTS, errors=errors)
            attempts_total += out.attempts if isinstance(out, Failure) else out[2]
            citation_failures += errors.count("citation")
            if isinstance(out, Failure):
                result.update(outcome="skipped", reason=out.last_reason, attempts=out.attempts,
                              failed_checks=out.failed_checks)
            else:
                draft, _, attempts = out
                result.update(outcome="drafted", recommendation=draft.recommendation, attempts=attempts)
        results.append(result)
    should_draft = [r for r in results if r["expected"].get("outcome") == "drafted"]
    drafted = [r for r in results if r["outcome"] == "drafted"]
    rates = {
        "grounding_failure_rate": sum(r.get("reason") == "grounding_failure" for r in should_draft)
        / max(1, len(should_draft)),
        "citation_violation_rate": citation_failures / max(1, attempts_total),
        "recommendation_agreement": sum(r["recommendation"] == r["expected"].get("recommendation") for r in drafted)
        / max(1, len(drafted)),
    }
    report = {"scenario_version": suite.get("version"), "model": cfg.model, "results": results, **rates}
    Path(args.report).write_text(json.dumps(report, indent=2), encoding="utf-8")
    for name, value in rates.items():
        print(f"{name}: {value:.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
