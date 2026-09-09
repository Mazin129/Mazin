"""Tests for the Web Research primitives — the safety-critical, network-free parts:
URL/SSRF guarding, HTML→text, DuckDuckGo parsing, and the guardrail opt-in. No real
network calls: socket resolution and _open are monkeypatched."""
import os
import socket

import websearch
from agents import Guardrail, WebResearchAgent, READ, NETWORK, WRITE, Result


def _ok(label, cond):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}")
    assert cond, label


def _fake_resolve(mapping):
    def _gai(host, *a, **k):
        ip = mapping.get(host, "93.184.216.34")           # default: a genuinely public ip
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 0))]
    return _gai


def test_url_safety(monkeypatch):
    print("\n  URL / SSRF safety")
    monkeypatch.setenv("VIO_ALLOW_NET", "1")
    monkeypatch.setattr(socket, "getaddrinfo",
                        _fake_resolve({"evil.internal": "10.0.0.5",
                                       "loop.test": "127.0.0.1",
                                       "good.example": "93.184.216.34"}))
    # scheme guard
    try:
        websearch.check_url("file:///etc/passwd"); _ok("file:// refused", False)
    except websearch.NetError:
        _ok("file:// refused", True)
    # SSRF: private + loopback
    for host in ("http://evil.internal/x", "http://loop.test/y"):
        try:
            websearch.check_url(host); _ok(f"{host} refused", False)
        except websearch.NetError:
            _ok(f"{host} refused", True)
    # public host allowed
    _ok("public host allowed", websearch.check_url("https://good.example/p").hostname
        == "good.example")


def test_allow_block(monkeypatch):
    print("\n  allow / block lists")
    monkeypatch.setenv("VIO_ALLOW_NET", "1")
    monkeypatch.setattr(socket, "getaddrinfo", _fake_resolve({}))
    monkeypatch.setenv("VIO_NET_BLOCK", "bad.com")
    try:
        websearch.check_url("https://bad.com/x"); _ok("blocklist refuses", False)
    except websearch.NetError:
        _ok("blocklist refuses", True)
    monkeypatch.delenv("VIO_NET_BLOCK", raising=False)
    monkeypatch.setenv("VIO_NET_ALLOW", "trusted.org")
    try:
        websearch.check_url("https://other.org/x"); _ok("allowlist refuses others", False)
    except websearch.NetError:
        _ok("allowlist refuses others", True)
    _ok("allowlist permits listed", websearch.check_url("https://docs.trusted.org/x")
        .hostname == "docs.trusted.org")
    # the fixed search engine bypasses the allow-list but not SSRF
    _ok("engine bypasses allowlist",
        websearch.check_url("https://html.duckduckgo.com/html/", engine=True) is not None)


def test_html_to_text():
    print("\n  HTML → text")
    html = ("<html><head><title>T</title><style>x{}</style></head><body>"
            "<script>evil()</script><h1>Hi</h1><p>one</p><p>two &amp; three</p></body>")
    txt = websearch.html_to_text(html)
    _ok("scripts/styles stripped", "evil" not in txt and "x{}" not in txt)
    _ok("entities unescaped", "two & three" in txt)
    _ok("text kept", "Hi" in txt and "one" in txt)


def test_ddg_parse(monkeypatch):
    print("\n  DuckDuckGo parsing")
    monkeypatch.setenv("VIO_ALLOW_NET", "1")
    monkeypatch.setattr(socket, "getaddrinfo", _fake_resolve({}))
    monkeypatch.delenv("VIO_NET_ALLOW", raising=False)
    monkeypatch.delenv("VIO_NET_BLOCK", raising=False)
    page = (
        '<a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com'
        '%2Fpage&rut=x">Example <b>Page</b></a>'
        '<a class="result__a" href="https://direct.example/post">Direct</a>')
    res = websearch.parse_ddg(page, k=5)
    _ok("two results parsed", len(res) == 2)
    _ok("uddg redirect decoded", res[0]["url"] == "https://example.com/page")
    _ok("title cleaned", res[0]["title"] == "Example Page")
    _ok("direct link kept", res[1]["url"] == "https://direct.example/post")


def test_disabled_by_default(monkeypatch):
    print("\n  off by default")
    monkeypatch.delenv("VIO_ALLOW_NET", raising=False)
    _ok("net_enabled False without opt-in", websearch.net_enabled() is False)
    try:
        websearch.search("anything"); _ok("search refuses when off", False)
    except websearch.NetError:
        _ok("search refuses when off", True)


def test_guardrail_optin(monkeypatch):
    print("\n  guardrail opt-in")
    g = Guardrail()

    class NetAgent:
        name = "research"
        permissions = frozenset({READ, NETWORK})

    class WriteAgent:
        name = "writer"
        permissions = frozenset({READ, WRITE})

    monkeypatch.setenv("VIO_ALLOW_NET", "1")
    r = g.check("q", NetAgent(), Result("ans", how="web research"), {})
    _ok("net passes when opted in", "confirm" not in r.answer.lower())

    monkeypatch.delenv("VIO_ALLOW_NET", raising=False)
    r = g.check("q", NetAgent(), Result("ans", how="web research"), {})
    _ok("net gated when not opted in", "confirm" in r.answer.lower())

    monkeypatch.setenv("VIO_ALLOW_NET", "1")
    r = g.check("q", WriteAgent(), Result("ans", how="write"), {})
    _ok("write still gates even with net on", "confirm" in r.answer.lower())


def test_agent_scoring(monkeypatch):
    print("\n  WebResearchAgent scoring")

    class FakeMind:
        import re as _re
        _RESEARCH_RE = __import__("reasoner").Mind._RESEARCH_RE

        def _research_request(self, q):
            m = self._RESEARCH_RE.match(q or "")
            return (m.group(1).strip() if m else "") or None

    a = WebResearchAgent(FakeMind())
    monkeypatch.setenv("VIO_ALLOW_NET", "1")
    _ok("fires on 'research: X'", a.score("research: BGP route flaps", {}) == 0.9)
    _ok("fires on 'look up X'", a.score("look up mTLS strict mode", {}) == 0.9)
    _ok("ignores normal question", a.score("what is a firewall?", {}) == 0.0)
    monkeypatch.delenv("VIO_ALLOW_NET", raising=False)
    _ok("abstains when net off", a.score("research: anything", {}) == 0.0)


if __name__ == "__main__":
    import types

    class _MP:
        """Tiny monkeypatch shim so this runs with plain `python test_websearch.py`."""
        def __init__(self):
            self._env, self._attr = [], []

        def setenv(self, k, v):
            self._env.append((k, os.environ.get(k)))
            os.environ[k] = v

        def delenv(self, k, raising=False):
            self._env.append((k, os.environ.get(k)))
            os.environ.pop(k, None)

        def setattr(self, obj, name, val):
            self._attr.append((obj, name, getattr(obj, name)))
            setattr(obj, name, val)

        def undo(self):
            for k, v in reversed(self._env):
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
            for obj, name, v in reversed(self._attr):
                setattr(obj, name, v)
            self._env, self._attr = [], []

    tests = [test_url_safety, test_allow_block, test_html_to_text, test_ddg_parse,
             test_disabled_by_default, test_guardrail_optin, test_agent_scoring]
    print("=" * 60 + "\n  WEB RESEARCH TESTS")
    for t in tests:
        mp = _MP()
        try:
            (t(mp) if t.__code__.co_argcount == 1 else t())
        finally:
            mp.undo()
    print("\nALL PASS")
