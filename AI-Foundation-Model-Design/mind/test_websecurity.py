"""
test_websecurity — pins who may reach Vio, especially through a proxy or tunnel.

A proxy or tunnel connects to Vio FROM localhost, so every request it forwards from the
public internet looks local at the socket level. Vio used to treat "local + no token"
as open, which meant a tunnel published every configuration with no login at all.
These checks pin the fix, and they drive the real handler methods rather than a copy.

Run:  python test_websecurity.py
"""
from __future__ import annotations

import os
import sys
import tempfile

PASS, FAIL = [], []


def check(name, cond):
    (PASS if cond else FAIL).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name}")


class FakeHandler:
    """Just enough of BaseHTTPRequestHandler for the gate methods to run."""

    def __init__(self, headers, path="/"):
        self.headers = {k.lower(): v for k, v in headers.items()}
        self.path = path
        self.sent = None

    class _H(dict):
        def get(self, k, d=None):
            return dict.get(self, k.lower(), d)

    def bind(self, web):
        self.headers = FakeHandler._H(self.headers)
        for name in ("_host_ok", "_proxied", "_authed", "_session",
                     "_refuse_host", "_refuse_no_token"):
            setattr(self, name, getattr(web.H, name).__get__(self))
        self._s = lambda code, body, ctype=None: setattr(self, "sent", (code, body))
        return self


def main():
    os.environ["VIO_DATA_DIR"] = tempfile.mkdtemp(prefix="vio_websec_")
    os.environ.setdefault("VIO_SEMANTIC_ASYNC", "0")
    os.environ.setdefault("VIO_TRAIN_ASYNC", "0")
    os.environ["VIO_NO_BROWSER"] = "1"
    for k in ("VIO_TOKEN", "VIO_ALLOWED_HOSTS"):
        os.environ.pop(k, None)

    print("=" * 72)
    print("  WEB SECURITY — who may reach Vio")
    print("=" * 72)
    import web

    CF = {"Host": "vio.tunnel.example.net", "X-Forwarded-For": "203.0.113.9",
          "X-Forwarded-Proto": "https"}
    LOCAL = {"Host": "localhost"}

    def h(headers, path="/"):
        return FakeHandler(headers, path).bind(web)

    # ---- tunnel detection ---------------------------------------------------
    print("\n-- is the request tunnelled? --")
    check("plain local request is not proxied", h(LOCAL)._proxied() is False)
    check("forwarding headers mark it proxied", h(CF)._proxied() is True)
    check("the --http-host-header localhost trick is still proxied",
          h({"Host": "localhost", "Cf-Ray": "x"})._proxied() is True)
    check("X-Forwarded-For (any reverse proxy) is proxied",
          h({"Host": "localhost", "X-Forwarded-For": "1.2.3.4"})._proxied() is True)

    # ---- with NO token: local open, tunnel closed --------------------------
    print("\n-- no token configured --")
    web.TOKEN = ""
    check("local browser is let in (dev convenience preserved)", h(LOCAL)._authed() is True)
    check("tunnelled request is NOT let in", h(CF)._authed() is False)
    check("tunnelled request with Host: localhost is NOT let in",
          h({"Host": "localhost", "Cf-Ray": "x"})._authed() is False)

    r = h(CF, "/")
    r._refuse_no_token()
    check("the page explains the lock instead of showing a useless login",
          r.sent[0] == 403 and "locked" in r.sent[1])
    r = h(CF, "/api/ask")
    r._refuse_no_token()
    check("the API refusal is JSON with a reason",
          r.sent[0] == 403 and "VIO_TOKEN" in r.sent[1])

    # ---- with a token: everyone must sign in over the tunnel -----------------
    print("\n-- token configured --")
    web.TOKEN = "correct-horse-battery-staple-42"
    web._SESSIONS.clear()
    check("tunnelled request without a session is refused", h(CF)._authed() is False)
    check("a forged session cookie is refused",
          h({**CF, "Cookie": "vio_session=forged"})._authed() is False)
    web._SESSIONS.add("real-session")
    check("a real session is let in",
          h({**CF, "Cookie": "vio_session=real-session"})._authed() is True)
    check("local requests need a session too once a token is set",
          h(LOCAL)._authed() is False)
    web._SESSIONS.clear()

    # ---- host allow-list ---------------------------------------------------
    print("\n-- host allow-list --")
    web.ALLOWED_HOSTS.clear()
    check("localhost always allowed", h(LOCAL)._host_ok() is True)
    check("an unlisted host is refused", h({"Host": "evil.example.com"})._host_ok() is False)
    web.ALLOWED_HOSTS.add(".tunnel.example.net")
    check("a leading-dot entry admits any host in that domain",
          h({"Host": "blue-otter-42.tunnel.example.net"})._host_ok() is True)
    check("the suffix does not admit a look-alike domain",
          h({"Host": "tunnel.example.net.evil.net"})._host_ok() is False)
    check("the suffix does not admit a bare lookalike ending",
          h({"Host": "eviltunnel.example.net"})._host_ok() is False)
    web.ALLOWED_HOSTS.clear()
    web.ALLOWED_HOSTS.add("vio.example.com")
    check("an exact host entry works", h({"Host": "vio.example.com"})._host_ok() is True)
    check("an exact entry does not act as a suffix",
          h({"Host": "x.vio.example.com"})._host_ok() is False)
    web.ALLOWED_HOSTS.clear()

    r = h({"Host": "evil.example.com"})
    r._refuse_host()
    check("a refused host gets a readable reason, not '{}'",
          r.sent[0] == 403 and "VIO_ALLOWED_HOSTS" in r.sent[1])

    print("=" * 72)
    print(f"  {len(PASS)} passed, {len(FAIL)} failed")
    for x in FAIL:
        print(f"    FAILED: {x}")
    print("\nALL PASS" if not FAIL else "\nFAILURES")
    return 1 if FAIL else 0


if __name__ == "__main__":
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    sys.exit(main())
