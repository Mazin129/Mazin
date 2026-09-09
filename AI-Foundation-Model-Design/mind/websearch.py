"""
websearch — networked research primitives for Vio's Web Research agent.

OFF BY DEFAULT. Set VIO_ALLOW_NET=1 to enable. Everything here is READ-ONLY
against the public web: a keyless search (DuckDuckGo HTML) plus fetch-a-page
and extract-readable-text. It is deliberately hardened, because giving a local
assistant internet access is a real capability:

  * SSRF guard — a host that resolves to a private / loopback / link-local /
    reserved address is refused, so an agent can never be steered into poking
    the user's own LAN or cloud metadata endpoints.
  * scheme guard — only http/https; no file://, ftp://, etc.
  * allow / block lists — VIO_NET_ALLOW (restrict fetches to these domains) and
    VIO_NET_BLOCK (always refuse these). Block wins.
  * bounded — per-page byte cap and request timeout.
  * redirects are re-validated (a safe URL can 302 to a private one).

Fetched text is DATA, never instructions: callers pass it to the LLM as
retrieved context, not as a system/user directive.
"""
from __future__ import annotations

import html
import ipaddress
import os
import re
import socket
import urllib.error
import urllib.parse
import urllib.request

UA = ("Mozilla/5.0 (compatible; VioResearch/1.0; +local assistant) "
      "AppleWebKit/537.36")
_TRUE = {"1", "true", "yes", "on"}


def net_enabled() -> bool:
    """Master switch — the user must opt in with VIO_ALLOW_NET=1."""
    return os.environ.get("VIO_ALLOW_NET", "").strip().lower() in _TRUE


def _int_env(name, default):
    try:
        return int(os.environ.get(name, "") or default)
    except ValueError:
        return default


def _max_bytes():
    return _int_env("VIO_NET_MAX_BYTES", 2_000_000)        # 2 MB / page


def _timeout():
    return _int_env("VIO_NET_TIMEOUT", 15)


def _domain_set(name):
    return {d.strip().lower() for d in os.environ.get(name, "").split(",") if d.strip()}


class NetError(Exception):
    """A request was refused by policy or failed — always surfaced, never silent."""


# --------------------------------------------------------------------------- #
# URL safety
# --------------------------------------------------------------------------- #
def _host_allowed(host, engine=False):
    h = (host or "").lower()
    block = _domain_set("VIO_NET_BLOCK")
    if any(h == b or h.endswith("." + b) for b in block):
        return False
    if engine:                       # the fixed search engine bypasses the allow-list
        return True
    allow = _domain_set("VIO_NET_ALLOW")
    if allow and not any(h == a or h.endswith("." + a) for a in allow):
        return False
    return True


def _assert_public(host):
    """Resolve host and refuse any non-public address (SSRF guard)."""
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        raise NetError(f"could not resolve host: {host}")
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved
                or ip.is_multicast or ip.is_unspecified):
            raise NetError(f"refusing non-public address for {host} ({ip})")


def check_url(url, engine=False):
    p = urllib.parse.urlparse(url)
    if p.scheme not in ("http", "https"):
        raise NetError("only http/https URLs are allowed")
    if not p.hostname:
        raise NetError("URL has no host")
    if not _host_allowed(p.hostname, engine=engine):
        raise NetError(f"host not allowed by policy: {p.hostname}")
    _assert_public(p.hostname)
    return p


# --------------------------------------------------------------------------- #
# HTTP (stdlib only)
# --------------------------------------------------------------------------- #
def _open(url, data=None, engine=False):
    if not net_enabled():
        raise NetError("internet access is off (set VIO_ALLOW_NET=1 to enable)")
    check_url(url, engine=engine)
    req = urllib.request.Request(
        url, data=data,
        headers={"User-Agent": UA, "Accept": "text/html,*/*", "Accept-Language": "en"})
    try:
        with urllib.request.urlopen(req, timeout=_timeout()) as r:
            final = r.geturl()
            if final != url:                   # a 30x may have moved us somewhere unsafe
                check_url(final, engine=engine)
            cap = _max_bytes()
            raw = r.read(cap + 1)
    except NetError:
        raise
    except (urllib.error.URLError, OSError, ValueError) as e:
        # surface every network failure as a NetError so callers never crash on it
        raise NetError(f"request to {url} failed: {e}")
    return raw[:cap]


