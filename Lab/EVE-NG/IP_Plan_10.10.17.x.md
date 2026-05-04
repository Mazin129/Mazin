# Updated IP Plan for EVE-NG at 10.10.17.100

## Why We Update the IPs

EVE-NG's pnet1 (Cloud1 / Management bridge) shares the same physical
interface as the EVE-NG management IP (10.10.17.100).

Any lab node connected to Cloud1 must use an IP in the 10.10.17.x
subnet so your PC can reach their GUIs directly.

---

## Updated Management IP Assignments

| Device | Old IP (generic) | New IP (your lab) | Access URL |
|--------|-----------------|-------------------|-----------|
| EVE-NG host | 10.99.0.100 | **10.10.17.100** | http://10.10.17.100/ |
| FGT-HQ (port6) | 10.99.0.1 | **10.10.17.101** | https://10.10.17.101 |
| FGT-HQ2 (port6) | 10.99.0.2 | **10.10.17.102** | https://10.10.17.102 |
| FGT-BR1 | 10.99.0.3 | **10.10.17.103** | https://10.10.17.103 |
| FAC-01 | 10.99.0.50 | **10.10.17.110** | https://10.10.17.110 |
| FAZ-01 | 10.99.0.60 | **10.10.17.111** | https://10.10.17.111 |
| Win-DC01 | 10.99.0.10 | **10.10.17.112** | RDP 10.10.17.112 |
| PC-Corp | DHCP | **10.10.17.120** | SSH |
| PC-Branch | DHCP | **10.10.17.121** | SSH |

Gateway for all lab nodes → **10.10.17.1** (your network gateway)

---

## Internal Lab VLANs (stay unchanged — routed through FGT-HQ)

These VLANs are internal to FGT-HQ and do NOT need Cloud1 access:

| VLAN | Subnet | Gateway |
|------|--------|---------|
| VLAN 10 — Data | 10.10.0.0/24 | 10.10.0.1 (FGT-HQ) |
| VLAN 20 — Voice | 10.20.0.0/24 | 10.20.0.1 |
| VLAN 30 — Wireless | 10.30.0.0/24 | 10.30.0.1 |
| VLAN 40 — Guest | 10.40.0.0/24 | 10.40.0.1 |
| VLAN 50 — IoT | 10.50.0.0/24 | 10.50.0.1 |
| VLAN 100 — Quarantine | 10.100.0.0/24 | 10.100.0.1 |
| Branch LAN | 172.16.1.0/24 | 172.16.1.1 (FGT-BR1) |
| VPN Tunnel | 169.254.0.0/30 | — |
