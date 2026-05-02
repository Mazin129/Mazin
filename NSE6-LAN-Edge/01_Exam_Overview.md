# NSE 6 — FortiNAC / LAN Edge Architect: Exam Overview

## Official Exam Blueprint (NSE6_FML-7.4)

| Domain | Weight | Key Topics |
|--------|--------|------------|
| FortiSwitch Deployment | ~25% | Managed mode, MCLAG, STP, VLANs |
| Wireless LAN (FortiAP) | ~25% | AP profiles, SSIDs, WPA3, WIDS |
| Network Access Control | ~20% | 802.1X, RADIUS, FortiAuthenticator |
| Security Fabric | ~15% | Topology, connectors, automation |
| FortiNAC | ~15% | Device profiling, policy enforcement |

---

## Domain 1: FortiSwitch Deployment

### Core Concepts
- **Managed vs Standalone mode**: FortiSwitch can be managed by FortiGate (Security Fabric) or standalone.
  - Managed: FortiLink protocol (802.1Q trunk between FGT and FSW)
  - Standalone: Full CLI/GUI access to FSW directly
- **FortiLink**: Dedicated interface on FortiGate. Can be physical or LAG.
- **MCLAG (Multi-chassis LAG)**: Two FortiSwitches act as one logical switch for upstream redundancy.

### VLAN Architecture
```
FortiGate
    │ FortiLink (trunk — all VLANs)
    │
FortiSwitch
    ├── Port 1  → VLAN 10 (Data)    untagged
    ├── Port 2  → VLAN 20 (Voice)   untagged
    ├── Port 3  → VLAN 10,20        trunk
    └── Port 4  → VLAN 30 (Mgmt)    untagged
```

### CLI Commands — FortiSwitch (Managed from FortiGate)
```bash
# List managed switches
get switch-controller managed-switch

# Show port VLAN assignment
config switch-controller managed-switch
    edit <switch-SN>
        config ports
            edit port1
                set vlan <vlan-name>
                set allowed-vlans <vlan-list>
            next
        end
    next
end

# MCLAG configuration
config switch-controller managed-switch
    edit <switch-SN>
        config ports
            edit port1
                set mclag-icl enable      # ICL port
            next
        end
    next
end
```

### STP (Spanning Tree)
- Default: MSTP on FortiSwitch
- FortiGate is always STP root by default when using managed switches
- Port states: Blocking → Listening → Learning → Forwarding

---

## Domain 2: Wireless LAN (FortiAP)

### AP Modes
| Mode | Description |
|------|-------------|
| Thin AP | Controlled by FortiGate/FortiWLC — default |
| FAP Local Bridge | Traffic bridges directly to local LAN |
| FAP Mesh | Wireless backhaul between APs |

### SSID Modes
| Mode | Traffic Path |
|------|-------------|
| Tunnel | All traffic tunneled to FortiGate (default) |
| Bridge | Traffic forwarded locally on AP |
| Mesh | Wireless backhaul |

### WPA3 / Security Standards
- **WPA3-Personal**: SAE (Simultaneous Authentication of Equals) — replaces PSK
- **WPA3-Enterprise**: 192-bit mode, CNSA suite
- **OWE (Opportunistic Wireless Encryption)**: Encryption without authentication (open networks)
- **PMF (Protected Management Frames)**: Mandatory in WPA3

### WIDS/WIPS
- **WIDS**: Wireless Intrusion Detection System
- Detects: Rogue APs, deauth floods, beacon floods, EAPOL replays
- **WIPS**: Active countermeasures — sends deauth to rogue clients

### FortiAP Profile Key Settings
```bash
config wireless-controller wtp-profile
    edit "Branch-AP-Profile"
        set ap-country US
        config platform
            set type FAP-431F
        end
        config radio 1
            set band 802.11ax-5G
            set channel-width 80MHz
            set vaps "Corporate-SSID" "Guest-SSID"
        end
    next
end
```

---

## Domain 3: Network Access Control (802.1X / FortiAuthenticator)

### 802.1X Authentication Flow
```
Client → Authenticator (FortiSwitch port) → RADIUS (FortiAuthenticator) → AD/LDAP
  EAP-Request         RADIUS Access-Request       LDAP Bind
  EAP-Response        RADIUS Access-Accept/Reject  
  EAP-Success         RADIUS VLAN Assignment (tunnel attrs)
```

### RADIUS Attributes for VLAN Assignment
```
Tunnel-Type         = VLAN (13)
Tunnel-Medium-Type  = IEEE-802 (6)
Tunnel-Private-Group-Id = <VLAN-ID>
```

### EAP Methods
| Method | Inner Auth | Certificate Required |
|--------|------------|---------------------|
| EAP-TLS | Certificates | Client + Server |
| PEAP-MSCHAPv2 | Username/Password | Server only |
| EAP-TTLS | Username/Password | Server only |
| EAP-FAST | Username/Password (PAC) | None (optional) |

### MAB (MAC Authentication Bypass)
- For devices that don't support 802.1X (printers, IoT)
- MAC address used as username AND password
- FortiAuthenticator can maintain MAC whitelist

---

## Domain 4: Security Fabric Integration

### Security Fabric Topology
```
FortiGate (Root)
├── FortiSwitch (via FortiLink)
├── FortiAP (via CAPWAP/DTLS)
├── FortiAuthenticator (REST API)
├── FortiAnalyzer (logging)
└── FortiClient EMS (endpoint visibility)
```

### Fabric Connectors
- **SDN Connectors**: AWS, Azure, GCP, VMware NSX
- **Threat Intelligence**: FortiGuard, MISP
- **ITSM**: ServiceNow, Jira

### Automation Stitches
- Trigger: Security rating failure, IOC match, new device
- Action: Quarantine device, email alert, webhook, script

---

## Domain 5: FortiNAC

### Device Profiling Methods
1. **SNMP traps** from network devices
2. **RADIUS accounting** 
3. **Passive fingerprinting** (DHCP, HTTP user-agent, OUI)
4. **Active scanning** (Nmap, WMI)

### Policy Types
| Policy | Enforcement |
|--------|-------------|
| Network Access Policy | VLAN assignment, ACL |
| Security Policy | Compliance check before admission |
| Isolation Policy | Non-compliant → remediation VLAN |

### FortiNAC Integration Points
- Reads port info from FortiSwitch/routers via SNMP
- Sends RADIUS CoA (Change of Authorization) to reassign VLANs
- Integrates with FortiGate Security Fabric for posture assessment
