"""Pure tests for llm.py (CS-009 v1.2, DI-010, DI-011; FR-010.2, FR-010.4, FR-010.5 AC-3/AC-4, FR-011.2 AC-5/AC-7).
Never builds a real Anthropic client (conftest guard); LocalLLM only talks to in-process 127.0.0.1 servers."""
import json
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

import llm
from conftest import Sleeps, chat_reply, free_port
from grounding import Draft, check_grounding
from llm import Failure, LocalLLM, StubLLM, complete_with_retry

ROOT = Path(__file__).resolve().parents[1]
TX, C1, C2 = (str(uuid.UUID(int=i)) for i in (1, 2, 3))
HIT = dict(entry_id="990001", listed_name="COBALT MERIDIAN EXPORTS", matched_name="Cobalt Meridian Exports",
           score=100.0, disposition="possible_match")
PLANTED = "sk-ant-api03-PLANTED-SECRET-0000"


def row(id_, party, cents, direction):
    return dict(id=id_, counterparty=party, amount_cents=cents, direction=direction, channel="wire",
                occurred_at="2026-11-14T12:00:00+00:00")


def evidence(rules=(("rapid_pass_through", 65),), hits=()):
    """AML-1042-shaped evidence: debit TX plus credits C1, C2 in history."""
    return dict(transaction=dict(row(TX, "Terrace Imports", 8090000, "debit"), account="SUBJECT_ACCOUNT"),
                history=[row(C2, "Cedar Coast LLC", 3560000, "credit"), row(C1, "Redwood Supply", 4820000, "credit")],
                rules=[dict(rule=r, points=p, evidence=[C1, C2, TX]) for r, p in rules],
                score=min(100, sum(p for _, p in rules)),
                screenings=[dict(name="Terrace Imports", snapshot="ab" * 32, threshold=88, hits=list(hits))],
                evidence_truncated=False, evidence_original_counts={})


def user_of(ev):
    # CS-008 render_prompt user format: <evidence> + canonical JSON + </evidence>.
    return "<evidence>" + json.dumps(ev, sort_keys=True, separators=(",", ":")) + "</evidence>"


def ok(_text):
    return None


def assert_clean(failure, *secrets):
    """Sanitized error: '<Class>[:<status>]' only; no secret, URL or response text anywhere in the Failure."""
    blob = repr(failure) + str(failure.error)
    for s in secrets:
        assert s not in blob


def test_prompt_version_is_pinned():
    # FR-010.3 AC-2: prompt_version is the template version string.
    assert llm.PROMPT_VERSION == "investigation-prompt-v2"


# ---------------------------------------------------------------- StubLLM (FR-010.2, CS-009)

# FR-010.2 AC-1: identical evidence gives byte-identical output, model id stub-v1.
def test_stub_is_deterministic():
    a = StubLLM().complete("system", user_of(evidence()))
    b = StubLLM().complete("other system", user_of(evidence()))
    assert a == b and a[1] == "stub-v1" and isinstance(a[0], str)


# CS-009 pinned templates (AML-1042 shape).
def test_stub_templates_for_fired_rule():
    d = json.loads(StubLLM().complete("s", user_of(evidence()))[0])
    assert d["summary"] == f"transaction {TX} scored 65 with fired rules: rapid_pass_through."
    assert d["recommendation"] == "escalate_for_review"
    assert d["cited_transaction_ids"] == sorted([TX, C1, C2])
    assert d["findings"][0]["statement"] == "rapid_pass_through fired for 65 points."
    assert d["findings"][0]["rule"] == "rapid_pass_through"
    cited = {i for f in d["findings"] for i in f["cited_transaction_ids"]}
    assert set(d["cited_transaction_ids"]) <= cited <= {TX, C1, C2}


# CS-009 boundary: nothing fired, no hit.
def test_stub_templates_for_clean_evidence():
    d = json.loads(StubLLM().complete("s", user_of(evidence(rules=())))[0])
    assert d["summary"] == f"transaction {TX} scored 0 with fired rules: none."
    assert d["recommendation"] == "no_further_action_suggested"
    assert [f["statement"] for f in d["findings"]] == ["no rules fired for this transaction."]
    assert TX in d["findings"][0]["cited_transaction_ids"] and d["findings"][0]["rule"] is None


