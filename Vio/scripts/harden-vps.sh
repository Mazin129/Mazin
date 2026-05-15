#!/usr/bin/env bash
# Phase 7 — VPS security hardening for Mazin's openclaw server.
#
# What it does (each step is skippable):
#   A) Rotate openclaw device identity (delete leaked device.json / device-auth.json,
#      restart container so it regenerates fresh credentials).
#   B) Set up SSH key authentication for the mazin user and optionally disable
#      password login once you confirm the key works.
#   C) Fix the server timezone to Asia/Riyadh.
#
# Run each section independently with: bash harden-vps.sh <section>
#   section: identity | sshkey | timezone | all
#
# Safe to re-run. Shows what it will do before doing it. Requires "apply" to proceed.
set -euo pipefail

SECTION="${1:-all}"

OC_ROOT="/docker/openclaw-5sds"
DATA="${OC_ROOT}/data"
OC_DIR="${DATA}/.openclaw"
IDENTITY_DIR="${OC_DIR}/identity"
CONTAINER="openclaw-5sds-openclaw-1"

c_red()    { printf '\033[31m%s\033[0m\n' "$*"; }
c_green()  { printf '\033[32m%s\033[0m\n' "$*"; }
c_blue()   { printf '\033[34m%s\033[0m\n' "$*"; }
c_yellow() { printf '\033[33m%s\033[0m\n' "$*"; }

require_root() {
  if [ "$(id -u)" -ne 0 ]; then
    c_red "Run with sudo: sudo bash $0 ${SECTION}"
    exit 1
  fi
}

confirm() {
  local prompt="$1"
  printf '%s\nType "apply" to proceed, anything else to skip: ' "$prompt"
  read -r ans
  [ "$ans" = "apply" ]
}

# ─────────────────────────────────────────────────────────
# A) Rotate openclaw device identity
# ─────────────────────────────────────────────────────────
rotate_identity() {
  c_blue "=== Section A: Rotate openclaw device identity ==="
  cat <<EOF

  WHY: The device.json and device-auth.json files contain an operator token
  and Ed25519 private key that were accidentally exposed. Deleting them
  forces openclaw to generate new credentials on next start.

  Files to delete:
    ${IDENTITY_DIR}/device.json
    ${IDENTITY_DIR}/device-auth.json

  Then restart container: ${CONTAINER}
EOF

  local found=0
  for f in "${IDENTITY_DIR}/device.json" "${IDENTITY_DIR}/device-auth.json"; do
    if [ -f "$f" ]; then
      echo "  EXISTS: $f"
      found=1
    else
      echo "  MISSING (already gone): $f"
    fi
  done

  if [ "$found" -eq 0 ]; then
    c_green "Identity files already gone. Nothing to do."
    return
  fi

  if confirm "Delete leaked identity files and restart openclaw?"; then
    for f in "${IDENTITY_DIR}/device.json" "${IDENTITY_DIR}/device-auth.json"; do
      [ -f "$f" ] && rm -f "$f" && c_green "deleted: $f"
    done
    c_blue "Restarting ${CONTAINER}..."
    docker restart "$CONTAINER" >/dev/null
    sleep 4
    docker ps --filter "name=^/${CONTAINER}\$" --format 'table {{.Names}}\t{{.Status}}'
    c_green "Done. openclaw will register new device credentials on first cloud sync."
    echo ""
    c_yellow "ACTION REQUIRED: Log into https://openclaw-5sds.srv1671720.hstgr.cloud/"
    c_yellow "and verify the agent responds normally. If it asks to re-pair, follow"
    c_yellow "the on-screen pairing flow."
  else
    c_yellow "Skipped identity rotation."
  fi
}

