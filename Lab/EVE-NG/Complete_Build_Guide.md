# FCSS Lab — Complete Build Guide (Step by Step)

This guide walks you from zero to a fully operational lab covering all NSE 6 and NSE 7 exam topics.

---

## Phase 0: What You Need Before Starting

### Hardware Requirements

| Option | Minimum | Recommended |
|--------|---------|-------------|
| **RAM** | 16 GB | 32 GB |
| **CPU** | 4 cores + VT-x/AMD-V | 8 cores (Intel i7/i9 or Ryzen 7/9) |
| **Disk** | 100 GB SSD free | 250 GB NVMe SSD |
| **OS** | Windows 10/11, Ubuntu 22.04, macOS | Ubuntu 22.04 bare-metal |

> **Important:** Virtualization must be enabled in BIOS/UEFI:
> - Intel: **VT-x** and **VT-d**
> - AMD: **AMD-V** and **IOMMU**

### Software Licenses / Accounts

| Resource | Where to Get | Cost |
|----------|-------------|------|
| Fortinet support account | support.fortinet.com | Free |
| FortiGate VM eval license | support.fortinet.com → Trial | Free 15-day |
| FortiAuthenticator eval | support.fortinet.com → Trial | Free |
| FortiAnalyzer eval | support.fortinet.com → Trial | Free |
| EVE-NG Community Edition | eve-ng.net | Free |
| Windows Server 2022 | Microsoft Eval Center | Free 180-day |

> **NFR licenses:** If you are a Fortinet partner or NSE student, request NFR (Not-For-Resale) licenses — they are free and don't expire.

---

## Phase 1: Install EVE-NG

### Step 1A — Download EVE-NG Community OVA

1. Go to `https://www.eve-ng.net/index.php/download/`
2. Download **Community Edition OVA** (latest, e.g. 6.x)
3. File will be named: `EVE-Community-x.x.x-xxxxx.ovf.zip`

### Step 1B — Install VirtualBox (if not already installed)

```
Download: https://www.virtualbox.org/wiki/Downloads
Install VirtualBox 7.x + Extension Pack
```

### Step 1C — Import EVE-NG into VirtualBox

```
VirtualBox → File → Import Appliance
  → Select: EVE-Community-x.x.x.ova
  → Settings to change before import:
      RAM:  16384 MB  (16 GB minimum; 32 GB if available)
      vCPU: 4         (8 if available)
      Network Adapter 1: NAT        ← internet for EVE-NG updates
      Network Adapter 2: Host-only  ← management access from your PC
  → Import
```

### Step 1D — Configure VirtualBox Host-Only Network

```
VirtualBox → File → Host Network Manager (or Tools → Network)
  → Create: vboxnet0
      IPv4 Address: 10.99.0.254
      Subnet Mask:  255.255.255.0
      DHCP Server:  DISABLED  ← we use static IPs
```

### Step 1E — First Boot and EVE-NG Setup

1. Start the EVE-NG VM in VirtualBox
2. Login at console: `root` / `eve`
3. The setup wizard runs automatically:

```
Enter root password:        [set a strong password]
Enter hostname:             eve-ng
Enter DNS domain:           lab.local
Configure management IP:    Static
  IP:      10.99.0.100
  Mask:    255.255.255.0
  Gateway: 10.99.0.254    ← VirtualBox host-only adapter IP
  DNS:     8.8.8.8
NTP server:                 pool.ntp.org
Proxmox/KVM hypervisor:     Yes (confirm KVM is available)
```

4. EVE-NG reboots. After reboot:

```bash
# Verify KVM is working (MUST show kvm-ok or modules loaded)
kvm-ok
# Expected: INFO: /dev/kvm exists  KVM acceleration can be used

# Update EVE-NG
apt-get update && apt-get upgrade -y

# Install HTML5 console support
apt-get install -y eve-ng-addons
```

5. Open browser on your PC: `http://10.99.0.100/`
   - Login: `admin` / `eve`
   - You should see the EVE-NG dashboard

---

## Phase 2: Get Fortinet Images

### Step 2A — Download from Fortinet Support Portal

Login at `https://support.fortinet.com`

**FortiGate VM for KVM:**
```
Support → Download → Firmware Images
  Product: FortiGate
  Platform: VM → KVM
  Version: 7.4.x (latest 7.4 build)
  File: FGT_VM64_KVM-v7.4.x-buildXXXX-FORTINET.out.kvm.zip
  → Download
```

