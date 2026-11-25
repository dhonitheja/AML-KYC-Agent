import json
from datetime import datetime, timedelta

import psycopg
from psycopg.rows import dict_row
from redis import Redis
from confluent_kafka import Consumer, Producer

from pipeline import BROKER, DSN, TOPIC, copy_audit, record_transactions
from rules import assess
from kyc import payment_screen_batch

# Account-keyed Kafka input serializes updates. Use event time for windows and an idle-key expiry for retention.
# KEYS[2] keeps each event's first counts: a batch that fails after this script ran is retried with every event
# already in the set, and recounting would let earlier events see later ones (ZADD NX alone only dedupes members).
# The stored counts are checked first and never pruned by event time: `forget_counts` deletes them only after the
# batch's DB commit, when the stored decision makes them unnecessary. So no later event can trim counts a retry needs.
VELOCITY = """
local first = redis.call('HGET', KEYS[2], ARGV[2])
if first then
  local sep = string.find(first, ',')
  return {tonumber(string.sub(first, 1, sep - 1)), tonumber(string.sub(first, sep + 1))}
end
redis.call('ZADD', KEYS[1], 'NX', ARGV[1], ARGV[2])
local latest=redis.call('ZREVRANGE',KEYS[1],0,0,'WITHSCORES')
redis.call('ZREMRANGEBYSCORE',KEYS[1],'-inf',tonumber(latest[2])-172800)
local counts={redis.call('ZCOUNT',KEYS[1],'('..(ARGV[1]-60),ARGV[1]),
              redis.call('ZCOUNT',KEYS[1],'('..(ARGV[1]-3600),ARGV[1])}
redis.call('HSET',KEYS[2],ARGV[2],counts[1]..','..counts[2])
redis.call('EXPIRE',KEYS[1],172800)
redis.call('EXPIRE',KEYS[2],172800)
return counts
"""
BATCH = 500
WINDOW = timedelta(hours=48)


def in_window(history, at):
    """History as the per-event query returned it: scored rows with occurred_at in [at-48h, at], by (time, id)."""
    return [item for occurred, _, item in sorted(history, key=lambda h: h[:2]) if at - WINDOW <= occurred <= at]


def score_batch(db, velocity_script, redis, rows, origins=None):
    """Score rows in order inside the caller's transaction. Returns one result per row.
    origins: per-row Kafka coordinates (topic, partition, offset) for the transaction.recorded row (FR-001.1).
    Per batch: one prior-score lookup, one history prefetch, one Redis pipeline and batched inserts,
    instead of about eight round trips per event."""
    origins = origins or [{"topic": TOPIC}] * len(rows)
    record_transactions(db, [(row, dict(origin, account_key=row["account"])) for row, origin in zip(rows, origins)])
    payment_screen_batch(db, rows)
    ids = [row["id"] for row in rows]
    previous = {r["id"]: r["inputs"] for r in db.execute(
        "SELECT transaction_id::text AS id, inputs FROM audit WHERE action='scored.v1' "
        "AND transaction_id = ANY(%s::uuid[])", (ids,))}
    fresh, seen = [], set()
    for row in rows:  # first occurrence of each unscored id; replays and in-batch duplicates reuse a decision
        if row["id"] not in previous and row["id"] not in seen:
            seen.add(row["id"])
            fresh.append((row, datetime.fromisoformat(row["occurred_at"])))
    if fresh:
        pipe = redis.pipeline(transaction=False)  # Redis runs these in order, so per-key counts match one-by-one
        for row, at in fresh:
            velocity_script(keys=["velocity:" + row["account"], "velocity-counts:" + row["account"]],
                            args=[at.timestamp(), row["id"]], client=pipe)
        counts = pipe.execute()
        history = {}
        for r in db.execute("""SELECT t.account, t.occurred_at, t.id::text, t.counterparty, t.amount_cents,
                t.direction, t.channel FROM transactions t JOIN audit a ON a.transaction_id=t.id AND a.action='scored.v1'
                WHERE t.account = ANY(%s) AND t.occurred_at BETWEEN %s AND %s""",
                ([row["account"] for row, _ in fresh], min(at for _, at in fresh) - WINDOW, max(at for _, at in fresh))):
            history.setdefault(r.pop("account"), []).append((r.pop("occurred_at"), r["id"], r))
    audit = []
    for (row, at), count in zip(fresh, counts if fresh else []):
        account = history.setdefault(row["account"], [])
        result = assess(row, *count, in_window(account, at))
        previous[row["id"]] = result
        account.append((at, row["id"], {k: row[k] for k in ("counterparty", "amount_cents", "direction", "channel")}
                        | {"id": row["id"]}))
        for action in ["scored.v1", "alerted.v1"] if result["alert"] else ["scored.v1"]:
            audit.append(("scorer-v1", action, row["case_id"], row["id"], result))
    copy_audit(db, audit)
    return [previous[row["id"]] for row in rows]


def forget_counts(redis, rows):
    """After the DB commit: the stored decisions replace the retry counts. A crash before this only leaves
    entries that the key's 48 h idle expiry removes."""
    pipe = redis.pipeline(transaction=False)
    for row in rows:
        pipe.hdel("velocity-counts:" + row["account"], row["id"])
    pipe.execute()


def run():
    """One DB transaction per polled batch (ADR-032). Alerts are produced only after the DB commit and offsets
    are committed only after the producer flush, so a crash replays the batch and reuses the stored decisions."""
    consumer = Consumer({"bootstrap.servers": BROKER, "group.id": "aml-scorer-v1",
                         "auto.offset.reset": "earliest", "enable.auto.commit": False})
    producer = Producer({"bootstrap.servers": BROKER, "enable.idempotence": True, "linger.ms": 1})
    redis = Redis(host="redis")
    velocity = redis.register_script(VELOCITY)
    consumer.subscribe([TOPIC])
    try:
        with psycopg.connect(DSN, autocommit=True, row_factory=dict_row) as db:
            while True:
                # ponytail: 20 ms poll bounds the added alert latency; tune BATCH/timeout if the latency gate tightens.
                batch = consumer.consume(BATCH, timeout=0.02)
                if not batch:
                    continue
                for msg in batch:
                    if msg.error():
                        raise RuntimeError(msg.error())
                rows = [json.loads(msg.value()) for msg in batch]
                with db.transaction():
                    results = score_batch(db, velocity, redis, rows,
                                          [dict(topic=msg.topic(), partition=msg.partition(), offset=msg.offset())
                                           for msg in batch])
                forget_counts(redis, rows)  # ids were canonicalized in place by record_transactions
                failed = []
                for msg, result in zip(batch, results):
                    if result["alert"]:
                        producer.produce("alerts", key=msg.key(), value=json.dumps(result),
                                         on_delivery=lambda err, _msg: err and failed.append(str(err)))
                if producer.flush(30) or failed:
                    raise RuntimeError(f"alert delivery incomplete: {failed}")  # exit without committing offsets
                consumer.commit(asynchronous=False)
    finally:
        consumer.close()


if __name__ == "__main__":
    run()
