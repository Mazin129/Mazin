# EVE-NG Setup Guide — FCSS Lab

## 1. EVE-NG Installation

### Option A: Bare Metal / VirtualBox OVA
```bash
# Download Community Edition OVA from https://www.eve-ng.net/
# Import into VirtualBox:
#   File → Import Appliance → eve-ng-community-x.x.x.ova
#   RAM: 16 GB minimum (32 GB recommended)
#   vCPU: 4 minimum (8 recommended)
#   Network Adapter 1: NAT (internet access for updates)
#   Network Adapter 2: Host-only (lab management — 10.99.0.x)

# After boot, set EVE-NG IP
# Default credentials: root / eve
# Run the setup wizard
/opt/unetlab/scripts/eve-setup.sh
```

### Option B: VMware ESXi OVA
```bash
# Import OVA → set nested virtualization:
# ESXi: Edit VM → CPU → "Expose hardware-assisted virtualization"
# Minimum: 16 GB RAM, 8 vCPU, 200 GB thin-provisioned disk
```

### EVE-NG Post-Install
```bash
# Update EVE-NG
apt-get update && apt-get upgrade -y

# Install community packages (HTML5 console, etc.)
apt-get install -y eve-ng-addons

# Check EVE-NG status
systemctl status eve-ng
```

---

## 2. FortiGate Image Preparation

### Obtain FortiGate KVM Image
1. Login to support.fortinet.com
2. Download → FortiGate → Firmware → 7.4.x → `FGT_VM64_KVM-v7.4.x-build.out.kvm.zip`
3. Extract: `fortios.qcow2`

### Install FortiGate Image in EVE-NG
```bash
# Create image directory (FGT-HQ)
mkdir -p /opt/unetlab/addons/qemu/fortinet-FGT-HQ-7.4.2
cp fortios.qcow2 /opt/unetlab/addons/qemu/fortinet-FGT-HQ-7.4.2/virtioa.qcow2

# Fix permissions
/opt/unetlab/wrappers/unl_wrapper -a fixpermissions

# Each FortiGate instance gets its own copy:
# fortinet-FGT-HQ, fortinet-FGT-HQ-2, fortinet-FGT-BR1
```

### FortiSwitch Virtual Image
```bash
mkdir -p /opt/unetlab/addons/qemu/fortinet-FSW-7.4.1
cp fortiswitchos.qcow2 /opt/unetlab/addons/qemu/fortinet-FSW-7.4.1/virtioa.qcow2
/opt/unetlab/wrappers/unl_wrapper -a fixpermissions
```

### FortiAuthenticator Image
```bash
mkdir -p /opt/unetlab/addons/qemu/fortinet-FAC-6.6.0
cp fortiauthenticator.qcow2 /opt/unetlab/addons/qemu/fortinet-FAC-6.6.0/virtioa.qcow2
/opt/unetlab/wrappers/unl_wrapper -a fixpermissions
```

---

## 3. Lab Topology Creation in EVE-NG

### Create New Lab
1. Open EVE-NG web UI: `http://<eve-ng-ip>/`
2. Login: admin / eve
3. **+** → Add new lab → Name: `FCSS-Lab` → Save
4. Right-click canvas → Add Node

### Node Settings

#### FGT-HQ
```
Image: fortinet-FGT-HQ-7.4.2
RAM: 2048 MB
vCPUs: 2
Ethernet: 8 (port1=WAN1, port2=WAN2, port3=FortiLink, port4=DMZ, port5=HA, port6=Mgmt, port7=spare, port8=spare)
```

#### FGT-HQ-2 (HA Standby)
```
Image: fortinet-FGT-HQ-7.4.2
RAM: 2048 MB
vCPUs: 2
Ethernet: 8
```

#### FGT-BR1
```
Image: fortinet-FGT-BR1-7.4.2
RAM: 1024 MB
vCPUs: 1
Ethernet: 4 (port1=WAN, port2=LAN, port3=spare, port4=spare)
```

#### FSW-01 (FortiSwitch)
```
Image: fortinet-FSW-7.4.1
RAM: 512 MB
vCPUs: 1
Ethernet: 28
```

#### FAC-01
```
Image: fortinet-FAC-6.6.0
RAM: 2048 MB
vCPUs: 2
Ethernet: 2
```

#### Win-DC-01
```
Image: win-2022 (pre-built qcow2)
RAM: 4096 MB
vCPUs: 2
Ethernet: 1
```

