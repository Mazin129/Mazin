# FCSS Lab Build — EVE-NG 6.2.0-3 Community (Already Installed)

## What You Skip
Since EVE-NG 6.2.0-3 is already running, skip Phase 1 of the main build guide.
Start here at Phase 2.

---

## Step 1 — Verify Your EVE-NG Health

SSH into your EVE-NG server first and run these checks:

```bash
# Confirm version
cat /etc/eve-release
# Expected: 6.2.0-3-community

# Confirm KVM acceleration is available (CRITICAL)
kvm-ok
# Expected:
#   INFO: /dev/kvm exists
#   KVM acceleration can be used
# If this FAILS → VMs will be unusable; enable VT-x in BIOS

# Check available RAM and disk
free -h
df -h /opt

# Check EVE-NG service is running
systemctl status eve-ng
# Expected: active (running)

# Confirm QEMU image directory exists
ls /opt/unetlab/addons/qemu/
# (may be empty or have existing images — that is fine)
```

---

## Step 2 — Network Configuration for Lab Access

### Find Your EVE-NG Management IP
```bash
ip addr show
# Look for the IP on pnet1 (management interface)
# Example output:
#   pnet1: inet 192.168.x.x/24   ← this is how you reach EVE-NG GUI
```

### EVE-NG 6.x Network Interfaces
| Interface | Name | Purpose |
|-----------|------|---------|
| pnet0 | Cloud0 | NAT — internet access for lab nodes |
| pnet1 | Cloud1 | Management bridge — your access to lab node GUIs |
| pnet2–9 | Cloud2–9 | Additional bridges (unused initially) |

### Connect Your PC to EVE-NG
Two options depending on your setup:

**Option A — EVE-NG is a VM on your PC (VirtualBox/VMware):**
```
Your PC browser → http://<host-only-adapter-IP>
Lab nodes use Cloud1 (pnet1) on same host-only subnet
Example: EVE-NG on 10.99.0.100 → nodes on 10.99.0.x
```

**Option B — EVE-NG is on a bare-metal server:**
```
Your PC browser → http://<server-IP>
For lab node GUI access: your PC must be on the same subnet
  OR add a static route on your PC:
  Windows: route add 10.99.0.0 mask 255.255.255.0 <server-IP>
  Linux:   ip route add 10.99.0.0/24 via <server-IP>
```

---

## Step 3 — Prepare for Fortinet Image Upload

### Check Disk Space First
```bash
df -h /opt
# You need at least 30 GB free for all images
# FortiGate ~1.5 GB × 3 instances = 4.5 GB
# FortiSwitch ~300 MB × 2 = 600 MB
# FortiAuthenticator ~1 GB
# FortiAnalyzer ~2 GB
# Windows Server ~10–15 GB
# Ubuntu ~2 GB
# Total: ~25 GB minimum
```

If space is tight:
```bash
# Check what's already in the QEMU folder
du -sh /opt/unetlab/addons/qemu/* 2>/dev/null | sort -hr

# Clean EVE-NG temp files
/opt/unetlab/wrappers/unl_wrapper -a cleanall
```

---

## Step 4 — Download Fortinet Images

### From Fortinet Support Portal

Login at `https://support.fortinet.com` → Download → VM Images

Download these **KVM** images:

| Product | Version | File to Download |
|---------|---------|-----------------|
| FortiGate | 7.4.x | `FGT_VM64_KVM-v7.4.x-build*.out.kvm.zip` |
| FortiSwitch | 7.4.x | `FSW_VM64_KVM-v7.4.x-build*.out.kvm.zip` |
| FortiAuthenticator | 6.6.x | `FAC_VM-v6.6.x-build*.out.kvm.zip` |
| FortiAnalyzer | 7.4.x | `FAZ_VM64_KVM-v7.4.x-build*.out.kvm.zip` |

> **Important:** Always pick **KVM** variant (not VMware .ovf or Hyper-V .vhd)

