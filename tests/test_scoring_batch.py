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
    assert retried == first
    burst = [r for r in retried if any(h["rule"] == "minute_velocity" for h in r["rules"])]
    assert len(burst) == 1  # only the 10th same-second event reaches the minute threshold


def test_failed_batch_retry_keeps_counts_trimmed_by_a_later_event():
    """A later event in the same failed batch trims the earlier members; their retry must reuse the first counts."""
    redis = Redis(host="redis")
    script = redis.register_script(VELOCITY)
    rows = scenario(f"BATCH-{uuid.uuid4().hex[:10]}")
    late = dict(rows[0], id=str(uuid.uuid4()), occurred_at=(T0 + timedelta(hours=49)).isoformat())
    with psycopg.connect(DSN, autocommit=True, row_factory=dict_row) as db:
        try:
            with db.transaction():
                first = score_batch(db, script, redis, rows + [late])
                raise RuntimeError("simulated failure before commit")
        except RuntimeError:
            pass
        with db.transaction():
            retried = score_batch(db, script, redis, rows + [late])
    assert retried == first
    assert any(h["rule"] == "minute_velocity" for r in retried for h in r["rules"])  # the burst still counts


def test_velocity_prunes_thousands_of_expired_events_in_one_call():
    """Expiring more members than Lua's unpack() limit must not fail the script (HDEL is chunked).
    Stored counts are kept 48 h past the window, so they go once the latest event is 96 h newer."""
    redis = Redis(host="redis")
    script = redis.register_script(VELOCITY)
    account = f"BATCH-{uuid.uuid4().hex[:10]}"
    keys = ["velocity:" + account, "velocity-counts:" + account, "velocity-counted:" + account]
    start = T0.timestamp()
    redis.zadd(keys[0], {f"old-{i}": start for i in range(9000)})
    redis.hset(keys[1], mapping={f"old-{i}": "1,1" for i in range(9000)})
    redis.zadd(keys[2], {f"old-{i}": start for i in range(9000)})
    assert script(keys=keys, args=[start + 97 * 3600, "new"]) == [1, 1]
    assert redis.zcard(keys[0]) == 1 and redis.hlen(keys[1]) == 1 and redis.zcard(keys[2]) == 1
    redis.delete(*keys)


def test_uppercase_ids_are_recorded_once_and_replays_reuse_the_decision():
    redis = Redis(host="redis")
    script = redis.register_script(VELOCITY)
    rows = scenario(f"BATCH-{uuid.uuid4().hex[:10]}")[:5]
    upper = [dict(r, id=r["id"].upper()) for r in rows]
    with psycopg.connect(DSN, autocommit=True, row_factory=dict_row) as db:
        with db.transaction():
            first = score_batch(db, script, redis, [dict(r) for r in upper])
        with db.transaction():
            replay = score_batch(db, script, redis, [dict(r) for r in upper])  # used to violate audit_score_once
        counts = {r["action"]: r["n"] for r in db.execute(
            "SELECT action, count(*) AS n FROM audit WHERE transaction_id = ANY(%s::uuid[]) GROUP BY action",
            ([r["id"] for r in rows],))}
    assert replay == first and [r["transaction_id"] for r in first] == [r["id"] for r in rows]  # lowercase
    assert counts["transaction.recorded"] == counts["scored.v1"] == len(rows)


def test_unscreenable_counterparty_is_recorded_without_stopping_the_batch():
    """A debit to "!!!" normalizes to an empty name; it must be audited as unscreenable, not raise."""
    redis = Redis(host="redis")
    script = redis.register_script(VELOCITY)
    row = dict(scenario(f"BATCH-{uuid.uuid4().hex[:10]}")[4], counterparty="!!!")
    with psycopg.connect(DSN, autocommit=True, row_factory=dict_row) as db:
        with db.transaction():
            score_batch(db, script, redis, [row])
        screened = db.execute("SELECT inputs FROM audit WHERE action='payment.screened.v1' AND transaction_id=%s",
                              (row["id"],)).fetchone()["inputs"]
    assert screened["unscreenable"] is True and screened["hits"] == []


def test_scorer_records_kafka_coordinates():
    redis = Redis(host="redis")
    script = redis.register_script(VELOCITY)
    row = scenario(f"BATCH-{uuid.uuid4().hex[:10]}")[0]
    with psycopg.connect(DSN, autocommit=True, row_factory=dict_row) as db:
        with db.transaction():
            score_batch(db, script, redis, [row], [dict(topic="transactions", partition=3, offset=42)])
        recorded = db.execute("SELECT inputs FROM audit WHERE action='transaction.recorded' AND transaction_id=%s",
                              (row["id"],)).fetchone()["inputs"]
    assert (recorded["topic"], recorded["partition"], recorded["offset"]) == ("transactions", 3, 42)
    assert recorded["account_key"] == row["account"]
