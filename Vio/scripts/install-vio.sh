#!/usr/bin/env bash
# Install / refresh Vio skills into an openclaw deployment.
#
# What it does:
#   1. Verifies openclaw layout under /docker/openclaw-5sds/.
#   2. Backs up the current openclaw.json (a fifth backup, openclaw rotates 4).
#   3. Clones (or pulls) the Mazin repo into /data/.openclaw/workspace/Mazin.
#   4. Symlinks the four Vio skill folders into /data/.openclaw/skills/.
#   5. Enables them inside openclaw.json (skills.entries) via jq.
#   6. Restarts the openclaw container.
#   7. Prints a verification summary.
#
# Read-only changes are preceded by a "PLAN" output. The script asks for
# 'apply' confirmation before any state change. Safe to re-run; idempotent.
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/Mazin129/Mazin.git}"
BRANCH="${BRANCH:-claude/enhance-vio-agent-ny2BM}"

OC_ROOT="/docker/openclaw-5sds"
DATA="${OC_ROOT}/data"
OC_DIR="${DATA}/.openclaw"
SKILLS_DIR="${OC_DIR}/skills"
WORKSPACE="${OC_DIR}/workspace"
CFG="${OC_DIR}/openclaw.json"
CONTAINER="openclaw-5sds-openclaw-1"

VIO_SKILLS=(vio vio-network vio-family vio-fortinet-study vio-memory)

c_red()   { printf '\033[31m%s\033[0m\n' "$*"; }
c_green() { printf '\033[32m%s\033[0m\n' "$*"; }
c_blue()  { printf '\033[34m%s\033[0m\n' "$*"; }
c_yellow(){ printf '\033[33m%s\033[0m\n' "$*"; }

require_root() {
  if [ "$(id -u)" -ne 0 ]; then
    c_red "Run with sudo: sudo bash $0"
    exit 1
  fi
}

require_layout() {
  for p in "$OC_ROOT" "$DATA" "$OC_DIR" "$CFG"; do
    if [ ! -e "$p" ]; then
      c_red "Missing: $p"
      c_red "This script expects Hostinger's hvps-openclaw at /docker/openclaw-5sds."
      exit 1
    fi
  done
}

ensure_tools() {
  local missing=()
  for t in jq git docker; do
    command -v "$t" >/dev/null || missing+=("$t")
  done
  if [ ${#missing[@]} -gt 0 ]; then
    c_yellow "Installing: ${missing[*]}"
    apt-get update -qq
    apt-get install -y -qq "${missing[@]}"
  fi
}

clone_or_update_repo() {
  local dest="${WORKSPACE}/Mazin"
  if [ -d "${dest}/.git" ]; then
    c_blue "Updating workspace repo..."
    git -C "$dest" fetch --depth=1 origin "$BRANCH"
    git -C "$dest" checkout -q "$BRANCH"
    git -C "$dest" reset --hard "origin/${BRANCH}"
  else
    c_blue "Cloning workspace repo..."
    mkdir -p "$WORKSPACE"
    git clone --depth=1 -b "$BRANCH" "$REPO_URL" "$dest"
  fi
  chown -R "$(stat -c %u "$DATA"):$(stat -c %g "$DATA")" "$dest"
}

link_skills() {
  mkdir -p "$SKILLS_DIR"
  for s in "${VIO_SKILLS[@]}"; do
    local src="${WORKSPACE}/Mazin/Vio/skills/${s}"
    local dst="${SKILLS_DIR}/${s}"
    if [ ! -d "$src" ]; then
      c_red "Skill source missing: $src"; exit 1
    fi
    if [ -L "$dst" ] || [ -e "$dst" ]; then
      rm -rf "$dst"
    fi
    ln -s "$src" "$dst"
    c_green "linked: $dst → $src"
  done
}

backup_config() {
  local stamp; stamp="$(date -u +%Y%m%dT%H%M%SZ)"
  local b="${CFG}.bak-vio-${stamp}"
  cp -a "$CFG" "$b"
  c_green "backup: $b"
  jq empty "$b" || { c_red "Backup not valid JSON — aborting."; exit 1; }
}

enable_in_config() {
  local tmp; tmp="$(mktemp)"
  jq \
    --arg s1 vio \
    --arg s2 vio-network \
    --arg s3 vio-family \
    --arg s4 vio-fortinet-study \
    --arg s5 vio-memory \
    '.skills //= {entries:{}} |
     .skills.entries //= {} |
     .skills.entries[$s1] = {enabled:true} |
     .skills.entries[$s2] = {enabled:true} |
     .skills.entries[$s3] = {enabled:true} |
     .skills.entries[$s4] = {enabled:true} |
     .skills.entries[$s5] = {enabled:true} |
     .skills.load //= {} |
     .skills.load.extraDirs //= [] |
     (.skills.load.extraDirs |= (. + ["/data/.openclaw/skills"] | unique)) |
     .tools.web.search.enabled = true |
     .tools.web.fetch.enabled = true' \
     "$CFG" > "$tmp"
  jq empty "$tmp"   # validate
  mv "$tmp" "$CFG"
  chown "$(stat -c %u "$DATA"):$(stat -c %g "$DATA")" "$CFG"
  chmod 600 "$CFG"
  c_green "config updated: skills enabled, web search/fetch turned on"
}

restart_container() {
  c_blue "Restarting openclaw container..."
  docker restart "$CONTAINER" >/dev/null
  sleep 3
  docker ps --filter "name=^/${CONTAINER}\$" --format 'table {{.Names}}\t{{.Status}}'
}

verify() {
  c_blue "Verification:"
  echo "--- skills folder ---"
  ls -la "$SKILLS_DIR"
  echo "--- enabled in config ---"
  jq '.skills.entries' "$CFG"
  echo "--- workspace repo ---"
  ls "${WORKSPACE}/Mazin" 2>/dev/null | head
  echo "--- container ---"
  docker logs --tail 20 "$CONTAINER" 2>&1 | tail -20
}

plan() {
  cat <<EOF
─────────────────────────────────────────────────────────────
  Vio install plan
─────────────────────────────────────────────────────────────
  Source repo : ${REPO_URL}
  Branch      : ${BRANCH}
  Workspace   : ${WORKSPACE}/Mazin   (git clone or pull)
  Skills      : ${SKILLS_DIR}/{${VIO_SKILLS[*]}}  (symlinks)
  Config      : ${CFG}
                - back up to ${CFG}.bak-vio-<timestamp>
                - enable skills: ${VIO_SKILLS[*]}
                - turn ON tools.web.search + tools.web.fetch
  Container   : restart ${CONTAINER}
─────────────────────────────────────────────────────────────
EOF
}

main() {
  require_root
  require_layout
  ensure_tools
  plan
  printf 'Type "apply" to proceed, anything else to abort: '
  read -r answer
  if [ "$answer" != "apply" ]; then
    c_yellow "Aborted. No changes made."
    exit 0
  fi
  clone_or_update_repo
  link_skills
  backup_config
  enable_in_config
  restart_container
  verify
  c_green "Done. Open https://openclaw-5sds.srv1671720.hstgr.cloud/ and ask Vio anything."
}

main "$@"