**FortiSwitch VM:**
```
Product: FortiSwitch
Platform: VM → KVM
Version: 7.4.x
File: FSW_VM64_KVM-v7.4.x-FORTINET.out.kvm.zip
```

**FortiAuthenticator VM:**
```
Product: FortiAuthenticator
Platform: VM → KVM
Version: 6.6.x
File: FAC_VM-v6.6.x-FORTINET.out.kvm.zip
```

**FortiAnalyzer VM:**
```
Product: FortiAnalyzer
Platform: VM → KVM
Version: 7.4.x
File: FAZ_VM64_KVM-v7.4.x-FORTINET.out.kvm.zip
```

### Step 2B — Extract Images

Each zip contains a `fortios.qcow2` (or similar named) file.

```bash
# On your PC (Linux/Mac):
unzip FGT_VM64_KVM-v7.4.x-buildXXXX.out.kvm.zip
# Extracts: fortios.qcow2

unzip FSW_VM64_KVM-v7.4.x.out.kvm.zip
# Extracts: fortiswitchos.qcow2  (name may vary)

unzip FAC_VM-v6.6.x.out.kvm.zip
# Extracts: fac.qcow2

unzip FAZ_VM64_KVM-v7.4.x.out.kvm.zip
# Extracts: faz.qcow2
```

### Step 2C — Upload Images to EVE-NG

Use SCP (Linux/Mac) or WinSCP (Windows) to copy to EVE-NG:

```bash
# From your PC — upload all images to EVE-NG
scp fortios.qcow2      root@10.99.0.100:/tmp/
scp fortiswitchos.qcow2 root@10.99.0.100:/tmp/
scp fac.qcow2          root@10.99.0.100:/tmp/
scp faz.qcow2          root@10.99.0.100:/tmp/
```

### Step 2D — Install Images on EVE-NG

SSH into EVE-NG: `ssh root@10.99.0.100`

```bash
# ── FortiGate ──────────────────────────────────────────────
# We need 3 separate copies: HQ, HQ-2 (HA), Branch
for FW in FGT-HQ FGT-HQ2 FGT-BR1; do
    mkdir -p /opt/unetlab/addons/qemu/fortinet-${FW}-7.4
    cp /tmp/fortios.qcow2 /opt/unetlab/addons/qemu/fortinet-${FW}-7.4/virtioa.qcow2
done

# ── FortiSwitch ─────────────────────────────────────────────
mkdir -p /opt/unetlab/addons/qemu/fortinet-FSW-7.4
cp /tmp/fortiswitchos.qcow2 /opt/unetlab/addons/qemu/fortinet-FSW-7.4/virtioa.qcow2

# ── FortiAuthenticator ───────────────────────────────────────
mkdir -p /opt/unetlab/addons/qemu/fortinet-FAC-6.6
cp /tmp/fac.qcow2 /opt/unetlab/addons/qemu/fortinet-FAC-6.6/virtioa.qcow2

# ── FortiAnalyzer ────────────────────────────────────────────
mkdir -p /opt/unetlab/addons/qemu/fortinet-FAZ-7.4
cp /tmp/faz.qcow2 /opt/unetlab/addons/qemu/fortinet-FAZ-7.4/virtioa.qcow2

# ── Fix permissions (REQUIRED after every image install) ─────
/opt/unetlab/wrappers/unl_wrapper -a fixpermissions

# ── Verify images are visible ────────────────────────────────
ls /opt/unetlab/addons/qemu/ | grep fortinet
```

---

## Phase 3: Get Additional VM Images

### Step 3A — Ubuntu 22.04 (Linux clients)

```bash
# On EVE-NG host — download Ubuntu cloud image
cd /tmp
wget https://cloud-images.ubuntu.com/jammy/current/jammy-server-cloudimg-amd64.img

# Convert to qcow2 and resize
qemu-img convert -f qcow2 -O qcow2 jammy-server-cloudimg-amd64.img ubuntu2204.qcow2
qemu-img resize ubuntu2204.qcow2 +20G

# Install to EVE-NG
mkdir -p /opt/unetlab/addons/qemu/linux-ubuntu-22.04
cp ubuntu2204.qcow2 /opt/unetlab/addons/qemu/linux-ubuntu-22.04/virtioa.qcow2
/opt/unetlab/wrappers/unl_wrapper -a fixpermissions
```

