"""Phase 1 synthetic stream, idempotent consumer and database acceptance check."""
import argparse
import json
import time
import uuid
from datetime import datetime, timedelta, timezone

TOPIC = "transactions"
BROKER = "kafka:9092"
DSN = "postgresql://aml_worker:synthetic-worker@postgres/aml"
SEED = [("Redwood Supply", 4820000, "credit", "ACH"),
        ("Cedar Coast LLC", 3560000, "credit", "wire"),
        ("Terrace Imports", 8090000, "debit", "wire")]


def event(run, i, now, seed=False, accounts=100):
    case_id = None
    # Load-test accounts are scoped to the run, so each run starts with empty 48 h histories (NFR-009).
    account = f"DEMO-{i % 100:03}" if accounts == 100 else f"LOAD-{str(run)[:8]}-{i * 7919 % accounts:05}"
    party, cents, direction, channel = f"Synthetic merchant {i % 47}", 1000 + i % 100000, "credit" if i % 2 else "debit", "ACH"
    if seed:
        case_id, account = "AML-1042", "DEMO-1042"
        party, cents, direction, channel = SEED[i]
        now = datetime(2026, 11, 14, 12, tzinfo=timezone.utc) + timedelta(days=int(i == 2), minutes=i)
    return dict(id=str(uuid.uuid5(run, str(i))), run_id=str(run), case_id=case_id,
                account=account, counterparty=party, amount_cents=cents, direction=direction,
                channel=channel, occurred_at=now.isoformat())


def produce(run, rate, count, seed=False, accounts=100):
    from confluent_kafka import Producer
    p = Producer({"bootstrap.servers": BROKER, "enable.idempotence": True})
    errors = []

    def delivered(err, msg):
        if err:
            errors.append(str(err))

    # Establish connectivity before starting the pacing clock.
    p.list_topics(TOPIC, timeout=30)
    start = time.monotonic()
    for i in range(count):
        msg = event(run, i, datetime.now(timezone.utc), seed, accounts)
        time.sleep(max(0, start + i / rate - time.monotonic()))
        p.produce(TOPIC, key=msg["account"], value=json.dumps(msg), on_delivery=delivered)
        p.poll(0)
    if p.flush(30) or errors:
        raise RuntimeError(f"Delivery incomplete: {errors}")


def record_transaction(db, row, origin):
    record_transactions(db, [(row, origin)])


def copy_audit(db, rows):
    """Append audit rows [(actor, action, case_id, transaction_id, inputs)] with one COPY (ADR-032).
    COPY fires the same triggers and constraints as INSERT; the audit table stays append-only."""
    if rows:
        with db.cursor().copy("COPY audit(actor,action,case_id,transaction_id,inputs) FROM STDIN") as copy:
            for actor, action, case_id, transaction_id, inputs in rows:
                copy.write_row((actor, action, case_id, transaction_id, json.dumps(inputs)))


def record_transactions(db, items):
    """The single write path for transactions: items = [(row, origin)]. One statement inserts the batch in id
    order, so ingest and scorer batch transactions take row locks in the same order and cannot deadlock.
    Only a newly inserted row gets a `transaction.recorded` audit entry. Returns the set of new ids."""
    from psycopg.types.json import Jsonb
    new = {r[0] if isinstance(r, tuple) else r["id"] for r in db.execute(
        """INSERT INTO transactions(id,run_id,case_id,account,counterparty,amount_cents,direction,channel,occurred_at)
           SELECT DISTINCT ON (id) id,run_id,case_id,account,counterparty,amount_cents,direction,channel,occurred_at
           FROM jsonb_to_recordset(%s) AS r(id uuid, run_id uuid, case_id text, account text, counterparty text,
                amount_cents bigint, direction text, channel text, occurred_at timestamptz)
           ORDER BY id
           ON CONFLICT(id) DO NOTHING RETURNING id::text AS id""", (Jsonb([row for row, _ in items]),))}
    audit, pending = [], set(new)
    for row, origin in items:  # first occurrence only: a batch can carry the same message twice
        if row["id"] in pending:
            pending.discard(row["id"])
            audit.append(("ingest-v1", "transaction.recorded", row["case_id"], row["id"], dict(record=row, **origin)))
    copy_audit(db, audit)
    return new


