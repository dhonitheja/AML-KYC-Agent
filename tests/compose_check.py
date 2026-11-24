"""Static Compose topology check (PLAN-002 T7; NFR-008 AC-2, AC-7, AC-8 network half; ADR-028/029/030).
Host-side CI tool, not collected by pytest. Reads `docker compose ... config --format json` on stdin:

  docker compose --profile fetch --profile local config --format json | python tests/compose_check.py base
  docker compose -f compose.yaml -f compose.anthropic.yaml --profile fetch --profile local config --format json \
      | python tests/compose_check.py anthropic

Exits 1 at the first failure with a precise message."""
import json
import os
import sys

ALLOWED_NETWORKS = {"internal", "ingress", "egress"}
INTERNAL_ONLY = {"kafka", "topic", "postgres", "redis", "migrate", "scorer", "ingest", "llm"}
EXPECTED_SERVICES = INTERNAL_ONLY | {"investigator", "api", "watchlist-fetch"}


def fail(msg):
    print(f"compose_check FAIL: {msg}")
    sys.exit(1)


def check(cond, msg):
    if not cond:
        fail(msg)


def nets(svc):
    return set(svc.get("networks") or {"default": None})


def secret_names(svc):
    return {s["source"] if isinstance(s, dict) else s for s in svc.get("secrets") or []}


def watchlist_mount(svc):
    return [v for v in svc.get("volumes") or [] if isinstance(v, dict) and v.get("target") == "/app/watchlists"]


def main(argv):
    if len(argv) != 2 or argv[1] not in ("base", "anthropic"):
        fail("usage: compose_check.py base|anthropic  (compose config JSON on stdin)")
    variant = argv[1]
    cfg = json.load(sys.stdin)
    services, networks = cfg.get("services") or {}, cfg.get("networks") or {}

    check(set(services) == EXPECTED_SERVICES,
          f"services {sorted(services)} != expected {sorted(EXPECTED_SERVICES)} "
          "(render with --profile fetch --profile local; add new services to compose_check)")
    check(set(networks) == ALLOWED_NETWORKS, f"top-level networks {sorted(networks)} != {sorted(ALLOWED_NETWORKS)}")
    check((networks["internal"] or {}).get("internal") is True, "networks.internal must set internal: true")
    for name in ("ingress", "egress"):
        check(not (networks[name] or {}).get("internal"), f"networks.{name} must not be internal")

    for name, svc in services.items():
        n = nets(svc)
        check("default" not in n, f"{name} is attached to the default network (declare networks: explicitly)")
        check(n <= ALLOWED_NETWORKS, f"{name} is on unexpected networks {sorted(n - ALLOWED_NETWORKS)}")
        if name != "api":
            check(not svc.get("ports"), f"{name} publishes host ports {svc.get('ports')}; only api may")
    for name in INTERNAL_ONLY:
        check(nets(services[name]) == {"internal"}, f"{name} networks {sorted(nets(services[name]))} != ['internal']")

    inv = services["investigator"]
    want = {"internal"} if variant == "base" else {"internal", "egress"}
    check(nets(inv) == want, f"investigator networks {sorted(nets(inv))} != {sorted(want)} ({variant})")
    env = inv.get("environment") or {}
    check((inv.get("build") or {}).get("target") == "investigator", "investigator requires its dedicated image")
    check(env.get("INVESTIGATOR_EGRESS") == ("enabled" if variant == "anthropic" else None),
          "investigator egress guard must match the network variant")
    for var in ("LLM_MODEL", "DATA_CLASSIFICATION"):
        check(not env.get(var), f"investigator {var} must have no compose default, got {env.get(var)!r}")
    has_key = "anthropic_api_key" in secret_names(inv)
    check(has_key == (variant == "anthropic"),
          f"investigator anthropic_api_key secret {'missing' if not has_key else 'present'} in {variant} variant")

    api = services["api"]
    check(nets(api) == {"internal", "ingress"}, f"api networks {sorted(nets(api))} != ['ingress', 'internal']")
    ports = api.get("ports") or []
    check(ports, "api must publish its loopback port")
    for p in ports:
        host_ip = p.get("host_ip") if isinstance(p, dict) else None
        check(host_ip == "127.0.0.1", f"api port {p} must bind host_ip 127.0.0.1")

    fetch = services["watchlist-fetch"]
    check(nets(fetch) == {"egress"}, f"watchlist-fetch networks {sorted(nets(fetch))} != ['egress']")
    check(fetch.get("profiles") == ["fetch"], f"watchlist-fetch profiles {fetch.get('profiles')} != ['fetch']")
    check(not fetch.get("secrets"), "watchlist-fetch must have no secrets")
    vols = fetch.get("volumes") or []
    check(len(vols) == 1 and vols[0].get("type") == "bind" and vols[0].get("target") == "/app/watchlists",
          f"watchlist-fetch must have exactly one bind mount at /app/watchlists, got {vols}")

    llm = services["llm"]
    check(llm.get("profiles") == ["local"], f"llm profiles {llm.get('profiles')} != ['local']")
    for key in ("ports", "secrets", "volumes"):
        check(not llm.get(key), f"llm must have no {key}, got {llm.get(key)}")
    build = llm.get("build") or {}
    dockerfile = os.path.join(build.get("context") or ".", build.get("dockerfile") or "Dockerfile")
    try:
        with open(dockerfile, encoding="utf-8") as f:
            froms = [ln for ln in f if ln.strip().upper().startswith("FROM ")]
    except OSError:
        fail(f"cannot read llm Dockerfile {dockerfile}")
    check(froms and all("@sha256:" in ln for ln in froms), f"{dockerfile} FROM must be pinned @sha256:<digest>")

    for name in ("api", "scorer"):
        mount = watchlist_mount(services[name])
        check(len(mount) == 1 and mount[0].get("read_only") is True, f"{name} must mount ./watchlists read_only")

    print(f"compose_check OK ({variant}): {len(services)} services, networks per ARCH-001 section 1a")


if __name__ == "__main__":
    main(sys.argv)