def test_stub_templates_for_screening_hit():
    d = json.loads(StubLLM().complete("s", user_of(evidence(rules=(), hits=[HIT])))[0])
    assert d["summary"].endswith(" payment screening recorded a screening hit.")
    assert d["recommendation"] == "escalate_for_review"
    assert "screening hit recorded for counterparty screening." in [f["statement"] for f in d["findings"]]


# CS-009: escalate iff any rule has points >= 60 or a hit exists (boundary 59/60).
@pytest.mark.parametrize("points,expected", [(59, "no_further_action_suggested"), (60, "escalate_for_review")])
def test_stub_recommendation_boundary(points, expected):
    d = json.loads(StubLLM().complete("s", user_of(evidence(rules=(("large_cash_activity", points),))))[0])
    assert d["recommendation"] == expected


# CS-009 boundary: at most 10 findings even with more fired rules.
def test_stub_caps_findings_at_ten():
    rules = tuple((f"rule_{chr(97 + i)}", 5) for i in range(12))
    text, _ = StubLLM().complete("s", user_of(evidence(rules=rules)))
    assert 1 <= len(Draft.model_validate_json(text).findings) <= 10


# FR-011 / CS-009: stub output is schema-valid and passes every grounding check.
@pytest.mark.parametrize("ev", [evidence(), evidence(rules=()), evidence(rules=(), hits=[HIT]),
                                evidence(rules=(("rapid_pass_through", 65), ("repeated_amount", 30)), hits=[HIT])])
def test_stub_output_is_grounded(ev):
    text, _ = StubLLM().complete("s", user_of(ev))
    assert "$" not in text and '\\"' not in text
    assert check_grounding(Draft.model_validate_json(text), ev) == []


# CS-009 failure: unparseable evidence raises (exercises the model_failure path).
@pytest.mark.parametrize("user", ["no evidence here", "<evidence>{not json</evidence>", ""])
def test_stub_raises_on_unparseable_evidence(user):
    with pytest.raises(Exception):
        StubLLM().complete("s", user)


# CS-009 Invariants: the anthropic import is lazy; stub (and local) never load it.
def test_stub_and_local_never_import_anthropic():
    code = ("import sys, llm; llm.StubLLM(); llm.LocalLLM('http://127.0.0.1:9', 'm', 1); "
            "assert 'anthropic' not in sys.modules")
    subprocess.run([sys.executable, "-c", code], cwd=ROOT, check=True, timeout=60)


# ---------------------------------------------------------------- complete_with_retry (FR-010.4, FR-011.2)

class Scripted:
    """Fake backend: one item per attempt (text, or an exception to raise); the last item repeats."""

    def __init__(self, *items):
        self.items, self.calls = list(items), 0

    def complete(self, system, user):
        item = self.items[min(self.calls, len(self.items) - 1)]
        self.calls += 1
        if isinstance(item, BaseException):
            raise item
        return item, "fake-model"


def classify(text):
    """validate callback per CS-009: None on success, an error tag, or (tag, failed_checks)."""
    return {"good": None, "invalid": "validation", "ungrounded": ("grounding", ["amounts", "rules"])}[text]


def test_retry_success_on_first_attempt_makes_one_call():
    fake, sleeps = Scripted("good"), Sleeps()
    assert complete_with_retry(fake, "s", "u", classify, 3, sleep=sleeps, rng=lambda: 0.5) == ("good", "fake-model", 1)
    assert fake.calls == 1 and sleeps == []


# FR-010.4: validation failures are retried; success on attempt 2 reports attempts=2.
def test_retry_recovers_after_invalid_output():
    fake = Scripted("invalid", "good")
    assert complete_with_retry(fake, "s", "u", classify, 3, sleep=Sleeps(), rng=lambda: 0.5) == ("good", "fake-model", 2)


