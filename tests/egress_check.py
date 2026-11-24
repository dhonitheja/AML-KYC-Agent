"""Egress probe run inside a container (PLAN-002 T6; NFR-008 AC-1, AC-6, AC-8). Not collected by pytest.

  python tests/egress_check.py --deny api.anthropic.com:443 --allow postgres:5432

--deny must fail to connect (DNS failure, unreachable, refused or timeout all count as blocked);
--allow must connect (positive control: proves the probe ran on a working network). No data is sent."""
import argparse
import socket
import sys


def target(value):
    host, _, port = value.rpartition(":")
    if not host or not port.isdigit():
        raise argparse.ArgumentTypeError(f"expected host:port, got {value!r}")
    return host, int(port)


def reachable(host, port):
    try:
        socket.create_connection((host, port), timeout=3).close()
        return True
    except OSError:
        return False


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--deny", action="append", type=target, default=[])
    parser.add_argument("--allow", action="append", type=target, default=[])
    args = parser.parse_args(argv)
    if not args.deny and not args.allow:
        parser.error("give at least one --deny or --allow")
    ok = True
    for (host, port), want in [(t, False) for t in args.deny] + [(t, True) for t in args.allow]:
        got = reachable(host, port)
        print(f"{'reachable' if got else 'blocked'} {host}:{port}" + ("" if got == want else
              (" LEAK" if got else " UNREACHABLE (allow expected)")))
        ok &= got == want
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
