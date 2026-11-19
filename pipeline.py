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


def event(run, i, now, seed=False):
    case_id = None
    account = f"DEMO-{i % 100:03}"
    party, cents, direction, channel = f"Synthetic merchant {i % 47}", 1000 + i % 100000, "credit" if i % 2 else "debit", "ACH"
    if seed:
        case_id, account = "AML-1042", "DEMO-1042"
        party, cents, direction, channel = SEED[i]
        now = datetime(2026, 11, 14, 12, tzinfo=timezone.utc) + timedelta(days=int(i == 2), minutes=i)
    return dict(id=str(uuid.uuid5(run, str(i))), run_id=str(run), case_id=case_id,
                account=account, counterparty=party, amount_cents=cents, direction=direction,
                channel=channel, occurred_at=now.isoformat())


def produce(run, rate, count, seed=False):
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
        msg = event(run, i, datetime.now(timezone.utc), seed)
        time.sleep(max(0, start + i / rate - time.monotonic()))
        p.produce(TOPIC, key=msg["account"], value=json.dumps(msg), on_delivery=delivered)
        p.poll(0)
    if p.flush(30) or errors:
        raise RuntimeError(f"Delivery incomplete: {errors}")


def ingest():
    import psycopg
    from confluent_kafka import Consumer
    from psycopg.types.json import Jsonb
    consumer = Consumer({"bootstrap.servers": BROKER, "group.id": "aml-ingest-v1",
                         "auto.offset.reset": "earliest", "enable.auto.commit": False})
    consumer.subscribe([TOPIC])
    sql = """INSERT INTO transactions(id,run_id,case_id,account,counterparty,amount_cents,direction,channel,occurred_at)
             VALUES (%(id)s,%(run_id)s,%(case_id)s,%(account)s,%(counterparty)s,%(amount_cents)s,%(direction)s,%(channel)s,%(occurred_at)s)
             ON CONFLICT(id) DO NOTHING RETURNING id"""
    try:
        with psycopg.connect(DSN, autocommit=True) as db:
            while True:
                batch = consumer.consume(100, timeout=0.25)
                if not batch:
                    continue
                with db.transaction():
                    for msg in batch:
                        if msg.error():
                            raise RuntimeError(msg.error())
                        row = json.loads(msg.value())
                        if db.execute(sql, row).fetchone():
                            inputs = dict(record=row, topic=msg.topic(), partition=msg.partition(), offset=msg.offset())
                            db.execute("""INSERT INTO audit(actor,action,case_id,transaction_id,inputs)
                                          VALUES ('ingest-v1','transaction.recorded',%s,%s,%s)""",
                                       (row["case_id"], row["id"], Jsonb(inputs)))
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
                FROM transactions t LEFT JOIN audit a ON a.transaction_id=t.id WHERE t.run_id=%s""", (run,)).fetchone()
            elapsed = time.monotonic() - start
            if rows == audited == count or elapsed > seconds + 60:
                break
            time.sleep(0.1)
    throughput = rows / elapsed
    passed = rows == audited == count and throughput >= target
    print(json.dumps(dict(run=str(run), rows=rows, audited=audited, expected=count,
                          seconds=round(elapsed, 3), persisted_per_second=round(throughput, 2), passed=passed)))
    return 0 if passed else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["ingest", "seed", "benchmark", "generate"])
    parser.add_argument("--seconds", type=int, default=60)
    parser.add_argument("--rate", type=int, default=50)
    args = parser.parse_args()
    if min(args.seconds, args.rate) <= 0:
        parser.error("rate and seconds must be positive")
    if args.command == "ingest":
        ingest()
    elif args.command == "benchmark":
        raise SystemExit(benchmark(args.seconds))
    elif args.command == "seed":
        produce(uuid.uuid5(uuid.NAMESPACE_DNS, "synthetic.northstar.aml1042"), 50, 3, True)
    else:
        produce(uuid.uuid4(), args.rate, args.seconds * args.rate)