# FR-010.4 AC-3 / AC-4: retries stop after LLM_MAX_ATTEMPTS and end as model_failure; never raises.
@pytest.mark.parametrize("max_attempts", [1, 3, 10])
def test_retry_exhausts_to_model_failure(max_attempts):
    fake = Scripted("invalid")
    result = complete_with_retry(fake, "s", "u", classify, max_attempts, sleep=Sleeps(), rng=lambda: 0.5)
    assert isinstance(result, Failure)
    assert result.attempts == fake.calls == max_attempts
    assert result.last_reason == "model_failure" and result.error == "validation"


# CS-009 backoff min(30, 2**(n-1)) * (0.5 + rng()) between attempts (none after the last).
@pytest.mark.parametrize("rng,expected", [(0.5, [1, 2, 4, 8, 16, 30]), (0.0, [0.5, 1, 2, 4, 8, 15])])
def test_retry_backoff_is_exponential_capped_and_jittered(rng, expected):
    sleeps = Sleeps()
    complete_with_retry(Scripted("invalid"), "s", "u", classify, 7, sleep=sleeps, rng=lambda: rng)
    assert sleeps == pytest.approx(expected)


# FR-011.2 AC-5: ungrounded output on every attempt -> exactly max attempts, grounding_failure + check names.
def test_retry_exhausts_to_grounding_failure_with_checks():
    fake = Scripted("ungrounded")
    result = complete_with_retry(fake, "s", "u", classify, 3, sleep=Sleeps(), rng=lambda: 0.5)
    assert isinstance(result, Failure) and result.attempts == fake.calls == 3
    assert result.last_reason == "grounding_failure" and result.failed_checks == ["amounts", "rules"]


# FR-010.4 AC-5 / FR-011.2 AC-7: the LAST attempt decides the reason.
@pytest.mark.parametrize("script,reason", [(("ungrounded", "invalid"), "model_failure"),
                                           (("invalid", "ungrounded"), "grounding_failure")])
def test_retry_last_reason_follows_last_attempt(script, reason):
    result = complete_with_retry(Scripted(*script), "s", "u", classify, 2, sleep=Sleeps(), rng=lambda: 0.5)
    assert isinstance(result, Failure) and result.last_reason == reason
    assert result.failed_checks == (["amounts", "rules"] if reason == "grounding_failure" else [])


# FR-010.4 AC-1 / NFR-006: a raising backend becomes a sanitized Failure; the message never survives.
def test_retry_sanitizes_backend_exception():
    result = complete_with_retry(Scripted(RuntimeError(PLANTED)), "s", "u", ok, 1, sleep=Sleeps(), rng=lambda: 0.5)
    assert isinstance(result, Failure) and result.last_reason == "model_failure" and result.attempts == 1
    assert result.error == "RuntimeError"
    assert_clean(result, PLANTED, "sk-ant")


# ---------------------------------------------------------------- AnthropicLLM (DI-010; fake client only)

def sdk():
    return pytest.importorskip("anthropic")


class FakeAnthropic:
    instances = []

    def __init__(self, **kwargs):
        self.kwargs, self.calls, self.outcomes = kwargs, [], []
        self.messages = SimpleNamespace(create=self._create)
        FakeAnthropic.instances.append(self)

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        out = self.outcomes[min(len(self.calls) - 1, len(self.outcomes) - 1)] if self.outcomes else reply("x")
        if isinstance(out, BaseException):
            raise out
        return out


def reply(*texts, stop_reason="end_turn", model="claude-returned-model", extra=()):
    blocks = [SimpleNamespace(type="text", text=t) for t in texts]
    return SimpleNamespace(content=list(extra) + blocks, model=model, stop_reason=stop_reason)


@pytest.fixture
def fake_anthropic(monkeypatch):
    FakeAnthropic.instances = []
    monkeypatch.setattr(sdk(), "Anthropic", FakeAnthropic)

    def build(*outcomes, timeout=7.0):
        client_llm = llm.AnthropicLLM(PLANTED, "claude-configured", timeout)
        FakeAnthropic.instances[-1].outcomes = list(outcomes)
        return client_llm, FakeAnthropic.instances[-1]

    return build


