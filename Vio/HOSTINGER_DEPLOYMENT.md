# Vio — Hostinger VPS Deployment & Hardening

Practical guide to running Vio on a Hostinger VPS so it stays up, stays
private, and stays yours.

---

## VPS sizing

| Use case | RAM | vCPU | Disk |
|----------|-----|------|------|
| Hosted LLM API (Claude/OpenAI), Vio is the orchestrator only | 4 GB | 2 | 50 GB |
| Self-hosted small model (Llama-3.1-8B, Qwen-2.5-7B via Ollama) | 16 GB | 4–8 | 100 GB SSD |
| Self-hosted 70B class | not on a generic Hostinger VPS — use a GPU host | | |

For a personal Vio, Option 1 is what makes sense: pay per token to a hosted
model API, run the *agent loop* on the VPS. The VPS holds memory + tools +
auth.

## Baseline OS hardening (Ubuntu 22.04 / 24.04)

```bash
# 1. Patch
apt update && apt full-upgrade -y && apt autoremove -y

# 2. Non-root user
adduser vio
usermod -aG sudo vio

# 3. SSH: keys only, no root login, custom port
sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config
sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
sed -i 's/^#\?Port .*/Port 2202/' /etc/ssh/sshd_config
systemctl reload sshd

# 4. Firewall
apt install -y ufw
ufw default deny incoming
ufw default allow outgoing
ufw allow 2202/tcp        # SSH
ufw allow 443/tcp         # HTTPS to Vio
ufw enable

# 5. Unattended security updates
apt install -y unattended-upgrades
dpkg-reconfigure -plow unattended-upgrades

# 6. Fail2ban for SSH
apt install -y fail2ban
systemctl enable --now fail2ban
```

## Application layout

```
/opt/vio/
  app/                  ← agent code (git-cloned, owned by vio:vio)
  venv/                 ← python venv
  data/                 ← SQLite + vector index, mode 0700
    memory.db
    embeddings/
  logs/                 ← rotated by logrotate
  config/
    vio.env             ← env vars, mode 0600
  prompts/
    system.md           ← copy of SYSTEM_PROMPT.md, hot-reloadable
```

Mount `/opt/vio/data` on an encrypted volume if your VPS plan supports
attached encrypted volumes. Otherwise, use full-disk LUKS at provision time.

## Systemd service

`/etc/systemd/system/vio.service`:

```ini
[Unit]
Description=Vio agent
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=vio
Group=vio
WorkingDirectory=/opt/vio/app
EnvironmentFile=/opt/vio/config/vio.env
ExecStart=/opt/vio/venv/bin/python -m vio.server
Restart=on-failure
RestartSec=5
# hardening
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true
ReadWritePaths=/opt/vio/data /opt/vio/logs
CapabilityBoundingSet=
AmbientCapabilities=
LockPersonality=true
MemoryDenyWriteExecute=true
RestrictRealtime=true
RestrictNamespaces=true
SystemCallArchitectures=native

[Install]
WantedBy=multi-user.target
```

Enable: `systemctl enable --now vio`

## Reverse proxy + TLS

Caddy is the lowest-friction option on Hostinger.

`/etc/caddy/Caddyfile`:

```
vio.{{YOUR_DOMAIN}} {
    encode zstd gzip
    @auth {
        not header Authorization "Bearer {{LONG_RANDOM_TOKEN}}"
    }
    respond @auth "unauthorized" 401

    reverse_proxy 127.0.0.1:8080 {
        header_up X-Real-IP {remote_host}
    }

    header {
        Strict-Transport-Security "max-age=31536000; includeSubDomains; preload"
        X-Content-Type-Options "nosniff"
        Referrer-Policy "no-referrer"
        Permissions-Policy "interest-cohort=()"
    }
}
```

Replace the bearer auth with WebAuthn or OAuth (Google/GitHub) before you let
family members use it.

## Secrets

Use `pass`, `sops+age`, or `systemd-creds`. **Never** put API keys directly in
`vio.env` committed to git.

Example with `systemd-creds`:

```bash
systemd-creds encrypt --name=anthropic_key - /etc/credstore.encrypted/anthropic_key.enc
# then in the service unit:
# LoadCredentialEncrypted=anthropic_key:/etc/credstore.encrypted/anthropic_key.enc
# the app reads $CREDENTIALS_DIRECTORY/anthropic_key
```

## Outbound egress (important for a security agent)

Vio will hit: your LLM provider, a few RSS feeds, your FortiGate, your
calendar. That's it. Lock egress with a host firewall or with a small
allow-list proxy:

```
api.anthropic.com:443
api.openai.com:443        # only if you use it
nvd.nist.gov:443
fortiguard.fortinet.com:443
<your-fortigate>:443
<your-caldav-host>:443
```

Egress lockdown stops a future RCE in a dependency from phoning home.

## Backups

```bash
# /etc/cron.daily/vio-backup
#!/bin/sh
set -e
TS=$(date -u +%Y%m%dT%H%M%SZ)
sqlite3 /opt/vio/data/memory.db ".backup '/tmp/memory-$TS.db'"
age -r age1... /tmp/memory-$TS.db > /opt/vio/data/backups/memory-$TS.db.age
rm /tmp/memory-$TS.db
find /opt/vio/data/backups -name 'memory-*.db.age' -mtime +30 -delete
# push to object storage off-VPS
```

Test restore monthly. A backup you have never restored is a wish, not a backup.

## Monitoring

- **Uptime**: a free Uptime-Kuma instance pinging `/healthz` every minute.
- **Logs**: ship JSON logs to `journald`; weekly review with
  `journalctl -u vio --since '7 days ago' | jq -r '.MESSAGE' | sort | uniq -c | sort -n`.
- **Anomaly**: alert if memory.db grows > 50 MB in a day, or if outbound
  tokens billed > 2× the trailing 7-day average.

## Incident-response checklist for Vio itself

If you suspect compromise of the VPS:

```
1) Isolate: ufw default deny outgoing; revoke API keys at provider side.
2) Snapshot: take a Hostinger snapshot for forensics BEFORE remediation.
3) Rotate: every secret in /opt/vio/config + every API key Vio could reach.
4) Audit: last 30 days of conversations table for prompt-injection patterns,
   memory.db diff against last clean backup.
5) Rebuild: pave from scratch, restore memory.db from a known-clean backup.
6) Post-mortem: write to reports/incident-YYYYMMDD.md.
```

## Cost guardrails

Put a hard monthly cap on the LLM provider account. Set a budget alert at
50% and 80%. If Vio ever starts looping, you want a circuit breaker before
the bill arrives.

```python
# pseudo-code in your agent loop
if monthly_tokens > LIMIT * 0.8:
    notify("Vio at 80% of budget"); pause_proactive()
if monthly_tokens > LIMIT:
    notify("Vio paused — budget hit"); raise BudgetExceeded
```
