"""Pure tests for grounding.py (CS-008 "grounding.py", FR-011.1-11.3, FR-009.3 AC-2, FR-009.4)."""
import json
import uuid

import pytest
from pydantic import ValidationError

from grounding import Draft, check_grounding, consistency

CHECKS = {"amounts", "counterparties", "rules", "sanctions"}
TX = str(uuid.UUID(int=1))


def row(id_, cents, party="Terrace Imports", direction="debit"):
    return dict(id=id_, counterparty=party, amount_cents=cents, direction=direction,
                channel="wire", occurred_at="2026-11-14T12:00:00+00:00")


def ev(amounts=(8090000,), parties=None, rules=(), hits=()):
    """Evidence in the CS-008 allow-list shape; the first amount is the alerted transaction."""
    parties = parties or ["Terrace Imports"] * len(amounts)
    rows = [row(str(uuid.UUID(int=i + 1)), cents, parties[i]) for i, cents in enumerate(amounts)]
    screenings = [dict(name="Terrace Imports", snapshot="ab" * 32, threshold=88, hits=list(hits))] if hits else []
    return dict(transaction=dict(rows[0], account="SUBJECT_ACCOUNT"), history=rows[1:],
                rules=[dict(rule=r, points=p, evidence=[TX]) for r, p in rules],
                score=min(100, sum(p for _, p in rules)), screenings=screenings)


def draft(summary="transaction reviewed.", statements=("transaction reviewed.",), cited=(TX,),
          finding_cites=None, recommendation="escalate_for_review"):
    findings = [dict(statement=s, cited_transaction_ids=list(finding_cites or cited), rule=None) for s in statements]
    return Draft.model_validate(dict(summary=summary, recommendation=recommendation,
                                     cited_transaction_ids=list(cited), findings=findings))


HIT = dict(entry_id="990001", listed_name="COBALT MERIDIAN EXPORTS", matched_name="Cobalt Meridian Exports",
           score=100.0, disposition="possible_match")

# CS-008 money table: text -> integer cents parsed from it.
PARSED = [
    ("$100000", [10000000]),
    ("$12345.67", [1234567]),
    ("$80,900.00", [8090000]),
    ("sent $80,900.50, then", [8090050]),
    ("sent $100, then", [10000]),
    ("$100,000, which", [10000000]),
    ("$48,200.00, $35,600.00", [4820000, 3560000]),
    ("total $83,800.00.", [8380000]),
    ("($80,900.00)", [8090000]),
    ("$ 48,200;", [4820000]),
]
# CS-008 MALFORMED cases, with evidence holding every plausible partial/truncated reading
# so the check can only fail because of the malformed guard.
MALFORMED = [
    ("$5.5", [550, 500, 5]),
    ("$1,00", [100, 10000]),
    ("$1,0000", [100000, 10000000]),
    ("$1,000,0", [100000, 1000000]),
    ("$100k", [10000, 1000]),
    ("$100USD", [10000]),
    ("$80,900.00.5", [8090000, 8090005]),
    ("$1.000,00", [100, 100000]),
]


def test_money_table_has_every_cs008_case():
    assert len(PARSED) + len(MALFORMED) + 1 == 19  # +1 = "scored 91.30"


# FR-011.2 AC-1: "$"-amounts are parsed whole to integer cents and must equal an evidence amount.
@pytest.mark.parametrize("text,cents", PARSED)
def test_amount_parsed_whole_matches_evidence(text, cents):
    assert check_grounding(draft(summary=text), ev(cents)) == []


# FR-011.2 AC-1 (failure): the same text against evidence one cent off fails, proving the exact parse.
@pytest.mark.parametrize("text,cents", PARSED)
def test_amount_one_cent_off_fails(text, cents):
    for i in range(len(cents)):
        wrong = list(cents)
        wrong[i] += 1
        assert "amounts" in check_grounding(draft(summary=text), ev(wrong))


# FR-011.2 AC-1 / CS-008: malformed "$"+digits always fails the amounts check.
@pytest.mark.parametrize("text,cents", MALFORMED)
def test_malformed_amount_fails(text, cents):
    assert "amounts" in check_grounding(draft(summary=text), ev(cents))