# CS-009 / ADR-022: SDK retries off, timeout passed; exact request kwargs, no sampling params, no tools.
def test_anthropic_constructor_and_exact_kwargs(fake_anthropic):
    model, client = fake_anthropic(reply("ab", "cd", extra=[SimpleNamespace(type="thinking", thinking="t")]))
    assert client.kwargs == {"api_key": PLANTED, "max_retries": 0, "timeout": 7.0}
    text, model_id = model.complete("SYS", "USR")
    assert (text, model_id) == ("abcd", "claude-returned-model")  # text blocks only; response.model stored
    assert client.calls == [dict(model="claude-configured", max_tokens=16000, output_config={"effort": "low"},
                                 system="SYS", messages=[{"role": "user", "content": "USR"}])]


# CS-009: non-text or empty content is an error (never a successful empty draft).
def test_anthropic_non_text_content_is_failure(fake_anthropic):
    model, _ = fake_anthropic(reply(extra=[SimpleNamespace(type="tool_use", id="t", name="x", input={})]))
    result = complete_with_retry(model, "s", "u", ok, 1, sleep=Sleeps(), rng=lambda: 0.5)
    assert isinstance(result, Failure) and result.last_reason == "model_failure"


def sdk_error(cls, status=None):
    exc = cls.__new__(cls)
    exc.args = (f"request failed for key {PLANTED}",)
    exc.message = exc.args[0]
    if status is not None:
        exc.status_code = status
    return exc


# DI-010: 429, 5xx, timeout, connection errors are retried up to max attempts.
@pytest.mark.parametrize("cls,status", [("RateLimitError", 429), ("InternalServerError", 500),
                                        ("APITimeoutError", None), ("APIConnectionError", None)])
def test_anthropic_retryable_errors(fake_anthropic, cls, status):
    model, client = fake_anthropic(sdk_error(getattr(sdk(), cls), status))
    result = complete_with_retry(model, "s", "u", ok, 3, sleep=Sleeps(), rng=lambda: 0.5)
    assert isinstance(result, Failure) and result.attempts == len(client.calls) == 3
    assert result.last_reason == "model_failure"
    assert result.error.startswith(cls) or (status and result.error.endswith(f":{status}"))
    assert_clean(result, PLANTED, "sk-ant")


# DI-010: other 4xx are non-retryable: one attempt only.
@pytest.mark.parametrize("cls,status", [("BadRequestError", 400), ("AuthenticationError", 401),
                                        ("NotFoundError", 404)])
def test_anthropic_non_retryable_errors(fake_anthropic, cls, status):
    model, client = fake_anthropic(sdk_error(getattr(sdk(), cls), status))
    result = complete_with_retry(model, "s", "u", ok, 3, sleep=Sleeps(), rng=lambda: 0.5)
    assert isinstance(result, Failure) and result.attempts == len(client.calls) == 1
    assert result.last_reason == "model_failure" and result.error.endswith(f":{status}")
    assert_clean(result, PLANTED, "sk-ant")


# CS-009: stop_reason refusal / max_tokens is non-retryable model_failure.
@pytest.mark.parametrize("stop", ["refusal", "max_tokens"])
def test_anthropic_stop_reasons_are_non_retryable(fake_anthropic, stop):
    model, client = fake_anthropic(reply("partial", stop_reason=stop))
    result = complete_with_retry(model, "s", "u", ok, 3, sleep=Sleeps(), rng=lambda: 0.5)
    assert isinstance(result, Failure) and result.attempts == len(client.calls) == 1
    assert result.last_reason == "model_failure"


# ---------------------------------------------------------------- LocalLLM (DI-011, FR-010.5)

EXPECTED_BODY = {"model": "local-test-model", "stream": False, "format": "json",
                 "messages": [{"role": "system", "content": "SYS"}, {"role": "user", "content": "USR"}],
                 "options": {"temperature": 0, "num_predict": 4096}}