### Verify Image Format After Download
```bash
# On your local machine after extracting zip
qemu-img info fortios.qcow2
# Expected: file format: qcow2
# If it shows raw or vmdk → wrong image, redownload KVM version
```

---

## Step 5 — Upload Images to EVE-NG 6.2.0-3

### Method A: SCP (Linux/Mac)
```bash
# From your local machine
scp fortios.qcow2          root@<eve-ng-ip>:/tmp/fgt.qcow2
scp fortiswitchos.qcow2    root@<eve-ng-ip>:/tmp/fsw.qcow2
scp fac.qcow2              root@<eve-ng-ip>:/tmp/fac.qcow2
scp faz.qcow2              root@<eve-ng-ip>:/tmp/faz.qcow2
```

### Method B: WinSCP (Windows)
```
Protocol: SCP
Hostname: <eve-ng-ip>
Username: root
Password: <your root password>
Upload all qcow2 files to: /tmp/
```

### Method C: EVE-NG Web UI Upload (6.x supports this)
```
EVE-NG GUI → System → VM Image Manager (if available in 6.2)
  → Upload → Select qcow2 file
  → This is the easiest method on 6.x
```

---

## Step 6 — Install Images (EVE-NG 6.2.0-3 Specific Paths)

SSH into EVE-NG and run:

```bash
# ── FortiGate: 3 separate copies (HQ Primary, HQ Standby, Branch) ──
for FW in FGT-HQ FGT-HQ2 FGT-BR1; do
    IMGDIR="/opt/unetlab/addons/qemu/fortinet-${FW}-7.4"
    mkdir -p "$IMGDIR"
    # Copy from /tmp — NOT move, so we keep the original
    cp /tmp/fgt.qcow2 "$IMGDIR/virtioa.qcow2"
    echo "Installed: $IMGDIR"
done

# ── FortiSwitch ─────────────────────────────────────────────────────
mkdir -p /opt/unetlab/addons/qemu/fortinet-FSW01-7.4
cp /tmp/fsw.qcow2 /opt/unetlab/addons/qemu/fortinet-FSW01-7.4/virtioa.qcow2

# ── FortiAuthenticator ───────────────────────────────────────────────
mkdir -p /opt/unetlab/addons/qemu/fortinet-FAC-6.6
cp /tmp/fac.qcow2 /opt/unetlab/addons/qemu/fortinet-FAC-6.6/virtioa.qcow2

# ── FortiAnalyzer ────────────────────────────────────────────────────
mkdir -p /opt/unetlab/addons/qemu/fortinet-FAZ-7.4
cp /tmp/faz.qcow2 /opt/unetlab/addons/qemu/fortinet-FAZ-7.4/virtioa.qcow2

# ── CRITICAL: Fix permissions after every install ────────────────────
/opt/unetlab/wrappers/unl_wrapper -a fixpermissions

# ── Verify all images installed correctly ────────────────────────────
for DIR in /opt/unetlab/addons/qemu/fortinet-*/; do
    echo -n "$DIR → "
    qemu-img info "$DIR/virtioa.qcow2" 2>/dev/null | grep "file format" || echo "MISSING virtioa.qcow2"
done
```

Expected output:
```
fortinet-FAC-6.6/    → file format: qcow2
fortinet-FAZ-7.4/    → file format: qcow2
fortinet-FGT-HQ-7.4/ → file format: qcow2
fortinet-FGT-HQ2-7.4/→ file format: qcow2
fortinet-FGT-BR1-7.4/→ file format: qcow2
fortinet-FSW01-7.4/  → file format: qcow2
```

---

## Step 7 — Ubuntu Linux Client Image