# --------------------------------------------------------------------------- #
# HTML → readable text
# --------------------------------------------------------------------------- #
def html_to_text(markup: str) -> str:
    t = re.sub(r"(?is)<(script|style|noscript|template|svg)\b.*?</\1>", " ", markup)
    t = re.sub(r"(?is)<head\b.*?</head>", " ", t)
    t = re.sub(r"(?s)<!--.*?-->", " ", t)
    t = re.sub(r"(?i)<(br|/p|/div|/li|/h[1-6]|/tr|/table)\s*/?>", "\n", t)
    t = re.sub(r"(?s)<[^>]+>", " ", t)
    t = html.unescape(t)
    t = re.sub(r"[ \t\f\v]+", " ", t)
    t = re.sub(r"\n[ \t]+", "\n", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def fetch(url: str) -> dict:
    """Fetch one page → {url, title, text}. Raises NetError on any refusal/failure."""
    raw = _open(url)
    markup = raw.decode("utf-8", "replace")
    m = re.search(r"(?is)<title[^>]*>(.*?)</title>", markup)
    title = html.unescape(re.sub(r"\s+", " ", m.group(1)).strip()) if m else url
    return {"url": url, "title": title or url, "text": html_to_text(markup)}


def _ddg_unwrap(href: str) -> str:
    if href.startswith("//"):
        href = "https:" + href
    p = urllib.parse.urlparse(href)
    if "duckduckgo.com" in (p.hostname or "") and p.path.startswith("/l/"):
        qs = urllib.parse.parse_qs(p.query)
        if qs.get("uddg"):
            return urllib.parse.unquote(qs["uddg"][0])
    return href


def parse_ddg(markup: str, k: int) -> list:
    """Extract result links from a DuckDuckGo HTML page. Pure — unit-testable."""
    out, seen = [], set()
    for m in re.finditer(
            r'(?is)<a\b[^>]*class="[^"]*\bresult__a\b[^"]*"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
            markup):
        url = _ddg_unwrap(html.unescape(m.group(1)))
        title = html_to_text(m.group(2))
        if not url or url in seen:
            continue
        try:
            check_url(url)                     # drop unsafe / disallowed results early
        except NetError:
            continue
        seen.add(url)
        out.append({"url": url, "title": title or url})
        if len(out) >= k:
            break
    return out


def parse_bing(markup: str, k: int) -> list:
    """Extract result links from a Bing SERP. Pure — unit-testable."""
    out, seen = [], set()
    for m in re.finditer(r'(?is)<li[^>]*class="[^"]*\bb_algo\b[^"]*"[^>]*>.*?'
                         r'<h2[^>]*>\s*<a\b[^>]*href="([^"]+)"[^>]*>(.*?)</a>', markup):
        url, title = html.unescape(m.group(1)), html_to_text(m.group(2))
        if not url.lower().startswith(("http://", "https://")) or url in seen:
            continue
        try:
            check_url(url)
        except NetError:
            continue
        seen.add(url)
        out.append({"url": url, "title": title or url})
        if len(out) >= k:
            break
    return out


def _generic_links(markup: str, k: int, skip_hosts=()) -> list:
    """Last-resort: pull external result links out of any SERP HTML."""
    out, seen = [], set()
    junk = ("duckduckgo.com", "bing.com", "microsoft.com", "msn.com", "go.microsoft",
            "google.com", "javascript:", "mailto:") + tuple(skip_hosts)
    for m in re.finditer(r'(?is)<a\b[^>]*href="(https?://[^"]+)"[^>]*>(.*?)</a>', markup):
        url = html.unescape(m.group(1))
        low = url.lower()
        if url in seen or any(j in low for j in junk):
            continue
        title = html_to_text(m.group(2))
        if len(title) < 3:
            continue
        try:
            check_url(url)
        except NetError:
            continue
        seen.add(url)
        out.append({"url": url, "title": title or url})
        if len(out) >= k:
            break
    return out


# search backends, tried in order until one returns results. Each is (name, fn).
def _src_ddg(query, k):
    data = urllib.parse.urlencode({"q": query, "kl": "us-en"}).encode()
    m = _open("https://html.duckduckgo.com/html/", data=data, engine=True).decode("utf-8", "replace")
    return parse_ddg(m, k)


def _src_bing(query, k):
    u = "https://www.bing.com/search?" + urllib.parse.urlencode({"q": query, "setlang": "en"})
    m = _open(u, engine=True).decode("utf-8", "replace")
    return parse_bing(m, k) or _generic_links(m, k)


def _src_ddg_lite(query, k):
    data = urllib.parse.urlencode({"q": query}).encode()
    m = _open("https://lite.duckduckgo.com/lite/", data=data, engine=True).decode("utf-8", "replace")
    return _generic_links(m, k)


_SOURCES = (("duckduckgo", _src_ddg), ("bing", _src_bing), ("duckduckgo-lite", _src_ddg_lite))


def search(query: str, k: int = 5) -> list:
    """Keyless web search → [{url, title}]. Tries several engines so a single blocked
    source doesn't break research. Raises NetError only if ALL sources fail."""
    if not net_enabled():
        raise NetError("internet access is off (set VIO_ALLOW_NET=1 to enable)")
    errors = []
    for name, fn in _SOURCES:
        try:
            res = fn(query, k)
        except Exception as e:                 # any source may fail; try the next one
            errors.append(f"{name}: {e}")
            continue
        if res:
            return res
    if errors:
        raise NetError("all search sources failed — " + " | ".join(errors))
    return []
