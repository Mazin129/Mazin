# FortiAP Lab Configuration — All commands on FGT-HQ

---

## 1. AP Profile (WTP Profile)

```bash
config wireless-controller wtp-profile
    edit "FAP-431F-Lab"
        set comment "Lab AP Profile — dual band"
        set ap-country US
        set dtls-policy dtls-enabled
        set handoff-rssi 25
        set handoff-sta-thresh 55
        config platform
            set type FAP-431F
        end
        # 5 GHz Radio
        config radio 1
            set mode ap
            set band 802.11ax-5G
            set channel "36" "40" "44" "48" "149" "153" "157" "161"
            set channel-width 80MHz
            set auto-power-level enable
            set auto-power-high 17
            set auto-power-low 10
            set vaps "Corp-SSID" "Guest-SSID"
            set wids-profile "Enterprise-WIDS"
        end
        # 2.4 GHz Radio
        config radio 2
            set mode ap
            set band 802.11ax-2.4G
            set channel "1" "6" "11"
            set channel-width 20MHz
            set auto-power-level enable
            set vaps "IoT-SSID"
            set wids-profile "Enterprise-WIDS"
        end
    next
end
```

---

## 2. WIDS Profile

```bash
config wireless-controller wids-profile
    edit "Enterprise-WIDS"
        set ap-scan enable
        set ap-bgscan-report-intv 30
        set ap-bgscan-intv 1
        set ap-bgscan-duration 20
        set deauth-unknown-src-thresh 10
        set rogue-scan enable
        set eapol-fail-flood enable
        set eapol-fail-intv 1
        set eapol-fail-thresh 10
        set spoofed-deauth enable
        set asleap-attack enable
        set weak-wep-iv enable
        set wireless-bridge enable
    next
end
```

---

## 3. SSIDs (VAPs)

### Corporate SSID (WPA3-Enterprise)
```bash
config wireless-controller vap
    edit "Corp-SSID"
        set ssid "CorpWLAN-Lab"
        set security wpa3-enterprise
        set encrypt AES
        set pmf enable
        set auth radius
        set radius-server "FortiAuth-RADIUS"
        set vlanid 30
        set traffic-mode tunnel
        set intra-vap-privacy enable
        set fast-bss-transition enable
        set ft-mobility-domain 1000
        set ft-over-ds enable
        set bss-transition enable
    next
end
```

### Guest SSID (Captive Portal)
```bash
config wireless-controller vap
    edit "Guest-SSID"
        set ssid "Guest-WiFi-Lab"
        set security captive-portal
        set vlanid 40
        set traffic-mode tunnel
        set intra-vap-privacy enable
        set captive-portal-fw-accounting enable
        set schedule "always"
    next
end
```

### IoT SSID (WPA2-Personal)
```bash
config wireless-controller vap
    edit "IoT-SSID"
        set ssid "IoT-Lab"
        set security wpa2-only-personal
        set passphrase "LabIoT2024!"
        set vlanid 50
        set traffic-mode tunnel
        set intra-vap-privacy enable
    next
end
```

---

## 4. RADIUS Server Reference

```bash
config wireless-controller hotspot20 anqp-3gpp-cellular
# (no change needed — RADIUS reference comes from VAP config above)

config user radius
    edit "FortiAuth-RADIUS"
        set server "10.99.0.50"
        set secret Fortinet123!
    next
end
```

---

## 5. Authorize and Assign AP Profile

```bash
# After FAP-01 connects and is discovered
config wireless-controller wtp
    edit "FP431F-SERIALNUMBER"
        set name "FAP-01-Lab"
        set admin enable
        set wtp-profile "FAP-431F-Lab"
        set override-vaps enable
        config vap-all
        end
        config radio
            edit 0                 # Radio 1 (5 GHz)
                set override-band enable
            next
            edit 1                 # Radio 2 (2.4 GHz)
                set override-band enable
            next
        end
    next
end
```

---

## 6. Band Steering

```bash
config wireless-controller setting
    set band-steering enable
    set band-steer-threshold 20    # Steer to 5 GHz when signal >= -70 dBm
end
```

---

## 7. Verification Commands

```bash
# List all APs and their status
get wireless-controller wtp

# Show connected wireless clients
diagnose wireless-controller wlac -c sta

# Show AP RF stats
diagnose wireless-controller wlac -c wtp

# Specific client details
diagnose wireless-controller wlac -d sta <MAC-address>

# CAPWAP debug
diagnose debug application cw_acd 0xff
diagnose debug enable
# (watch AP join → run for 60s → stop)
diagnose debug disable
diagnose debug reset

# Rogue AP list
diagnose wireless-controller wlac -c rogue-ap

# Roaming events
diagnose wireless-controller wlac -c roam
```

---

## 8. Lab Exercises — Wireless

### Exercise 1: Connect to Corp-SSID with 802.1X
1. On Win-PC1, configure Network Adapter → WPA3-Enterprise → PEAP-MSCHAPv2
2. Use domain credentials (corp\testuser)
3. Verify VLAN 30 IP assigned
4. Check FAC logs: Authentication → RADIUS Logs

### Exercise 2: Test WIDS
```bash
# Simulate deauth flood from Linux client
# (educational — only in isolated lab)
# apt-get install aircrack-ng
# aireplay-ng --deauth 50 -a <BSSID> wlan0mon

# Check FGT alert logs:
execute log filter category event
execute log filter field subtype wireless
execute log display
```

### Exercise 3: Captive Portal Guest Flow
1. Connect to Guest-WiFi-Lab SSID
2. Open browser → verify redirect to captive portal
3. Register → check VLAN 40 IP
4. Verify internet access only (no VLAN 10 access)

### Exercise 4: WPA3-SAE vs WPA2-PSK
1. Create second test SSID with WPA2-PSK
2. Capture 4-way handshake with Wireshark (educational demo)
3. Create WPA3-SAE SSID — demonstrate SAE exchange (no crackable handshake)
