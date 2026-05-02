# Image Upload via MobaXterm + FortiSwitch Notes

## MobaXterm Upload Method

MobaXterm has a built-in SFTP file browser — no SCP commands needed.

### Step 1 — Connect to EVE-NG in MobaXterm
```
MobaXterm → Session → SSH
  Remote host: <eve-ng-server-IP>
  Username:    root
  Port:        22
→ OK
```

When the SSH session opens, MobaXterm **automatically shows the SFTP panel on the left sidebar** — this is the drag-and-drop upload area.

### Step 2 — Navigate to Upload Destination
In the left SFTP panel:
```
Click the folder icon or navigate to: /tmp
```
You will see the files currently in `/tmp` on the server.

### Step 3 — Upload the Image Files
```
Option A — Drag and Drop:
  Drag your .zip files from Windows Explorer
  → Drop into the MobaXterm left SFTP panel (while in /tmp)

Option B — Upload button:
  Click the Upload (↑ arrow) button in the SFTP panel toolbar
  → Browse to your .zip files
  → Select all → Open

Upload ALL zip files at once:
  - FGT_VM64_KVM-v7.4.x-build*.out.kvm.zip
  - FSW_VM64_KVM-v7.4.x-FORTINET.out.kvm.zip
  - FAC_VM-v6.6.x-build*.out.kvm.zip
  - FAZ_VM64_KVM-v7.4.x-build*.out.kvm.zip
```

### Step 4 — Verify Upload Completed
In the MobaXterm terminal (right side):
```bash
ls -lh /tmp/*.zip
# Should show all 4 zip files with correct sizes
# FortiGate zip:       ~1.5 GB
# FortiSwitch zip:     ~200–400 MB
# FortiAuthenticator:  ~800 MB
# FortiAnalyzer:       ~2 GB
```

---

## About the FortiSwitch Image You Found

### Confirm It Is Correct
```
FSW_VM64_KVM-v7.4.x-FORTINET.out.kvm.zip ✓ CORRECT
                ^^^
                VM64 = 64-bit VM
                KVM  = correct hypervisor for EVE-NG
```

### Extract and Identify the qcow2 File
```bash
cd /tmp

# Extract FortiSwitch zip
unzip FSW_VM64_KVM-v7.4.x-FORTINET.out.kvm.zip -d fsw-extract

# See what's inside
ls -lh fsw-extract/
```

The zip typically contains ONE of these (name varies by version):
```
fortiswitchos.qcow2          ← most common
FSW_VM64.qcow2               ← some versions
disk1.qcow2                  ← rare
```

Note the exact filename — you need it for the install step.

---

## Full Extract + Install Script

Run this in the MobaXterm terminal after all zips are uploaded to /tmp:

```bash
cd /tmp

# ── 1. Extract all zips ───────────────────────────────────────────────
echo "Extracting FortiGate..."
mkdir -p fgt-extract && unzip -o FGT_VM64_KVM*.zip -d fgt-extract/

echo "Extracting FortiSwitch..."
mkdir -p fsw-extract && unzip -o FSW_VM64_KVM*.zip -d fsw-extract/

echo "Extracting FortiAuthenticator..."
mkdir -p fac-extract && unzip -o FAC_VM*.zip -d fac-extract/

echo "Extracting FortiAnalyzer..."
mkdir -p faz-extract && unzip -o FAZ_VM64_KVM*.zip -d faz-extract/

echo ""
echo "Contents of each extract:"
echo "=== FortiGate ===" && ls fgt-extract/
echo "=== FortiSwitch ===" && ls fsw-extract/
echo "=== FortiAuthenticator ===" && ls fac-extract/
echo "=== FortiAnalyzer ===" && ls faz-extract/
```

**Paste the output here** (or check it yourself). It shows the exact qcow2 filename inside each zip. Then run the install:

