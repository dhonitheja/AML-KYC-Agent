from datetime import datetime, timedelta

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from redis import Redis
from quixstreams import Application

from pipeline import BROKER, DSN, TOPIC, record_transaction
from rules import assess

# Account-keyed Kafka input serializes updates. NX also makes retried events
# count once. Use event time for windows and an idle-key expiry for retention.
VELOCITY = """
redis.call('ZADD', KEYS[1], 'NX', ARGV[1], ARGV[2])
local latest=redis.call('ZREVRANGE',KEYS[1],0,0,'WITHSCORES')
redis.call('ZREMRANGEBYSCORE',KEYS[1],'-inf',tonumber(latest[2])-172800)
redis.call('EXPIRE',KEYS[1],172800)
return {redis.call('ZCOUNT',KEYS[1],'('..(ARGV[1]-60),ARGV[1]),
        redis.call('ZCOUNT',KEYS[1],'('..(ARGV[1]-3600),ARGV[1])}
"""


def run():
    app = Application(broker_address=BROKER, consumer_group="aml-scorer-v1",
                      auto_offset_reset="earliest", producer_extra_config={"linger.ms": 1})
    velocity = Redis(host="redis").register_script(VELOCITY)
    with psycopg.connect(DSN, autocommit=True, row_factory=dict_row) as db:
        def score(row):
            with db.transaction():
                record_transaction(db, row, {"topic": TOPIC, "account_key": row["account"]})
                previous = db.execute("SELECT inputs FROM audit WHERE transaction_id=%s AND action='scored.v1'",
                                      (row["id"],)).fetchone()
                if previous:
                    return previous["inputs"]
                at = datetime.fromisoformat(row["occurred_at"])
                counts = velocity(keys=["velocity:"+row["account"]], args=[at.timestamp(), row["id"]])
                history = db.execute("""SELECT t.id::text,t.counterparty,t.amount_cents,t.direction,t.channel
                    FROM transactions t JOIN audit a ON a.transaction_id=t.id AND a.action='scored.v1'
                    WHERE t.account=%s AND t.occurred_at BETWEEN %s AND %s ORDER BY t.occurred_at,t.id""",
                                     (row["account"], at-timedelta(hours=48), at)).fetchall()
                result = assess(row, *counts, history)
                actions = ["scored.v1", "alerted.v1"] if result["alert"] else ["scored.v1"]
                for action in actions:
                    db.execute("""INSERT INTO audit(actor,action,case_id,transaction_id,inputs)
                        VALUES ('scorer-v1',%s,%s,%s,%s)""",
                               (action,row["case_id"],row["id"],Jsonb(result)))
                return result

        scored = app.dataframe(app.topic(TOPIC, value_deserializer="json")).apply(score)
        scored.filter(lambda record: record["alert"]).to_topic(app.topic("alerts", value_serializer="json"))
        app.run()


if __name__ == "__main__":
    run()
