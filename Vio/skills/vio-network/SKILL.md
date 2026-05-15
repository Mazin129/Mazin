# Vio — Network & Security

> Load this skill when Mazin asks about networks, firewalls, Wi-Fi, VPN,
> routing, switching, NAC, SOC, alerts, incident response, hardening,
> CVEs, or vendor-specific configs (Fortinet, Cisco, MikroTik, Aruba).

---

## How to answer a troubleshooting question

Always follow this 3-step skeleton:

1. **Hypothesis** — what I think is happening, in one sentence.
2. **Proof** — the single command that would confirm or refute it.
3. **Fix** — the exact CLI block to apply IF the proof confirms.

If the user hasn't run command 2 yet, don't write the fix — make them
run it first. Don't guess past evidence.

---

## Standard triage trees (use these verbatim)

### "Internet is slow"

```
1) one user or many?
   one  -> client problem (Wi-Fi RSSI, NIC driver, DNS resolver, MTU)
   many -> upstream

2) Many users, same VLAN or different?
   same     -> AP/switch/VLAN issue
   different-> firewall, WAN, or DNS

3) WAN test (FortiGate CLI):
     get system performance status
     diagnose sys top-summary | head
     diagnose sniffer packet wan1 'icmp' 4 10
     execute ping 1.1.1.1
   high latency on WAN only      -> ISP, escalate
   clean WAN + slow internal     -> conserve mode / IPS engine / policy log

4) Health:
     diagnose hardware sysinfo memory
     diagnose hardware sysinfo conserve
     diagnose sys session full-stat

5) DNS quietly broken:
     execute dnsfilter test-domain google.com
     diagnose test application dnsproxy 2
```

### "VPN is up but no traffic"

```
1) Both phases up?    diagnose vpn tunnel list
2) Proxy IDs match exactly on both ends? (most common cause)
3) Route into the tunnel?  get router info routing-table all | grep <subnet>
4) Policy in BOTH directions, correct zones?
5) NAT disabled on the VPN policy?
6) Source from a host actually inside the local proxy ID:
     execute ping-options source <inside-ip>
     execute ping <remote-host>
7) Encrypted/decrypted counters increasing?
```

### "Wi-Fi client associates but no DHCP"

```
1) AP managed and operational?  get wireless-controller wtp
2) SSID has the correct VLAN tag (and dynamic VLAN attribute if RADIUS)?
3) FortiSwitch uplink trunk carries that VLAN?
4) DHCP server reachable from the VLAN SVI?
     execute ping-options source <svi-ip>
     execute ping <dhcp-server>
5) Sniff at the AP:
     diagnose sniffer packet any 'port 67 or port 68' 4 50
6) RADIUS attributes: Tunnel-Type=13, Tunnel-Medium-Type=6,
   Tunnel-Private-Group-Id=<vlan>
```

---

## Hardening checklists — give these on request

### FortiGate (edge/internet-facing)

- [ ] Admin GUI on a dedicated management interface, NOT on WAN
- [ ] `set admin-https-redirect enable`, disable plain HTTP
- [ ] Trusted hosts on every admin account
- [ ] MFA on every admin (FortiToken or TOTP)
- [ ] Default `admin` renamed, default password changed
- [ ] SSL inspection: full inspection egress, CA pushed to endpoints
- [ ] IPS profile on every WAN-facing policy
- [ ] Anti-Replay = strict at the internet edge
- [ ] DNS filter blocks newly-registered domains
- [ ] FortiAnalyzer or syslog/SIEM, disk-full = overwrite-oldest
- [ ] Encrypted config backup nightly, off-box
- [ ] HA secondary tested by quarterly failover

### FortiSwitch (managed)

- [ ] Native VLAN ≠ 1 and ≠ any production VLAN
- [ ] Edge ports: STP edge-port + BPDU guard + DHCP snooping + Dynamic ARP Inspection
- [ ] 802.1X on every user-facing port
- [ ] Storm control on broadcast/multicast/unknown-unicast
- [ ] Voice VLAN explicit, not "tag all"
- [ ] SNMPv3 only

### FortiAP

- [ ] WPA3-Personal or WPA3-Enterprise where supported; WPA2/3
  transition mode otherwise — never WPA2 alone in 2026
- [ ] PMF (802.11w) required
- [ ] WIDS profile attached; rogue AP suppression on your spectrum only
- [ ] Per-SSID category filtering for guest/IoT
- [ ] Captive portal + bandwidth shaper on guest

---

## CLI quick reference (memorize these — most-used)

```
# Show all sessions for one source IP
diagnose sys session filter src 10.10.17.42
diagnose sys session list

# Real-time packet capture
diagnose sniffer packet any 'host 10.10.17.42 and port 443' 4 0 a

# Which policy will a flow hit?
diagnose firewall iprope lookup <src-ip> <src-port> <dst-ip> <dst-port> <proto> <ingress-if>

# IPS + signature versions
diagnose autoupdate versions

# Drop counters
diagnose firewall iprope-count list

# Routing
get router info routing-table all
get router info bgp summary
get router info ospf neighbor
```

## Security-operations triage (alerts)

For each alert, walk these 6 steps and produce a 3-line note:

```
1) Identity — who/what? resolve IP/user to a known asset.
2) Action  — what TTP? map to ATT&CK technique ID.
3) Outcome — did it succeed? (auth log says yes? data egress observed?)
4) Scope   — any other hosts/users with the same TTP in the last 7 days?
5) Decision — close benign | investigate | contain | escalate.
6) Record — 3-line note even if benign.
```

| Log field | Common ATT&CK technique |
|-----------|-------------------------|
| FortiGuard `attack=*.Exploit.*` web | T1190 Exploit Public-Facing App |
| `attack=Microsoft.Windows.SMB.*` | T1210 Remote Service Exploitation |
| FortiAuth repeated 802.1X fail | T1110 Brute Force |
| DNS to newly-registered domain | T1071.004 DNS C2 |
| Outbound to known-bad geo at 03:00 | T1041 Exfil over C2 |

## Change-management micro-process

Use this every time:

```
1) State the change in one sentence.
2) Show current state ('show'/'get' output).
3) Propose the diff (CLI block).
4) Risk + rollback (one line each).
5) Apply during the change window.
6) Verify (the one command that proves it works).
7) Commit to memory (load vio-memory skill, write a fact).
```

## Incident severity (use ONE definition, stick to it)

| Sev | Definition | First action |
|-----|------------|--------------|
| 1 | Active compromise, data leaving | Isolate, page on-call, preserve evidence |
| 2 | Confirmed unauthorized access, no exfil yet | Contain, rotate creds, hunt |
| 3 | High-probability suspicious | Investigate within 1 hour |
| 4 | Likely benign, verify | Investigate within 8 hours |
| 5 | Policy/hygiene violation | Track in backlog |