# FR-011.2 AC-1 / RR-21: bare decimals (no "$") are not checked.
@pytest.mark.parametrize("text", ["scored 91.30", "80900.00 left the account"])
def test_amount_without_dollar_is_ignored(text):
    assert check_grounding(draft(summary=text), ev([1])) == []


# FR-011.2 AC-1: "$100000" is $100,000.00, never truncated to $100.
def test_hundred_thousand_against_one_hundred_dollars_fails():
    assert "amounts" in check_grounding(draft(summary="$100000"), ev([10000]))


# FR-011.2 AC-1: "$81,000" when only $80,900.00 exists fails.
def test_unstated_amount_fails():
    assert "amounts" in check_grounding(draft(summary="debit of $81,000"), ev([8090000]))


# FR-011.2 AC-1: the sum of the cited credits passes (AML-1042: $48,200 + $35,600 = $83,800).
def test_sum_of_cited_credits_passes_in_finding_and_summary():
    c1, c2 = str(uuid.UUID(int=2)), str(uuid.UUID(int=3))
    evidence = ev([8090000, 4820000, 3560000])
    in_finding = draft(statements=["credits totalled $83,800.00."], cited=(c1,), finding_cites=(c1, c2))
    assert check_grounding(in_finding, evidence) == []
    in_summary = draft(summary="credits totalled $83,800.00.", cited=(c1, c2))
    assert check_grounding(in_summary, evidence) == []


# FR-011.2: the sum only counts when the transactions are cited.
def test_sum_of_uncited_transactions_fails():
    assert "amounts" in check_grounding(draft(summary="credits totalled $83,800.00."), ev([8090000, 4820000, 3560000]))


# Review findings: a repeated citation must not double a total, an id without an amount must not allow $0.00,
# and extra spaces after "$" make the amount malformed rather than unchecked.
def test_repeated_citation_does_not_double_the_total():
    assert "amounts" in check_grounding(draft(summary="paid $161,800.00.", cited=(TX, TX)), ev([8090000]))


def test_cited_id_without_amount_does_not_allow_zero():
    rule_only = str(uuid.UUID(int=99))
    assert "amounts" in check_grounding(draft(summary="moved $0.00.", cited=(rule_only,)), ev([8090000]))


def test_dollar_with_several_spaces_is_malformed():
    assert "amounts" in check_grounding(draft(summary="paid $  999."), ev([8090000]))


# FR-011.2: checks cover every finding statement, not only the summary.
def test_amount_in_finding_statement_is_checked():
    bad = draft(statements=["transaction reviewed.", "debit of $81,000."])
    assert "amounts" in check_grounding(bad, ev([8090000]))


# FR-011.2 AC-2: a quoted counterparty absent from the evidence fails check (b).
def test_unknown_counterparty_fails():
    assert "counterparties" in check_grounding(draft(summary='paid "Ghost Holdings Ltd".'), ev())


# FR-011.2 AC-2 (happy/boundary): names match after watchlist.normalize (case, punctuation, token order),
# against transaction, history or a screening matched_name.
@pytest.mark.parametrize("name", ["Terrace Imports", "terrace imports", "Imports, TERRACE", "Redwood Supply"])
def test_known_counterparty_passes_after_normalization(name):
    evidence = ev([8090000, 4820000], parties=["Terrace Imports", "Redwood Supply"])
    assert check_grounding(draft(summary=f'paid "{name}".'), evidence) == []


def test_screening_matched_name_counts_as_counterparty():
    evidence = ev(hits=[HIT])
    assert "counterparties" not in check_grounding(draft(summary='near "Cobalt Meridian Exports".'), evidence)


# FR-011.2 AC-3: a rule named in text that did not fire fails check (c); a fired one passes.
def test_rule_not_fired_fails():
    evidence = ev(rules=[("rapid_pass_through", 65)])
    assert "rules" in check_grounding(draft(summary="large_cash_activity fired."), evidence)
    assert "rules" in check_grounding(draft(statements=["large_cash_activity fired."]), evidence)