# ─────────────────────────────────────────────────────────
# B) SSH key authentication
# ─────────────────────────────────────────────────────────
setup_sshkey() {
  c_blue "=== Section B: SSH key authentication ==="

  local TARGET_USER="mazin"
  local SSH_DIR="/home/${TARGET_USER}/.ssh"
  local AUTH_KEYS="${SSH_DIR}/authorized_keys"

  cat <<EOF

  CURRENT STATE:
EOF
  grep -E "^PasswordAuthentication|^PubkeyAuthentication|^PermitRootLogin" /etc/ssh/sshd_config || true
  echo ""

  # Check if there's already a key
  if [ -s "$AUTH_KEYS" ]; then
    c_green "SSH authorized_keys already exists:"
    cat "$AUTH_KEYS"
    echo ""
    c_yellow "If the key above is YOUR key (from MobaXterm), you can skip to disabling passwords."
    c_yellow "If it's unknown, delete it first: rm ${AUTH_KEYS}"
    echo ""
  fi

  cat <<'EOF'
  HOW TO ADD YOUR KEY (run these steps in MobaXterm on your Windows PC):

  Step 1 — Generate a key (if you don't have one yet):
    In MobaXterm → Tools → MobaKeyGen → Generate → save private key as mazin-vps.ppk
    Copy the "Public key for pasting" text at the top of MobaKeyGen.

  Step 2 — Paste your PUBLIC key below when prompted.
    (It starts with: ssh-rsa  or  ssh-ed25519)

EOF

  printf 'Paste your SSH public key (one line), then press Enter: '
  read -r PUBKEY

  if [ -z "$PUBKEY" ]; then
    c_yellow "No key provided. Skipping SSH key setup."
    return
  fi

  # Basic validation
  if ! echo "$PUBKEY" | grep -qE "^(ssh-rsa|ssh-ed25519|ecdsa-sha2-nistp256) "; then
    c_red "That doesn't look like a valid SSH public key. Aborting to avoid lockout."
    return
  fi

  cat <<EOF

  PLAN:
    Create ${AUTH_KEYS}
    Add your public key
    Set permissions (700 dir, 600 file, owned by ${TARGET_USER})
    Keep PasswordAuthentication YES for now (you must test key login first)

EOF

  if confirm "Add the key?"; then
    mkdir -p "$SSH_DIR"
    # Avoid duplicates
    if ! grep -qF "$PUBKEY" "$AUTH_KEYS" 2>/dev/null; then
      echo "$PUBKEY" >> "$AUTH_KEYS"
    fi
    chown -R "${TARGET_USER}:${TARGET_USER}" "$SSH_DIR"
    chmod 700 "$SSH_DIR"
    chmod 600 "$AUTH_KEYS"
    c_green "Key added to ${AUTH_KEYS}"
    echo ""
    c_yellow "═══════════════════════════════════════════════════════════════"
    c_yellow " TEST KEY LOGIN NOW before disabling passwords:"
    c_yellow " Open a NEW MobaXterm tab → SSH → host: your-server-ip"
    c_yellow "   → Use private key: mazin-vps.ppk"
    c_yellow " Confirm you can log in, then run this script again:"
    c_yellow "   sudo bash harden-vps.sh sshkey"
    c_yellow " It will then offer to disable password authentication."
    c_yellow "═══════════════════════════════════════════════════════════════"
    echo ""
  else
    c_yellow "Skipped key setup."
    return
  fi

  # Second run — disable passwords if key already confirmed working
  if grep -qF "$PUBKEY" "$AUTH_KEYS" 2>/dev/null; then
    cat <<EOF

  Your key is present. Next step: disable password authentication.

  WARNING: Only do this AFTER you've confirmed key login works in a separate
  terminal. If you lock yourself out there is no undo without Hostinger's
  VPS console.

EOF
    if confirm "Disable PasswordAuthentication in sshd?"; then
      # Create a drop-in so we don't touch the main sshd_config
      cat > /etc/ssh/sshd_config.d/10-no-passwords.conf <<'SSHEOF'
PasswordAuthentication no
ChallengeResponseAuthentication no
SSHEOF
      systemctl reload sshd
      c_green "PasswordAuthentication disabled. Key-only login enforced."
      c_green "Test from a NEW terminal to confirm access before closing this one."
    else
      c_yellow "Kept password authentication enabled."
    fi
  fi
}

# ─────────────────────────────────────────────────────────
# C) Timezone
# ─────────────────────────────────────────────────────────
fix_timezone() {
  c_blue "=== Section C: Fix server timezone ==="
  local CURRENT; CURRENT=$(timedatectl show --property=Timezone --value 2>/dev/null || cat /etc/timezone 2>/dev/null || echo "unknown")
  local TARGET="Asia/Riyadh"

  echo ""
  echo "  Current timezone : ${CURRENT}"
  echo "  Target timezone  : ${TARGET}  (Arabia Standard Time, UTC+3)"
  echo ""

  if [ "$CURRENT" = "$TARGET" ]; then
    c_green "Timezone is already ${TARGET}. Nothing to do."
    return
  fi

  if confirm "Set timezone to ${TARGET}?"; then
    timedatectl set-timezone "$TARGET"
    c_green "Timezone set to $(timedatectl show --property=Timezone --value)"
    echo "  Current time: $(date)"
  else
    c_yellow "Skipped timezone change."
  fi
}

# ─────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────
main() {
  require_root

  case "$SECTION" in
    identity)  rotate_identity ;;
    sshkey)    setup_sshkey ;;
    timezone)  fix_timezone ;;
    all)
      rotate_identity
      echo ""
      setup_sshkey
      echo ""
      fix_timezone
      ;;
    *)
      c_red "Unknown section: ${SECTION}"
      echo "Usage: sudo bash $0 [identity|sshkey|timezone|all]"
      exit 1
      ;;
  esac

  echo ""
  c_blue "═══════════════════════════════════════════════════════════════"
  c_blue " Phase 7 hardening complete."
  c_blue " Remaining: rotate 5 external API keys in Hostinger panel:"
  c_blue "   OpenAI · Gemini · Telegram Bot · Oxylabs · Nexos"
  c_blue " Set them as new env vars in Hostinger → Manage → Environment."
  c_blue "═══════════════════════════════════════════════════════════════"
}

main