> **Ubuntu cloud image default login:** ubuntu / ubuntu  
> First boot: set password via `sudo passwd ubuntu`

### Step 3B — Windows Server 2022 (Active Directory)

Windows images cannot be downloaded by script. Options:

**Option A — Microsoft Evaluation ISO:**
```
1. Download from: https://www.microsoft.com/en-us/evalcenter/evaluate-windows-server-2022
2. Get: Windows Server 2022 ISO (180-day eval)
3. Install in a VirtualBox VM, then export the VDI
4. Convert VDI to qcow2:
   qemu-img convert -f vdi -O qcow2 WinServer2022.vdi WinServer2022.qcow2
5. Upload to EVE-NG:
   scp WinServer2022.qcow2 root@10.99.0.100:/tmp/
   mkdir -p /opt/unetlab/addons/qemu/win-2022
   cp /tmp/WinServer2022.qcow2 /opt/unetlab/addons/qemu/win-2022/virtioa.qcow2
   /opt/unetlab/wrappers/unl_wrapper -a fixpermissions
```

**Option B — Use existing EVE-NG Windows templates:**
```
EVE-NG community provides pre-built Windows templates.
Check: https://www.eve-ng.net/index.php/documentation/howtos/
Search: "Windows Server EVE-NG"
```

---

## Phase 4: Build the Lab Topology in EVE-NG

### Step 4A — Create the Lab

1. Open browser: `http://10.99.0.100/`
2. Login: `admin` / `eve`
3. Click **+** (Add new lab)
4. Name: `FCSS-Secure-Networking`
5. Description: `NSE 6 + NSE 7 Lab`
6. Click **Save**

### Step 4B — Add Nodes

Right-click on canvas → **Add Node**. Add each node below:

#### Node 1: FGT-HQ (Primary Firewall)
```
Template: fortinet-FGT-HQ-7.4
Name:     FGT-HQ
RAM:      2048
vCPUs:    2
Ethernet: 8
```

#### Node 2: FGT-HQ2 (HA Standby)
```
Template: fortinet-FGT-HQ2-7.4
Name:     FGT-HQ2
RAM:      2048
vCPUs:    2
Ethernet: 8
```

#### Node 3: FGT-BR1 (Branch Firewall)
```
Template: fortinet-FGT-BR1-7.4
Name:     FGT-BR1
RAM:      1024
vCPUs:    1
Ethernet: 4
```

#### Node 4: FSW-01 (FortiSwitch)
```
Template: fortinet-FSW-7.4
Name:     FSW-01
RAM:      512
vCPUs:    1
Ethernet: 24
```

#### Node 5: FAC-01 (FortiAuthenticator)
```
Template: fortinet-FAC-6.6
Name:     FAC-01
RAM:      2048
vCPUs:    2
Ethernet: 2
```

#### Node 6: FAZ-01 (FortiAnalyzer)
```
Template: fortinet-FAZ-7.4
Name:     FAZ-01
RAM:      4096
vCPUs:    2
Ethernet: 2
```

#### Node 7: Win-DC-01 (Domain Controller)
```
Template: win-2022
Name:     Win-DC-01
RAM:      4096
vCPUs:    2
Ethernet: 1
```

#### Node 8 & 9: Linux Clients
```
Template: linux-ubuntu-22.04
Name:     PC-Corp (VLAN 10 data client)
RAM:      512
vCPUs:    1
Ethernet: 1

Name:     PC-Branch (Branch client)
RAM:      512
vCPUs:    1
Ethernet: 1
```

### Step 4C — Add Networks (Cloud Nodes)

Right-click canvas → **Add Network**:

```
Network 1:
  Name: Internet-Cloud
  Type: Cloud0   (pnet0 — NAT — gives internet access)

Network 2:
  Name: Mgmt-Cloud
  Type: Cloud1   (pnet1 — bridged to host-only vboxnet0 — 10.99.0.x)
```

### Step 4D — Wire All Connections

Click a node's port stub, drag to target. Connect:

