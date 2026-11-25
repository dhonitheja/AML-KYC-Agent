import uuid
from datetime import datetime, timezone

from pipeline import event
from rules import assess


def fixture():
    run = uuid.uuid4()
    return [event(run, i, None, True) for i in range(3)]


def test_seed_totals():
    first, second, debit = fixture()
    assert first["amount_cents"] + second["amount_cents"] == 8380000
    assert debit["amount_cents"] == 8090000
    assert first["case_id"] == debit["case_id"] == "AML-1042"


def test_unique_and_repeatable_ids():
    run = uuid.uuid4()
    now = datetime.now(timezone.utc)
    ids = [event(run,i,now)["id"] for i in range(3600)]
    assert len(set(ids)) == 3600
    assert event(run,10,now)["id"] == ids[10]


def test_northstar_pass_through():
    a,b,c = fixture()
    result = assess(c,1,1,[a,b])
    assert result["alert"]
    assert result["rules"] == [dict(rule="rapid_pass_through",points=65,evidence=[a["id"],b["id"],c["id"]])]
    assert not assess(c,1,1,[])["alert"]


def test_remaining_rules():
    a,b,c = fixture()
    c.update(amount_cents=10000000,channel="cash")
    credits = [dict(a,id=str(i),counterparty=str(i)) for i in range(4)]
    previous_debits = [dict(c,id=str(i+4)) for i in range(2)]
    result=assess(c,10,40,credits+previous_debits)
    assert {hit["rule"] for hit in result["rules"]} == {
        "large_single_transfer","large_cash_activity","minute_velocity","hour_velocity",
        "multiple_credit_sources","repeated_amount"}
    assert result["score"] == 100


def test_demo_accounts_by_default_and_load_accounts_scoped_to_the_run():
    run, other, now = uuid.uuid4(), uuid.uuid4(), datetime.now(timezone.utc)
    assert event(run, 7, now)["account"] == "DEMO-007"
    assert event(run, 7, now, accounts=100)["account"].startswith(f"LOAD-{str(run)[:8]}-")  # 100 is not demo mode
    assert event(run, 7, now, accounts=100)["account"] != event(other, 7, now, accounts=100)["account"]
