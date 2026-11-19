"""Producer-to-alert-consumer p95 for independent Northstar scenarios."""
import json
import math
import time
import uuid

from confluent_kafka import Consumer, Producer, TopicPartition
from pipeline import BROKER, TOPIC, event


def sample(producer, consumer, timeout):
    run = uuid.uuid4()
    account = "BENCH-" + str(run)
    for i in range(3):
        row = event(run, i, None, True)
        row["account"] = account
        if i == 2:
            started = time.monotonic()
        producer.produce(TOPIC,key=account,value=json.dumps(row))
    if producer.flush(10):
        raise RuntimeError("Unsent Northstar events")
    while time.monotonic()-started < timeout:
        msg=consumer.poll(0.05)
        if not msg:
            continue
        if msg.error():
            raise RuntimeError(msg.error())
        alert=json.loads(msg.value())
        if alert["transaction_id"] == row["id"]:
            if "rapid_pass_through" not in {h["rule"] for h in alert["rules"]}:
                raise AssertionError("Northstar alert missing pass-through evidence")
            return (time.monotonic()-started)*1000
    raise TimeoutError(f"No Northstar alert for {row['id']}")


if __name__ == "__main__":
    producer=Producer({"bootstrap.servers":BROKER,"linger.ms":0})
    consumer=Consumer({"bootstrap.servers":BROKER,"group.id":str(uuid.uuid4()),
                       "enable.auto.commit":False,"fetch.wait.max.ms":10})
    partition=TopicPartition("alerts",0)
    try:
        _,end=consumer.get_watermark_offsets(partition,timeout=30)
        consumer.assign([TopicPartition("alerts",0,end)])
        sample(producer,consumer,90)
        samples=[sample(producer,consumer,10) for _ in range(40)]
        p95=sorted(samples)[math.ceil(len(samples)*0.95)-1]
        print(json.dumps({"samples":len(samples),"detected":len(samples),"p95_ms":p95,"max_ms":max(samples)}))
        raise SystemExit(0 if p95 < 500 else 1)
    finally:
        consumer.close()
