# FortiSwitch Lab Configuration (Managed via FortiGate)

## All commands entered on FGT-HQ CLI under the switch-controller context.

---

## 1. Authorize FortiSwitch

```bash
# After FortiSwitch is discovered (plug into FortiLink port3 of FGT-HQ)
execute switch-controller authorize FSW01-SERIAL-NUMBER

# Verify switch is online
get switch-controller managed-switch
# Expected: Status = Authorized, Connection = Connected
```

---

## 2. VLAN Definitions

```bash
# VLANs are FortiGate interface objects (already created in FGT-HQ config)
# They are pushed automatically to FortiSwitch via FortiLink
# Verify with:
get switch-controller managed-switch
diagnose switch-controller switch-info port-stats FSW01-SERIAL port1
```

---

## 3. Port VLAN Assignment

```bash
config switch-controller managed-switch
    edit "FSW01-SERIAL"
        config ports
            # Port 1 — Win-PC1 (Data VLAN 10)
            edit "port1"
                set vlan "vlan10"
                set edge-port enable
                set stp-bpdu-guard enable
                set storm-control-policy "default-storm"
                set qos-policy "data-qos"
            next
            # Port 2 — IP Phone (Voice VLAN 20, Data VLAN 10 for soft phone)
            edit "port2"
                set vlan "vlan20"
                set allowed-vlans "vlan10"
                set edge-port enable
                set stp-bpdu-guard enable
            next
            # Port 3 — FortiAP (Wireless trunk — all WiFi VLANs)
            edit "port3"
                set allowed-vlans "vlan30" "vlan40"
                set edge-port enable
                set stp-bpdu-guard enable
            next
            # Port 4 — Linux test client (VLAN 10)
            edit "port4"
                set vlan "vlan10"
                set edge-port enable
                set stp-bpdu-guard enable
                set port-security port-security-mode 802.1X-mac-based
                set mab-eapol-request enable
            next
            # Port 20 — MCLAG ICL to FSW-02
            edit "port20"
                set mclag-icl enable
                set allowed-vlans "all"
            next
            # Port 21 — Uplink to FortiGate (FortiLink — auto-configured)
            # (This port is managed by FortiLink, do not configure manually)
        end
    next
end
```

---

## 4. 802.1X Port Authentication

```bash
config switch-controller managed-switch
    edit "FSW01-SERIAL"
        config ports
            edit "port1"
                set port-security port-security-mode 802.1X
                set auth-fail-vlan enable
                set auth-fail-vlanid "vlan100"    # Quarantine VLAN
                set guest-vlan enable
                set guest-vlanid "vlan40"
                set mab-eapol-request enable
            next
        end
    next
end
```

---

## 5. STP Configuration

```bash
config switch-controller stp-settings
    edit "FSW01-SERIAL"
        set status enable
        set revision 1
        set max-hops 20
    next
end

# Force FortiGate as root (done from FGT-HQ, already lowest bridge ID by default)
config switch-controller stp-instance
    edit 1
        set vlan-range "10 20 30 40 50 99 100"
        set priority 4096
    next
end
```

---

## 6. MCLAG Configuration

```bash
# FSW-01 and FSW-02 form an MCLAG pair
# ICL = port20 on both switches

config switch-controller managed-switch
    edit "FSW01-SERIAL"
        config ports
            edit "port20"
                set mclag-icl enable
            next
        end
    next
end

config switch-controller managed-switch
    edit "FSW02-SERIAL"
        config ports
            edit "port20"
                set mclag-icl enable
            next
        end
    next
end

# MCLAG group — server/AP connected to both switches via LAG
config switch-controller managed-switch
    edit "FSW01-SERIAL"
        config ports
            edit "port10"                # Server uplink on FSW-01
                set mclag enable
                set mclag-trunk-id 1
            next
        end
    next
end

config switch-controller managed-switch
    edit "FSW02-SERIAL"
        config ports
            edit "port10"                # Server uplink on FSW-02
                set mclag enable
                set mclag-trunk-id 1
            next
        end
    next
end
```

---

## 7. Storm Control Policy

```bash
config switch-controller storm-control-policy
    edit "default-storm"
        set unknown-unicast-rate 200
        set unknown-multicast-rate 200
        set broadcast-rate 100
    next
end
```

---

## 8. QoS Policies

```bash
config switch-controller qos qos-policy
    edit "data-qos"
        set default-cos 0
        set trust-ip-dscp-map "default"
        set trust-dot1p-map "default"
    next
    edit "voice-qos"
        set default-cos 5
        set trust-ip-dscp-map "dscp-to-cos"
        set trust-dot1p-map "default"
    next
end

config switch-controller qos ip-dscp-map
    edit "dscp-to-cos"
        config cos-queue
            edit 1
                set dscp-values "46"     # EF — VoIP RTP → CoS 5
                set cos 5
            next
            edit 2
                set dscp-values "26"     # AF31 — Signaling → CoS 3
                set cos 3
            next
        end
    next
end
```

---

## 9. Port Mirroring (SPAN)

```bash
# Mirror port1 traffic to port24 for Wireshark capture
config switch-controller managed-switch
    edit "FSW01-SERIAL"
        config mirror
            edit "span-port1"
                set dst "port24"
                set src-ingress "port1"
                set src-egress "port1"
                set mode both
                set status active
            next
        end
    next
end
```

---

## 10. Verification Commands

```bash
# Switch status
get switch-controller managed-switch

# Port statistics
diagnose switch-controller switch-info port-stats FSW01-SERIAL port1

# MAC address table
diagnose switch-controller switch-info mac-table FSW01-SERIAL

# LLDP neighbors
diagnose switch-controller switch-info lldp FSW01-SERIAL

# STP topology
diagnose switch-controller switch-info spanning-tree FSW01-SERIAL

# MCLAG status
diagnose switch-controller switch-info mclag FSW01-SERIAL
```
