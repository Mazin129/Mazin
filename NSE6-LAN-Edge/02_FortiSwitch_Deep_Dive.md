# FortiSwitch Deep Dive — NSE 6 LAN Edge

## FortiLink Architecture

### Physical Setup
```
FortiGate (FGT)          FortiSwitch (FSW)
┌─────────────┐          ┌──────────────────┐
│  port3 ─────┼──────────┼── internal1      │
│  (FortiLink)│  802.1Q  │  (uplink/trunk)  │
└─────────────┘  trunk   └──────────────────┘
```

### FortiLink Configuration (FortiGate CLI)
```bash
# Create FortiLink interface
config system interface
    edit "fortilink"
        set type fortilink
        set fortilink-split-interface disable
        set member "port3"
    next
end

# Enable switch-controller
config switch-controller global
    set ac-discovery-type auto
end
```

### Auto-discovery: FortiSwitch discovers FortiGate via LLDP on FortiLink port.

---

## MCLAG (Multi-Chassis LAG)

### Purpose
- Provides active/active redundancy at L2
- Two FortiSwitches appear as ONE logical switch to upstream devices
- Eliminates STP blocking on redundant links

### MCLAG Architecture
```
          FortiGate
         /         \
   FortiLink1    FortiLink2
       |               |
 FortiSwitch-A ─── FortiSwitch-B
  (ICL port)       (ICL port)
       \               /
        ─── LAG ───────
              |
          Server/AP
```

### Key Terms
| Term | Description |
|------|-------------|
| ICL | Inter-Chassis Link — trunk between two MCLAG peers |
| MCLAG trunk | LAG between MCLAG switch pair and downstream device |
| Peer-link | Same as ICL |
| MCLAG domain | Group of two switches forming MCLAG pair |

### FortiSwitch MCLAG CLI
```bash
# On FortiGate (managed switch config)
config switch-controller managed-switch
    edit "FSW-A-Serial"
        config ports
            edit "port24"
                set mclag-icl enable
            next
        end
    next
end

config switch-controller managed-switch
    edit "FSW-B-Serial"
        config ports
            edit "port24"
                set mclag-icl enable
            next
        end
    next
end
```

---

## VLAN Design Best Practices

### Recommended VLAN Scheme
| VLAN ID | Name | Purpose |
|---------|------|---------|
| 1 | default | Never use for production |
| 10 | Data | Corporate workstations |
| 20 | Voice | VoIP phones |
| 30 | Wireless | WiFi clients |
| 40 | Guest | Internet-only |
| 50 | IoT | Printers, cameras |
| 99 | Mgmt | Network device management |
| 100 | Quarantine | Non-compliant devices |

### Native VLAN Security
- **Always change native VLAN from 1** on trunk ports
- Disable unused ports: `set status down`
- Enable port security / sticky MAC where 802.1X is not deployed

---

## STP Configuration

### MSTP Regions
```bash
# FortiSwitch STP config (standalone)
config switch stp settings
    set status enable
    set revision 1
    set hello-time 2
    set max-age 20
    set forward-time 15
end

# Instance mapping
config switch stp instance
    edit 1
        set vlan-range "10 20 30"
        set priority 4096          # Make this SW root for inst 1
    next
    edit 2
        set vlan-range "40 50 99"
        set priority 8192
    next
end
```

### BPDU Guard / Root Guard
```bash
config switch-controller managed-switch
    edit <serial>
        config ports
            edit port1              # Access port facing endpoint
                set stp-bpdu-guard enable    # Drop BPDUs — prevent rogue SW
                set stp-root-guard enable    # Prevent this port becoming root
                set edge-port enable         # PortFast equivalent
            next
        end
    next
end
```

---

## Port Security & Storm Control

### MAC Limiting
```bash
config switch-controller managed-switch
    edit <serial>
        config ports
            edit port1
                set max-bundle 1
                set learning-limit 5       # Max 5 MACs per port
            next
        end
    next
end
```

### Storm Control
```bash
config switch-controller storm-control-policy
    edit "default-storm"
        set unknown-unicast-rate 200    # pps
        set unknown-multicast-rate 200
        set broadcast-rate 100
    next
end
```

---

## QoS (Quality of Service)

### 802.1p / DSCP Trust
```bash
config switch-controller managed-switch
    edit <serial>
        config ports
            edit port1
                set qos-policy "voice-qos"
            next
        end
    next
end

config switch-controller qos qos-policy
    edit "voice-qos"
        set trust-dot1p-map "default"
        set trust-ip-dscp-map "default"
    next
end
```

### CoS Queue Mapping (Voice Priority)
- Voice (DSCP EF / 46) → Queue 7 (highest)
- Signaling (DSCP CS3 / 24) → Queue 5
- Best Effort → Queue 0

---

## Diagnostics & Troubleshooting

### From FortiGate (Managed)
```bash
# Check switch connectivity
diagnose switch-controller switch-info port-stats <serial> <port>

# MAC address table
diagnose switch-controller switch-info mac-table <serial>

# LLDP neighbors
diagnose switch-controller switch-info lldp <serial>

# Check FortiLink status
diagnose netlink brctl host

# Switch log on FortiGate
execute log filter category event
execute log display
```

### From FortiSwitch CLI (direct)
```bash
# Interface stats
get switch interface
diagnose switch interface list

# STP state
get spanning-tree detail

# VLAN membership
get switch vlan

# Show connected devices
get switch mac-table all
```

### Common Issues
| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| Switch not discovered | FortiLink not in "fortilink" type | Recreate interface as fortilink type |
| Switch disconnects randomly | FortiLink goes down | Check physical link / LACP |
| 802.1X not working | RADIUS reachability | `diagnose test authserver radius` |
| VLAN traffic not passing | Native VLAN mismatch | Verify trunk config on both ends |
| STP loops | BPDU guard missing on access ports | Enable edge-port + BPDU guard |
