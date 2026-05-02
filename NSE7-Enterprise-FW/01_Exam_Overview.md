# NSE 7 — Enterprise Firewall Administrator: Exam Overview

## Official Exam Blueprint (NSE7_EFW-7.4)

| Domain | Weight | Key Topics |
|--------|--------|------------|
| Enterprise Firewall Architecture | ~20% | VDOMs, inter-VDOM routing, NGFW modes |
| Routing | ~20% | BGP, OSPF, policy-based routing, SD-WAN |
| VPN | ~15% | IPsec (dial-up, hub-spoke, ADVPN), SSL-VPN |
| High Availability | ~15% | A/P, A/A HA, session sync, FGSP |
| Advanced Threat Protection | ~15% | IPS, SSL inspection, application control, ATP |
| Authentication & Identity | ~10% | FSSO, RADIUS, SAML, captive portal |
| Troubleshooting | ~5% | Sniffer, debug flow, session table |

---

## Domain 1: Enterprise Firewall Architecture

### VDOM (Virtual Domain)
- Divides a single FortiGate into multiple independent virtual firewalls
- Each VDOM has its own: policies, routes, VPNs, admins, interfaces
- Use cases: Multi-tenant, role separation (DMZ/LAN/WAN), MSSP

```
FortiGate Physical
├── root VDOM       ← Default; manages fabric
├── LAN-VDOM        ← Internal network
├── DMZ-VDOM        ← Server farm
└── WAN-VDOM        ← Internet uplink
```

### VDOM Modes
| Mode | Description |
|------|-------------|
| NAT/Route | Default — FGT acts as L3 router/firewall |
| Transparent | FGT acts as L2 bridge — invisible to routing |

### Inter-VDOM Link
- Virtual interface pair connecting two VDOMs
- No physical cable required
- Appears as regular interfaces in each VDOM

```bash
config system vdom-link
    edit "vdom-link1"
    next
end
# Creates vdom-link1.0 and vdom-link1.1 interfaces
# Assign vdom-link1.0 to LAN-VDOM, vdom-link1.1 to WAN-VDOM
```

### NGFW Mode (Policy Mode)
| Mode | Policy Type | Profile-based or Policy-based |
|------|-------------|-------------------------------|
| Profile-based (default) | Traditional policies with UTM profiles | Profile-based |
| Policy-based (NGFW) | Application and user ID in policy | Policy-based — no UTM profiles |

```bash
config system settings
    set inspection-mode proxy        # or flow
    set ngfw-mode policy-based       # or profile-based
end
```

### Inspection Modes
| Mode | Depth | Performance | Certificate Visibility |
|------|-------|-------------|----------------------|
| Flow | Shallow — stream-based | High | Limited |
| Proxy | Deep — full reassembly | Lower | Full (SSL inspect) |

---

## Domain 2: Routing

### BGP (Border Gateway Protocol)

```bash
config router bgp
    set as 65001
    set router-id 1.1.1.1
    set ibgp-multipath enable
    set ebgp-multipath enable
    config neighbor
        edit "10.0.0.2"
            set remote-as 65002
            set activate enable
            set soft-reconfiguration enable
            set route-map-in "RM-IN-FILTER"
            set route-map-out "RM-OUT-FILTER"
        next
    end
    config network
        edit 1
            set prefix 192.168.0.0/16
        next
    end
end
```

#### BGP Attributes (decision order)
1. Weight (Cisco-specific / FortiGate local)
2. Local Preference (iBGP)
3. Locally Originated
4. AS Path length (shorter = preferred)
5. Origin (IGP < EGP < incomplete)
6. MED (lower = preferred)
7. eBGP over iBGP
8. IGP metric to next hop
9. Oldest eBGP route
10. Router ID (lower = preferred)

### OSPF

```bash
config router ospf
    set router-id 1.1.1.1
    config area
        edit 0.0.0.0
        next
        edit 0.0.0.1        # Stub area
            set type stub
            set default-cost 10
        next
    end
    config ospf-interface
        edit "internal"
            set interface "internal"
            set area "0.0.0.0"
            set network-type broadcast
            set priority 100        # Highest = DR
            set hello-interval 10
            set dead-interval 40
            set authentication md5
            set md5-keys ...
        next
    end
    config network
        edit 1
            set prefix 10.0.0.0/8
            set area "0.0.0.0"
        next
    end
end
```

#### OSPF Router Types
| Type | Description |
|------|-------------|
| Internal Router | All interfaces in one area |
| ABR | Connects multiple areas; has interface in area 0 |
| ASBR | Redistributes external routes into OSPF |
| Backbone Router | Has interface in area 0 |

#### OSPF Area Types
| Type | LSA Types Allowed | Default Route |
|------|------------------|---------------|
| Backbone (0) | 1,2,3,4,5 | No |
| Standard | 1,2,3,4,5 | No |
| Stub | 1,2,3 | Yes (injected by ABR) |
| Totally Stub | 1,2 | Yes |
| NSSA | 1,2,3,7 | Optional |
| Totally NSSA | 1,2,7 | Yes |

### Policy-Based Routing (PBR)
```bash
config router policy
    edit 1
        set input-device "port2"
        set srcaddr "Branch-Subnet"
        set protocol 6              # TCP
        set dst "0.0.0.0/0"
        set action permit
        set nexthop "203.0.113.1"   # Force to ISP2
        set gateway "203.0.113.1"
    next
end
```

---

## Domain 3: VPN

### IPsec IKEv2 Hub-and-Spoke

