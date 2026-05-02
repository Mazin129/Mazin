# FCSS Lab Topology — EVE-NG Design

## Lab Overview

This single topology covers ALL objectives for both NSE 6 and NSE 7:

```
                          INTERNET (Cloud/NAT)
                               │
                         ┌─────┴─────┐
                         │  FGT-HQ   │  FortiGate 7.4 (Root VDOM)
                         │ (FW-01)   │  HA Primary
                         └──┬───┬───┘
                     WAN1   │   │ WAN2 (SD-WAN)
              203.0.113.1/30│   │198.51.100.1/30
                            │   │
                     ┌──────┘   └──────┐
                     │                 │
              ┌──────┴──────┐  ┌───────┴─────┐
              │  ISP-1-SIM  │  │  ISP-2-SIM  │
              │(Linux router│  │(Linux router│
              │  loopback)  │  │  loopback)  │
              └─────────────┘  └─────────────┘

FGT-HQ Internal Interfaces:
  port3 → FortiLink (FortiSwitch)
  port4 → DMZ (10.10.10.0/24)
  port5 → HA Heartbeat (FGT-HQ-2)
  port6 → Management (10.99.0.0/24)

                    ┌──────────────┐
port3 (FortiLink) ──┤  FSW-01      │  FortiSwitch 7.4
                    │  24-port     │
                    └──┬──┬──┬────┘
                    p1 │  │p2│p3
                       │  │  │
                  VLAN10│  │VLAN20 │VLAN30
                  (Data)│  │(Voice)│(Wireless)
                       │  │  │
               ┌───────┘  │  └──────────┐
               │          │             │
         ┌─────┴───┐ ┌────┴────┐  ┌────┴────┐
         │ Win-PC1 │ │ IP-Phone│  │  FAP-01 │ FortiAP
         │(VLAN 10)│ │(VLAN 20)│  │ (WLAN)  │
         └─────────┘ └─────────┘  └─────────┘

FSW-01 port 20 ──── FSW-02 (MCLAG ICL)
FSW-02 port 20 ──── FSW-01

               ┌──────────────┐
               │  FAC-01      │  FortiAuthenticator 6.x
               │ 10.99.0.50   │  RADIUS / LDAP Proxy / FSSO
               └──────────────┘

               ┌──────────────┐
               │  FAZ-01      │  FortiAnalyzer 7.4
               │ 10.99.0.60   │  Logging / Reporting
               └──────────────┘

               ┌──────────────┐
               │  Win-DC-01   │  Windows Server 2022
               │ 10.10.0.10   │  AD DS / DNS / NPS (RADIUS)
               └──────────────┘

─────────────────── BRANCH SITE ───────────────────

                    ┌──────────────┐
                    │  FGT-BR1     │  FortiGate 7.4
                    │  Branch FW   │  IPsec Spoke / ADVPN
                    └──┬──────┬───┘
               WAN/VPN │      │ LAN
                       │      │ 172.16.1.0/24
                  (IPsec│      │
                  to HQ)│  ┌───┴──────┐
                       │  │ Lin-PC2  │
                       │  │(VLAN 10) │
                       │  └──────────┘

─────────────────── HA PEER ───────────────────────

               ┌──────────────┐
               │  FGT-HQ-2   │  FortiGate 7.4
               │  HA Standby │  A/P Cluster with FGT-HQ
               └─────────────┘
                port5 ─── FGT-HQ port5 (HA heartbeat)
```

---

## IP Addressing Plan

### Management Network (10.99.0.0/24)

| Device | IP | Role |
|--------|-----|------|
| FGT-HQ (port6) | 10.99.0.1 | HQ Firewall management |
| FGT-HQ-2 (port6) | 10.99.0.2 | HA Standby management |
| FAC-01 | 10.99.0.50 | FortiAuthenticator |
| FAZ-01 | 10.99.0.60 | FortiAnalyzer |
| Win-DC-01 | 10.99.0.10 | Domain Controller |
| EVE-NG host | 10.99.0.254 | EVE-NG management bridge |

### Data VLAN 10 (10.10.0.0/24)

