"""Model providers (offline stub default, local Ollama and Anthropic opt-in) and the bounded retry loop (CS-009)."""
import http.client
import json
import random
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass, field

PROMPT_VERSION = "investigation-prompt-v2"
FABRICATED_ID = "ffffffff-ffff-ffff-ffff-ffffffffffff"
UNGROUNDED = ' "Phantom Holdings" moved $1.23 under invented_rule after an OFAC match.'


@dataclass
class Failure:
    attempts: int
    error: str
    failed_checks: list = field(default_factory=list)
    last_reason: str = "model_failure"


class ModelError(Exception):
    """Backend-neutral failure: a sanitized tag ("<Class>[:<status>]") and whether to retry. Never chained."""

    def __init__(self, tag, retryable):
        super().__init__(tag)
        self.tag = tag
        self.retryable = retryable


def is_uuid(value):
    try:
        uuid.UUID(str(value))
        return True
    except ValueError:
        return False


class StubLLM:
    """Deterministic, offline. script: per-attempt modes ok|raise|fabricated_id|ungrounded (last one repeats)."""

    def __init__(self, script=None):
        self.script = list(script or ["ok"])
        self.calls = 0

    def params(self):
        return {}

    def complete(self, system, user):
        mode = self.script[min(self.calls, len(self.script) - 1)]
        self.calls += 1
        if mode == "raise":
            raise RuntimeError("stub forced failure")
        start = user.index("<evidence>") + len("<evidence>")
        evidence = json.loads(user[start:user.rindex("</evidence>")])
        tid = evidence["transaction"]["id"]
        ids = sorted({tid, *(h["id"] for h in evidence["history"])})
        rules = evidence["rules"]
        known = set(ids) | {str(e) for r in rules for e in r["evidence"] if is_uuid(e)}
        hit = any(s["hits"] for s in evidence["screenings"])
        summary = (f"transaction {tid} scored {evidence['score']} with fired rules: "
                   f"{', '.join(r['rule'] for r in rules) or 'none'}.")
        findings = [dict(statement=f"{r['rule']} fired for {r['points']} points.", rule=r["rule"],
                         cited_transaction_ids=sorted(known & {str(e) for e in r["evidence"]}) or [tid])
                    for r in rules]
        if hit:
            summary += " payment screening recorded a screening hit."
            findings.append(dict(statement="screening hit recorded for counterparty screening.",
                                 rule=None, cited_transaction_ids=[tid]))
        if not findings:
            findings.append(dict(statement="no rules fired for this transaction.", rule=None,
                                 cited_transaction_ids=[tid]))
        findings = findings[:10]
        if mode == "fabricated_id":
            ids = sorted(ids + [FABRICATED_ID])
        if mode == "ungrounded":
            summary += UNGROUNDED
        covered = {i for f in findings for i in f["cited_transaction_ids"]}
        findings[0]["cited_transaction_ids"] = sorted(set(findings[0]["cited_transaction_ids"]) | (set(ids) - covered))
        escalate = hit or any(r["points"] >= 60 for r in rules)
        draft = dict(summary=summary, cited_transaction_ids=ids, findings=findings,
                     recommendation="escalate_for_review" if escalate else "no_further_action_suggested")
        return json.dumps(draft), "stub-v1"


ANTHROPIC_MAX_TOKENS = 16000
ANTHROPIC_EFFORT = "low"


class AnthropicLLM:
    def __init__(self, api_key, model, timeout):
        import anthropic
        self.client = anthropic.Anthropic(api_key=api_key, max_retries=0, timeout=timeout)
        self.model = model

    def params(self):
        return {"max_tokens": ANTHROPIC_MAX_TOKENS, "effort": ANTHROPIC_EFFORT}

    def complete(self, system, user):
        try:
            response = self.client.messages.create(
                model=self.model, max_tokens=ANTHROPIC_MAX_TOKENS, output_config={"effort": ANTHROPIC_EFFORT},
                system=system, messages=[{"role": "user", "content": user}])
        except Exception as exc:
            raise ModelError(_sanitize(exc), _anthropic_retryable(exc)) from None
        if response.stop_reason in ("refusal", "max_tokens"):
            raise ModelError(f"stop_reason:{response.stop_reason}", False)
        text = "".join(b.text for b in response.content if b.type == "text")  # thinking blocks are skipped
        if not text:
            raise ModelError("validation", True)  # no text content is an error (CS-009); retryable like bad JSON
        return text, response.model


