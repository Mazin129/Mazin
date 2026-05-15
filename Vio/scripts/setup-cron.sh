#!/usr/bin/env bash
# Set up cron jobs for Vio proactive tasks:
#   - Daily morning brief (sent to Telegram) at 07:00 Arabia time
#   - Weekly Friday hygiene (clean old memory entries)
#   - Weekly Saturday digest reminder
#
# Requires:
#   - TZ set to Asia/Riyadh (run harden-vps.sh timezone first)
#   - TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID set in environment or passed as args
#
# Usage:
#   sudo bash setup-cron.sh
#   TELEGRAM_BOT_TOKEN=xxx TELEGRAM_CHAT_ID=yyy sudo bash setup-cron.sh
set -euo pipefail

CONTAINER="openclaw-5sds-openclaw-1"
OC_ROOT="/docker/openclaw-5sds"
DATA="${OC_ROOT}/data"
OC_DIR="${DATA}/.openclaw"
WORKSPACE="${OC_DIR}/workspace"
SCRIPTS_DIR="${OC_DIR}/scripts"
LOG_DIR="${DATA}/logs"

c_green()  { printf '\033[32m%s\033[0m\n' "$*"; }
c_blue()   { printf '\033[34m%s\033[0m\n' "$*"; }
c_yellow() { printf '\033[33m%s\033[0m\n' "$*"; }
c_red()    { printf '\033[31m%s\033[0m\n' "$*"; }

require_root() {
  if [ "$(id -u)" -ne 0 ]; then
    c_red "Run with sudo: sudo bash $0"
    exit 1
  fi
}

confirm() {
  printf '%s\nType "apply" to proceed, anything else to abort: ' "$1"
  read -r ans
  [ "$ans" = "apply" ]
}

check_timezone() {
  local tz; tz=$(timedatectl show --property=Timezone --value 2>/dev/null || echo "UTC")
  if [ "$tz" != "Asia/Riyadh" ]; then
    c_yellow "⚠ Timezone is ${tz}, not Asia/Riyadh."
    c_yellow "  Cron times will be based on ${tz}. Run harden-vps.sh timezone first for correct local times."
    echo ""
  else
    c_green "Timezone: ${tz} ✓"
  fi
}

write_memory_hygiene_script() {
  mkdir -p "$SCRIPTS_DIR"
  cat > "${SCRIPTS_DIR}/memory-hygiene.sh" <<'EOF'
#!/usr/bin/env bash
# Weekly: remove superseded facts and done followups older than 30 days.
set -euo pipefail
MEMORY_FILE="/data/.openclaw/workspace/vio-memory/memory.json"
LOG="/data/logs/memory-hygiene.log"
mkdir -p /data/logs
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Running memory hygiene..." >> "$LOG"
docker exec openclaw-5sds-openclaw-1 node -e "
const fs=require('fs');
const p='${MEMORY_FILE}';
let m={facts:[],followups:[]};
try{m=JSON.parse(fs.readFileSync(p,'utf8'))}catch(e){process.exit(0);}
const cutoff=new Date(Date.now()-30*24*60*60*1000).toISOString();
const before=[m.facts.length, m.followups.length];
m.facts=m.facts.filter(f=>!(f.supersededBy && f.created<cutoff));
m.followups=m.followups.filter(f=>!(f.doneAt && f.doneAt<cutoff));
fs.writeFileSync(p,JSON.stringify(m,null,2));
console.log('cleaned. facts:',m.facts.length,'(was',before[0]+')','followups:',m.followups.length,'(was',before[1]+')');
" >> "$LOG" 2>&1
EOF
  chmod +x "${SCRIPTS_DIR}/memory-hygiene.sh"
  c_green "Written: ${SCRIPTS_DIR}/memory-hygiene.sh"
}

write_telegram_brief_script() {
  local BOT_TOKEN="${1:-}"
  local CHAT_ID="${2:-}"
  mkdir -p "$SCRIPTS_DIR" "$LOG_DIR"

  cat > "${SCRIPTS_DIR}/morning-brief.sh" <<SCRIPT
#!/usr/bin/env bash
# Send Vio's morning brief via Telegram.
# Bot token and chat ID come from environment (set by Hostinger panel or .env).
set -euo pipefail

BOT_TOKEN="\${TELEGRAM_BOT_TOKEN:-${BOT_TOKEN}}"
CHAT_ID="\${TELEGRAM_CHAT_ID:-${CHAT_ID}}"
LOG="/data/logs/morning-brief.log"
MEMORY="/data/.openclaw/workspace/vio-memory/memory.json"

if [ -z "\$BOT_TOKEN" ] || [ -z "\$CHAT_ID" ]; then
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] SKIP: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set" >> "\$LOG"
  exit 0
