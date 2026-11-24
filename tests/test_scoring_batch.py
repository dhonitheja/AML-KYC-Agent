"""Phase 6 batched scorer (ADR-032). `in_window` is pure; the rest needs postgres and redis.
Each test uses fresh synthetic accounts, so Redis velocity keys and history start empty."""
import uuid
from datetime import datetime, timedelta, timezone

import psycopg
from psycopg.rows import dict_row
from redis import Redis

from pipeline import DSN
from scoring import VELOCITY, in_window, score_batch

T0 = datetime(2026, 11, 20, 12, tzinfo=timezone.utc)


def test_in_window_bounds_and_order():
    rows = [(T0 - timedelta(hours=48, seconds=1), "a", "too old"), (T0, "c", "now"),
            (T0 - timedelta(hours=48), "b", "edge"), (T0 + timedelta(seconds=1), "d", "future")]
    assert in_window(rows, T0) == ["edge", "now"]


def scenario(account):
    """Credits from four parties, a pass-through debit, a repeated amount and a 10-event velocity burst."""
    run = uuid.uuid4()
    shape = [("Party A", 4_000_000, "credit", 0), ("Party B", 2_000_000, "credit", 1), ("Party C", 1_000_000, "credit", 2),
             ("Party D", 1_000_000, "credit", 3), ("Out", 7_900_000, "debit", 4), ("Party C", 1_000_000, "credit", 5)]
    shape += [(f"Burst {i}", 1000 + i, "credit", 6) for i in range(10)]
    return [dict(id=str(uuid.uuid4()), run_id=str(run), case_id=None, account=account, counterparty=party,
                 amount_cents=cents, direction=direction, channel="ACH",
                 occurred_at=(T0 + timedelta(minutes=minute)).isoformat())
            for party, cents, direction, minute in shape]


def shape_of(result):
    return result["score"], result["alert"], [(r["rule"], r["points"]) for r in result["rules"]]


def test_batch_matches_one_at_a_time_including_duplicates_and_replay():
    redis = Redis(host="redis")
    script = redis.register_script(VELOCITY)
    one, many = scenario(f"BATCH-{uuid.uuid4().hex[:10]}"), scenario(f"BATCH-{uuid.uuid4().hex[:10]}")
    with psycopg.connect(DSN, autocommit=True, row_factory=dict_row) as db:
        sequential = []
        for row in one:
            with db.transaction():
                sequential += score_batch(db, script, redis, [row])
        with db.transaction():
            batched = score_batch(db, script, redis, many + [many[4]])  # in-batch duplicate of the debit
        with db.transaction():
            replayed = score_batch(db, script, redis, many[:5])  # a replayed batch reuses stored decisions
        rows = db.execute("SELECT action, count(*) AS n FROM audit WHERE transaction_id = ANY(%s::uuid[]) "
                          "GROUP BY action", ([r["id"] for r in many],)).fetchall()

    assert [shape_of(r) for r in batched[:-1]] == [shape_of(r) for r in sequential]
    assert batched[-1] == batched[4] and replayed == batched[:5]
    assert {"rapid_pass_through", "multiple_credit_sources"} <= {r["rule"] for r in batched[4]["rules"]}
    assert "repeated_amount" in {r["rule"] for r in batched[5]["rules"]}
    assert "minute_velocity" in {r["rule"] for r in batched[-2]["rules"]}
    expected = {"transaction.recorded": len(many), "scored.v1": len(many),
                "alerted.v1": sum(r["alert"] for r in batched[:-1]), "payment.screened.v1": 1}  # the one debit
    assert {r["action"]: r["n"] for r in rows} == expected  # exactly once despite the duplicate and replay


def test_failed_batch_retry_keeps_first_velocity_counts():
    """A batch that fails after the Redis pipeline but before the DB commit must rescore identically."""
    redis = Redis(host="redis")
    script = redis.register_script(VELOCITY)
    rows = scenario(f"BATCH-{uuid.uuid4().hex[:10]}")
    with psycopg.connect(DSN, autocommit=True, row_factory=dict_row) as db:
        try:
            with db.transaction():
                first = score_batch(db, script, redis, rows)
                raise RuntimeError("simulated failure before commit")
        except RuntimeError:
            pass
        assert db.execute("SELECT count(*) AS n FROM transactions WHERE id = ANY(%s::uuid[])",
                          ([r["id"] for r in rows],)).fetchone()["n"] == 0  # rolled back
        with db.transaction():
            retried = score_batch(db, script, redis, rows)
    assert [shape_of(r) for r in retried] == [shape_of(r) for r in first]
    burst = [r for r in retried if any(h["rule"] == "minute_velocity" for h in r["rules"])]
    assert len(burst) == 1  # only the 10th same-second event reaches the minute threshold