| Device | IP | Role |
|--------|-----|------|
| FGT-HQ VLAN 10 SVI | 10.10.0.1 | Gateway |
| Win-PC1 | 10.10.0.100 (DHCP) | Test workstation |
| Win-DC-01 | 10.10.0.10 | AD / DNS |

### Voice VLAN 20 (10.20.0.0/24)

| Device | IP | Role |
|--------|-----|------|
| FGT-HQ VLAN 20 SVI | 10.20.0.1 | Gateway |
| IP-Phone-01 | 10.20.0.100 (DHCP) | VoIP test device |

### Wireless VLAN 30 (10.30.0.0/24)

| Device | IP | Role |
|--------|-----|------|
| FGT-HQ VLAN 30 SVI | 10.30.0.1 | Gateway |
| Wireless clients | 10.30.0.x (DHCP) | WiFi test devices |

### Guest VLAN 40 (10.40.0.0/24)

| Device | IP | Role |
|--------|-----|------|
| FGT-HQ VLAN 40 SVI | 10.40.0.1 | Gateway |
| Guest clients | 10.40.0.x (DHCP) | Guest WiFi |

### DMZ (10.10.10.0/24)

| Device | IP | Role |
|--------|-----|------|
| FGT-HQ DMZ | 10.10.10.1 | DMZ gateway |
| Web-Server-01 | 10.10.10.10 | Test web server |

### Branch (172.16.1.0/24)

| Device | IP | Role |
|--------|-----|------|
| FGT-BR1 LAN | 172.16.1.1 | Branch gateway |
| Lin-PC2 | 172.16.1.100 | Branch test client |

### VPN Tunnel Addresses (169.254.0.x)

| Tunnel | HQ End | Branch End |
|--------|---------|-----------|
| HQ-to-BR1 | 169.254.0.1/30 | 169.254.0.2/30 |

---

## EVE-NG Node Configuration

### Required Images

| Image | EVE-NG Type | RAM | vCPU | Notes |
|-------|------------|-----|------|-------|
| FortiGate 7.4.x | `fortigate` or `qemu` | 2 GB | 2 | Use KVM qcow2 image |
| FortiSwitch 7.4.x | `qemu` | 512 MB | 1 | Virtual FSW image |
| FortiAuthenticator 6.x | `qemu` | 2 GB | 2 | FAC VM image |
| FortiAnalyzer 7.4.x | `qemu` | 4 GB | 2 | FAZ VM image |
| Windows Server 2022 | `qemu` | 4 GB | 2 | AD DS role |
| Ubuntu 22.04 | `linux` | 512 MB | 1 | Linux clients |

### Image Upload Commands (EVE-NG host)
```bash
# Upload FortiGate image (example)
mkdir -p /opt/unetlab/addons/qemu/fortinet-FGT-v7.4.2
cp fortios.qcow2 /opt/unetlab/addons/qemu/fortinet-FGT-v7.4.2/virtioa.qcow2
/opt/unetlab/wrappers/unl_wrapper -a fixpermissions
```

---

## Lab Exercises Map

| Lab | NSE 6/7 Domain | Exercises |
|-----|----------------|-----------|
| Lab 1 | NSE 6 FortiSwitch | FortiLink setup, VLAN config, MCLAG, STP |
| Lab 2 | NSE 6 Wireless | FortiAP deployment, SSID profiles, WPA3, WIDS |
| Lab 3 | NSE 6 NAC | 802.1X, MAB, RADIUS, FortiAuthenticator |
| Lab 4 | NSE 6 Security Fabric | Fabric setup, automation stitches |
| Lab 5 | NSE 7 VDOM | Multi-VDOM, inter-VDOM links, transparent mode |
| Lab 6 | NSE 7 Routing | BGP eBGP/iBGP, OSPF areas, redistribution |
| Lab 7 | NSE 7 VPN | Site-to-site IPsec, ADVPN, SSL-VPN |
| Lab 8 | NSE 7 HA | A/P clustering, session sync, failover test |
| Lab 9 | NSE 7 ATP | SSL deep inspection, IPS, AppCtrl, AV, sandbox |
| Lab 10 | NSE 7 SD-WAN | SD-WAN rules, SLA, failover, application steering |
| Lab 11 | NSE 7 Troubleshoot | Debug flow, sniffer, session table analysis |