def local(url, timeout=5):
    return LocalLLM(url, "local-test-model", timeout)


def retry(model, max_attempts=3, validate=ok):
    return complete_with_retry(model, "SYS", "USR", validate, max_attempts, sleep=Sleeps(), rng=lambda: 0.5)


# DI-011: exact POST /api/chat body, JSON content type, no auth header (B16).
@pytest.mark.parametrize("suffix", ["", "/"])
def test_local_request_shape(fake_server, suffix):
    server = fake_server(lambda req: chat_reply("{}"))
    local(server.url + suffix).complete("SYS", "USR")
    req, = server.requests
    assert req["method"] == "POST" and req["path"] == "/api/chat"
    assert json.loads(req["body"]) == EXPECTED_BODY
    assert req["headers"]["content-type"] == "application/json"
    assert "authorization" not in req["headers"] and "x-api-key" not in req["headers"]


# FR-010.5 AC-3: model id is the configured LLM_MODEL, the server's echo is ignored.
def test_local_returns_content_and_configured_model(fake_server):
    server = fake_server(lambda req: chat_reply('{"summary": "x"}', model="some-other-model:latest"))
    assert local(server.url).complete("SYS", "USR") == ('{"summary": "x"}', "local-test-model")


# CS-009: 429 and 5xx are retried until max attempts (FR-010.4 AC-3).
@pytest.mark.parametrize("status", [429, 500, 503])
def test_local_retryable_status(fake_server, status):
    server = fake_server(lambda req: (status, {}, "busy"))
    result = retry(local(server.url))
    assert isinstance(result, Failure) and result.attempts == len(server.requests) == 3
    assert result.last_reason == "model_failure" and result.error == f"HTTPError:{status}"


# CS-009: other 4xx stop after one attempt (404 = model not present).
@pytest.mark.parametrize("status", [400, 401, 403, 404, 422])
def test_local_non_retryable_status(fake_server, status):
    server = fake_server(lambda req: (status, {}, "nope"))
    result = retry(local(server.url))
    assert isinstance(result, Failure) and result.attempts == len(server.requests) == 1
    assert result.last_reason == "model_failure" and result.error == f"HTTPError:{status}"


# CS-009 / B16 security: a 3xx is never followed (cannot steer evidence elsewhere) and is non-retryable.
@pytest.mark.parametrize("status", [301, 302, 307, 308])
def test_local_redirect_not_followed(fake_server, status):
    target = fake_server(lambda req: chat_reply("{}"))
    server = fake_server(lambda req: (status, {"Location": target.url + "/api/chat"}, ""))
    result = retry(local(server.url))
    assert isinstance(result, Failure) and result.attempts == 1 and result.last_reason == "model_failure"
    assert target.requests == []


# FR-010.5 AC-4: a refused port is retryable and exhausts to model_failure with attempts == max.
def test_local_refused_port_exhausts():
    port = free_port()
    result = retry(local(f"http://127.0.0.1:{port}"), max_attempts=3)
    assert isinstance(result, Failure) and result.attempts == 3 and result.last_reason == "model_failure"
    assert_clean(result, str(port), "127.0.0.1")


# FR-010.4 AC-2: a hanging server is aborted at the timeout; each timeout is a retryable attempt.
def test_local_hanging_call_aborted_at_timeout(fake_server):
    release = threading.Event()

    def hang(req):
        release.wait(10)
        return chat_reply("{}")

    server = fake_server(hang)
    try:
        started = time.monotonic()
        result = retry(LocalLLM(server.url, "local-test-model", 0.3), max_attempts=2)
        elapsed = time.monotonic() - started
    finally:
        release.set()
    assert isinstance(result, Failure) and result.attempts == 2 and result.last_reason == "model_failure"
    assert len(server.requests) == 2 and elapsed < 3


