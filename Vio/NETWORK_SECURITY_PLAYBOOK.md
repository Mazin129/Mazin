# Vio — Network & Security Playbook

Vio should be able to *operate*, not just explain. This playbook is the
working knowledge it needs at its fingertips. Feed it into Vio's RAG store
and tag chunks with `playbook,network` or `playbook,security`.

---

## 1. Triage tree — "the internet is slow"

```
1) Is it one user or many?
   one  -> client problem (Wi-Fi RSSI, NIC, DNS resolver, MTU)
   many -> upstream

2) Many users — same VLAN or different?
   same     -> AP/switch/VLAN issue
   different-> firewall, WAN, or DNS

3) WAN test:
     diagnose sys top-summary | head
     diagnose sniffer packet wan1 'icmp' 4 10
     execute ping-options source <internal-ip>
     execute ping 1.1.1.1
   - high latency on WAN only      -> ISP, escalate
   - clean WAN, slow internal      -> conserve mode? IPS engine? policy log

4) FortiGate health:
     get system performance status
     diagnose sys session full-stat
     diagnose hardware sysinfo memory
   - CPU > 80% sustained           -> find top sessions
        diagnose sys session list | grep proto
   - conserve mode "yes"           -> memory pressure, restart problem
        diagnose hardware sysinfo conserve

5) DNS as the silent killer:
     execute dnsfilter test-domain google.com
     diagnose test application dnsproxy 2
```

## 2. Triage tree — "VPN is up but no traffic"

```
1) Phase 1 + Phase 2 both up?
     diagnose vpn ike gateway list
     diagnose vpn tunnel list
2) Proxy IDs match exactly on both ends?  (most common cause)
3) Route present pointing into the tunnel?
     get router info routing-table all | grep <remote-subnet>
4) Policy in BOTH directions, with the right zones?
5) NAT disabled on the VPN policy?
6) Source from a host actually in the local proxy ID:
     execute ping-options source <inside-ip>
     execute ping <remote-host>
7) Counter increasing?
     diagnose vpn tunnel list | grep -A2 "name=<tun>"
     -> npu_flag=00 means software path; check if NPU offload is required
```

## 3. Triage tree — "client associates to Wi-Fi but no DHCP"

```
1) AP managed and operational?
     get wireless-controller wtp
     diagnose wireless-controller wlac -c wtp
2) SSID has correct VLAN tag + dynamic VLAN if used?
3) FortiSwitch uplink trunk carries the VLAN?
     diagnose switch-controller switch-info port-stats <sw-sn>
4) DHCP server reachable from that VLAN?
     execute ping-options source <svi-of-vlan>
     execute ping <dhcp-server>
5) Sniff at the AP:
     diagnose sniffer packet any 'port 67 or port 68' 4 50
6) FortiAuthenticator/RADIUS sending the right VLAN attribute?
     - Tunnel-Type=13, Tunnel-Medium-Type=6, Tunnel-Private-Group-Id=<vlan>
```

## 4. Hardening checklist — FortiGate

- [ ] Admin GUI on a dedicated management interface, not WAN
- [ ] Trusted hosts set on every admin account
- [ ] MFA on every admin account (FortiToken or TOTP)
- [ ] `set admin-https-redirect enable` and disable HTTP entirely
- [ ] Default password for `admin` changed; rename admin account
- [ ] FortiGuard categories evaluated, not blanket-allowed
- [ ] SSL inspection: full inspection on egress, with CA pushed to clients
- [ ] IPS profile applied to every WAN-facing policy
- [ ] Anti-Replay = strict on internet edge
- [ ] DNS filter blocks newly-registered domains
- [ ] Logging to FortiAnalyzer (or syslog + SIEM) with disk full action = overwrite-oldest
- [ ] Config backup nightly, encrypted, off-box
- [ ] HA secondary tested by failover quarterly

## 5. Hardening checklist — FortiSwitch (managed)

- [ ] Native VLAN ≠ 1, and ≠ any production VLAN
- [ ] Edge ports: STP edge-port + BPDU guard + DHCP snooping + ARP inspection
- [ ] 802.1X on every user-facing port
- [ ] Voice VLAN explicit, not "tag everything"
- [ ] Storm control on broadcast/multicast/unknown-unicast
- [ ] LLDP-MED for phones/APs, plain LLDP elsewhere
- [ ] No SNMPv1/v2c — SNMPv3 only

## 6. Hardening checklist — FortiAP

- [ ] WPA3-Personal or WPA3-Enterprise where clients support it; WPA2/3
      transition mode otherwise — never WPA2 alone in 2026
- [ ] PMF (802.11w) required
- [ ] DTIM tuned (1–3) for mixed mobile/IoT
- [ ] Band steering on 6 GHz–capable APs
- [ ] WIDS profile attached; rogue AP suppression enabled if you own the spectrum
- [ ] Per-SSID FortiGuard category filtering for guest/IoT SSIDs
- [ ] Captive portal on guest, with bandwidth shaper

## 7. Security operations — daily alert triage

```
For each alert:
  1) Identity: who/what (user, host, IP) — resolve to a known asset
  2) Action: what did they do — map to ATT&CK technique ID
  3) Outcome: did it succeed (auth log says yes? data egress observed?)
  4) Scope: any other hosts/users showing the same TTP in last 7 days?
  5) Decision: close as benign | investigate | contain | escalate
  6) Record: every alert gets a 3-line note even if benign
```

Map Fortinet log fields → ATT&CK:

| Log field | Common technique |
|-----------|------------------|
| `attack=Microsoft.Windows.SMB.*` | T1210 Lateral Movement / Exploitation |
| `attack=*.Exploit.*` against web | T1190 Exploit Public-Facing App |
| FortiAuth repeated 802.1X fail | T1110 Brute Force |
| DNS to newly-registered domain | T1071.004 DNS C2 |
| Outbound to known-bad geo at 03:00 | T1041 Exfil over C2 |

## 8. Common CLI quick-reference

```bash
# Show all sessions for one source IP
diagnose sys session filter src 10.10.17.42
diagnose sys session list

# Real-time packet capture
diagnose sniffer packet any 'host 10.10.17.42 and port 443' 4 0 a

# Policy lookup (which policy will a flow hit?)
diagnose firewall iprope lookup <src-ip> <src-port> <dst-ip> <dst-port> <proto> <ingress-if>

# IPS engine + signature versions
diagnose autoupdate versions

# Drop counters by reason
diagnose firewall iprope-count list
diagnose sys session stat

# Routing
get router info routing-table all
get router info bgp summary
get router info ospf neighbor
diagnose ip rtcache list
```

## 9. Change-management micro-process (use this every time)

```
1) State the change in one sentence ("allow VLAN 30 to print server tcp/9100").
2) Show current state (the relevant `get` / `show` output).
3) Propose the diff (CLI block).
4) Risk + rollback (one-line each).
5) Apply during the change window.
6) Verify (the one command that proves it works).
7) Commit to memory (Vio records the change as a fact).
```

## 10. Incident severity (use ONE definition, stick to it)

| Sev | Definition | First action |
|-----|------------|--------------|
| 1 | Active compromise, data leaving | Isolate, page on-call, preserve evidence |
| 2 | Confirmed unauthorized access, no exfil yet | Contain, rotate creds, hunt |
| 3 | Suspicious — high probability of (1) or (2) | Investigate within 1 hour |
| 4 | Suspicious — likely benign, needs verification | Investigate within 8 hours |
| 5 | Policy or hygiene violation | Track in backlog |
