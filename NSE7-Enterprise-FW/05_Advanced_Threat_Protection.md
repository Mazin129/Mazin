# Advanced Threat Protection — NSE 7 Enterprise Firewall

## SSL/TLS Inspection

### Why SSL Inspection Is Required
Over 80% of internet traffic is encrypted. Without inspection:
- Malware delivered over HTTPS bypasses AV/IPS
- Data exfiltration over encrypted channels goes undetected
- C2 (Command & Control) traffic hides in TLS

### SSL Inspection Modes
| Mode | Method | Performance | Visibility |
|------|--------|-------------|------------|
| Certificate Inspection | Check cert only (no decrypt) | High | Low |
| Deep Inspection (Proxy) | Full decrypt/re-encrypt (MitM) | Lower | Full |
| Deep Inspection (Flow) | Stream-based decryption | Medium | Good |

### Deep Inspection Architecture
```
Client → FortiGate (MITM) → Server
         ↓                    ↓
  Presents forged cert    Real cert verified
  signed by FGT CA       by FortiGate

Client must TRUST FortiGate CA certificate
(Deploy via GPO/MDM to all managed devices)
```

### SSL Profile Configuration
```bash
config firewall ssl-ssh-profile
    edit "Corp-Deep-Inspect"
        set comment "Full deep inspection for corporate users"
        set caname "Fortinet_CA_SSL"
        set untrusted-caname "Fortinet_CA_Untrusted"
        set ssl-anomalies-log enable
        set ssl-exemptions-log enable
        config https
            set ports 443 8443
            set status deep-inspection
            set proxy-after-tcp-handshake enable
        end
        config imaps
            set ports 993
            set status deep-inspection
        end
        config smtps
            set ports 465
            set status deep-inspection
        end
        config ssl-exempt
            edit 1
                set type wildcard-fqdn
                set wildcard-fqdn "*.banking-site.com"    # Exempt banking
            next
            edit 2
                set type category
                set category 6                             # Financial exempt
            next
        end
        config ssl-server
            edit 1
                set ip 10.10.10.50
                set ftps-client-cert-request bypass
                set https-client-cert-request bypass
            next
        end
    next
end
```

### Certificate Pinning Issues
Some applications (mobile banking, OS updates) use **certificate pinning** — they refuse connections where the certificate changes. These must be exempted from deep inspection.

```bash
config firewall ssl-ssh-profile
    edit "Corp-Deep-Inspect"
        config ssl-exempt
            edit 10
                set type cert-fingerprint
                set cert-fingerprint "SHA256:XXXXXXXXXXXX"    # Pin exemption
            next
        end
    next
end
```

---

## Intrusion Prevention System (IPS)

### IPS Architecture
```
Traffic → FortiGate → IPS Engine
                        ↓
              Signature Database (FortiGuard)
                        ↓
              Pattern Matching (protocol decoder)
                        ↓
              Action: Monitor / Block / Reset / Quarantine
```

### IPS Sensor Configuration
```bash
config ips sensor
    edit "Enterprise-IPS"
        set block-malicious-url enable
        set extended-log enable
        config entries
            # Block all critical severity, server-side attacks
            edit 1
                set location server
                set severity critical
                set action block
                set status enable
            next
            # Block high severity
            edit 2
                set location server client
                set severity high
                set action block
                set status enable
            next
            # Monitor medium severity
            edit 3
                set severity medium
                set action monitor
                set status enable
            next
            # Custom override for specific signature
            edit 100
                set rule 12345           # Signature ID
                set action block
                set packet-log enable    # Capture packets on trigger
                set status enable
            next
        end
    next
end
```

### IPS Bypass / Exemption
```bash
config ips sensor
    edit "Enterprise-IPS"
        config filter
            edit 1
                set name "Exempt-Scanner"
                set srcaddr "Vuln-Scanner-IP"
                set status disable       # Don't apply IPS to scanner
            next
        end
    next
end
```

### IPS Signatures Database
```bash
# Update IPS signatures
execute update-ips

# Check signature version
get system fortiguard

# List matching signatures
diagnose ips signature list
diagnose ips signature detail <sig-id>
```

---

## Application Control

### Application Categories (FortiGuard)
| Category | Examples | Default Action |
|----------|---------|---------------|
| Peer-to-Peer | BitTorrent, eMule | Block |
| Proxy | Ultrasurf, Tor | Block |
| Video/Audio | YouTube, Netflix | Monitor |
| Collaboration | Teams, Slack, Zoom | Allow |
| Cloud.IT | Dropbox, OneDrive | Monitor |
| Game | Online games | Block (work hours) |

### Application Control Profile
```bash
config application list
    edit "Corp-AppCtrl"
        set comment "Corporate application control"
        set unknown-application-action pass
        set unknown-application-log enable
        config entries
            # Block P2P
            edit 1
                set category 6         # Peer-to-Peer
                set action block
                set log enable
            next
            # Block proxy/anonymizers
            edit 2
                set category 7         # Proxy
                set action block
                set log enable
            next
            # Allow Office365 explicitly
            edit 3
                set application 31077 31078 31079    # O365 apps
                set action pass
            next
            # Rate-limit video streaming
            edit 4
                set category 8         # Video/Audio
                set action pass
                set per-ip-shaper "Video-10M"
            next
        end
    next
end
```