# CS-009 v1.2: a 200 carrying an error, a non-JSON body or bad message.content is a retryable validation failure.
@pytest.mark.parametrize("body", [
    {"error": "model runner crashed"},
    "<html>not json</html>",
    {"model": "m", "done": True},
    {"model": "m", "message": {"role": "assistant", "content": ""}, "done": True},
    {"model": "m", "message": {"role": "assistant", "content": None}, "done": True},
    {"model": "m", "message": {"role": "assistant", "content": 42}, "done": True},
    {"model": "m", "message": {"role": "assistant", "content": "{}"}, "done": True, "error": "partial"},
])
def test_local_bad_200_is_retryable_validation(fake_server, body):
    server = fake_server(lambda req: (200, {"Content-Type": "application/json"}, body))
    result = retry(local(server.url), max_attempts=2)
    assert isinstance(result, Failure) and result.attempts == len(server.requests) == 2
    assert result.error == "validation" and result.last_reason == "model_failure"


# DI-011 / LLM10: done_reason "length" (output cap hit) is non-retryable model_failure.
def test_local_done_reason_length_is_non_retryable(fake_server):
    server = fake_server(lambda req: chat_reply('{"summary": "trunc', done_reason="length"))
    result = retry(local(server.url))
    assert isinstance(result, Failure) and result.attempts == len(server.requests) == 1
    assert result.last_reason == "model_failure"


# B16 security: proxy env vars cannot reroute the call (ProxyHandler({})).
def test_local_ignores_proxy_env(fake_server, monkeypatch):
    dead_proxy = f"http://127.0.0.1:{free_port()}"
    for name in ("HTTP_PROXY", "http_proxy", "HTTPS_PROXY", "https_proxy", "ALL_PROXY", "all_proxy"):
        monkeypatch.setenv(name, dead_proxy)
    for name in ("NO_PROXY", "no_proxy"):
        monkeypatch.delenv(name, raising=False)
    server = fake_server(lambda req: chat_reply("{}"))
    assert local(server.url).complete("SYS", "USR") == ("{}", "local-test-model")
    assert len(server.requests) == 1


# CS-009 / NFR-006 security: errors carry neither the URL nor the response text, and are not chained.
@pytest.mark.parametrize("status,body", [(500, "LEAKED-RESPONSE-TEXT"), (404, "LEAKED-RESPONSE-TEXT"),
                                         (200, "LEAKED-RESPONSE-TEXT not json")])
def test_local_errors_are_sanitized(fake_server, status, body):
    server = fake_server(lambda req: (status, {}, body))
    result = retry(local(server.url), max_attempts=1)
    assert isinstance(result, Failure)
    port = server.url.rsplit(":", 1)[1]
    assert_clean(result, "LEAKED", server.url, port)
    with pytest.raises(Exception) as exc:
        local(server.url).complete("SYS", "USR")
    text = str(exc.value) + repr(exc.value)
    assert "LEAKED" not in text and server.url not in text and port not in text
    assert exc.value.__cause__ is None and (exc.value.__suppress_context__ or exc.value.__context__ is None)


# FR-010.4 AC-5 / FR-011.2 AC-7 with a real model error on LocalLLM: the last attempt decides.
@pytest.mark.parametrize("order,reason", [(("ungrounded", 500), "model_failure"),
                                          ((500, "ungrounded"), "grounding_failure")])
def test_local_last_reason_ordering(fake_server, order, reason):
    def responder(req):
        step = order[min(len(server.requests) - 1, len(order) - 1)]
        return (step, {}, "err") if isinstance(step, int) else chat_reply(step)

    server = fake_server(responder)
    result = retry(local(server.url), max_attempts=2, validate=classify)
    assert isinstance(result, Failure) and result.attempts == 2 and result.last_reason == reason


# ---------------------------------------------------------------- params() per backend (CS-009 v1.2)

def test_params_per_backend(fake_anthropic):
    assert StubLLM().params() == {}
    assert local("http://127.0.0.1:9").params() == {"temperature": 0, "format": "json", "num_predict": 4096}
    model, _ = fake_anthropic(reply("x"))
    assert model.params() == {"max_tokens": 16000, "effort": "low"}