```
FGT-HQ  e0/0 (port1) ──── Internet-Cloud       [WAN1]
FGT-HQ  e0/1 (port2) ──── Internet-Cloud       [WAN2 — SD-WAN]
FGT-HQ  e0/2 (port3) ──── FSW-01 e0/0 (port1) [FortiLink]
FGT-HQ  e0/3 (port4) ──── [leave free / DMZ]
FGT-HQ  e0/4 (port5) ──── FGT-HQ2 e0/4 (port5)[HA Heartbeat]
FGT-HQ  e0/5 (port6) ──── Mgmt-Cloud           [Management]

FGT-HQ2 e0/5 (port6) ──── Mgmt-Cloud           [HA Mgmt]

FGT-BR1 e0/0 (port1) ──── Internet-Cloud       [Branch WAN]
FGT-BR1 e0/1 (port2) ──── PC-Branch eth0       [Branch LAN]

FSW-01  e0/1 (port2) ──── PC-Corp eth0         [VLAN 10 client]

FAC-01  e0/0 (port1) ──── Mgmt-Cloud           [FAC management]
FAZ-01  e0/0 (port1) ──── Mgmt-Cloud           [FAZ management]
Win-DC  e0/0         ──── Mgmt-Cloud           [DC management]
```

### Step 4E — Save Topology

`File → Save` or `Ctrl+S`

---

## Phase 5: Initial Device Configuration

### Step 5A — Start All Nodes

```
Select All nodes → Right-click → Start
Wait 2–3 minutes for all VMs to boot
```

### Step 5B — Configure FGT-HQ via Console

Right-click FGT-HQ → Console (HTML5 Telnet)

```bash
# Default: admin / (blank password — just press Enter)

# Set admin password first
config system admin
    edit admin
        set password Fortinet123!
    next
end

# Set management interface
config system interface
    edit port6
        set ip 10.99.0.1/24
        set allowaccess https ssh ping
    next
end

# Management default route
config router static
    edit 1
        set dst 0.0.0.0/0
        set gateway 10.99.0.254
        set device port6
    next
end
```

Now you can use the GUI: open `https://10.99.0.1` in your browser.

### Step 5C — Configure FGT-HQ2 via Console

```bash
config system admin
    edit admin
        set password Fortinet123!
    next
end

config system interface
    edit port6
        set ip 10.99.0.2/24
        set allowaccess https ssh ping
    next
end

config router static
    edit 1
        set dst 0.0.0.0/0
        set gateway 10.99.0.254
        set device port6
    next
end
```

### Step 5D — Configure FAC-01 via Console

```bash
# Login: admin / (blank)
config system interface
    edit port1
        set ip 10.99.0.50/24
        set allowaccess https ssh ping
    next
end

config system route
    edit 1
        set dst 0.0.0.0/0
        set gateway 10.99.0.1
        set device port1
    next
end
```

GUI: `https://10.99.0.50`

### Step 5E — Configure FAZ-01 via Console

```bash
config system interface
    edit port1
        set ip 10.99.0.60/24
        set allowaccess https ssh ping
    next
end

config system route
    edit 1
        set dst 0.0.0.0/0
        set gateway 10.99.0.1
        set device port1
    next
end
```

GUI: `https://10.99.0.60`

### Step 5F — Configure Windows Server 2022 (Domain Controller)

Set static IP on the Windows NIC:
```
IP:      10.99.0.10
Mask:    255.255.255.0
Gateway: 10.99.0.1
DNS:     127.0.0.1 (self — it will be the DNS server)
```

Install Active Directory Domain Services:
```powershell
# Run in PowerShell as Administrator
Install-WindowsFeature -Name AD-Domain-Services -IncludeManagementTools
Install-ADDSForest `
    -DomainName "corp.local" `
    -DomainNetbiosName "CORP" `
    -SafeModeAdministratorPassword (ConvertTo-SecureString "Fortinet123!" -AsPlainText -Force) `
    -Force
# Server reboots automatically
```

After reboot, create test users:
```powershell
# Create OUs and users for lab testing
New-ADOrganizationalUnit -Name "Corp-Users" -Path "DC=corp,DC=local"
New-ADOrganizationalUnit -Name "Groups" -Path "DC=corp,DC=local"

# Test users
New-ADUser -Name "Test User1" -SamAccountName "testuser1" `
    -UserPrincipalName "testuser1@corp.local" `
    -AccountPassword (ConvertTo-SecureString "Fortinet123!" -AsPlainText -Force) `
    -Enabled $true -Path "OU=Corp-Users,DC=corp,DC=local"

