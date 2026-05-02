# FCSS Quick Reference Card

## Critical CLI Commands Cheatsheet

### System Status
```bash
get system status                          # FW model, firmware, serial
get hardware status                        # CPU, memory, disk
diagnose sys top                           # Process CPU/mem (like top)
get system performance status              # CPU%, mem%, session count
diagnose autoupdate status                 # FortiGuard update versions/times
```

### Interfaces & Routing
```bash
get system interface                       # All interface IPs/status
get router info routing-table all          # Full routing table
diagnose ip route list                     # Kernel routing table
get router info bgp summary                # BGP neighbor states
get router info bgp neighbors X.X.X.X received-routes
get router info bgp neighbors X.X.X.X advertised-routes
get router info ospf neighbor              # OSPF adjacencies
get router info ospf database             # OSPF LSDB
diagnose ip router bgp all enable         # BGP debug
diagnose ip router ospf all enable        # OSPF debug
```

### Firewall & Sessions
```bash
diagnose sys session list                  # Session table
diagnose sys session stat                  # Session stats (total, rates)
diagnose sys session filter src X.X.X.X   # Filter sessions
diagnose sys session clear                 # Clear all sessions
diagnose firewall iprope lookup S D P SP DP  # Policy lookup for 5-tuple
diagnose firewall auth list               # Active auth sessions (FSSO/portal)
```

### Debug Flow (Packet Trace)
```bash
diagnose debug flow filter addr X.X.X.X
diagnose debug flow filter proto 6
diagnose debug flow filter port 443
diagnose debug flow show console enable
diagnose debug flow show function-name enable
diagnose debug enable
diagnose debug flow trace start 100
# When done:
diagnose debug flow trace stop
diagnose debug disable
diagnose debug reset
```

### Packet Sniffer
```bash
# Levels: 1=IP hdr, 2=+hex, 3=+ascii, 4=full L2+hex+ascii, 6=full+checksum
diagnose sniffer packet port1 "host X.X.X.X" 4 100 l
diagnose sniffer packet any "port 443" 1 0 a   # all interfaces, count=∞
```

### VPN / IPsec
```bash
get vpn ipsec tunnel summary               # All tunnels status
diagnose vpn tunnel list name "tunnel-name"
diagnose vpn ike gateway flush name "tunnel-name"
diagnose vpn tunnel flush "p2-name"
diagnose debug application ike -1         # IKE debug
diagnose debug enable
get vpn ssl monitor                        # SSL-VPN active tunnels
```

### FortiSwitch (Managed)
```bash
get switch-controller managed-switch
diagnose switch-controller switch-info port-stats <SN> <port>
diagnose switch-controller switch-info mac-table <SN>
diagnose switch-controller switch-info lldp <SN>
diagnose switch-controller switch-info spanning-tree <SN>
execute switch-controller authorize <SN>
execute switch-controller get-conn-status
```

### Wireless
```bash
get wireless-controller wtp               # All APs and status
diagnose wireless-controller wlac -c sta  # All connected clients
diagnose wireless-controller wlac -c wtp  # AP details
diagnose wireless-controller wlac -d sta <MAC>
diagnose wireless-controller wlac -c rogue-ap
diagnose debug application cw_acd 0xff   # CAPWAP debug
```

### Authentication / RADIUS
```bash
diagnose test authserver radius <srv> <user> <pass>
diagnose test authserver ldap <srv> <user> <pass>
diagnose debug application fnbamd 255    # Auth daemon debug
diagnose debug enable
```

### High Availability
```bash
get system ha status                      # HA state and members
diagnose sys ha status                    # Detailed HA info
execute ha failover set 1                 # Force failover to secondary
execute ha failover unset 1               # Revert
execute ha synchronize config             # Force config sync
diagnose sys ha checksum cluster          # Verify config in sync
diagnose debug application hatalk -1     # HA heartbeat debug
```

### Security Fabric
```bash
diagnose sys csf topology                 # Fabric topology map
diagnose sys csf upstream                 # Upstream connection
diagnose sys csf check                    # Fabric health check
diagnose sys automation-stitch test <name>
```

### Logs
```bash
execute log filter category traffic
execute log filter category event
execute log filter category utm
execute log filter field srcip X.X.X.X
execute log display
```

---

## Key Port Numbers Reference

| Service | Protocol | Port |
|---------|----------|------|
| RADIUS Auth | UDP | 1812 |
| RADIUS Acct | UDP | 1813 |
| RADIUS CoA | UDP | 3799 |
| TACACS+ | TCP | 49 |
| IKE | UDP | 500 |
| NAT-T | UDP | 4500 |
| CAPWAP Control | UDP | 5246 |
| CAPWAP Data | UDP | 5247 |
| Security Fabric | TCP | 8013 |
| FSSO | TCP | 8000 |
| FortiAnalyzer log | TCP | 514 (OFTP) |
| Syslog | UDP | 514 |
| LDAP | TCP | 389 |
| LDAPS | TCP | 636 |
| BGP | TCP | 179 |
| OSPF | IP Protocol | 89 |

---

## Administrative Distance Reference

| Protocol | AD |
|----------|----|
| Connected | 0 |
| Static | 10 |
| eBGP | 20 |
| OSPF | 110 |
| RIP | 120 |
| iBGP | 200 |

---

## Common Exam Traps

| Topic | Common Wrong Answer | Correct Answer |
|-------|--------------------|-----------------|
| BGP outbound control | Local Preference | MED (sent to peer to influence inbound) |
| BGP inbound control | MED | Local Preference (affects local AS outbound) |
| CAPWAP control port | 5247 | 5246 (control), 5247 is data |
| RADIUS CoA port | 1812 | 3799 (RFC 3576) |
| Security Fabric port | 443 | 8013 |
| OSPF E1 vs E2 | E1 adds external cost only | E2 = flat cost, E1 = external + internal cost |
| HA session sync | All sessions synced | Management sessions and local-out NOT synced |
| WPA3 key exchange | 4-way handshake | SAE (Dragonfly) — no crackable handshake |
| Debug flow policy ID 0 | Allowed by implicit allow | DROPPED by implicit deny |
| FortiSwitch VLAN creation | Created on FSW CLI | Created as FGT interfaces, pushed via FortiLink |
| ADVPN requirement | Just `auto-discovery-sender` | ALSO needs `set net-device enable` |
| SSL VPN srcintf | `ssl-vpn` | `ssl.root` (the virtual SSL-VPN interface) |
| IPS `location server` | Blocks all traffic | Only blocks attacks targeting servers |

---

## Exam Day Strategy

### NSE 6 — LAN Edge
1. FortiSwitch VLAN architecture questions — know the CLI hierarchy
2. 802.1X flow — memorize RADIUS attributes for VLAN assignment
3. WPA3 differences — SAE, OWE, PMF modes
4. WIDS attack types — deauth flood vs rogue AP vs evil twin
5. Security Fabric port 8013 and requirements (FAZ needed for root)

### NSE 7 — Enterprise Firewall
1. BGP attributes — Local Pref (outbound) vs MED (inbound control)
2. OSPF area types — know LSA types blocked in each area
3. HA election order — priority → interfaces up → uptime (when override enabled)
4. Debug flow — know what each output line means
5. IPsec — "no proposal chosen" = Phase 1 proposal mismatch
6. SD-WAN SLA mode vs other modes
7. VDOM inter-communication via vdom-links — firewall policy needed in EACH VDOM
