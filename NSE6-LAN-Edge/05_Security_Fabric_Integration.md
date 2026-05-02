# Security Fabric Integration — NSE 6 LAN Edge

## Security Fabric Overview

The Fortinet Security Fabric is a unified, cooperative security architecture where all Fortinet devices share:
- **Topology awareness** — every device knows the full network map
- **Threat intelligence** — IOC sharing in real-time
- **Centralized policy** — push config from FortiGate root
- **Automation** — stitches that trigger cross-device actions

### Fabric Roles
| Role | Description |
|------|-------------|
| Root FortiGate | Top of fabric; connects to FortiAnalyzer & FortiManager |
| Downstream FortiGate | Branch/segment FGTs; connect upstream to root |
| FortiSwitch | Managed via FortiLink; fabric member |
| FortiAP | Managed via CAPWAP; fabric member |
| FortiAuthenticator | REST API integration; identity provider |
| FortiClient EMS | Endpoint agent management; posture data |
| FortiAnalyzer | Log aggregation; threat correlation |
| FortiManager | Centralized config management |

---

## Fabric Setup Requirements

### Prerequisites
1. Root FortiGate must have FortiAnalyzer connected (logging required)
2. Each fabric member must trust the root FGT certificate
3. All devices must be on same management VLAN or routable
4. Security Fabric port: **TCP 8013** (between FGT members)

### Enable Security Fabric on Root FGT
```bash
config system csf
    set status enable
    set group-name "HQ-Fabric"
    set group-password <fabric-password>
    set upstream-ip 0.0.0.0          # Empty = this is root
    set fabric-object-unification default
    set saml-configuration-sync enable
    config trusted-list
        edit 1
            set authorization-type serial
            set serial "FGT60F-XXXXXXXXX"    # Downstream FGT serial
        next
    end
end
```

### Enable Security Fabric on Downstream FGT
```bash
config system csf
    set status enable
    set upstream-ip 10.0.0.1         # Root FGT IP
    set upstream-interface "wan1"
    set group-name "HQ-Fabric"
    set group-password <fabric-password>
end
```

---

## Fabric Topology Verification
```bash
# Show full fabric topology
diagnose sys csf topology

# Check upstream connection
diagnose sys csf upstream

# Fabric synchronization status
diagnose sys csf sync-status

# Sample output:
# Root: FGT-HQ (10.0.0.1) [CONNECTED]
#   ├── FGT-Branch1 (10.1.0.1) [CONNECTED]
#   └── FGT-Branch2 (10.2.0.1) [CONNECTED]
```

---

## Fabric Connectors

### SDN Connectors
```bash
config system sdn-connector
    edit "AWS-Prod"
        set type aws
        set access-key "AKIAXXXXXXXXXXXXXXXX"
        set secret-key <secret>
        set region "us-east-1"
        set update-interval 60
    next
end
```

### Dynamic Address Objects (from SDN)
```bash
config firewall address
    edit "AWS-WebServers"
        set type dynamic
        set sdn "AWS-Prod"
        set filter "Tag.Role=web-server"    # AWS Tag filter
    next
end
```

### Threat Intelligence Connectors
```bash
config system external-resource
    edit "Custom-IOC-Feed"
        set type ip
        set resource "https://threatfeed.example.com/ioc-ips.txt"
        set refresh-rate 60             # minutes
        set status enable
    next
end
```

---

## Automation Stitches

### Stitch: Quarantine on IOC Match
```bash
config system automation-trigger
    edit "IOC-Detected"
        set event-type ioc
        set ioc-level high
    next
end

config system automation-action
    edit "Quarantine-Host"
        set action-type quarantine
    next
end

config system automation-stitch
    edit "Auto-Quarantine-IOC"
        set status enable
        set trigger "IOC-Detected"
        config actions
            edit 1
                set action "Quarantine-Host"
                set delay 0
            next
        end
    next
end
```

