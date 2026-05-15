# Vio on Hostinger — Step by Step (Windows edition)

Beginner-friendly walkthrough. Each phase is small. Do one phase, take a
short break, do the next. Never skip a phase without telling me — if
something fails, stop and share the error.

> Convention in this doc:
> - `> like this` means click/type **in the Hostinger website (hPanel)**.
> - ```text in a black box``` means **type exactly that on the VPS terminal**.
> - `{{LIKE_THIS}}` is a placeholder — replace with your real value.

---

## Phase 0 — Things to have ready (15 minutes)

You need:

1. A Hostinger account (https://hpanel.hostinger.com). Sign up if needed.
2. A VPS plan. For Vio:
   - **Minimum**: KVM 2 (8 GB RAM, 2 vCPU) — fine if Vio uses a hosted
     LLM API (Anthropic / OpenAI).
   - **Recommended**: KVM 4 (16 GB RAM, 4 vCPU) — required if you also
     want to run a small local model (Ollama).
3. A domain name (optional but recommended). You can buy one in Hostinger
   too. Example: `vio.{{YOUR_DOMAIN}}`. Without a domain you can still
   reach Vio by IP, just without HTTPS auto-cert.
4. Windows 10 or 11 on your laptop. Built-in Windows Terminal is enough.
   We will **not** use PuTTY — modern Windows has SSH built in.

You do NOT need:
- A graphics card on the VPS (Hostinger KVM VPS has no GPU; that's ok).
- Any AI tool installed yet. We start clean.

---

## Phase 1 — Buy / pick the VPS in Hostinger (10 minutes)

1. Log in to https://hpanel.hostinger.com.
2. Top menu → **VPS** → **Get VPS** (or open your existing VPS).
3. Plan: pick **KVM 2** or **KVM 4** as above.
4. Location: pick the data center closest to you (e.g. for Saudi Arabia
   or Egypt: **Lithuania** or **France**; for India: **India**).
5. OS template: choose **Ubuntu 24.04 LTS** (clean, no panel).
   - **Do not** pick "with Plesk" or "with cPanel" — extra surface area.
   - **Do not** pick the "AI" or "OpenAI" template if offered — we want a
     clean OS so we control everything.
6. Hostname: anything. `vio-vps` is fine.
7. Root password: hPanel will ask for one — **let it generate a long one**
   and copy it to a password manager (Bitwarden, 1Password, KeePass).
   We will disable password login later; you just need it once.
8. **SSH keys** section: if you see "Add SSH key", skip for now. We will
   add the key in Phase 3 from the VPS side.
9. Click **Create / Setup**.

The VPS takes 1–5 minutes to provision. When it shows **Running**,
note down:
- **IP address** (looks like `203.0.113.42`)
- **Username**: `root` (default for fresh Ubuntu)
- **Password**: the one you just saved

> If you already have a VPS from before and unsure of state, run the
> discovery script (Phase 4) first — it won't change anything.

---

## Phase 2 — Connect from Windows for the first time (10 minutes)

Windows 10/11 has an SSH client built in. You don't need PuTTY.

1. Press the **Windows key** → type `Terminal` → open **Windows Terminal**.
   (If you only see "PowerShell" or "Command Prompt", that works too.)
2. Type the connect command, replacing the IP with yours:

   ```
   ssh root@{{YOUR_VPS_IP}}
   ```

3. First time only — Windows will ask:
   ```
   The authenticity of host '...' can't be established.
   Are you sure you want to continue connecting (yes/no)?
   ```
   Type `yes` and Enter.
4. Enter the root password you saved. Nothing shows as you type (no
   stars, no dots) — that is normal. Press Enter.
5. You should see a `root@vio-vps:~#` prompt. **You are inside the VPS.**

If this step fails:
- Wrong IP? Re-check in hPanel.
- "Permission denied" → password typo. Try again. After 3 fails Hostinger
  may temp-block your client IP for 10 min.
- "Connection refused" → VPS still booting. Wait 2 minutes, try again.

---

## Phase 3 — Make yourself a non-root user (10 minutes)

Logging in as root every day is dangerous. We create a normal user
called `mazin` and give it sudo (admin power).

Run these on the VPS, **one line at a time** (paste, Enter, watch
output). Replace `mazin` with whatever username you want.

```
adduser mazin
```
- It asks for a password — pick a **strong** one, save in password
  manager. The other fields (Full Name, Room Number…) you can leave
  blank, just press Enter.

```
usermod -aG sudo mazin
```
This puts you in the `sudo` group (admin).

Now from your **Windows laptop** (open a SECOND Windows Terminal tab,
keep the root one open as a safety net), connect as the new user:

```
ssh mazin@{{YOUR_VPS_IP}}
```

Enter the `mazin` password you just made. You should see a `mazin@…$`
prompt (note the `$` instead of `#` — that means non-root).

Test that sudo works:

```
sudo whoami
```
It asks for your `mazin` password, then prints `root`. ✅

**Do not close the root tab yet** — keep it as a rescue session until
Phase 5 is done.

---

## Phase 4 — Run the discovery script (5 minutes)

This script only **reads** — it changes nothing. It produces a single
text report you can share back.

In your `mazin@…$` window:

```
curl -fsSL https://raw.githubusercontent.com/Mazin129/Mazin/claude/enhance-vio-agent-ny2BM/Vio/scripts/discover.sh -o /tmp/discover.sh
bash /tmp/discover.sh > /tmp/vio-discovery.txt 2>&1
echo "DONE. Lines: $(wc -l < /tmp/vio-discovery.txt)"
```

You should see something like `DONE. Lines: 215`.

To view it:
```
less /tmp/vio-discovery.txt
```
Use arrow keys / Page Down to scroll. Press `q` to quit.

To copy it to your Windows laptop so you can paste it back to me, from
**Windows Terminal** (NOT inside the VPS), run:

```
scp mazin@{{YOUR_VPS_IP}}:/tmp/vio-discovery.txt %USERPROFILE%\Downloads\
```

Or, the simplest path: inside the VPS terminal type `cat
/tmp/vio-discovery.txt`, then **select-all + copy** the output and paste
it into chat with me.

Public IPs and MAC addresses are auto-redacted, so it is safe to share.

---

## Phase 5 — Baseline hardening (15 minutes)

Only after Phase 4 succeeds. These commands run as `mazin` user with
`sudo`. They lock the front door of the VPS before we put any agent on it.

### 5.1 Update the system
```
sudo apt update && sudo apt -y full-upgrade && sudo apt -y autoremove
```
If it asks about config file conflicts, accept the default ("keep local
version"). If it asks to restart services, press Tab → OK → Enter.

### 5.2 Set timezone
```
sudo timedatectl set-timezone {{YOUR_TZ}}
```
Examples: `Asia/Riyadh`, `Africa/Cairo`, `Asia/Dubai`, `Asia/Kolkata`,
`Europe/Istanbul`. Confirm: `timedatectl`.

### 5.3 SSH: keys instead of passwords
On your **Windows laptop** (not the VPS), in a Windows Terminal:
```
ssh-keygen -t ed25519 -C "mazin-laptop"
```
Press Enter to accept the default file path. Set a passphrase — write it
down. This creates two files:
- `C:\Users\YOU\.ssh\id_ed25519` (private — never share)
- `C:\Users\YOU\.ssh\id_ed25519.pub` (public — safe to share)

Copy the public key to the VPS:
```
type %USERPROFILE%\.ssh\id_ed25519.pub | ssh mazin@{{YOUR_VPS_IP}} "mkdir -p ~/.ssh && chmod 700 ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"
```

Test from Windows in a **new** tab:
```
ssh mazin@{{YOUR_VPS_IP}}
```
If it logs you in **without asking for a password** (or only asks for the
key passphrase you just set), keys are working.

### 5.4 Disable root login + passwords
Only do this AFTER 5.3 succeeded on a new tab.

On the VPS:
```
sudo sed -i.bak 's/^#\?PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config
sudo sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
sudo systemctl reload ssh
```

Test by opening **yet another** new Windows tab:
```
ssh mazin@{{YOUR_VPS_IP}}
```
Must still work (via key). The old root tab will still be alive in its
current session — but new root logins will be refused. That's correct.

### 5.5 Firewall
```
sudo apt install -y ufw
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw --force enable
sudo ufw status verbose
```

### 5.6 Fail2ban + unattended security upgrades
```
sudo apt install -y fail2ban unattended-upgrades
sudo systemctl enable --now fail2ban
sudo dpkg-reconfigure -plow unattended-upgrades   # press Yes
```

### 5.7 Re-run discovery
```
bash /tmp/discover.sh > /tmp/vio-discovery-2.txt 2>&1
```
Share `vio-discovery-2.txt` to confirm hardening took effect (UFW
active, root login off, fail2ban running).

**Now you can safely close the root rescue tab.**

---

## Phase 6 — Install Vio skills (10 minutes)

This phase is already done if you ran `install-vio.sh`. Skip to Phase 7
if Vio is already responding at your openclaw URL.

If starting fresh:

```
curl -fsSL https://raw.githubusercontent.com/Mazin129/Mazin/claude/enhance-vio-agent-ny2BM/Vio/scripts/install-vio.sh -o /tmp/install-vio.sh
sudo bash /tmp/install-vio.sh
```

Type `apply` when prompted. The script clones the repo, links skills,
updates the openclaw config, and restarts the container.

Verify at: https://openclaw-5sds.srv1671720.hstgr.cloud/

Test: ask Vio "what is your management subnet?" — it should answer
`192.168.100.0/24` from memory.

---

## Phase 7 — Security hardening (20 minutes)

This phase covers three important items. Run them now.

### 7a — Rotate leaked device identity

The openclaw device identity files were accidentally exposed. Delete
them so openclaw regenerates fresh credentials:

```
curl -fsSL https://raw.githubusercontent.com/Mazin129/Mazin/claude/enhance-vio-agent-ny2BM/Vio/scripts/harden-vps.sh -o /tmp/harden-vps.sh
sudo bash /tmp/harden-vps.sh identity
```

Type `apply` when prompted. openclaw will restart and pair with new
credentials. Log in at your openclaw URL and confirm it still works.

### 7b — SSH key login (stop using passwords)

**In MobaXterm (on your Windows PC):**

1. Click **Tools** → **MobaKeyGen**
2. Click **Generate**, move your mouse to create randomness
3. Key type: Ed25519 (preferred) or RSA 4096
4. Set a **Key passphrase** — write it down
5. Click **Save private key** → save as `mazin-vps.ppk`
6. **Copy** the text in the "Public key for pasting into OpenSSH" box
   at the top (starts with `ssh-ed25519 …`)

**On the VPS terminal:**

```
sudo bash /tmp/harden-vps.sh sshkey
```

When prompted, paste your public key (the line you copied from
MobaKeyGen). Then the script will ask you to confirm it works before
disabling password login.

**⚠ Always test key login in a NEW MobaXterm tab before closing the
password-based tab. Locking yourself out requires using Hostinger's
browser console to fix.**

### 7c — Fix server timezone

```
sudo bash /tmp/harden-vps.sh timezone
```

Type `apply`. This sets the server clock to Asia/Riyadh (UTC+3) so
cron jobs and logs show the correct local time.

### 7d — Rotate external API keys

⚠ **Critical**: The following keys were accidentally shown in a
terminal paste earlier in this session. Rotate them immediately:

| Service | Where to rotate |
|---------|-----------------|
| **OpenAI** | https://platform.openai.com → API keys → Delete old → Create new |
| **Gemini** | https://aistudio.google.com → Get API key → Delete old |
| **Telegram Bot** | Talk to @BotFather → `/revoke` → get new token |
| **Oxylabs** | Oxylabs dashboard → Credentials → Reset |
| **Nexos** | Nexos dashboard → API keys → Regenerate |

After rotating, update each key in the Hostinger hPanel:
`VPS → Manage → Environment Variables` (or `docker-compose.yaml` env
section) — then restart the openclaw container:

```
sudo docker restart openclaw-5sds-openclaw-1
```

---

## Phase 8 — Proactive morning brief (10 minutes)

Vio can send you a daily Telegram message with open follow-ups.

Requirements:
1. A Telegram bot token (ask @BotFather for `/newbot` — keep the new
   token after rotating the old one in Phase 7d)
2. Your personal Telegram Chat ID (send `/start` to your bot, then
   visit `https://api.telegram.org/bot{{TOKEN}}/getUpdates` to find
   your `chat.id`)

Then run:

```
sudo TELEGRAM_BOT_TOKEN={{YOUR_NEW_TOKEN}} TELEGRAM_CHAT_ID={{YOUR_CHAT_ID}} bash /tmp/setup-cron.sh
```

Or download the script first:

```
curl -fsSL https://raw.githubusercontent.com/Mazin129/Mazin/claude/enhance-vio-agent-ny2BM/Vio/scripts/setup-cron.sh -o /tmp/setup-cron.sh
sudo bash /tmp/setup-cron.sh
```

Type `apply` when prompted. This installs three cron jobs:
- Daily 07:00 Arabia time — morning brief to Telegram
- Every Friday 22:00 — memory file cleanup
- Daily 03:00 — auto-pull latest Vio skills from GitHub

Test the morning brief immediately:
```
sudo bash /data/.openclaw/scripts/morning-brief.sh
```
Check your Telegram for the message.

---

## Quick reference — what each thing does

| Thing | What it does | Why we use it |
|-------|--------------|---------------|
| `apt` | Ubuntu package manager | Install/upgrade software |
| `sudo` | Run a command as root | Admin tasks for non-root user |
| `ssh` | Encrypted remote login | The way you talk to the VPS |
| `ssh-keygen` | Make a keypair | Replaces passwords for SSH |
| `ufw` | Friendly firewall | Block all ports except what you allow |
| `fail2ban` | Bans IPs that brute-force SSH | Stops the constant SSH attacks |
| `unattended-upgrades` | Auto-applies security patches | Keeps you safe between visits |
| Discovery script | Read-only inventory | Tells us exactly what's there |

## Mistakes new users make (avoid these)

- ❌ Working as `root` for everything. → Use the `mazin` user.
- ❌ Pasting commands you don't understand. → Ask me first.
- ❌ Disabling password SSH **before** keys are tested. → You'll lock
  yourself out. Always test in a NEW tab first.
- ❌ Installing Docker + Caddy + Ollama + LibreChat all at once. → One
  thing at a time, verify, then next.
- ❌ Reusing the root password as the `mazin` password. → Two different
  strong passwords.

## If you get locked out

Hostinger hPanel → your VPS → **Browser Terminal** (or "VNC console")
gives you a console that bypasses SSH entirely. You can log in as root
there to fix SSH config. That's why we keep a root rescue tab in
Phase 3 and a password set in Phase 1 — defense in depth.