New-ADUser -Name "svc-fac" -SamAccountName "svc-fac" `
    -UserPrincipalName "svc-fac@corp.local" `
    -AccountPassword (ConvertTo-SecureString "Fortinet123!" -AsPlainText -Force) `
    -Enabled $true -Path "CN=Users,DC=corp,DC=local"

# Security groups
New-ADGroup -Name "Corp-Data-Users" -GroupScope Global -Path "OU=Groups,DC=corp,DC=local"
New-ADGroup -Name "Corp-Voice-Users" -GroupScope Global -Path "OU=Groups,DC=corp,DC=local"
New-ADGroup -Name "Corp-Guest-Users" -GroupScope Global -Path "OU=Groups,DC=corp,DC=local"

# Add testuser1 to Corp-Data-Users
Add-ADGroupMember -Identity "Corp-Data-Users" -Members "testuser1"
```

---

## Phase 6: Apply FortiGate Full Configuration

Now apply the full configs from the repo. Paste into FortiGate CLI or use the GUI:

### Step 6A — FGT-HQ Full Config

SSH to `10.99.0.1` (admin / Fortinet123!) and paste the content from:
```
Lab/Configs/FortiGate/FGT-HQ_full_config.md
```

Apply sections in this order:
```
1. System Baseline     (hostname, NTP, DNS)
2. Interfaces          (VLANs, WAN ports)
3. SD-WAN              (members + health checks + service rules)
4. DHCP Servers        (one per VLAN)
5. FortiAnalyzer       (logging)
6. Firewall Addresses  (objects and groups)
7. Firewall Policies   (LAN→internet, guest, VPN)
8. IPsec VPN           (HQ-to-BR1 tunnel)
9. RADIUS config       (FortiAuthenticator reference)
10. High Availability  (after FGT-HQ2 is ready)
11. Security Fabric    (after FAZ-01 is logging)
12. SSL Inspection     (deep inspect profile)
```

### Step 6B — Apply Licenses (REQUIRED for full functionality)

```
FGT-HQ GUI → System → FortiGuard
  → Enter evaluation license key (from support.fortinet.com)
  → Or: System → Dashboard → License Information → Upload
```

After license is applied:
```bash
# Force FortiGuard update
execute update-av
execute update-ips

# Verify
diagnose autoupdate status
```

### Step 6C — FortiSwitch (Automatic — via FortiLink)

```
1. FortiSwitch must be running (started in EVE-NG)
2. On FGT-HQ: Network → FortiSwitch Manager
   → FSW-01 should appear as "Discovered"
3. Click Authorize
4. FSW-01 status changes to "Connected"
5. Now apply configs from:
   Lab/Configs/FortiSwitch/FSW-01_config.md
```

### Step 6D — FortiAuthenticator Config

Apply from: `Lab/Configs/FortiAuthenticator/FAC-01_config.md`

```
GUI: https://10.99.0.50

Order:
1. LDAP integration → connect to Win-DC-01 (10.99.0.10)
2. Create Local CA → for EAP-TLS
3. Create RADIUS clients → FGT-HQ as NAS
4. Create RADIUS policies → 802.1X wired + wireless
5. FSSO configuration → agentless polling of DC
```

### Step 6E — FortiAnalyzer Config

```
GUI: https://10.99.0.60
1. System → Network → set IP 10.99.0.60/24
2. Add FortiGate as device:
   Device Manager → Add Device → Discover → 10.99.0.1
3. Authorize FGT-HQ
4. On FGT-HQ: verify logs arriving:
   execute log fortianalyzer test-connectivity
```

---

## Phase 7: Verification Checklist

Run through this checklist in order:

