"""Pure AST scan (PLAN-002 T8; NFR-008 AC-5, ARCH-001 B18 / RR-23): data modules make no outbound calls,
and watchlist.py only GETs the public OFAC list without touching DB/Kafka/Redis modules."""
import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
NETWORK = {"urllib", "requests", "httpx", "socket", "http", "aiohttp", "anthropic", "ssl", "ftplib", "smtplib"}
DATA_STORES = {"psycopg", "pipeline", "redis", "confluent_kafka", "kyc", "scoring"}


def tree(name):
    return ast.parse((ROOT / name).read_text(encoding="utf-8"), filename=name)


def imported(t):
    """Top-level module of every import, including function-local ones."""
    mods = set()
    for node in ast.walk(t):
        if isinstance(node, ast.Import):
            mods |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            mods.add(node.module.split(".")[0])
    return mods


def calls(t, name):
    return [n for n in ast.walk(t) if isinstance(n, ast.Call) and
            (getattr(n.func, "attr", None) == name or getattr(n.func, "id", None) == name)]


# NFR-008 AC-5: api/pipeline/scoring/kyc/rules import no network module (llm.py is the permitted one, ADR-029).
@pytest.mark.parametrize("name", ["api.py", "pipeline.py", "scoring.py", "kyc.py", "rules.py"])
def test_data_modules_import_no_network_module(name):
    assert imported(tree(name)) & NETWORK == set()


# NFR-008 AC-5 / NFR-008.3(b): watchlist.py imports no database, Kafka or Redis module.
def test_watchlist_imports_no_data_store():
    assert imported(tree("watchlist.py")) & DATA_STORES == set()


# NFR-008 AC-5: watchlist.py issues only HTTP GET: urlopen(url) with no body, and no Request objects.
def test_watchlist_only_gets():
    t = tree("watchlist.py")
    opens = calls(t, "urlopen")
    assert opens, "watchlist.py should fetch with urlopen"
    for c in opens:
        assert len(c.args) == 1 and "data" not in {k.arg for k in c.keywords}
    assert calls(t, "Request") == []


# Scanner self-check: the scan really detects function-local and dotted imports.
def test_scanner_detects_local_imports():
    t = ast.parse("def f():\n    import urllib.request\n    from http import client\n")
    assert imported(t) == {"urllib", "http"}
