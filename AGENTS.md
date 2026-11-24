# Repository Guidelines

## Project structure

Python modules live at the repository root. `pipeline.py` produces synthetic transactions and persists them to PostgreSQL. `rules.py` evaluates scoring rules, while `scoring.py` connects those rules to the event stream and Redis velocity counters. For onboarding and watchlist changes, start with `kyc.py` and `watchlist.py`. FastAPI routes live in `api.py`.

Keep database changes in `sql/`, following the numbered migration pattern (for example, `003-kyc.sql`). The fictional screening fixture is `watchlists/sample.xml`. Use synthetic identities and payments for development and tests.

## Local development commands

Run these commands from the repository root. On Windows, use Docker Desktop in Linux container mode.

| Command | Purpose |
| --- | --- |
| `docker compose up --build -d` | Build and start the stack. Explore the API at `http://localhost:8000/docs`. |
| `docker compose run --rm ingest seed` | Replay the three transactions for case `AML-1042`. Check `GET /alerts` for the resulting alert. |
| `docker compose run --rm --entrypoint python ingest -m pytest -v` | Run the test suite against the running services. |
| `docker compose down` | Stop the stack and retain the named volumes. |

## Coding style

Use four-space indentation and snake_case for Python functions and variables. Preserve field names and units such as `amount_cents`. Keep rule calculations in `rules.py` so tests can exercise them directly. The repository has no configured formatter or linter.

## Testing guidelines

Place pytest tests in `tests/test_*.py` and name functions `test_<behavior>`. When changing persistence, test replaying the same event and check both the transaction and its audit records.

CI also runs `docker compose run --rm --entrypoint python ingest latency.py` and requires seeded alert latency below 500 ms at p95. Run `docker compose run --rm ingest benchmark --seconds 60` to check that all offered events persist at an average of at least 50 per second.

## Commits and pull requests

Follow the Git history's imperative subjects, such as "Add KYC onboarding, OFAC snapshot loading and payment screening". In pull requests, describe the behavior change, identify affected routes or migrations, and report the tests and benchmarks you ran. Link a related issue when available.
