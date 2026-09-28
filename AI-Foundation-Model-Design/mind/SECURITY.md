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

## 3. Alternative — Cloudflare Tunnel

**Run `start_vio_cloudflare.bat`.** It will not start without a token, checks that
`cloudflared` is installed (`winget install --id Cloudflare.cloudflared`), starts Vio,
and opens the tunnel.

- **Quick tunnel (default):** no account. You get a random `https://….trycloudflare.com`
  address that changes on every start. `VIO_ALLOWED_HOSTS=.trycloudflare.com` (leading
  dot = the whole domain) admits it.
- **Named tunnel:** a fixed address on your own domain. One-time setup is at the bottom
  of the script. Put **Cloudflare Access** (email one-time code, your address only) in
  front — Cloudflare then checks who you are before a request ever reaches your PC.

**This is the public internet, unlike Tailscale.** Anyone with the link reaches the
login page. What protects you:

- `cloudflared` connects to Vio *from localhost*, so tunnelled traffic looks local at
  the socket. Vio instead detects it by the headers Cloudflare (and any reverse proxy)
  adds — `Cf-Ray`, `Cf-Connecting-Ip`, `X-Forwarded-For`, … — and **always requires the
  token for it**, even with `--http-host-header localhost`. With no token set, tunnelled
  requests are refused outright.
- `VIO_CLOUDFLARE=1` (set by the script) makes Vio refuse to *start* without a token.
- The session cookie is `HttpOnly`, `SameSite=Strict`, and `Secure` (via `VIO_HTTPS=1`).
- Login is constant-time and throttled after repeated failures.

Tradeoff: traffic transits Cloudflare, which terminates TLS at its edge.

---

## Environment variables

| Variable | Meaning |
|---|---|
| `VIO_TOKEN` | Access code. Set = login required. Unset = genuinely-local requests only, no login; anything arriving through a tunnel/proxy is refused. |
| `MIND_HOST` | Bind address. Default `127.0.0.1` (local only). Vio **refuses** to bind elsewhere without `VIO_TOKEN`. |
| `VIO_ALLOWED_HOSTS` | Comma-separated hostnames allowed in the `Host` header (your tailnet/tunnel name). A leading dot allows a whole domain: `.trycloudflare.com`. |
| `VIO_CLOUDFLARE` | Set when a Cloudflare tunnel is in use: Vio refuses to start without `VIO_TOKEN`. |
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
