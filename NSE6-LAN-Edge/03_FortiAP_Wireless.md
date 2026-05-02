# FortiAP Wireless Deep Dive — NSE 6 LAN Edge

## CAPWAP Protocol (Control and Provisioning of Wireless APs)

### CAPWAP Channels
| Channel | Port | Protocol | Purpose |
|---------|------|----------|---------|
| Control | UDP 5246 | DTLS encrypted | Config, management |
| Data | UDP 5247 | Optional DTLS | Data plane (tunnel mode) |

### AP Discovery Sequence
1. AP broadcasts CAPWAP Discovery Request (UDP 5246)
2. FortiGate responds with Discovery Response
3. AP sends Join Request → FortiGate sends Join Response
4. DTLS tunnel established → Config pushed
5. AP becomes **Online**

### DTLS Encryption
```bash
# Enforce DTLS on control channel (default: enabled)
config wireless-controller timers
    set discovery-interval 5
end

# Verify DTLS on data channel
config wireless-controller wtp-profile
    edit "profile-name"
        set dtls-policy dtls-enabled    # Options: clear-text | dtls-enabled
    next
end
```

---

## Radio Configuration

### 802.11 Standards Comparison
| Standard | Band | Max Speed | Key Feature |
|----------|------|-----------|-------------|
| 802.11a | 5 GHz | 54 Mbps | Legacy |
| 802.11g | 2.4 GHz | 54 Mbps | Legacy |
| 802.11n (WiFi 4) | 2.4/5 GHz | 600 Mbps | MIMO |
| 802.11ac (WiFi 5) | 5 GHz | 6.9 Gbps | MU-MIMO, beamforming |
| 802.11ax (WiFi 6) | 2.4/5/6 GHz | 9.6 Gbps | OFDMA, BSS coloring |
| 802.11be (WiFi 7) | 2.4/5/6 GHz | 46 Gbps | MLO, 4096-QAM |

### Channel Width Tradeoffs
| Width | Throughput | Interference Risk | Use Case |
|-------|-----------|-------------------|---------|
| 20 MHz | Low | Low | High-density |
| 40 MHz | Medium | Medium | Mixed |
| 80 MHz | High | High | Low-density/backhaul |
| 160 MHz | Highest | Very High | Point-to-point only |

---

## AP Profiles

### WTP Profile (AP Hardware Profile)
```bash
config wireless-controller wtp-profile
    edit "FAP-431F-Profile"
        set ap-country US
        set handoff-rssi 25          # dBm threshold for roaming
        set handoff-sta-thresh 55    # % load before offload
        config platform
            set type FAP-431F
        end
        config radio 1
            set mode ap
            set band 802.11ax-5G
            set channel "36" "40" "44" "48"
            set channel-width 80MHz
            set auto-power-level enable
            set auto-power-high 17   # max dBm
            set auto-power-low 10    # min dBm
            set vaps "Corporate" "Guest"
        end
        config radio 2
            set mode ap
            set band 802.11ax-2.4G
            set channel "1" "6" "11"
            set channel-width 20MHz
            set vaps "IoT"
        end
    next
end
```

---

## SSID / VAP Configuration

### Corporate SSID (WPA3-Enterprise)
```bash
config wireless-controller vap
    edit "Corporate"
        set ssid "CorpWLAN"
        set security wpa3-enterprise
        set encrypt AES
        set pmf enable
        set radius-server "FortiAuth-RADIUS"
        set vlanid 30
        set traffic-mode tunnel
        set intra-vap-privacy enable     # Block client-to-client
    next
end
```

### Guest SSID (WPA3-Personal / Captive Portal)
```bash
config wireless-controller vap
    edit "Guest"
        set ssid "Guest-WiFi"
        set security captive-portal
        set captive-portal-fw-accounting enable
        set vlanid 40
        set traffic-mode tunnel
        set schedule "business-hours"    # Time-based availability
        set quarantine enable
    next
end
```

### IoT SSID (WPA2-Personal / Isolated)
```bash
config wireless-controller vap
    edit "IoT"
        set ssid "IoT-Network"
        set security wpa2-only-personal
        set passphrase "Str0ng-IoT-Key!"
        set vlanid 50
        set intra-vap-privacy enable
        set local-bridging disable       # Force tunnel to FGT
    next
end
```

