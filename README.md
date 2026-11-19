# Real-time AML/KYC Agent · Phase 1

Synthetic-data engineering demo. The Python producer sends account-keyed transactions to Redpanda. A Python consumer commits transactions and their audit records in one PostgreSQL transaction before acknowledging Kafka offsets. Replayed event IDs are ignored. The application login can append to the audit table but cannot update or delete entries. Database administrators retain control. Redis is available for Phase 2. No services publish host ports. Compose credentials are local demonstration values.

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

The browser POC is separate. Live scoring, case investigation agents and the shared analyst console belong to subsequent phases. No model credentials or real customer data are needed.