def _anthropic_retryable(exc):
    import anthropic  # already loaded: only AnthropicLLM calls this
    if isinstance(exc, anthropic.APIStatusError):  # 429 and 5xx retry; other 4xx stop
        status = getattr(exc, "status_code", None)
        return isinstance(status, int) and (status == 429 or status >= 500)
    return True  # APITimeoutError, APIConnectionError, unknown: bounded by max_attempts


LOCAL_TEMPERATURE = 0
LOCAL_FORMAT = "json"
LOCAL_NUM_PREDICT = 4096


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """A 3xx surfaces as HTTPError (non-retryable): a response cannot steer evidence elsewhere."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class LocalLLM:
    """Self-hosted Ollama /api/chat on the internal network (DI-011). No auth, no secret, stdlib only."""

    def __init__(self, url, model, timeout):
        self.url = url.rstrip("/") + "/api/chat"
        self.model = model
        self.timeout = timeout
        # Empty ProxyHandler: HTTP(S)_PROXY env vars cannot reroute the call. Never urlopen (global opener).
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect)

    def params(self):
        return {"temperature": LOCAL_TEMPERATURE, "format": LOCAL_FORMAT, "num_predict": LOCAL_NUM_PREDICT}

    def complete(self, system, user):
        body = json.dumps({"model": self.model, "stream": False, "format": LOCAL_FORMAT,
                           "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                           "options": {"temperature": LOCAL_TEMPERATURE, "num_predict": LOCAL_NUM_PREDICT}})
        req = urllib.request.Request(self.url, data=body.encode(), method="POST",
                                     headers={"Content-Type": "application/json"})
        deadline = time.monotonic() + self.timeout
        try:
            with self.opener.open(req, timeout=self.timeout) as resp:
                # The socket timeout only bounds each read, so a server trickling bytes could hold the consumer
                # forever. read1 returns after one socket read; the deadline caps the whole call at ~2x timeout.
                chunks = []
                while chunk := resp.read1(65536):
                    chunks.append(chunk)
                    if time.monotonic() > deadline:
                        raise TimeoutError
                raw = b"".join(chunks)
        except urllib.error.HTTPError as exc:
            exc.close()
            raise ModelError(f"HTTPError:{exc.code}", exc.code == 429 or exc.code >= 500) from None
        except (urllib.error.URLError, OSError, http.client.HTTPException) as exc:
            # refused, DNS, timeout, reset, remote disconnect: retryable. The reason text is never kept.
            raise ModelError(type(exc).__name__, True) from None
        try:
            data = json.loads(raw)
        except ValueError:
            raise ModelError("validation", True) from None
        if not isinstance(data, dict) or "error" in data:
            raise ModelError("validation", True)
        if data.get("done_reason") == "length":
            raise ModelError("done_reason:length", False)
        message = data.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str) or not content:
            raise ModelError("validation", True)
        return content, self.model  # server model echo ignored: model_version = LLM_MODEL


def _sanitize(exc):
    status = getattr(exc, "status_code", None)
    return type(exc).__name__ + (f":{status}" if isinstance(status, int) else "")


def complete_with_retry(llm, system, user, validate, max_attempts, sleep=time.sleep, rng=random.random):
    """(text, model_id, attempts) on success, else Failure. Never raises on model failure."""
    failure = None
    for attempt in range(1, max_attempts + 1):
        try:
            text, model_id = llm.complete(system, user)
        except ModelError as exc:
            failure = Failure(attempt, exc.tag)
            if not exc.retryable:
                return failure
        except Exception as exc:  # never chained, logged or stored: only the sanitized name survives
            failure = Failure(attempt, _sanitize(exc))
        else:
            result = validate(text)
            if result is None:
                return text, model_id, attempt
            tag, checks = (result, []) if isinstance(result, str) else result
            failure = Failure(attempt, tag, list(checks),
                              "grounding_failure" if tag == "grounding" else "model_failure")
        if attempt < max_attempts:
            sleep(min(30, 2 ** (attempt - 1)) * (0.5 + rng()))
    return failure