def test_fired_rule_passes():
    evidence = ev(rules=[("rapid_pass_through", 65)])
    assert check_grounding(draft(summary="rapid_pass_through fired for 65 points."), evidence) == []


# CS-008: the two recommendation values never trip the rules check.
@pytest.mark.parametrize("word", ["escalate_for_review", "no_further_action_suggested"])
def test_recommendation_words_do_not_trip_rules(word):
    assert check_grounding(draft(summary=f"outcome: {word}."), ev()) == []


# FR-011.2 AC-4: "OFAC match" with no screening hit fails check (d); with a hit it passes.
def test_ofac_without_hit_fails_and_with_hit_passes():
    assert "sanctions" in check_grounding(draft(summary="OFAC match on the payee."), ev())
    assert "sanctions" not in check_grounding(draft(summary="OFAC match on the payee."), ev(hits=[HIT]))


# CS-008: every term, case-insensitive, including negations, fails without a hit.
@pytest.mark.parametrize("text", ["no sanctions concern.", "payee is SANCTIONED.", "a sanction applies.",
                                  "sdn listed.", "watchlist match found.", "Screening Hit recorded."])
def test_sanctions_terms_fail_without_hit(text):
    assert "sanctions" in check_grounding(draft(statements=[text]), ev())


# CS-008: word-bounded, so ordinary words containing the letters do not trip it.
def test_sanctions_terms_are_word_bounded():
    assert check_grounding(draft(summary="sdnx and sanctionsxyz are not terms."), ev()) == []


# FR-011.2: names returned are drawn from the four check names only.
def test_failed_check_names_are_known():
    bad = draft(summary='"Ghost Ltd" sent $1 under large_cash_activity; OFAC match.')
    assert set(check_grounding(bad, ev())) == CHECKS


# FR-011.2 AC-6: checking makes no model call.
def test_check_grounding_makes_no_model_call():
    from investigator import render_prompt
    from llm import StubLLM
    evidence = ev(rules=[("rapid_pass_through", 65)])
    stub = StubLLM()
    text, _ = stub.complete(*render_prompt(evidence)[:2])
    before = stub.calls
    check_grounding(Draft.model_validate_json(text), evidence)
    assert stub.calls == before == 1


# FR-011.1 / CS-008 Draft schema.
def base(**over):
    data = dict(summary="transaction reviewed.", recommendation="escalate_for_review", cited_transaction_ids=[TX],
                findings=[dict(statement="transaction reviewed.", cited_transaction_ids=[TX], rule=None)])
    data.update(over)
    return data


def finding(statement="transaction reviewed.", cites=(TX,), **extra):
    return dict(statement=statement, cited_transaction_ids=list(cites), rule=None, **extra)


def test_draft_happy_path_accepts_one_and_ten_findings():
    assert len(Draft.model_validate(base()).findings) == 1
    assert len(Draft.model_validate(base(findings=[finding()] * 10)).findings) == 10


# FR-011.1 AC-1: zero or more than 10 findings is rejected.
@pytest.mark.parametrize("n", [0, 11])
def test_finding_count_out_of_range_rejected(n):
    with pytest.raises(ValidationError):
        Draft.model_validate(base(findings=[finding()] * n))


# FR-011.1 AC-2: statement length 300 is the boundary.
def test_statement_length_boundary():
    Draft.model_validate(base(findings=[finding("x" * 300)]))
    for bad in ["x" * 301, ""]:
        with pytest.raises(ValidationError):
            Draft.model_validate(base(findings=[finding(bad)]))


# CS-008: summary 1..2000.
def test_summary_length_boundary():
    Draft.model_validate(base(summary="x" * 2000))
    for bad in ["x" * 2001, ""]:
        with pytest.raises(ValidationError):
            Draft.model_validate(base(summary=bad))


# FR-011.1 AC-2: empty citations rejected, in a finding and in the draft.
def test_empty_citations_rejected():
    with pytest.raises(ValidationError):
        Draft.model_validate(base(findings=[finding(cites=())]))
    with pytest.raises(ValidationError):
        Draft.model_validate(base(cited_transaction_ids=[]))