```
INFRASTRUCTURE
□ ping 8.8.8.8 from FGT-HQ CLI                    (internet works)
□ https://10.99.0.1  reachable from your browser   (FGT-HQ GUI)
□ https://10.99.0.50 reachable                     (FAC-01 GUI)
□ https://10.99.0.60 reachable                     (FAZ-01 GUI)
□ FGT-HQ: Network → FortiSwitch shows FSW-01 Connected

LICENSING
□ FGT-HQ: System → FortiGuard → all services green
□ diagnose autoupdate status → IPS/AV versions shown

VLAN ROUTING
□ ping 10.10.0.1 from PC-Corp (VLAN 10 gateway reachable)
□ PC-Corp gets DHCP IP in 10.10.0.x range
□ PC-Corp can reach internet (http://example.com)

AUTHENTICATION
□ diagnose test authserver radius FortiAuth-RADIUS testuser1 Fortinet123!
   Expected: Authentication was successful.
□ 802.1X port on FSW-01: connect PC-Corp → check VLAN 10 assigned

FORTIANALYZER
□ FGT-HQ: execute log fortianalyzer test-connectivity
   Expected: OK
□ FAZ-01: Log View → Traffic shows FGT-HQ logs arriving

HA CLUSTER
□ FGT-HQ + FGT-HQ2: get system ha status
   Expected: both units shown, one as PRIMARY one as SECONDARY
□ Test failover: execute ha failover set 1
   → Traffic continues on FGT-HQ2
   → execute ha failover unset 1  (restore original primary)

VPN
□ FGT-BR1: get vpn ipsec tunnel summary
   Expected: HQ-to-BR1 status UP
□ ping 10.10.0.1 from PC-Branch  (branch → HQ via IPsec)

SECURITY FABRIC
□ FGT-HQ: diagnose sys csf topology
   Expected: FGT-HQ (root) with FSW-01, FGT-BR1 shown
□ Security Fabric → Security Rating → Run
   Expected: Score appears with recommendations
```

---

## Phase 8: Lab Exercises — Where to Start

Once the checklist is green, work through the labs in this order:

| Order | Lab | Time | File |
|-------|-----|------|------|
| 1 | FortiSwitch VLANs + 802.1X | 60 min | `FSW-01_config.md` |
| 2 | FortiAP + WPA3 SSIDs | 60 min | `FAP-01_config.md` |
| 3 | FortiAuthenticator RADIUS + FSSO | 90 min | `FAC-01_config.md` |
| 4 | Security Fabric + Automation | 45 min | `05_Security_Fabric_Integration.md` |
| 5 | VDOMs + Inter-VDOM links | 60 min | `02_VDOM_Architecture.md` |
| 6 | BGP + OSPF routing | 90 min | `03_BGP_OSPF_Routing.md` |
| 7 | IPsec + ADVPN + SSL-VPN | 90 min | `04_IPsec_SD-WAN.md` |
| 8 | HA Clustering + Failover test | 60 min | `06_HA_Clustering.md` |
| 9 | SSL Inspection + IPS + AV | 60 min | `05_Advanced_Threat_Protection.md` |
| 10 | SD-WAN SLA + App steering | 45 min | `03_BGP_OSPF_Routing.md` (SD-WAN section) |
| 11 | Debug Flow + Troubleshooting | 60 min | `Resources/Quick_Reference.md` |

---

## Common Build Problems & Fixes

| Problem | Cause | Fix |
|---------|-------|-----|
| `kvm-ok` fails | VT-x not enabled in BIOS or nested VT not enabled in VirtualBox | Enable VT-x in BIOS; VirtualBox VM Settings → System → Processor → Enable Nested VT-x |
| FortiGate node won't start | Wrong image folder name or wrong file name | Folder must be exact; file must be `virtioa.qcow2`; re-run fixpermissions |
| FortiGate console shows "BIOS" loop | Image not bootable / wrong format | Re-download image; verify qcow2 format with `qemu-img info` |
| FortiSwitch not discovered | FortiLink interface not type `fortilink` | `config system interface → edit port3 → set type fortilink` |
| EVE-NG nodes can't reach internet | Cloud0 (pnet0) not NATing | On VirtualBox EVE-NG VM: Network Adapter 1 must be NAT (not bridged) |
| Can't reach EVE-NG GUI from browser | Host-only adapter not configured | Verify vboxnet0 = 10.99.0.254/24 in VirtualBox Host Network Manager |
| FortiGate shows "License not valid" | No eval license applied | Apply from support.fortinet.com → VM eval request |
| FAZ not receiving logs | FGT-HQ logging config wrong or FAZ not authorizing device | `execute log fortianalyzer test-connectivity` on FGT; authorize device in FAZ |
| RADIUS auth fails | Wrong shared secret | Must match exactly on FGT RADIUS server object and FAC client definition |