```bash
# ── 2. Find the qcow2 in each folder ────────────────────────────────
FGT_IMG=$(find /tmp/fgt-extract -name "*.qcow2" | head -1)
FSW_IMG=$(find /tmp/fsw-extract -name "*.qcow2" | head -1)
FAC_IMG=$(find /tmp/fac-extract -name "*.qcow2" | head -1)
FAZ_IMG=$(find /tmp/faz-extract -name "*.qcow2" | head -1)

echo "FortiGate image:       $FGT_IMG"
echo "FortiSwitch image:     $FSW_IMG"
echo "FortiAuthenticator:    $FAC_IMG"
echo "FortiAnalyzer image:   $FAZ_IMG"

# ── 3. Install to EVE-NG (only run after confirming images above) ────
# FortiGate — 3 copies
for FW in FGT-HQ FGT-HQ2 FGT-BR1; do
    DIR="/opt/unetlab/addons/qemu/fortinet-${FW}-7.4"
    mkdir -p "$DIR"
    cp "$FGT_IMG" "$DIR/virtioa.qcow2"
    echo "Installed: $DIR"
done

# FortiSwitch
mkdir -p /opt/unetlab/addons/qemu/fortinet-FSW01-7.4
cp "$FSW_IMG" /opt/unetlab/addons/qemu/fortinet-FSW01-7.4/virtioa.qcow2
echo "Installed: FortiSwitch"

# FortiAuthenticator
mkdir -p /opt/unetlab/addons/qemu/fortinet-FAC-6.6
cp "$FAC_IMG" /opt/unetlab/addons/qemu/fortinet-FAC-6.6/virtioa.qcow2
echo "Installed: FortiAuthenticator"

# FortiAnalyzer
mkdir -p /opt/unetlab/addons/qemu/fortinet-FAZ-7.4
cp "$FAZ_IMG" /opt/unetlab/addons/qemu/fortinet-FAZ-7.4/virtioa.qcow2
echo "Installed: FortiAnalyzer"

# ── 4. Fix permissions (MANDATORY) ──────────────────────────────────
/opt/unetlab/wrappers/unl_wrapper -a fixpermissions
echo "Permissions fixed."

# ── 5. Final verification ────────────────────────────────────────────
echo ""
echo "=== Installed Images ==="
for DIR in /opt/unetlab/addons/qemu/fortinet-*/; do
    IMG="$DIR/virtioa.qcow2"
    if [ -f "$IMG" ]; then
        SIZE=$(du -sh "$IMG" | cut -f1)
        echo "✓  $(basename $DIR)  →  $SIZE"
    else
        echo "✗  $(basename $DIR)  →  MISSING virtioa.qcow2"
    fi
done
```

---

## Important Note About FortiSwitch in EVE-NG

FortiSwitch VM (managed mode) in EVE-NG has **one key difference** from real hardware:

| Feature | Real FortiSwitch | EVE-NG FortiSwitch VM |
|---------|-----------------|----------------------|
| FortiLink | Physical port | Virtual NIC (port1) |
| Port count | 24/48 physical | Up to 24 virtual NICs |
| PoE | Yes | No (not needed for lab) |
| FortiLink discovery | Automatic | Automatic via virtual NIC |

**The FortiSwitch VM connects to FortiGate FortiLink via its first NIC (port1 / e0/0).**
No special config needed — FortiGate discovers it automatically once wired.

---

## After Install — Quick Sanity Check

```bash
# Confirm EVE-NG sees the images
# Open browser → http://<eve-ng-ip>/ → Add Node → QEMU
# You should see fortinet-FGT-HQ-7.4, fortinet-FSW01-7.4, etc. in the dropdown

# OR check from CLI:
ls /opt/unetlab/addons/qemu/ | grep fortinet
```

Expected:
```
fortinet-FAC-6.6
fortinet-FAZ-7.4
fortinet-FGT-BR1-7.4
fortinet-FGT-HQ-7.4
fortinet-FGT-HQ2-7.4
fortinet-FSW01-7.4
```
