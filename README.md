# Real-time AML/KYC Agent · Phases 1 and 2

Synthetic-data engineering demo. The Python producer sends account-keyed transactions to Redpanda. A Python consumer commits transactions and their audit records in one PostgreSQL transaction before acknowledging Kafka offsets. Replayed event IDs are ignored. The application login can append to the audit table but cannot update or delete entries. Database administrators retain control. Redis tracks event-time velocity. FastAPI listens on host loopback port 8000. Compose credentials are local demonstration values.

## Run on Windows with Docker Desktop in Linux container mode

Open PowerShell inside the extracted project folder.

```powershell
docker compose up --build -d
docker compose run --rm ingest seed
docker compose run --rm ingest benchmark --seconds 60
docker compose exec postgres psql -U postgres -d aml -c "SELECT counterparty, direction, amount_cents, occurred_at FROM transactions WHERE case_id='AML-1042' ORDER BY occurred_at;"
docker compose down
```

The seed sends two credits totaling $83,800 followed by an $80,900 debit the next day. Rerunning the seed preserves the three transaction identities. Named volumes retain records across normal restarts. The benchmark uses a fresh run ID and offers 60 events per second. It counts durable transaction rows and matching audit entries through the end of the run, includes startup and drain time, and exits successfully only when all records arrive with average persisted throughput of at least 50/s. This measures phase 1 ingestion, not scoring latency. To stream additional data use `docker compose run --rm ingest generate --rate 50 --seconds 120`.

The browser POC is separate. The scorer runs independently of any model. Investigation agents and the shared analyst console belong to later phases. No model credentials or real customer data are needed.

## Phase 2 · scoring and alerts

The Quix Streams consumer scores account-keyed arrivals using 48 hours of previously scored account history. Seven illustrative rules cover rapid pass-through, large transfers, large cash activity, one-minute and one-hour velocity, repeated amounts, and debits after credits from multiple counterparties. Scores of 60 or more produce a Kafka message on `alerts` with the triggering transaction ID and evidence. Redis counts each event ID once in rolling event-time windows and retains two days of activity. Older late arrivals can have incomplete velocity context. Subsequent arrivals do not retrospectively rescore earlier transactions.

PostgreSQL records ingestion, scoring and alert decisions. A replay reuses the original decision. Alerts are delivered at least once. Downstream consumers should deduplicate by transaction ID and rule version. The migration runs during Compose startup on both new and existing Phase 1 databases. The API has read-only routes for the latest 100 alerts and individual transaction scores. Run locally with synthetic data.

After starting Compose, run these PowerShell commands:

```powershell
docker compose run --rm --entrypoint python ingest -m pytest -q
docker compose run --rm --entrypoint python ingest latency.py
Invoke-RestMethod http://localhost:8000/alerts
```

CI runs a warm-up, then 40 independent Northstar scenarios on isolated account keys. It measures from just before the triggering debit is published until the benchmark consumer receives its matching alert, including broker, Redis and database work. Missing alerts, missing pass-through evidence or p95 of 500 ms or more fail CI. This tests the seeded scenario. The 1,000 transactions/s load test belongs to Phase 6.
