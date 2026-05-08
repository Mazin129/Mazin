# All-in-One Self-Contained EVE-NG Lab — Basic Configuration

**Goal:** Run the entire FCSS Secure Networking lab fully inside EVE-NG with **zero dependency** on the host's physical network (`10.10.17.x`). All management/GUI access happens through a Linux desktop node *inside* the lab, accessed via EVE-NG's HTML5 console.

---

## 1. Topology

```
                    +-------------------+
                    |  MGMT-NET         |   internal bridge (192.168.100.0/24)
                    |  192.168.100.0/24 |
                    +---+---+---+---+---+
                        |   |   |   |
                  port5 |   |   |   | port5
                        |   |   |   |
                +-------+   |   |   +------+
                |           |   |          |
            [FGT-HQ]   [FGT-HQ2] [FGT-BR1]   [FAZ-01 port1]
            .101        .102      .103        .111
                        |
                +-------+
                | Desktop-Mgmt (Linux)
                | .10  -> Browser, ping, ssh
                +-------+

  Inside-LAN nets (HQ/BR), WAN sims = built later
```

| Node           | Mgmt IP (port5/port1) | Role                      |
| -------------- | --------------------- | ------------------------- |
| FGT-HQ         | 192.168.100.101       | HQ firewall               |
| FGT-HQ2        | 192.168.100.102       | HQ HA peer                |
| FGT-BR1        | 192.168.100.103       | Branch firewall           |
| FAZ-01         | 192.168.100.111       | FortiAnalyzer (port1)     |
| Desktop-Mgmt   | 192.168.100.10        | Linux node — admin access |

Login on every FortiGate: `admin` / `Fortinet123!`
Login on FAZ: `admin` / `Fortinet123!`

---

## 2. EVE-NG Lab Wiring

In the EVE-NG GUI on lab `FCSS-Secure-Net`:

1. **Add a Network object**
   - Right-click canvas → **Network**
   - Name: `MGMT-NET`
   - Type: **Bridge** (do NOT pick Cloud0/pnet0)
2. **Add Linux node**
   - Add Node → Template: **Linux** (any small image: TinyCore, Ubuntu Desktop, Kali)
   - Name: `Desktop-Mgmt`
   - 1 Ethernet
3. **Wire mgmt links**
   - FGT-HQ port5  → MGMT-NET
   - FGT-HQ2 port5 → MGMT-NET
   - FGT-BR1 port5 → MGMT-NET
   - FAZ-01 port1  → MGMT-NET
   - Desktop-Mgmt e0 → MGMT-NET
4. Start all nodes.

> Access Desktop-Mgmt by **double-clicking** the node — EVE-NG opens the HTML5/VNC console in your browser. From there you have a full Linux desktop with Firefox.

---

## 3. FortiGate Bootstrap (paste over telnet console)

Console each FortiGate via EVE-NG (right-click → Console, or telnet to `localhost:<port>` from EVE-NG SSH).

### 3.1 FGT-HQ

```bash
config system global
    set hostname FGT-HQ
    set admin-sport 443
    set timezone 04
end

config system interface
    edit port5
        set alias MGMT
        set mode static
        set ip 192.168.100.101 255.255.255.0
        set allowaccess ping https ssh http
        set description "Out-of-band management"
    next
end

config system admin
    edit admin
        set password Fortinet123!
    next
end
```

### 3.2 FGT-HQ2

```bash
config system global
    set hostname FGT-HQ2
    set admin-sport 443
    set timezone 04
end

config system interface
    edit port5
        set alias MGMT
        set mode static
        set ip 192.168.100.102 255.255.255.0
        set allowaccess ping https ssh http
    next
end

config system admin
    edit admin
        set password Fortinet123!
    next
end
```

### 3.3 FGT-BR1

```bash
config system global
    set hostname FGT-BR1
    set admin-sport 443
    set timezone 04
end

config system interface
    edit port5
        set alias MGMT
        set mode static
        set ip 192.168.100.103 255.255.255.0
        set allowaccess ping https ssh http
    next
end

config system admin
    edit admin
        set password Fortinet123!
    next
end
```

---

## 4. FortiAnalyzer Bootstrap (FAZ-01)

Console FAZ-01. Login `admin` / blank, set password to `Fortinet123!`, then:

```bash
config system interface
    edit port1
        set ip 192.168.100.111 255.255.255.0
        set allowaccess ping https ssh http webservice
    next
end

config system admin user
    edit admin
        set password Fortinet123!
    next
end
```

---

## 5. Desktop-Mgmt (Linux) Setup

After boot, open a terminal in the HTML5 console:

```bash
sudo ip addr add 192.168.100.10/24 dev eth0
sudo ip link set eth0 up
```

Persistent (Ubuntu/Debian) — edit `/etc/netplan/01-netcfg.yaml`:

```yaml
network:
  version: 2
  ethernets:
    eth0:
      addresses: [192.168.100.10/24]
```

Apply: `sudo netplan apply`

### Test reachability

```bash
ping -c 2 192.168.100.101
ping -c 2 192.168.100.102
ping -c 2 192.168.100.103
ping -c 2 192.168.100.111
```

### Open GUIs

In Firefox on Desktop-Mgmt:

- `https://192.168.100.101` → FGT-HQ
- `https://192.168.100.102` → FGT-HQ2
- `https://192.168.100.103` → FGT-BR1
- `https://192.168.100.111` → FAZ-01

Accept the self-signed cert. Login `admin` / `Fortinet123!`.

---

## 6. Save Lab State

In EVE-NG: **More Options → Export running config** on each FortiGate to persist the bootstrap as the startup-config so reboots don't lose it.

---

## 7. Next Steps (after GUI access works)

1. Apply the full HQ/BR1 configs from `Lab/Configs/FortiGate/FGT-HQ_full_config.md` (data-plane interfaces, policies, IPsec, SD-WAN).
2. Build out FortiSwitch / FortiAP via `Lab/Configs/FortiSwitch/` and `Lab/Configs/FortiAP/`.
3. Register FortiGates to FAZ-01 (`config log fortianalyzer setting`).
4. Snapshot the lab (EVE-NG → "Wipe nodes" then export to .unl).

---

## Why this design

- **Portable**: lab runs identically on any EVE-NG host — no host network changes.
- **No vSwitch issues**: avoids the VMware promiscuous-mode/forged-transmits limitation that blocked direct host access.
- **Clean separation**: management network (192.168.100.0/24) is isolated from data-plane and WAN-sim networks built later.
- **Single pane of glass**: one Linux desktop reaches every device GUI.
