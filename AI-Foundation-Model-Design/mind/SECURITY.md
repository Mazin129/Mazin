# Reaching Vio securely from anywhere

Vio's web API can teach, forget, train, and swap its model — so it must **never** sit
unauthenticated on the open internet. This guide gives the secure way.

## TL;DR
1. **Set an access token** so Vio requires a login.
2. **Expose it with Tailscale** (private mesh VPN) — not a port-forward.
3. Never open port 8100 to the internet directly.

---

## 1. Turn on the access token (do this first)

Pick a long random code and set it before starting Vio:

**Windows (cmd):**
```
set VIO_TOKEN=paste-a-long-random-code-here
python web.py
```
**Windows (permanent, all terminals):**
```
setx VIO_TOKEN "paste-a-long-random-code-here"
```
(open a new terminal after `setx`)

Now every visitor gets a **login page** and needs the code. The code is checked in
constant time, brute-force attempts are throttled, and a successful login gets a
`HttpOnly`, `SameSite=Strict` session cookie. Losing the code locks everyone out — keep it safe.

> Generate a strong code:  `python -c "import secrets;print(secrets.token_urlsafe(24))"`

---

## 2. Expose it with Tailscale (recommended — most secure)

Tailscale is a private WireGuard mesh. Vio stays on your machine; only **your own devices**
can reach it, end-to-end encrypted. Nothing is ever on the public internet.

1. Install Tailscale on the **Vio machine** and on your **phone/laptop**: https://tailscale.com/download
   Sign in with the same account on both.
2. On the Vio machine, publish Vio over your tailnet **with automatic HTTPS**:
   ```
   tailscale serve --bg 8100
   ```
   Tailscale prints an address like `https://your-pc.tailXXXX.ts.net`.
3. Tell Vio that hostname is allowed (DNS-rebinding protection), then start it:
   ```
   set VIO_TOKEN=your-code
   set VIO_ALLOWED_HOSTS=your-pc.tailXXXX.ts.net
   set VIO_HTTPS=1
   python web.py
   ```
4. On your phone (Tailscale on), open `https://your-pc.tailXXXX.ts.net`, log in with the code.

That's it: TLS from Tailscale, access limited to your devices, plus Vio's own login. Two locks.

---

## 3. Alternative — Cloudflare Tunnel + Access

Use only if you need access from devices you can't put on Tailscale, or to share.
`cloudflared tunnel` exposes Vio through Cloudflare (no open ports), and **Cloudflare Access**
adds an identity login in front. Still set `VIO_TOKEN` and `VIO_ALLOWED_HOSTS=<your.tunnel.host>`
underneath. Tradeoff: traffic transits Cloudflare.

---

## Environment variables

| Variable | Meaning |
|---|---|
| `VIO_TOKEN` | Access code. Set = login required. Unset = localhost-only, no login. |
| `MIND_HOST` | Bind address. Default `127.0.0.1` (local only). Vio **refuses** to bind elsewhere without `VIO_TOKEN`. |
| `VIO_ALLOWED_HOSTS` | Comma-separated hostnames allowed in the `Host` header (your tailnet/tunnel name). |
| `VIO_HTTPS` | Set when TLS terminates in front (Tailscale/Cloudflare/proxy) so the cookie is marked `Secure`. |
| `MIND_PORT` | Port (default 8100). |
| `VIO_ALLOW_NET` | `1` lets the Web Research agent search the web, read pages, and learn from them. Unset/`0` = no outbound web access (default). |
| `VIO_NET_ALLOW` | Comma-separated domains the research agent may fetch (e.g. `docs.microsoft.com,rfc-editor.org`). Blank = any **public** site. |
| `VIO_NET_BLOCK` | Comma-separated domains the research agent must never fetch (block wins over allow). |

## Web research (outbound access)
`VIO_ALLOW_NET=1` turns on Vio's Web Research agent: ask `research: <topic>` (or
"look up …", "search the web for …") and it searches, reads the top pages, learns them
into the library, and answers with citations. Safeguards, always on when enabled:
- **Read-only** over the public web — it fetches pages, never posts or logs in.
- **SSRF-guarded** — a host resolving to a private/loopback/link-local/reserved address
  is refused, so it can't be steered into your LAN or a cloud metadata endpoint.
- **http/https only**, per-page size cap, request timeout, redirects re-validated.
- Fetched text is treated as **data, not instructions** (prompt-injection safety).
- Anything promoted into the fine-tuned *model* still passes the human approval gate.

To keep it tightly scoped, set `VIO_NET_ALLOW` to just the domains you trust.

## Don'ts
- ❌ Don't port-forward 8100 on your router.
- ❌ Don't run bound to `0.0.0.0` without `VIO_TOKEN` (Vio refuses this by design).
- ❌ Don't put the token in a shared repo or a screenshot.
- ❌ Don't enable `VIO_ALLOW_NET` on an untrusted/shared machine without a `VIO_NET_ALLOW` list.
