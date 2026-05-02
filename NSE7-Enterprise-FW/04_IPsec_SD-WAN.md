# IPsec VPN & SD-WAN Deep Dive — NSE 7 Enterprise Firewall

## IPsec Fundamentals

### IKE Phases
```
IKEv1 Phase 1 (Main Mode — 6 messages OR Aggressive Mode — 3 messages)
  → Negotiates: Encryption, Hash, DH group, lifetime
  → Authenticates: PSK or certificates
  → Result: ISAKMP SA (bidirectional)

IKEv1 Phase 2 (Quick Mode — 3 messages)
  → Negotiates: ESP/AH, encryption, hash, PFS, lifetime, selectors
  → Result: IPsec SA (unidirectional pair: inbound + outbound)

IKEv2 (4 messages total — IKE_SA_INIT + IKE_AUTH)
  → Combined phase 1+2 in fewer messages
  → Native support for EAP, MOBIKE, redirect
```

### Encryption Algorithms
| Algorithm | Key Size | Strength | Use |
|-----------|---------|---------|-----|
| AES-128-CBC | 128-bit | Good | General |
| AES-256-CBC | 256-bit | Strong | Compliance |
| AES-128-GCM | 128-bit | Strong + AEAD | IKEv2/preferred |
| AES-256-GCM | 256-bit | Strongest | High security |
| 3DES | 168-bit | Legacy/weak | Avoid |

### DH Groups
| Group | Algorithm | Bits | Recommendation |
|-------|-----------|------|----------------|
| 1 | MODP | 768 | Avoid |
| 2 | MODP | 1024 | Avoid |
| 5 | MODP | 1536 | Minimum |
| 14 | MODP | 2048 | Recommended |
| 19 | ECP | 256 | Preferred (ECDH) |
| 20 | ECP | 384 | High security |
| 21 | ECP | 521 | Maximum security |

---

## Site-to-Site IPsec (Static Peers)

### FortiGate A (HQ)
```bash
config vpn ipsec phase1-interface
    edit "HQ-to-Branch"
        set interface "wan1"
        set ike-version 2
        set keylife 86400
        set peertype one
        set remote-gw 198.51.100.5         # Branch public IP
        set proposal aes256gcm-prfsha256
        set dhgrp 19
        set psksecret <psk>
        set dpd on-idle
        set dpd-retryinterval 20
    next
end

config vpn ipsec phase2-interface
    edit "HQ-to-Branch-P2"
        set phase1name "HQ-to-Branch"
        set proposal aes256gcm
        set pfs enable
        set dhgrp 19
        set auto-negotiate enable
        set keylifeseconds 3600
        set src-subnet 10.0.0.0/8         # HQ interesting traffic
        set dst-subnet 192.168.10.0/24    # Branch subnet
    next
end
```

### Routing over IPsec (Recommended: Route-based VPN)
```bash
# Route-based: tunnel interface gets IP, route traffic through it
config system interface
    edit "HQ-to-Branch"
        set ip 169.254.0.1/30
        set remote-ip 169.254.0.2
        set type tunnel
    next
end

config router static
    edit 1
        set dst 192.168.10.0/24
        set device "HQ-to-Branch"
    next
end
```

---

## Hub-and-Spoke with ADVPN

### Hub FortiGate
```bash
config vpn ipsec phase1-interface
    edit "ADVPN-Hub"
        set type dynamic                    # Accept any peer IP
        set interface "wan1"
        set ike-version 2
        set peertype any
        set net-device enable               # Required for ADVPN
        set add-route disable               # Hub doesn't add spoke routes
        set auto-discovery-sender enable    # Hub sends shortcut offers
        set proposal aes256gcm-prfsha384
        set dhgrp 20
        set psksecret <psk>
        set dpd on-idle
    next
end

config vpn ipsec phase2-interface
    edit "ADVPN-Hub-P2"
        set phase1name "ADVPN-Hub"
        set proposal aes256gcm
        set auto-negotiate enable
        set keylifeseconds 3600
    next
end
```

### Spoke FortiGate
```bash
config vpn ipsec phase1-interface
    edit "ADVPN-Spoke"
        set type static
        set interface "wan1"
        set ike-version 2
        set remote-gw 203.0.113.1           # Hub public IP
        set net-device enable
        set auto-discovery-receiver enable  # Accept shortcut offers from hub
        set auto-discovery-forwarder enable # Forward traffic to trigger shortcuts
        set proposal aes256gcm-prfsha384
        set dhgrp 20
        set psksecret <psk>
    next
end
```

