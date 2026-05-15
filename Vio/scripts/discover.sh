#!/usr/bin/env bash
# Vio VPS discovery — read-only.
# Prints a single redacted report you can paste back.
# It does NOT change any state. No sudo required for most checks.
#
# Usage:
#   bash discover.sh > vio-discovery.txt 2>&1
# Then share the file. Sensitive fields (public IPs, MACs) are redacted.

set -u
LC_ALL=C

hr() { printf '\n===== %s =====\n' "$*"; }
have() { command -v "$1" >/dev/null 2>&1; }
run()  { echo "\$ $*"; eval "$@" 2>&1 | sed -e 's/[0-9a-fA-F:]\{17\}/MAC-REDACTED/g'; echo; }

# Redact public IPv4 from output; keep RFC1918 + loopback visible.
redact() {
  sed -E '
    s/\b((10\.[0-9]+\.[0-9]+\.[0-9]+)|(172\.(1[6-9]|2[0-9]|3[01])\.[0-9]+\.[0-9]+)|(192\.168\.[0-9]+\.[0-9]+)|(127\.[0-9]+\.[0-9]+\.[0-9]+)|(169\.254\.[0-9]+\.[0-9]+))\b/&/g;
    s/\b([0-9]{1,3}\.){3}[0-9]{1,3}\b/PUB-IP-REDACTED/g
  '
}

{
echo "Vio discovery report   $(date -u +%FT%TZ)"
echo "host: $(hostname 2>/dev/null)"

hr "OS / kernel"
run "cat /etc/os-release"
run "uname -a"
run "uptime"

hr "CPU / memory / disk"
run "lscpu | sed -n '1,15p'"
run "free -h"
run "df -hT -x tmpfs -x devtmpfs"
run "lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT,RO"
have swapon && run "swapon --show"

hr "Network interfaces (MACs redacted)"
run "ip -br addr"
run "ip route"
have resolvectl && run "resolvectl status | sed -n '1,25p'"
[ -f /etc/resolv.conf ] && run "cat /etc/resolv.conf"

hr "Listening sockets"
if have ss; then run "ss -tulnp 2>/dev/null || ss -tuln"
elif have netstat; then run "netstat -tulnp 2>/dev/null || netstat -tuln"
fi

hr "Firewall"
have ufw       && run "ufw status verbose"        || echo "ufw: not installed"
have nft       && run "nft list ruleset 2>/dev/null | head -100" || echo "nft: not installed"
have iptables  && run "iptables -S | head -100"   || echo "iptables: not installed"
have firewall-cmd && run "firewall-cmd --state && firewall-cmd --list-all"

hr "SSH config (non-secret bits only)"
[ -f /etc/ssh/sshd_config ] && run "grep -Ei '^(port|permitrootlogin|passwordauthentication|pubkeyauthentication|allowusers|allowgroups|x11forwarding|maxauthtries|clientaliveinterval)' /etc/ssh/sshd_config"

hr "Users with login shells"
run "getent passwd | awk -F: '\$7 !~ /nologin|false/ {print \$1, \$3, \$6, \$7}'"
run "who -a 2>/dev/null | head"

hr "Sudoers (just file listing, no contents)"
run "ls -la /etc/sudoers.d/ 2>/dev/null"

hr "Cron / timers"
run "ls -la /etc/cron.* 2>/dev/null"
have systemctl && run "systemctl list-timers --all --no-pager 2>/dev/null | head -30"

hr "Key system services"
if have systemctl; then
  for s in ssh sshd nginx caddy apache2 httpd docker containerd podman \
           postgresql mysql mariadb redis-server mongod ollama \
           fail2ban unattended-upgrades ufw firewalld \
           cron crond systemd-journald; do
    state=$(systemctl is-active "$s" 2>/dev/null || true)
    enabled=$(systemctl is-enabled "$s" 2>/dev/null || true)
    [ -n "$state" ] && printf '  %-22s active=%-10s enabled=%s\n' "$s" "$state" "$enabled"
  done
fi

hr "Installed languages / runtimes"
for c in python3 python pip3 node npm pnpm yarn go rustc java php ruby perl; do
  have "$c" && printf '  %-10s %s\n' "$c" "$($c --version 2>&1 | head -1)"
done

hr "AI / agent stacks present"
for c in ollama llama-server vllm openwebui open-webui librechat n8n \
         docker docker-compose podman caddy nginx sqlite3 qdrant \
         chroma redis-cli psql mongo; do
  have "$c" && printf '  %-15s %s\n' "$c" "$(command -v $c)"
done
have docker && run "docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}' 2>/dev/null | head -30"
have docker && run "docker images --format 'table {{.Repository}}\t{{.Tag}}\t{{.Size}}' 2>/dev/null | head -30"

hr "Web servers — vhosts"
[ -d /etc/nginx ]  && run "ls /etc/nginx/sites-enabled/ /etc/nginx/conf.d/ 2>/dev/null"
[ -d /etc/caddy ]  && run "ls -la /etc/caddy/ 2>/dev/null"
[ -d /etc/apache2/sites-enabled ] && run "ls /etc/apache2/sites-enabled/ 2>/dev/null"

hr "Outbound connectivity tests"
have curl && {
  for u in https://api.anthropic.com https://api.openai.com https://nvd.nist.gov \
           https://fortiguard.fortinet.com https://github.com; do
    code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "$u" || echo timeout)
    printf '  %-45s HTTP %s\n' "$u" "$code"
  done
}

hr "Time / locale"
run "timedatectl 2>/dev/null || date"
run "locale | head"

hr "Security posture quick checks"
have getenforce && run "getenforce"
have aa-status  && run "aa-status --enabled 2>/dev/null && echo apparmor=enabled || echo apparmor=disabled"
[ -f /var/log/auth.log ] && echo "auth log size: $(stat -c%s /var/log/auth.log) bytes"
[ -f /var/log/secure   ] && echo "secure log size: $(stat -c%s /var/log/secure) bytes"

hr "Last 5 reboots"
have last && run "last -x reboot 2>/dev/null | head -5"

hr "Process tree (top 15 by RSS)"
run "ps -eo pid,user,rss,pcpu,comm --sort=-rss | head -15"

hr "Package manager + recent installs"
if have dpkg; then run "dpkg -l | wc -l && echo packages installed"; run "ls -lt /var/log/apt/history.log* 2>/dev/null | head -3"
elif have rpm;  then run "rpm -qa | wc -l && echo packages installed"
fi

echo
echo "---- end of report ----"
} | redact
