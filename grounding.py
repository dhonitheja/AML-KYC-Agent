"""Deterministic grounding checks for drafted narratives (FR-011). Pure: no I/O, no model."""
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from watchlist import normalize

CHECKS = ["amounts", "counterparties", "rules", "sanctions"]
RECOMMENDATIONS = ("escalate_for_review", "no_further_action_suggested")
MONEY = re.compile(r"\$\s?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?!\w|[.,]\d)")
MONEY_START = re.compile(r"\$\s?\d")
RULE = re.compile(r"\b[a-z]+(?:_[a-z]+)+\b")
SANCTIONS = re.compile(r"\b(?:sanctions|sanctioned|sanction|ofac|sdn|watchlist match|screening hit)\b", re.IGNORECASE)
QUOTED = re.compile(r'"([^"]*)"')


class Finding(BaseModel):
    model_config = ConfigDict(extra="forbid")
    statement: str = Field(min_length=1, max_length=300)
    cited_transaction_ids: list[str] = Field(min_length=1)
    rule: str | None = None


class Draft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    summary: str = Field(min_length=1, max_length=2000)
    recommendation: Literal["escalate_for_review", "no_further_action_suggested"]
    cited_transaction_ids: list[str] = Field(min_length=1)
    findings: list[Finding] = Field(min_length=1, max_length=10)

    @model_validator(mode="after")
    def summary_ids_in_findings(self):
        cited = {i for f in self.findings for i in f.cited_transaction_ids}
        if not set(self.cited_transaction_ids) <= cited:
            raise ValueError("Every summary-cited id must appear in a finding")
        return self


def money(text):
    """Integer cents for every $ amount in text, or None if any $+digit is malformed."""
    found = MONEY.findall(text)
    if len(found) != len(MONEY_START.findall(text)):
        return None
    cents = []
    for match in found:
        whole, _, frac = match[1:].strip().replace(",", "").partition(".")
        if frac and len(frac) != 2:
            return None
        cents.append(int(whole) * 100 + int(frac or 0))
    return cents


def _transactions(evidence):
    return [evidence["transaction"], *evidence.get("history", [])]


def check_grounding(draft, evidence):
    amounts = {t["id"]: t["amount_cents"] for t in _transactions(evidence)}
    parties = {normalize(t["counterparty"]) for t in _transactions(evidence)}
    parties |= {normalize(h.get("matched_name") or "") for s in evidence.get("screenings", []) for h in s["hits"]}
    parties.discard("")
    fired = {r["rule"] for r in evidence.get("rules", [])}
    hit = any(s["hits"] for s in evidence.get("screenings", []))
    parts = [(draft.summary, draft.cited_transaction_ids)]
    parts += [(f.statement, f.cited_transaction_ids) for f in draft.findings]
    failed = set()
    for text, cited in parts:
        allowed = set(amounts.values()) | {sum(amounts[i] for i in cited if i in amounts)}
        cents = money(text)
        if cents is None or not set(cents) <= allowed:
            failed.add("amounts")
        if any(normalize(q) not in parties for q in QUOTED.findall(text)):
            failed.add("counterparties")
        if any(r not in fired and r not in RECOMMENDATIONS for r in RULE.findall(text)):
            failed.add("rules")
        if not hit and SANCTIONS.search(text):
            failed.add("sanctions")
    return [c for c in CHECKS if c in failed]


def consistency(draft, evidence):
    if draft.recommendation != "no_further_action_suggested":
        return None
    if any(r["points"] >= 60 for r in evidence.get("rules", [])):
        return "no_further_action_suggested despite a rule scoring 60 or more points"
    if any(s["hits"] for s in evidence.get("screenings", [])):
        return "no_further_action_suggested despite a screening hit"
    return None