```bash
# Hub configuration (dialup server)
config vpn ipsec phase1-interface
    edit "ADVPN-Hub"
        set type dynamic            # Accepts dynamic peer IPs
        set interface "wan1"
        set ike-version 2
        set peertype any
        set net-device enable       # Required for ADVPN
        set add-route disable
        set auto-discovery-sender enable   # ADVPN
        set proposal aes256-sha256
        set dhgrp 14
        set psksecret <psk>
    next
end
```

### ADVPN (Auto-Discovery VPN)
- Spokes negotiate **shortcuts** directly with each other after initial traffic through hub
- Hub sends "shortcut offer" to both spokes
- Reduces latency for spoke-to-spoke traffic
- Requires `net-device enable` and `auto-discovery-sender/forwarder/receiver`

```
Spoke1 ──────► Hub ──────► Spoke2
              ↓ ADVPN shortcut negotiated
Spoke1 ◄──────────────────► Spoke2 (direct)
```

### SSL-VPN
```bash
config vpn ssl settings
    set servercert "Server-Cert"
    set tunnel-ip-pools "SSLVPN-POOL"
    set dns-server1 10.0.0.53
    set port 443
    set idle-timeout 300
end

config vpn ssl web portal
    edit "full-access"
        set tunnel-mode enable
        set web-mode enable
        set ip-pools "SSLVPN-POOL"
        set split-tunneling enable
        set split-tunneling-routing-address "Corp-Subnets"
    next
end
```

---

## Domain 4: High Availability

### HA Modes
| Mode | Active Units | Session Sync | Use Case |
|------|-------------|-------------|---------|
| Active/Passive (A/P) | 1 active + 1 standby | Yes | Standard failover |
| Active/Active (A/A) | Both active | Partial | Load distribution |
| FGSP | Independent units | Session-state sync | Asymmetric routing |

### A/P Configuration
```bash
config system ha
    set mode a-p
    set group-id 1
    set group-name "FGT-HA-Cluster"
    set password <ha-password>
    set hbdev "port3" 50 "port4" 50    # Heartbeat interfaces + priority
    set session-sync-dev "port3"
    set override enable
    set priority 200           # Higher = primary
    set monitor "port1" "port2"        # Monitored interfaces
end
```

### HA Failover Triggers
1. Physical link down on monitored interface
2. Heartbeat loss (dead-time exceeded)
3. Manual failover
4. Remote link failure (via remote link monitoring)

### Session Synchronization
- Syncs: TCP sessions, SNAT mappings, IPsec SAs, SSL-VPN sessions
- Does NOT sync: Local out traffic, management sessions to HA members
- Sync interface: dedicated heartbeat/HA link

### FGSP (FortiGate Session Life Support Protocol)
```bash
config system ha
    set session-pickup enable
    set session-pickup-delay enable
    config secondary-vcluster
        set override disable
    end
end

config system cluster-sync
    edit 1
        set peerip 10.0.0.2         # Peer FortiGate IP
        set syncvd "root"
    next
end
```

### Virtual MAC
- HA cluster uses virtual MAC addresses
- Upstream switches learn virtual MAC → no MAC flap on failover
- Virtual MAC: `00:09:0f:09:xx:xx` (xx = group-id based)

---

## Domain 5: Advanced Threat Protection

### SSL/TLS Inspection
```bash
# Deep inspection profile
config firewall ssl-ssh-profile
    edit "deep-inspect"
        set comment "Full SSL deep inspection"
        config https
            set ports 443
            set status deep-inspection
            set client-certificate bypass    # or inspect
        end
        config dot
            set status deep-inspection       # DNS over TLS
        end
        set caname "Fortinet_CA_SSL"        # FortiGate re-signing CA
        set untrusted-caname "Fortinet_CA_Untrusted"
    next
end
```

### IPS
```bash
config ips sensor
    edit "Enterprise-IPS"
        set block-malicious-url enable
        config entries
            edit 1
                set rule 12345          # Specific signature ID
                set action block
                set status enable
            next
            edit 2
                set location server
                set severity high critical
                set action block
                set status enable
            next
        end
    next
end
```

### Application Control
```bash
config application list
    edit "App-Control"
        set unknown-application-action pass
        config entries
            edit 1
                set category 6          # Peer-to-Peer
                set action block
            next
            edit 2
                set application 15832   # Facebook
                set action monitor
            next
        end
    next
end
```

---

## Domain 6: Troubleshooting

### Debug Flow (Packet Path Analysis)
```bash
# Trace specific traffic
diagnose debug flow filter addr 10.1.1.100
diagnose debug flow filter proto 6        # TCP
diagnose debug flow filter port 443
diagnose debug flow show console enable
diagnose debug flow show function-name enable
diagnose debug enable
diagnose debug flow trace start 100       # Capture 100 packets

# Stop debug
diagnose debug flow trace stop
diagnose debug disable
diagnose debug reset
```

### Packet Sniffer
```bash
# Capture on interface
diagnose sniffer packet port1 "host 10.1.1.100 and port 443" 4 100 l
# Format: interface filter verbose count timestamp
# Verbose: 1=header 2=header+hex 3=header+hex+ascii 4=full layer2
```

### Session Table
```bash
# Find specific session
diagnose sys session filter src 10.1.1.100
diagnose sys session filter dst 8.8.8.8
diagnose sys session list

# Clear sessions
diagnose sys session clear

# Session stats
diagnose sys session stat
```

### Policy Match Verification
```bash
# Check which policy matches
diagnose firewall iprope lookup 10.1.1.100 8.8.8.8 6 1234 443
# Returns: policy ID that matches this 5-tuple
```
