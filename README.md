# Real-time AML/KYC Agent · Phases 1 through 3

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

## Phase 3 · KYC onboarding and screening

Rapid pass-through alone triggers a transaction alert (65 points against the 60-point alert threshold). Screening findings are separate audit events. A name similarity hit identifies a candidate for analyst review. An agreeing or conflicting full birth date is recorded with the match. Neither the screener nor the scoring service clears, blocks, or closes a case.

With Compose running, open http://localhost:8000/docs and submit a synthetic person or business to **POST /onboarding**. Use a UUID as the application ID. Provide the declared identity and at least one document's extracted fields. A person needs a birth date. A business can supply recursively nested owners. Documents are submitted as structured fields; the endpoint compares name, birth date, ID and address. It screens the applicant, document name variants, and each owner. Reusing the same ID and payload returns the original result. Changed input under that ID returns HTTP 409.

The demo and CI use fictional SDN-format entries in `watchlists/sample.xml`. Try “Cobalt Meridan Exports” to see a spelling-variant hit, or “Juniper Orchard Services” for a clean control. The stream screens an outbound counterparty on first encounter for each account and list snapshot. Results include snapshot SHA-256, entry ID, matched name or alias, similarity score and reasoning. Normalization ignores case, accents, punctuation and word order. The illustrative threshold is 88/100. Similar names alone cannot establish identity.

To load the public [OFAC SDN XML list](https://ofac.treasury.gov/sanctions-list-service), use the following PowerShell commands after building the image. The loader validates a download before replacing the local file. Restart services to change the selected path. Repeat the first command to refresh an active snapshot; future counterparty encounters use its new hash. Historical findings retain their original snapshot ID.

```powershell
docker compose run --rm -v "${PWD}/watchlists:/app/watchlists" --entrypoint python ingest watchlist.py
$env:SDN_FILE = "watchlists/sdn.xml"
docker compose up -d --force-recreate api scorer
```

The automated screening tests run in fixture mode (the default). They submit applications to FastAPI and payments through Kafka, then check the recorded findings in PostgreSQL. Use synthetic identity documents and payment data only.
