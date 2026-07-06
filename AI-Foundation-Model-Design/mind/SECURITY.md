# Security audit — Vio (the local reasoning assistant)

Threat model: Vio is a **personal, local** app. It binds only to `127.0.0.1`
(never the network), stores data as local JSON, and makes **no outbound network
calls**. The realistic risks are (a) a crafted input abusing the maths parser, and
(b) a malicious website in your browser reaching the local server. Both are fixed.

## Findings and fixes

| # | Severity | Finding | Fix | Verified |
|---|---|---|---|---|
| 1 | **Critical (RCE)** | `sympy.parse_expr` uses `eval()` internally, so a mathy-looking payload like `1+eval("__import__('os').system(...)")` executed arbitrary code. | Strict **input whitelist** before parsing (`reasoner.py _parse`): reject quotes/underscores/brackets/backslash and any multi-letter name that isn't a known maths function. | Exploits now return "no-source" (never executed); legit maths unaffected. |
| 2 | High | A malicious web page could POST to `http://localhost:8100` (CSRF / DNS-rebinding) and trigger server-side actions. | **Host-header check** (`web.py _host_ok`): accept only `localhost` / `127.0.0.1`. Blocks DNS-rebinding (attacker's domain would appear in `Host`). | Spoofed `Host: evil.com` → **403**. |
| 3 | Medium | No request-size limit → a huge upload could exhaust memory (DoS). | **32 MB body cap** (`MAX_BODY`) → 413 on oversize. | — |
| 4 | Low | Missing hardening headers. | `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`; JSON parse wrapped in try/except. | — |

## What was checked and is clean

- **No `eval`/`exec`/`os.system`/`subprocess`/`pickle`/`__import__`** anywhere in the
  app code (only the interactive `input()` CLI prompt, which is safe).
- **No outbound network** from Vio (`mind/`) — fully offline. (The ML *training*
  scripts in `prototype/` download tiny-shakespeare from one hardcoded GitHub URL;
  that is separate from Vio and not run by it.)
- **File I/O uses fixed paths** in the script directory — no path traversal. Personal
  memory/library (`mind_memory.json`, `knowledge.json`) are git-ignored (private).
- Server bound to `127.0.0.1` only — not reachable from other machines.

## Notes / residual

- No authentication is used — acceptable for a single-user localhost app, and the
  Host check prevents cross-site abuse. If you ever expose it beyond localhost
  (don't, without more work), add auth + HTTPS + CORS controls first.
- Everything Vio tells you is either verified (maths) or retrieved from what you
  taught it — it does not execute anything from documents you upload; they are
  stored as text and only searched.
