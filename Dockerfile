FROM python:3.12-slim AS base
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN useradd --system --uid 10001 app && mkdir -p /app/state && chown app /app/state

FROM base AS investigator
COPY investigator.py llm.py grounding.py watchlist.py eval_investigator.py ./
COPY tests/eval/scenarios.json ./tests/eval/scenarios.json
COPY tests/egress_check.py ./tests/egress_check.py
USER app
ENTRYPOINT ["python", "-u", "investigator.py"]

FROM base AS application
COPY *.py ./
COPY watchlists/sample.xml ./watchlists/sample.xml
COPY tests ./tests
USER app
ENTRYPOINT ["python", "-u", "pipeline.py"]
