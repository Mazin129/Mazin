# VDOM Architecture — NSE 7 Enterprise Firewall

## VDOM Fundamentals

### Creating VDOMs
```bash
# Enable VDOM feature
config system global
    set vdom-mode multi-vdom
end

# Create VDOMs
config vdom
    edit "LAN-VDOM"
    next
    edit "DMZ-VDOM"
    next
    edit "WAN-VDOM"
    next
end

# Assign interface to VDOM
config system interface
    edit "port1"
        set vdom "LAN-VDOM"
        set ip 192.168.10.1/24
        set allowaccess ping https ssh
    next
    edit "port2"
        set vdom "WAN-VDOM"
        set ip 203.0.113.1/30
    next
end
```

### VDOM Admin Accounts
```bash
# Create VDOM-specific admin
config system admin
    edit "lan-admin"
        set password <password>
        set vdom "LAN-VDOM"          # Restricts admin to this VDOM
        set accprofile "prof_admin"
    next
end
```

---

## Inter-VDOM Routing

### Architecture Patterns

#### Pattern 1: Hub VDOM (WAN-VDOM routes between all VDOMs)
```
LAN-VDOM ──── vdom-link1 ──── WAN-VDOM ──── vdom-link2 ──── DMZ-VDOM
                                   │
                                 port2
                              (Internet)
```

#### Pattern 2: Full Mesh (each VDOM pair has direct link)
```
LAN-VDOM ──── vdom-link1 ──── DMZ-VDOM
    │                              │
vdom-link2                   vdom-link3
    │                              │
WAN-VDOM ──────────────────────────┘
```

### Inter-VDOM Link Configuration
```bash
# Create the link (creates paired interfaces: .0 and .1)
config system vdom-link
    edit "lan-to-wan"
    next
end

# Assign each end to a VDOM
config system interface
    edit "lan-to-wan.0"
        set vdom "LAN-VDOM"
        set ip 10.200.0.1/30
        set type vdom-link
    next
    edit "lan-to-wan.1"
        set vdom "WAN-VDOM"
        set ip 10.200.0.2/30
        set type vdom-link
    next
end

# Static route in LAN-VDOM pointing to WAN-VDOM
config router static
    edit 1
        set dst 0.0.0.0/0
        set gateway 10.200.0.2          # WAN-VDOM end of link
        set device "lan-to-wan.0"
    next
end
```

### Firewall Policy for Inter-VDOM Traffic
```bash
# In LAN-VDOM: allow LAN to exit toward WAN-VDOM
config firewall policy
    edit 1
        set name "LAN-to-WAN"
        set srcintf "port1"
        set dstintf "lan-to-wan.0"
        set srcaddr "LAN-Subnet"
        set dstaddr "all"
        set action accept
        set nat disable              # NAT handled in WAN-VDOM
    next
end

# In WAN-VDOM: NAT and route LAN traffic to Internet
config firewall policy
    edit 1
        set name "LAN-via-WAN-to-Internet"
        set srcintf "lan-to-wan.1"
        set dstintf "port2"
        set srcaddr "all"
        set dstaddr "all"
        set action accept
        set nat enable
    next
end
```

---

## NGFW Policy Mode

### Profile-based vs Policy-based
```
Profile-based (traditional):
  Policy → UTM profiles attached (AV, IPS, AppCtrl, WebFilter)
  Inspection: flow OR proxy per policy

Policy-based (NGFW):
  Policy → Application and User directly in policy source/destination
  All policies use flow inspection by default
  No UTM profiles — inline policy matching
```

### Switching to NGFW Mode
```bash
config system settings
    set vdom "root"
    set ngfw-mode policy-based
    set inspection-mode flow
end
```

### Policy-based NGFW Firewall Policy
```bash
config firewall policy
    edit 1
        set name "Allow-Office365"
        set srcintf "internal"
        set dstintf "wan1"
        set srcaddr "all"
        set dstaddr "all"
        set action accept
        set application 15839 15895 15905     # Office365 app IDs
        set internet-service-src-name "Fortinet-LAN-Subnets"
        set nat enable
    next
end
```

---

## Transparent Mode VDOM

### Use Case
- Insert FortiGate inline without changing IP addressing
- No routing changes on existing network
- Common for: IPS-only deployment, compliance inspection

### Transparent Mode Configuration
```bash
config system settings
    set vdom "DMZ-VDOM"
    set opmode transparent
    set manageip 10.10.10.10/24      # Management IP (out-of-band)
    set gateway 10.10.10.1
end

# Interfaces in transparent mode act as bridge ports
config system interface
    edit "port3"
        set vdom "DMZ-VDOM"
        set type physical
    next
    edit "port4"
        set vdom "DMZ-VDOM"
        set type physical
    next
end
```

### Transparent Mode Policy
```bash
config firewall policy
    edit 1
        set srcintf "port3"           # Upstream side
        set dstintf "port4"           # Downstream side
        set srcaddr "all"
        set dstaddr "all"
        set action accept
        set utm-status enable
        set ips-sensor "default"
        set ssl-ssh-profile "deep-inspect"
    next
end
```

---

## Virtual Wire Pair

### Use Case
- Bump-in-the-wire inspection without configuration complexity of transparent mode
- FortiGate passes traffic invisibly at L2
- Supports VLAN pass-through

```bash
config system virtual-wire-pair
    edit "vwire1"
        set member "port5" "port6"
        set wildcard-vlan enable
    next
end

config firewall policy
    edit 100
        set srcintf "port5"
        set dstintf "port6"
        set srcaddr "all"
        set dstaddr "all"
        set action accept
        set utm-status enable
        set ips-sensor "default"
    next
    edit 101
        set srcintf "port6"
        set dstintf "port5"
        set srcaddr "all"
        set dstaddr "all"
        set action accept
        set utm-status enable
        set ips-sensor "default"
    next
end
```

---

## Traffic Shaping (QoS)

### Shaping Policies
```bash
# Traffic shaper
config firewall shaper traffic-shaper
    edit "VoIP-Shaper"
        set guaranteed-bandwidth 2000   # kbps
        set maximum-bandwidth 5000
        set priority high
        set per-policy enable
    next
end

# Shaping policy (applied before firewall policy lookup)
config firewall shaping-policy
    edit 1
        set name "Prioritize-VoIP"
        set srcintf "internal"
        set dstintf "wan1"
        set srcaddr "all"
        set dstaddr "all"
        set service "VOIP"
        set traffic-shaper "VoIP-Shaper"
        set traffic-shaper-reverse "VoIP-Shaper"
    next
end
```

### Per-IP Shaping
```bash
config firewall shaper per-ip-shaper
    edit "Per-User-10M"
        set max-bandwidth 10240         # kbps per IP
        set max-concurrent-session 1000
    next
end
```

---

## Diagnostics

```bash
# List VDOMs
get system vdom

# Switch VDOM context in CLI
config global                    # Global context
config vdom
    edit "LAN-VDOM"             # Enter VDOM context

# Show VDOM resource usage
get system vdom-link
diagnose sys vd list
diagnose sys vd detail root

# Inter-VDOM link stats
get system interface vdom-link1.0
diagnose netlink interface list vdom-link1.0

# VDOM routing table
get router info routing-table all

# Check policy hits per VDOM
diagnose firewall iprope list 100    # Policy table in hex
```