#### Linux Clients (Ubuntu)
```
Image: linux (Ubuntu 22.04 cloud image)
RAM: 512 MB
vCPUs: 1
Ethernet: 1
```

### Networks (EVE-NG Cloud/Bridge Nodes)
```
Management-Cloud → Bridge to EVE-NG management (pnet1 / 10.99.0.x)
Internet-Cloud    → NAT cloud (pnet0) — provides internet access
```

### Connections Wiring
```
FGT-HQ port1 ──────────── Internet-Cloud
FGT-HQ port2 ──────────── Internet-Cloud
FGT-HQ port3 ──────────── FSW-01 port1 (FortiLink)
FGT-HQ port4 ──────────── DMZ-Switch (or direct to Web-Server)
FGT-HQ port5 ──────────── FGT-HQ-2 port5 (HA heartbeat crossover)
FGT-HQ port6 ──────────── Management-Cloud
FGT-HQ-2 port6 ────────── Management-Cloud
FGT-BR1 port1 ─────────── Internet-Cloud (simulates WAN)
FGT-BR1 port2 ─────────── Lin-PC2 eth0
FSW-01 port2 ──────────── Win-PC1 eth0
FSW-01 port3 ──────────── IP-Phone eth0
FSW-01 port4 ──────────── FAP-01 eth0 (simulated AP)
FSW-01 port20 ─────────── FSW-02 port20 (MCLAG ICL)
FAC-01 port1 ──────────── Management-Cloud
FAZ-01 port1 ──────────── Management-Cloud
Win-DC-01 eth0 ─────────── Management-Cloud
```

---

## 4. FortiGate Initial Bootstrap

### Console Access via EVE-NG
- Right-click node → Console (HTML5 or telnet)
- Default creds: `admin` / (blank password)

### FGT-HQ Initial Config via Console
```bash
# Set hostname
config system global
    set hostname FGT-HQ
end

# Set management interface
config system interface
    edit port6
        set ip 10.99.0.1/24
        set allowaccess https ssh ping
        set description "Management"
    next
end

# Default route for management
config router static
    edit 1
        set dst 0.0.0.0/0
        set gateway 10.99.0.254
        set device port6
    next
end

# Enable GUI on HTTPS
config system global
    set admin-sport 443
    set admin-ssh-port 22
end
```

### FortiAuthenticator Initial Config
```bash
# Via console (admin / (blank))
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

---

## 5. VirtualBox Alternative Setup

### Host-Only Network Setup
```
VirtualBox → File → Host Network Manager:
  Create:
    vboxnet0 → 10.99.0.254/24 (Management)
    vboxnet1 → 10.200.0.254/24 (Inter-device links)
```

### FortiGate VirtualBox VM Settings
```
Name: FGT-HQ
Type: Linux / Other Linux (64-bit)
RAM: 2048 MB
CPU: 2 vCPUs (enable Nested VT-x/AMD-V if available)
Storage: Import KVM qcow2 (use qemu-img convert to VDI)
Network:
  Adapter 1: NAT (WAN1)
  Adapter 2: NAT (WAN2)
  Adapter 3: Host-only vboxnet0 (Management + FortiLink simulation)
  Adapter 4: Internal Network "lab-dmz"
  Adapter 5: Internal Network "lab-ha"
```

### Convert qcow2 to VDI for VirtualBox
```bash
# On Linux host
qemu-img convert -f qcow2 -O vdi fortios.qcow2 fortios.vdi

# On Windows host (requires QEMU for Windows)
qemu-img.exe convert -f qcow2 -O vdi fortios.qcow2 fortios.vdi
```

---

## 6. Quick Connectivity Verification Checklist

After standing up the lab, verify these before starting exercises:

```
□ FGT-HQ GUI reachable at https://10.99.0.1
□ FGT-HQ-2 GUI reachable at https://10.99.0.2
□ FGT-BR1 GUI reachable at https://10.99.0.3 (or console)
□ FAC-01 GUI reachable at https://10.99.0.50
□ FAZ-01 GUI reachable at https://10.99.0.60
□ Win-DC-01 pingable from FGT-HQ (10.99.0.10)
□ FortiSwitch discovered in FGT-HQ → Network → FortiSwitch
□ Internet access from FGT-HQ (ping 8.8.8.8 from CLI)
□ FortiGate licenses applied (eval or NFR)
□ FortiGuard updates completed (System → FortiGuard)
```
