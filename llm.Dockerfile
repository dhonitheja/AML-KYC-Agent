# Self-hosted model server for LLM_MODE=local (ADR-029, DI-011). Built only with --profile local.
# Weights are downloaded once at build time; the running container sits on the internal network only.
FROM ollama/ollama:0.40.17@sha256:ccc42bcd3d5fcf7ab0d532b300382154e1a4da56fc666bdb313b78ebdd912754
ARG OLLAMA_MODEL
ENV OLLAMA_MODELS=/models OLLAMA_NOPRUNE=1 OLLAMA_HOST=0.0.0.0:11434
RUN test -n "$OLLAMA_MODEL" || { echo "OLLAMA_MODEL build arg is required"; exit 1; }; \
    ollama serve & pid=$!; \
    for i in $(seq 30); do ollama list >/dev/null 2>&1 && break; sleep 1; done; \
    ollama pull "$OLLAMA_MODEL" && ollama list; status=$?; kill $pid; exit $status
RUN chmod -R a+rX /models && useradd --system --uid 10001 app
ENV HOME=/tmp
USER app