fi

# Pull open follow-ups from memory
FOLLOWUPS=\$(docker exec openclaw-5sds-openclaw-1 node -e "
const fs=require('fs');
try {
  const m=JSON.parse(fs.readFileSync('\${MEMORY}','utf8'));
  const open=m.followups.filter(f=>!f.doneAt);
  if(open.length===0){console.log('• No open follow-ups');process.exit(0);}
  open.slice(0,5).forEach(f=>{
    const due=f.dueAt? ' (due '+f.dueAt+')':'';
    console.log('[P'+f.priority+'] '+f.description+due);
  });
  if(open.length>5) console.log('...and '+(open.length-5)+' more');
} catch(e){ console.log('Memory empty'); }
" 2>/dev/null)

TODAY=\$(date '+%A, %d %B %Y')
MSG="🌅 *Vio Morning Brief — \${TODAY}*

*Open follow-ups:*
\${FOLLOWUPS}

_Reply in chat to get help with any of these._"

curl -s -X POST "https://api.telegram.org/bot\${BOT_TOKEN}/sendMessage" \
  --data-urlencode "chat_id=\${CHAT_ID}" \
  --data-urlencode "text=\${MSG}" \
  --data-urlencode "parse_mode=Markdown" \
  >> "\$LOG" 2>&1

echo "" >> "\$LOG"
SCRIPT
  chmod +x "${SCRIPTS_DIR}/morning-brief.sh"
  c_green "Written: ${SCRIPTS_DIR}/morning-brief.sh"
}

install_crons() {
  local CRON_FILE="/etc/cron.d/vio"

  cat > "$CRON_FILE" <<CRON
# Vio proactive tasks — Arabia Standard Time (UTC+3)
# Make sure TZ=Asia/Riyadh is set on the server.

SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin

# Morning brief — every day at 07:00 local (04:00 UTC)
0 4 * * *   root   bash ${SCRIPTS_DIR}/morning-brief.sh

# Weekly memory hygiene — every Friday at 22:00 local (19:00 UTC)
0 19 * * 5  root   bash ${SCRIPTS_DIR}/memory-hygiene.sh

# Auto git-pull Mazin repo (keeps Vio skills fresh) — daily at 03:00 local
0 0 * * *   root   git -C ${WORKSPACE}/Mazin pull --ff-only origin claude/enhance-vio-agent-ny2BM >> ${LOG_DIR}/git-pull.log 2>&1
CRON
  chmod 644 "$CRON_FILE"
  c_green "Cron installed: ${CRON_FILE}"
}

main() {
  require_root
  check_timezone
  mkdir -p "$LOG_DIR"

  # Get Telegram credentials
  local BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-}"
  local CHAT_ID="${TELEGRAM_CHAT_ID:-}"

  if [ -z "$BOT_TOKEN" ]; then
    printf 'Telegram Bot Token (leave blank to skip Telegram): '
    read -r BOT_TOKEN
  fi
  if [ -n "$BOT_TOKEN" ] && [ -z "$CHAT_ID" ]; then
    printf 'Your Telegram Chat ID (send /start to your bot to get it): '
    read -r CHAT_ID
  fi

  cat <<EOF

PLAN:
  Write scripts to: ${SCRIPTS_DIR}/
    - morning-brief.sh    (daily 07:00 Arabia time via Telegram)
    - memory-hygiene.sh   (weekly Friday 22:00)
  Install cron file: /etc/cron.d/vio
    - daily morning brief
    - weekly memory hygiene
    - daily git pull (keeps skills auto-updated)
EOF

  if confirm "Install Vio cron jobs?"; then
    write_memory_hygiene_script
    write_telegram_brief_script "$BOT_TOKEN" "$CHAT_ID"
    install_crons
    echo ""
    c_green "═══════════════════════════════════════════════════════════════"
    c_green " Vio cron jobs installed."
    c_green " Check logs in ${LOG_DIR}/"
    if [ -n "$BOT_TOKEN" ]; then
      c_green " Morning brief will start tomorrow at 07:00 Arabia time."
      c_yellow " To test now: bash ${SCRIPTS_DIR}/morning-brief.sh"
    else
      c_yellow " No Telegram token provided. Morning brief is installed but will"
      c_yellow " skip silently. Set TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID in"
      c_yellow " Hostinger → Manage → Environment to activate it."
    fi
    c_green "═══════════════════════════════════════════════════════════════"
  else
    c_yellow "Aborted. No changes made."
  fi
}

main
