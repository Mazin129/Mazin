# Host Vio online (production)

This kit runs Vio behind real HTTPS on your own domain, with the admin API locked by
a token. One `docker compose up` brings up **Caddy (TLS) → Vio → Ollama**.

> For *personal* remote access without a public server, Tailscale is simpler and more
> private — see `../SECURITY.md`. Use *this* when you want a public URL.

---

## First, the one real decision: where does the LLM run?

Vio's reasoner + retrieval are featherweight and run on any tiny box. The *thinking*
comes from the LLM (Ollama), which wants memory and ideally a GPU. Pick a path:

| Path | Speed | Cost/mo | Privacy | Notes |
|---|---|---|---|---|
| **A — CPU VPS, all-in-one** | slow (10–40 s/answer) | ~$6–12 | full (self-hosted) | fine for light personal use; needs ≥8 GB RAM for a 7–8B model |
| **B — GPU VPS** | fast | ~$150–500 | full | overkill unless heavily used |
| **C — small VPS + hosted LLM API** | fast | ~$5 + usage | model runs off-box | point `VIO_LLM_URL` at an OpenAI/Ollama-compatible endpoint |
| **D — Tailscale to your home PC** | fast (your GPU) | $0 | full | not "public", but reachable anywhere — see SECURITY.md |

This kit defaults to **Path A** (Ollama in a container). For **B**, uncomment the GPU block
in `docker-compose.yml`. For **C**, drop the `ollama` service and set `VIO_LLM_URL`.

---

## Steps (Path A)

**You need:** a small Linux VPS (Ubuntu, ≥8 GB RAM), a domain, Docker.

1. **Point your domain at the server.** Create an `A` record: `vio.yourdomain.com → <server IP>`.

2. **On the server, install Docker:**
   ```
   curl -fsSL https://get.docker.com | sh
   ```

3. **Get Vio and configure:**
   ```
   git clone <your repo> && cd AI-Foundation-Model-Design/mind/deploy
   cp .env.example .env
   nano .env        # set DOMAIN and a strong VIO_TOKEN
   ```
   Generate a token: `python3 -c "import secrets;print(secrets.token_urlsafe(24))"`

4. **Open only the web ports** (Vio itself is never exposed directly):
   ```
   ufw allow 80,443/tcp && ufw enable
   ```

5. **Launch:**
   ```
   docker compose up -d --build
   docker compose exec ollama ollama pull llama3.1     # ~5 GB, one time
   ```

6. **Open** `https://vio.yourdomain.com` — Caddy has already fetched a real TLS cert.
   Log in with your token. Done.

**Load your knowledge** (once):
```
docker compose exec vio python teach_datasets.py       # bundled datasets
# your own docs: put them in a folder, mount it, then:  python ingest.py /docs
```

---

## Operate it

- **Logs:** `docker compose logs -f vio`
- **Update:** `git pull && docker compose up -d --build`
- **Backup** (this is your brain — do it):
  ```
  docker run --rm -v mind_viodata:/d -v $PWD:/b alpine tar czf /b/vio-backup.tgz -C /d .
  ```
- **Restore:** untar into the `viodata` volume.
- **Stop:** `docker compose down` (data volumes persist).

---

## Alternative: no Docker (systemd on a VPS)

If you'd rather run it directly, use `vio.service` (in this folder):
```
pip install -r requirements.txt
sudo cp vio.service /etc/systemd/system/  &&  sudo systemctl enable --now vio
```
Then put Caddy or nginx in front for TLS, and set `VIO_TOKEN` + `MIND_HOST=127.0.0.1`
so only the proxy can reach it. (Ollama installed separately.)

---

## Security checklist (all enforced or documented)

- [x] Token auth on every route (`VIO_TOKEN`) — the app refuses to boot public without it
- [x] TLS via Caddy (auto Let's Encrypt); HSTS + nosniff + frame-deny headers
- [x] Vio never exposed directly — only Caddy binds 80/443; Vio is on the internal network
- [x] Host-header allowlist (`VIO_ALLOWED_HOSTS`) against DNS-rebinding
- [ ] **You:** firewall to 80/443 only, keep the token secret, back up the volume