```bash
# Download directly on EVE-NG (needs internet on pnet0)
cd /tmp
wget -q --show-progress \
  https://cloud-images.ubuntu.com/jammy/current/jammy-server-cloudimg-amd64.img \
  -O ubuntu2204.img

# Convert and resize to 20 GB
qemu-img convert -f qcow2 -O qcow2 ubuntu2204.img ubuntu2204.qcow2
qemu-img resize ubuntu2204.qcow2 +20G

# Install
mkdir -p /opt/unetlab/addons/qemu/linux-ubuntu-2204
cp ubuntu2204.qcow2 /opt/unetlab/addons/qemu/linux-ubuntu-2204/virtioa.qcow2
/opt/unetlab/wrappers/unl_wrapper -a fixpermissions

echo "Ubuntu size: $(du -sh /opt/unetlab/addons/qemu/linux-ubuntu-2204/virtioa.qcow2)"
```

---

## Step 8 — Windows Server 2022 (for Active Directory)

EVE-NG 6.x supports Windows VMs. Two approaches:

### Approach A — Build from ISO (Cleanest)

```bash
# 1. Download Windows Server 2022 eval ISO (on your PC)
#    https://www.microsoft.com/en-us/evalcenter/evaluate-windows-server-2022
#    File: ~5 GB ISO

# 2. Upload ISO to EVE-NG
scp WindowsServer2022_EVAL.iso root@<eve-ng-ip>:/opt/unetlab/addons/qemu/win-2022/

# 3. Create a blank disk to install onto
mkdir -p /opt/unetlab/addons/qemu/win-2022
qemu-img create -f qcow2 /opt/unetlab/addons/qemu/win-2022/virtioa.qcow2 60G

# 4. In EVE-NG GUI: Add Node → win-2022 → set CDROM to the ISO
#    Boot the VM → install Windows normally via HTML5 console
#    After install: Eject ISO, set static IP, join domain later
```

### Approach B — Use a Pre-built Template (Fastest)

Many EVE-NG users share pre-built Windows qcow2 images.
Check the EVE-NG community Discord/forum for shared images, or:

```bash
# If you already have a Windows qcow2 from a previous lab:
mkdir -p /opt/unetlab/addons/qemu/win-2022
cp /path/to/existing/windows.qcow2 /opt/unetlab/addons/qemu/win-2022/virtioa.qcow2
/opt/unetlab/wrappers/unl_wrapper -a fixpermissions
```

---

## Step 9 — Create the Lab in EVE-NG 6.2.0-3 GUI

Open browser: `http://<eve-ng-ip>/`
Login: `admin` / `eve`

### Add New Lab
```
Click the folder icon → Add new lab
  Name:        FCSS-Secure-Networking
  Version:     1
  Author:      Your name
  Description: NSE6 LAN Edge + NSE7 Enterprise FW Lab
→ Save
```

### Add Nodes — EVE-NG 6.2.0 Procedure
```
Right-click empty canvas → Add Node → QEMU
  
  For each Fortinet device:
    Node Type: QEMU
    Template:  Select the fortinet-* image you installed
    Name:      [as listed below]
    RAM/CPU:   [as listed below]
```

| Node Name | Template | RAM | vCPU | NICs |
|-----------|----------|-----|------|------|
| FGT-HQ | fortinet-FGT-HQ-7.4 | 2048 | 2 | 8 |
| FGT-HQ2 | fortinet-FGT-HQ2-7.4 | 2048 | 2 | 8 |
| FGT-BR1 | fortinet-FGT-BR1-7.4 | 1024 | 1 | 4 |
| FSW-01 | fortinet-FSW01-7.4 | 512 | 1 | 24 |
| FAC-01 | fortinet-FAC-6.6 | 2048 | 2 | 2 |
| FAZ-01 | fortinet-FAZ-7.4 | 4096 | 2 | 2 |
| Win-DC01 | win-2022 | 4096 | 2 | 1 |
| PC-Corp | linux-ubuntu-2204 | 512 | 1 | 1 |
| PC-Branch | linux-ubuntu-2204 | 512 | 1 | 1 |

