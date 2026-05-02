# FCSS in Secure Networking — Complete Study & Lab Guide

> **Target Certifications:**
> - Fortinet NSE 6 — LAN Edge Architect
> - Fortinet NSE 7 — Enterprise Firewall Administrator
>
> Passing both earns you **FCSS in Secure Networking**.

---

## Repository Structure

```
Mazin/
├── README.md                          ← You are here
├── NSE6-LAN-Edge/
│   ├── 01_Exam_Overview.md
│   ├── 02_FortiSwitch_Deep_Dive.md
│   ├── 03_FortiAP_Wireless.md
│   ├── 04_FortiAuthenticator_NAC.md
│   ├── 05_Security_Fabric_Integration.md
│   └── Practice_Exam_Questions.md     ← 120 Q&A with explanations
├── NSE7-Enterprise-FW/
│   ├── 01_Exam_Overview.md
│   ├── 02_VDOM_Architecture.md
│   ├── 03_BGP_OSPF_Routing.md
│   ├── 04_IPsec_SD-WAN.md
│   ├── 05_Advanced_Threat_Protection.md
│   ├── 06_HA_Clustering.md
│   └── Practice_Exam_Questions.md     ← 150 Q&A with explanations
├── Lab/
│   ├── EVE-NG/
│   │   ├── Topology_Design.md
│   │   ├── EVE-NG_Setup_Guide.md
│   │   └── lab_topology.unl           ← Import directly into EVE-NG
│   ├── VirtualBox/
│   │   ├── VirtualBox_Setup_Guide.md
│   │   └── network_config.md
│   └── Configs/
│       ├── FortiGate/
│       ├── FortiSwitch/
│       ├── FortiAP/
│       └── FortiAuthenticator/
└── Resources/
    └── Quick_Reference.md
```

---

## Certification Path

```
┌─────────────────────────────────────────────────────┐
│              FCSS in Secure Networking               │
│                                                     │
│  Prerequisite: NSE 4 (FortiGate Security)           │
├─────────────────────────┬───────────────────────────┤
│   NSE 6 — LAN Edge      │  NSE 7 — Enterprise FW    │
│   Architect             │  Administrator            │
│                         │                           │
│  Exam: NSE6_FML-7.4     │  Exam: NSE7_EFW-7.4      │
│  Duration: 70 min       │  Duration: 60 min         │
│  Questions: 60          │  Questions: 60            │
│  Passing: ~72%          │  Passing: ~70%            │
│  Languages: EN/JP       │  Languages: EN/JP/FR      │
└─────────────────────────┴───────────────────────────┘
```

## Study Approach

| Week | Focus |
|------|-------|
| 1–2  | NSE 6: FortiSwitch managed mode, VLANs, STP |
| 3–4  | NSE 6: FortiAP profiles, WPA3, WIDS/WIPS |
| 5    | NSE 6: FortiAuthenticator, 802.1X, RADIUS |
| 6–7  | NSE 7: FortiGate VDOMs, HA, policy routing |
| 8–9  | NSE 7: BGP, OSPF, SD-WAN, IPsec |
| 10   | NSE 7: UTM, IPS, SSL inspection, ATP |
| 11–12| Lab work + Practice exams |

## Lab Requirements

| Platform | Min RAM | Min vCPU | Storage |
|----------|---------|----------|---------|
| EVE-NG Community | 16 GB | 4 cores | 100 GB |
| VirtualBox (Host) | 32 GB | 8 cores | 200 GB |

### VM Images Needed
- FortiGate 7.4.x (KVM/QEMU image for EVE-NG)
- FortiSwitch 7.4.x (optional — SW emulated via FortiGate)
- FortiAuthenticator 6.x
- FortiAnalyzer 7.4.x (logging)
- Linux (Ubuntu 22.04) — client/RADIUS test endpoints
- Windows Server 2022 — AD/LDAP source

---

## Quick Reference Commands

```bash
# FortiGate — show running config summary
get system status
get hardware status

# Security Fabric verification
diagnose sys csf topology
diagnose sys csf upstream

# FortiSwitch (managed)
get switch-controller managed-switch
diagnose switch-controller switch-info port-stats <switch-sn>

# FortiAP (managed)
get wireless-controller wtp
diagnose wireless-controller wlac -c sta
```

---

*Study hard, lab harder. The CLI is your best friend.*