---

## WPA3 Deep Dive

### SAE (Simultaneous Authentication of Equals)
- Replaces 4-way handshake PSK
- **Forward secrecy**: Past sessions can't be decrypted if key is compromised
- **Offline dictionary attack resistant**: No way to collect handshake for offline cracking
- Uses **Dragonfly** key exchange (password-based Diffie-Hellman)

### OWE (Opportunistic Wireless Encryption)
- Open network with encryption (no authentication)
- Protects against passive eavesdropping on open networks
- Each client gets unique encryption key
- Replaces legacy "Open" SSIDs
- Transition mode: Broadcasts both OWE and Open SSIDs simultaneously

### PMF (Protected Management Frames) — 802.11w
| Mode | Behavior |
|------|---------|
| disabled | No PMF (vulnerable to deauth attacks) |
| optional | PMF negotiated if client supports it |
| required | All clients must use PMF (WPA3 default) |

---

## WIDS/WIPS Policies

### WIDS Detection Capabilities
```
Attack Type              Detection Method
─────────────────────────────────────────
Rogue AP                 SSID/BSSID not in allowed list
Rogue AP-on-wire         Same SSID, different BSSID on wire
Deauth flood             > threshold deauth frames/second
Beacon flood             > threshold beacons from same BSSID
EAPOL replay attack      Repeated EAPOL handshake frames
Weak WEP IV attack       WEP IV patterns
Spoofed deauth           Management frame from unknown BSSID
Hotspot interference     Evil twin detection
```

### WIDS Profile Configuration
```bash
config wireless-controller wids-profile
    edit "Enterprise-WIDS"
        set ap-scan enable
        set ap-bgscan-report-intv 30
        set deauth-unknown-src-thresh 10    # deauths/s = attack
        set rogue-scan enable
        set eapol-fail-flood enable
        set eapol-fail-intv 1
        set eapol-fail-thresh 10
        set spoofed-deauth enable
    next
end

# Assign WIDS profile to AP profile
config wireless-controller wtp-profile
    edit "FAP-431F-Profile"
        set wids-profile "Enterprise-WIDS"
    next
end
```

### WIPS (Active Countermeasures)
```bash
config wireless-controller wtp-profile
    edit "FAP-431F-Profile"
        config radio 1
            set wids-profile "Enterprise-WIDS"
        end
    next
end

# Rogue AP containment — sends deauth to rogue clients
config wireless-controller setting
    set rogue-scan enable
    set phishing-ssid-detect enable
end
```

---

## Roaming Technologies

### Fast Roaming (802.11r — FT)
- Reduces roaming time from ~50ms to ~2ms
- Pre-authenticates to target AP before roaming
- **FT over the Air**: Client communicates directly with target AP
- **FT over DS**: Client communicates via current AP

### 802.11k (Neighbor Reports)
- AP tells clients about nearby APs
- Client makes informed roaming decisions

### 802.11v (BSS Transition Management)
- AP can "push" client to roam (load balancing)

### FortiGate Roaming Config
```bash
config wireless-controller vap
    edit "Corporate"
        set fast-bss-transition enable      # 802.11r
        set ft-mobility-domain 1000
        set ft-r0-key-lifetime 9999
        set ft-over-ds enable
        set bss-transition enable           # 802.11v
    next
end
```

---

## Wireless Diagnostics

```bash
# List all managed APs
get wireless-controller wtp

# Show AP status
diagnose wireless-controller wlac -c wtp

# List connected clients
diagnose wireless-controller wlac -c sta

# Check specific client
diagnose wireless-controller wlac -d sta <MAC>

# AP event log
diagnose wireless-controller wlac -c sta-stats

# CAPWAP debug
diagnose debug application cw_acd 0xff
diagnose debug enable
```

### Common Wireless Issues
| Issue | Diagnostic Command | Likely Fix |
|-------|-------------------|-----------|
| AP offline | `diagnose wireless-controller wlac -c wtp` | Check CAPWAP reachability |
| Client not associating | `diagnose wireless-controller wlac -d sta <mac>` | Check security/RADIUS |
| Poor throughput | Check channel utilization | Change channel/width |
| Rogue AP detected | WIDS logs | Enable WIPS containment |
| Roaming issues | `diagnose wireless-controller wlac -c roam` | Enable 802.11r |