def ingest():
    import psycopg
    from confluent_kafka import Consumer
    from psycopg.types.json import Jsonb
    consumer = Consumer({"bootstrap.servers": BROKER, "group.id": "aml-ingest-v1",
                         "auto.offset.reset": "earliest", "enable.auto.commit": False})
    consumer.subscribe([TOPIC])
    try:
        with psycopg.connect(DSN, autocommit=True) as db:
            while True:
                batch = consumer.consume(100, timeout=0.25)
                if not batch:
                    continue
                for msg in batch:
                    if msg.error():
                        raise RuntimeError(msg.error())
                with db.transaction():
                    record_transactions(db, [(json.loads(msg.value()),
                                              dict(topic=msg.topic(), partition=msg.partition(), offset=msg.offset()))
                                             for msg in batch])
                consumer.commit(asynchronous=False)
    finally:
        consumer.close()


def benchmark(seconds):
    import psycopg
    # Offer headroom so a 50/s result includes broker and consumer drain time.
    run, target, offered = uuid.uuid4(), 50, 60
    count = seconds * offered
    with psycopg.connect(DSN, autocommit=True) as db:
        start = time.monotonic()
        produce(run, offered, count)
        while True:
            rows, audited = db.execute("""SELECT count(*),count(a.transaction_id)
                FROM transactions t LEFT JOIN audit a ON a.transaction_id=t.id AND a.action='transaction.recorded' WHERE t.run_id=%s""", (run,)).fetchone()
            elapsed = time.monotonic() - start
            if rows == audited == count or elapsed > seconds + 60:
                break
            time.sleep(0.1)
    throughput = rows / elapsed
    passed = rows == audited == count and throughput >= target
    print(json.dumps(dict(run=str(run), rows=rows, audited=audited, expected=count,
                          seconds=round(elapsed, 3), persisted_per_second=round(throughput, 2), passed=passed)))
    return 0 if passed else 1


def loadtest(rate, seconds, accounts, target):
    """Phase 6 gate (NFR-009): offer `rate`/s for `seconds` over `accounts` keys and pass only if every
    transaction is recorded and scored and scored rows / elapsed (including drain) >= target."""
    import psycopg
    run, count = uuid.uuid4(), rate * seconds
    with psycopg.connect(DSN, autocommit=True) as db:
        start = time.monotonic()
        produce(run, rate, count, accounts=accounts)
        while True:
            recorded, scored = db.execute("""SELECT count(*) FILTER (WHERE a.action='transaction.recorded'),
                count(*) FILTER (WHERE a.action='scored.v1') FROM transactions t JOIN audit a ON a.transaction_id=t.id
                WHERE t.run_id=%s AND a.action IN ('transaction.recorded','scored.v1')""", (run,)).fetchone()
            elapsed = time.monotonic() - start
            if recorded == scored == count or elapsed > seconds + 60:
                break
            time.sleep(0.25)
    throughput = scored / elapsed
    passed = recorded == scored == count and throughput >= target
    print(json.dumps(dict(run=str(run), offered_per_second=rate, accounts=accounts, expected=count,
                          recorded=recorded, scored=scored, seconds=round(elapsed, 3),
                          scored_per_second=round(throughput, 2), target=target, passed=passed)))
    return 0 if passed else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["ingest", "seed", "benchmark", "generate", "loadtest"])
    parser.add_argument("--seconds", type=int, default=60)
    parser.add_argument("--rate", type=int, default=50)
    parser.add_argument("--accounts", type=int, default=10000, help="loadtest only")
    parser.add_argument("--target", type=int, default=1000, help="loadtest only: required scored/s")
    args = parser.parse_args()
    if min(args.seconds, args.rate, args.accounts, args.target) <= 0:
        parser.error("rate, seconds, accounts and target must be positive")
    if args.command == "ingest":
        ingest()
    elif args.command == "benchmark":
        raise SystemExit(benchmark(args.seconds))
    elif args.command == "loadtest":
        raise SystemExit(loadtest(args.rate, args.seconds, args.accounts, args.target))
    elif args.command == "seed":
        produce(uuid.uuid5(uuid.NAMESPACE_DNS, "synthetic.northstar.aml1042"), 50, 3, True)
    else:
        produce(uuid.uuid4(), args.rate, args.seconds * args.rate)