### Add Cloud Networks
```
Right-click canvas → Add Network

Network 1:
  Name: Internet
  Type: Cloud0   (pnet0 — NAT — gives lab nodes internet)

Network 2:
  Name: Management
  Type: Cloud1   (pnet1 — your PC can reach this)
```

### Wire Connections
```
Click a node's port dot → drag → drop on target port dot

FGT-HQ  port1 ──── Internet        (WAN1)
FGT-HQ  port2 ──── Internet        (WAN2 / SD-WAN)
FGT-HQ  port3 ──── FSW-01 port1    (FortiLink)
FGT-HQ  port5 ──── FGT-HQ2 port5  (HA heartbeat)
FGT-HQ  port6 ──── Management      (GUI access)

FGT-HQ2 port6 ──── Management      (HA standby mgmt)

FGT-BR1 port1 ──── Internet        (Branch WAN)
FGT-BR1 port2 ──── PC-Branch eth0  (Branch LAN)

FSW-01  port2 ──── PC-Corp eth0    (VLAN10 client)

FAC-01  port1 ──── Management
FAZ-01  port1 ──── Management
Win-DC01 eth0 ──── Management
```

---

## Step 10 — Start and Bootstrap

### Start All Nodes
```
Select all → Right-click → Start
Wait 3 minutes for all VMs to boot
```

### Bootstrap FGT-HQ via Console
Right-click FGT-HQ → Console

```bash
# Press Enter at login prompt
# Username: admin
# Password: (blank — just press Enter)

# Set admin password
config system admin
    edit admin
        set password Fortinet123!
    next
end

# Management interface
config system interface
    edit port6
        set ip 10.99.0.1/24
        set allowaccess https ssh ping
    next
end

# Management gateway (→ EVE-NG pnet1)
config router static
    edit 1
        set dst 0.0.0.0/0
        set gateway 10.99.0.254
        set device port6
    next
end
```

Test: `ping 10.99.0.254` — should succeed.
Then: open `https://10.99.0.1` in your browser.

### Bootstrap Remaining Devices
```
FGT-HQ2  → console → IP: 10.99.0.2/24   gateway: 10.99.0.254
FGT-BR1  → console → IP: 10.99.0.3/24   gateway: 10.99.0.254
FAC-01   → console → IP: 10.99.0.50/24  gateway: 10.99.0.1
FAZ-01   → console → IP: 10.99.0.60/24  gateway: 10.99.0.1
Win-DC01 → Windows GUI → IP: 10.99.0.10/24
```

---

## Step 11 — Apply Full Lab Configs

Once all GUIs are reachable, apply configs from the repo:

```
FGT-HQ  → Lab/Configs/FortiGate/FGT-HQ_full_config.md
FSW-01  → Lab/Configs/FortiSwitch/FSW-01_config.md  (via FGT-HQ CLI)
FAP-01  → Lab/Configs/FortiAP/FAP-01_config.md       (via FGT-HQ CLI)
FAC-01  → Lab/Configs/FortiAuthenticator/FAC-01_config.md
```

---

## EVE-NG 6.2.0-3 Specific Notes

### Image Naming in 6.x
EVE-NG 6.x is more flexible with naming — the folder name becomes the template name shown in the GUI. Keep names short and descriptive (no spaces).

### Console Access in 6.x
- HTML5 console is built-in — no extra packages needed
- Right-click any node → `Console (HTML5)` or `Console (VNC)`
- FortiGate uses: **VNC** console (not SSH at first boot)

### If a Node Won't Start
```bash
# Check EVE-NG logs on the server
tail -f /opt/unetlab/data/Logs/unl_wrapper.log

# Check if KVM is loaded
lsmod | grep kvm
# Expected: kvm_intel (or kvm_amd) and kvm listed

# Restart the EVE-NG service
systemctl restart eve-ng
```

### Performance Tip for 6.2.0-3
```bash
# Enable CPU performance governor (makes VMs faster)
apt-get install -y cpufrequtils
cpufreq-set -g performance

# Check current governor
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor
```