### Stitch: Webhook on Security Rating Fail
```bash
config system automation-action
    edit "Notify-SIEM"
        set action-type webhook
        set uri "https://siem.corp.local/api/events"
        set http-body "{\"event\": \"%%log%%\", \"device\": \"%%serial%%\"}"
        set method post
    next
end
```

### Stitch: Email Alert on Admin Login
```bash
config system automation-trigger
    edit "Admin-Login"
        set event-type event-log
        set logid 44548              # Admin login event ID
    next
end

config system automation-action
    edit "Email-SecOps"
        set action-type email
        set email-to "secops@corp.local"
        set email-subject "FortiGate Admin Login: %%user%%"
        set message "Login from %%srcip%% at %%time%%"
    next
end
```

---

## Security Rating

### What It Checks
| Category | Example Checks |
|----------|---------------|
| Security Posture | Admin password strength, 2FA enabled |
| Fabric Coverage | All devices registered to fabric |
| Optimization | Unused policies, shadowed rules |
| Configuration | Logging to FAZ, NTP sync, firmware version |
| Compliance | Regulatory baseline (PCI, HIPAA, GDPR) |

### Accessing Security Rating
```
Security Fabric → Security Rating → Run Assessment
```

### Improving Score
```bash
# Enable 2FA for admin accounts
config system admin
    edit "admin"
        set two-factor fortitoken
        set fortitoken "FTKMOBILE-XXXXXXXX"
    next
end

# Enforce minimum password length
config system password-policy
    set status enable
    set min-length 12
    set must-contain upper-case-letter lower-case-letter number
    set change-4-time enable
end
```

---

## Zero Trust Network Access (ZTNA)

### ZTNA vs Traditional VPN
| Feature | VPN | ZTNA |
|---------|-----|------|
| Trust model | Trust after auth | Never trust, always verify |
| Access scope | Full network | Per-application |
| Posture check | Optional | Mandatory |
| Device identity | Username only | Device cert + posture |

### ZTNA Tags (from FortiClient EMS)
```bash
# EMS sends device posture as ZTNA tags to FortiGate
# Example tags:
#   OS-Windows-11, AV-Compliant, Patch-Current, Domain-Joined

config firewall policy
    edit 100
        set name "ZTNA-Corp-App"
        set srcintf "ssl-vpn-tunnel"
        set dstintf "internal"
        set srcaddr "Corp-ZTNA-Users"
        set dstaddr "Corp-App-Server"
        set ztna-status enable
        set ztna-tags "AV-Compliant" "Patch-Current"
        set action accept
    next
end
```

### ZTNA Access Proxy
```bash
config firewall access-proxy
    edit "Corp-Web-App"
        set vip "ZTNA-VIP"
        set client-cert enable
        config api-gateway
            edit 1
                set url-map "/"
                set service tcp-forwarding
                set realservers
                    edit 1
                        set ip 10.10.10.50
                        set port 443
                    next
                end
            next
        end
    next
end
```

---

## FortiClient EMS Integration

### EMS Connector on FortiGate
```bash
config endpoint-control fctems
    edit "Corp-EMS"
        set server "ems.corp.local"
        set https-port 443
        set serial-number "FEMS-XXXXXXXX"
        set fortinetone-cloud-authentication disable
        set status enable
    next
end
```

### Dynamic Address from EMS Tags
```bash
config firewall address
    edit "Compliant-Endpoints"
        set type dynamic
        set sdn "Corp-EMS"
        set filter "ztna-tag=AV-Compliant"
    next
end
```

---

## Fabric Diagnostics

```bash
# Full fabric health check
diagnose sys csf topology
diagnose sys csf upstream
diagnose sys csf check

# Automation stitch testing
diagnose sys automation-stitch test <stitch-name>

# SDN connector sync
diagnose sys sdn-connector refresh <connector-name>

# Security fabric certificate
diagnose debug application csfd 255
diagnose debug enable
```

### Fabric Event Logs
```bash
# Filter fabric-related events
execute log filter category event
execute log filter field subtype fabric
execute log display
```