### BGP over ADVPN (spoke-to-spoke routing)
```bash
# On Hub — iBGP route reflector
config router bgp
    set as 65001
    set router-id 10.200.0.1
    config neighbor
        edit "0.0.0.0"                    # Dynamic neighbor template
            set remote-as 65001
            set route-reflector-client enable
            set interface "ADVPN-Hub"
            set update-source "ADVPN-Hub"
        next
    end
end

# On Spoke
config router bgp
    set as 65001
    set router-id 10.200.0.10
    config neighbor
        edit "10.200.0.1"                 # Hub tunnel IP
            set remote-as 65001
            set interface "ADVPN-Spoke"
        next
    end
    config network
        edit 1
            set prefix 192.168.10.0/24    # Advertise local subnet
        next
    end
end
```

---

## Dial-up VPN (Remote Access)

### IKEv2 with EAP (FortiClient)
```bash
config vpn ipsec phase1-interface
    edit "Remote-Access"
        set type dynamic
        set interface "wan1"
        set ike-version 2
        set peertype any
        set xauthtype auto
        set authmethod signature            # Certificate auth
        set eap enable
        set eap-identity send-request
        set certificate "Server-Cert"
        set proposal aes256gcm-prfsha384
        set dhgrp 20
        set mode-cfg enable                 # Assign IP to client
        set ipv4-start-ip 10.100.0.10
        set ipv4-end-ip 10.100.0.250
        set ipv4-netmask 255.255.255.0
        set dns-mode auto
        set assign-ip enable
    next
end
```

### Split Tunneling
```bash
config vpn ipsec phase1-interface
    edit "Remote-Access"
        set split-include-service "Corp-Subnets"    # Only these go through VPN
        set ipv4-split-include "Corp-Subnets"
    next
end
```

---

## SSL-VPN

### Web Mode vs Tunnel Mode
| Mode | Client Req | Access Scope | Port |
|------|-----------|-------------|------|
| Web Mode | Browser only | Web apps, RDP via portal | TCP 443 |
| Tunnel Mode | FortiClient | Full network access | TCP 443 (DTLS preferred) |
| Both | FortiClient | Full access + portal | TCP 443 |

### SSL-VPN Full Configuration
```bash
config vpn ssl settings
    set servercert "SSL-VPN-Cert"
    set port 10443
    set idle-timeout 600
    set login-timeout 30
    set tunnel-ip-pools "SSLVPN-POOL"
    set dns-server1 10.0.0.53
    set route-source-interface enable
end

config vpn ssl web portal
    edit "employee-portal"
        set tunnel-mode enable
        set web-mode enable
        set split-tunneling enable
        set split-tunneling-routing-address "Corp-Subnets"
        set ip-pools "SSLVPN-POOL"
        set host-check av
        set host-check-interval 300
    next
    edit "contractor-portal"
        set tunnel-mode disable
        set web-mode enable              # Web-only for contractors
        set ip-pools "Contractor-POOL"
    next
end

config vpn ssl web host-check-software
    edit "AV-Check"
        set type av
        set version "latest-defined"
        set interval 300
    next
end
```

### SSL-VPN Authentication with RADIUS
```bash
config vpn ssl settings
    set auth-timeout 300
end

config vpn ssl web user-group-bookmark
    edit "Corp-SSL-Users"
        set groups "Corp-VPN-Group"
    next
end

config firewall policy
    edit 50
        set name "SSL-VPN-Policy"
        set srcintf "ssl.root"
        set dstintf "internal"
        set srcaddr "SSLVPN-POOL"
        set dstaddr "Corp-Subnets"
        set groups "Corp-VPN-Group"
        set action accept
        set nat disable
    next
end
```

---

## IPsec Troubleshooting

### Debug IKE Negotiation
```bash
# IKEv2 debug
diagnose debug application ike -1
diagnose debug enable
# Initiate VPN or wait for peer
# Look for: IKE_SA_INIT, IKE_AUTH, CREATE_CHILD_SA messages

# Quick check of tunnel status
get vpn ipsec tunnel name "HQ-to-Branch"
get vpn ipsec tunnel summary

# SA details
diagnose vpn tunnel list name "HQ-to-Branch"

# Clear IKE SA and renegotiate
diagnose vpn ike gateway flush name "HQ-to-Branch"
diagnose vpn tunnel flush "HQ-to-Branch-P2"
```

### Common IPsec Issues
| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| Phase 1 fails | Proposal mismatch, PSK wrong, NAT-T needed | Match proposals exactly, enable nat-traversal |
| Phase 2 fails | Selector mismatch (interesting traffic) | Verify src/dst subnets match on both ends |
| Tunnel up but no traffic | Missing route or firewall policy | Add static route + bidirectional policy |
| Tunnel drops randomly | DPD timeout, ISP packet loss | Increase DPD retries, check ISP |
| ADVPN shortcuts not forming | net-device not enabled | Enable `set net-device enable` on both hub and spoke |

### NAT Traversal (NAT-T)
```bash
config vpn ipsec phase1-interface
    edit "HQ-to-Branch"
        set nattraversal enable        # Auto-detect NAT
        set keepalive 20               # NAT-T keepalive interval (seconds)
    next
end
```
- NAT-T encapsulates ESP in UDP 4500
- Required when either peer is behind NAT