### Application Identification Methods
1. **Signature-based**: FortiGuard application signatures
2. **Port/Protocol**: Default app by port (L4)
3. **Behavioral**: Traffic pattern analysis
4. **SSL CN**: Certificate common name matching

---

## Antivirus

### AV Scan Modes
| Mode | Method | Performance | Detection |
|------|--------|-------------|-----------|
| Flow-based | Stream scan | Fast | Good |
| Proxy-based | Full file buffering | Slower | Best |
| Hybrid | Both | Balanced | Best |

### AV Profile Configuration
```bash
config antivirus profile
    edit "Corp-AV"
        set comment "Corporate AV profile"
        set feature-set flow          # or proxy
        config http
            set status enable
            set archive-block encrypted
            set archive-log encrypted infected
            set scan-archive-contents enable
        end
        config ftp
            set status enable
        end
        config smtp
            set status enable
            set executables virus
        end
        set av-virus-log enable
        set av-block-log enable
        config content-disarm
            set status enable         # CDR: remove active content from files
            set office-macro remove
            set office-hylink remove
            set pdf-javacode remove
        end
    next
end
```

### CDR (Content Disarm and Reconstruction)
- Strips active content from documents (macros, JavaScript, hyperlinks)
- Delivers clean document to user
- High-security environments: never block but always sanitize

---

## Web Filtering

### FortiGuard Web Categories
```bash
config webfilter profile
    edit "Corp-WebFilter"
        set comment "Corporate web filter"
        config ftgd-wf
            config filters
                # Block security-risk categories
                edit 1
                    set category 9         # Hacking
                    set action block
                next
                edit 2
                    set category 12        # Malware sites
                    set action block
                next
                # Warn social media
                edit 3
                    set category 26        # Social Networking
                    set action warning
                next
                # Monitor news
                edit 4
                    set category 19        # News
                    set action monitor
                next
            end
        end
        config override
            set ovrd-dur 00:30:00          # User can override for 30 min
            set ovrd-dur-mode constant
        end
        set log-all-url enable
        set web-content-log enable
        set web-filter-activex-log enable
        set web-filter-applet-log enable
    next
end
```

### DNS Filter
```bash
config dnsfilter profile
    edit "Corp-DNS-Filter"
        set comment "Block DNS-based C2 and malicious domains"
        set ftgd-dns enable
        config ftgd-dns
            config filters
                edit 1
                    set category 26        # Botnet C&C
                    set action block
                next
                edit 2
                    set category 27        # Malware
                    set action block
                next
            end
        end
        set sdns-ftgd-err-log enable
        set sdns-domain-log enable
        set block-botnet enable
    next
end
```

---

## FortiSandbox Integration (ATP)

### ATP Workflow
```
Suspicious file detected by AV
        ↓
File hash checked against FortiGuard cloud sandbox cache
        ↓ (if unknown)
File submitted to FortiSandbox
        ↓
Sandbox analyzes in isolated VM (Windows/Linux/Android)
        ↓
Verdict: Clean / Malicious / Risk
        ↓
Result returned to FortiGate → Block or allow
        ↓
Hash shared with Security Fabric (global threat intel)
```

### FortiSandbox Configuration
```bash
config system fortisandbox
    set status enable
    set server "sandbox.corp.local"
    set source-ip 10.0.0.1
    set ssl-min-proto-version TLSv1-2
    set interface-select-method auto
end

config antivirus profile
    edit "Corp-AV"
        config http
            set fortisandbox-error-optioncheck     # Hold file pending analysis
        end
        set fortisandbox-mode inline-block         # Block until verdict
    next
end
```

---

## Traffic Shaping & QoS

### Policy-Based Shaping
```bash
config firewall shaping-policy
    edit 1
        set name "Limit-YouTube"
        set service "HTTP" "HTTPS"
        set app-category 8             # Video/Audio
        set ip-version 4
        set traffic-shaper "YouTube-Shaper"
        set traffic-shaper-reverse "YouTube-Shaper"
        set srcintf "internal"
        set dstintf "wan1"
    next
end

config firewall shaper traffic-shaper
    edit "YouTube-Shaper"
        set guaranteed-bandwidth 5000   # 5 Mbps guaranteed
        set maximum-bandwidth 20000     # 20 Mbps max
        set priority low
        set per-policy enable
    next
end
```

---

## Diagnostics for UTM

```bash
# Check AV engine status
diagnose antivirus version
diagnose antivirus signature list

# IPS engine status
diagnose ips session list
diagnose ips anomaly list

# Web filter cache
diagnose webfilter cache stats
diagnose webfilter fortiguard stats

# Application control
diagnose application list

# SSL inspection debug
diagnose debug application ssl -1
diagnose debug enable

# See what profile is being applied to a session
diagnose sys session list | grep "policy_id"
```