# FR-011.1 AC-3: a summary id that is in no finding is rejected.
def test_summary_id_missing_from_findings_rejected():
    with pytest.raises(ValidationError):
        Draft.model_validate(base(cited_transaction_ids=[TX, str(uuid.UUID(int=2))]))


# ADR-019: extra="forbid" on Draft and Finding.
def test_extra_fields_rejected():
    with pytest.raises(ValidationError):
        Draft.model_validate(base(ai_generated=False))
    with pytest.raises(ValidationError):
        Draft.model_validate(base(findings=[finding(action="close_case")]))


# FR-009.3 AC-2: a recommendation outside the two values is rejected.
@pytest.mark.parametrize("value", ["close_case", "ESCALATE_FOR_REVIEW", "", None])
def test_bad_recommendation_rejected(value):
    with pytest.raises(ValidationError):
        Draft.model_validate(base(recommendation=value))


# CS-008 validate_draft(raw, evidence_ids, fired_rules): returns a Draft or an error value, never raises.
def validate(data, ids=(TX,), fired=("rapid_pass_through",)):
    from investigator import validate_draft
    raw = data if isinstance(data, str) else json.dumps(data)
    return validate_draft(raw, set(ids), set(fired))


def test_validate_draft_happy_path_returns_draft():
    result = validate(base(findings=[dict(finding(), rule="rapid_pass_through")]))
    assert isinstance(result, Draft) and result.findings[0].rule == "rapid_pass_through"


# FR-009.4 AC-1 / FR-011.1 AC-2: an id outside the evidence, in the draft or a finding, is rejected.
def test_validate_draft_rejects_fabricated_ids():
    fake = str(uuid.UUID(int=999))
    assert not isinstance(validate(base(cited_transaction_ids=[TX, fake],
                                        findings=[finding(cites=(TX, fake))])), Draft)
    assert not isinstance(validate(base(findings=[finding(), finding(cites=(fake,))])), Draft)


# FR-011.1 AC-2: a finding rule that did not fire is rejected (schema failure, not grounding).
def test_validate_draft_rejects_unfired_finding_rule():
    assert not isinstance(validate(base(findings=[dict(finding(), rule="large_cash_activity")])), Draft)


# FR-009.3 AC-2 / CS-008: invalid JSON and markdown fences are rejected without raising.
@pytest.mark.parametrize("raw", ["", "not json", "```json\n" + json.dumps(base()) + "\n```", "[]", "null"])
def test_validate_draft_rejects_non_json(raw):
    assert not isinstance(validate(raw), Draft)


def test_validate_draft_rejects_bad_recommendation_without_raising():
    assert not isinstance(validate(base(recommendation="close_case")), Draft)


# FR-011.3 AC-1: no_further_action with a 60-point rule warns; the recommendation is unchanged.
def test_consistency_warns_on_high_points():
    d = draft(recommendation="no_further_action_suggested")
    reason = consistency(d, ev(rules=[("rapid_pass_through", 65)]))
    assert isinstance(reason, str) and reason
    assert d.recommendation == "no_further_action_suggested"
    assert consistency(d, ev(rules=[("x_y", 60)])) and consistency(d, ev(rules=[("x_y", 59)])) is None


# FR-011.3 AC-2: no_further_action with a screening hit warns.
def test_consistency_warns_on_screening_hit():
    d = draft(recommendation="no_further_action_suggested")
    assert consistency(d, ev(hits=[HIT]))
    assert d.recommendation == "no_further_action_suggested"


# FR-011.3 AC-3: escalate, or no_further_action with neither condition, gives no warning.
def test_consistency_no_warning_cases():
    assert consistency(draft(), ev(rules=[("rapid_pass_through", 65)], hits=[HIT])) is None
    clean = ev(rules=[("large_cash_activity", 25)])
    clean["screenings"] = [dict(name="Juniper Orchard Services", snapshot="ab" * 32, threshold=88, hits=[])]
    assert consistency(draft(recommendation="no_further_action_suggested"), clean) is None
