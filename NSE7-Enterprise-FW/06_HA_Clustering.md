# HA Clustering — NSE 7 Enterprise Firewall

## HA Overview

### HA Modes Comparison
| Feature | Active/Passive | Active/Active | FGSP |
|---------|---------------|---------------|------|
| Active units | 1 | All | All |
| Traffic distribution | Primary only | Load balanced | Load balanced |
| Session sync | Full | Partial | TCP/UDP state |
| Failover time | < 1 sec | < 1 sec | Sub-second |
| Configuration sync | Full | Full | No (independent) |
| Asymmetric routing | No | No | Yes |
| HA heartbeat required | Yes | Yes | No (uses network) |

---

## Active/Passive (A/P) Deep Dive

### Roles
- **Primary**: Handles ALL traffic, sends heartbeats, pushes config to secondary
- **Secondary**: Monitors heartbeats, stands by, syncs config from primary

### A/P Configuration
```bash
config system ha
    set mode a-p
    set group-id 10
    set group-name "FGT-HA"
    set password ENC <ha-password>
    set priority 200                    # Higher = primary
    set override enable                 # Return to primary after recovery
    set hbdev "port3" 50               # Heartbeat interface + priority
    set session-sync-dev "port3"        # Session sync on same heartbeat link
    set monitor "port1" "port2"         # Interfaces to monitor
    set pingserver-monitor-interface "port1"
    set pingserver-failover-threshold 1
    set unicast-hb enable               # Unicast heartbeat (recommended)
    set unicast-hb-peerip 10.1.1.2     # Secondary heartbeat IP
end
```

### Primary Election Criteria (in order)
1. **Override enabled**: Device with higher priority wins after recovery
2. **Priority**: Higher wins (default 128; range 1–255)
3. **Number of monitored interfaces up**: More up = preferred
4. **Uptime**: Longer uptime wins (if override disabled)
5. **Serial number**: Higher hex value wins (tiebreaker)

### Heartbeat
- Default: Every 200ms on heartbeat interfaces
- Dead time: 6 seconds (3 missed heartbeats × 2 sec = 6 sec)
- Interfaces dedicated to HA: Direct cross-over or dedicated switch
- **Never** put heartbeat interfaces on production VLANs

### Session Synchronization
```bash
# What IS synced:
# - TCP sessions (established)
# - UDP sessions
# - SNAT table
# - IPsec SAs
# - SSL-VPN tunnels
# - ARP table

# What is NOT synced:
# - Management sessions to FortiGate (SSH/HTTPS admin)
# - Local-out sessions
# - HA management interface sessions
```

### HA Management Interface
```bash
# Dedicate an interface for out-of-band management of each unit
config system ha
    set ha-mgmt-status enable
    config ha-mgmt-interfaces
        edit 1
            set interface "mgmt"
            set gateway 10.99.0.1
        next
    end
end

# Configure unique IPs for each unit
# Primary: 10.99.0.10
# Secondary: 10.99.0.11
```

---

## Active/Active Deep Dive

### A/A Load Distribution
```
                    Virtual IP (shared)
                         │
                    Virtual MAC
                         │
               ┌─────────┴──────────┐
          FGT-Primary           FGT-Secondary
          (processes own        (processes forwarded
           sessions)             sessions from primary)
```

### Session Distribution (SLB)
- Primary receives ALL sessions
- Distributes based on load-balance algorithm
- Secondary processes assigned sessions via HA link
- **Asymmetric risk**: If secondary fails, primary picks up all sessions

### A/A Configuration
```bash
config system ha
    set mode a-a
    set group-id 10
    set load-balance-all enable
    set arps 1
    set arps-interval 8
end
```

---

## FGSP (FortiGate Session Life Support Protocol)

### Use Case
- Asymmetric routing environments (traffic goes in on FGT-A, comes back on FGT-B)
- Carrier-grade deployments
- Independent FortiGates (no HA cluster, no shared config)
- Each FortiGate has its own management IP, config, policies

### FGSP Architecture
```
Router-A ──── FGT-A
   │              │← Session state sync via FGSP
Router-B ──── FGT-B
```

### FGSP Configuration
```bash
# On FGT-A
config system standalone-cluster
    set standalone-group-id 1
    set group-member-id 0              # This is member 0
    config cluster-peer
        edit 1
            set peerip 10.200.0.2      # FGT-B sync IP
        next
    end
end

config system session-sync
    edit 1
        set peerip 10.200.0.2
        set syncvd "root"
        set down-intfs-before-sess-sync enable
    next
end
```

---

## HA Upgrade Procedure

### Uninterrupted Upgrade (Recommended)
```
Step 1: Upgrade secondary (standby) first
         → Secondary downloads firmware, installs, reboots
         → Traffic stays on primary during secondary upgrade

Step 2: Force failover to secondary (now running new firmware)
         execute ha failover set 1

Step 3: Upgrade old primary (now secondary)
         → Installs firmware, reboots, rejoins cluster

Step 4: Force failover back to original primary (optional)
         execute ha failover unset 1

Best practice: Test failover before upgrade in maintenance window
```

### Firmware Upgrade Commands
```bash
# On secondary FortiGate (direct HA mgmt IP)
execute restore image ftp <firmware.out> <ftp-server>

# Verify firmware on each unit
get system status | grep Version

# Force failover (from primary)
execute ha failover set 1            # Force secondary to become primary
execute ha failover unset 1          # Revert
```

---

## HA Diagnostics

```bash
# HA status overview
get system ha status

# Sync status
diagnose sys ha dump-by dev

# Detailed member info
diagnose sys ha status

# Check heartbeat packets
diagnose debug application hatalk -1
diagnose debug enable

# HA session sync check
diagnose sys session
diagnose ha check-session-sync

# Show failover history
diagnose sys event | grep failover

# Check HA checksum (config sync verification)
diagnose sys ha checksum cluster

# Force sync config from primary to secondary
execute ha synchronize config
```

### HA Troubleshooting Guide
| Symptom | Cause | Fix |
|---------|-------|-----|
| Secondary won't join cluster | Group name/password mismatch | Verify `group-name` and `password` match |
| Config not syncing | Checksum mismatch | `execute ha synchronize config` |
| Split-brain | Heartbeat link down | Restore heartbeat connectivity |
| Failover not happening | Priority or override issues | Check `set override`, `set priority` |
| Sessions not resuming after failover | Session sync not enabled | Enable `session-sync-dev` |
| Management unreachable after failover | No HA mgmt interface | Configure dedicated HA mgmt |

---

## Virtual Clustering (VDOMs in HA)

### Purpose
- Different VDOMs can have different primary units
- VDOM1 active on FGT-A, VDOM2 active on FGT-B
- True active/active at VDOM level

```bash
config system ha
    set mode a-p
    config secondary-vcluster
        set vcluster-id 2
        set priority 200                # This FGT is primary for vcluster 2
        set monitor "port4"
        set vdom "DMZ-VDOM"
    end
end
```

---

## Remote Link Failover

### Monitoring Upstream Availability
```bash
config system ha
    set pingserver-monitor-interface "port1"
    set pingserver-slave-monitor-interface "port1"
    set pingserver-flip-timeout 60
end

config system link-monitor
    edit "ISP1-Monitor"
        set srcintf "wan1"
        set server "8.8.8.8" "1.1.1.1"
        set interval 500               # ms
        set failtime 3
        set recoverytime 5
        set ha-priority 10             # Reduce HA priority if link goes down
    next
end
```
