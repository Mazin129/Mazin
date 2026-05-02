# FortiAuthenticator Lab Configuration

## All config via GUI: https://10.99.0.50  (admin / blank initially)

---

## 1. Initial Network Setup

```bash
# Via console first boot
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

## 2. LDAP Integration (Active Directory)

```
GUI: Authentication → Remote Auth Servers → LDAP → Create New

Name: Corp-AD
Primary Server: 10.99.0.10
Port: 389
Base DN: DC=corp,DC=local
Bind DN: CN=svc-fac,CN=Users,DC=corp,DC=local
Bind Password: Fortinet123!
Username Attr: sAMAccountName
Filter: (&(objectClass=user)(objectCategory=person))
Secure: LDAPS optional (port 636)
Test: Authentication → Test Credentials
```

---

## 3. Local CA for EAP-TLS

```
GUI: Certificate Management → Local CAs → Create New

Root CA:
  Name: Lab-Root-CA
  Key Type: RSA
  Key Size: 4096
  Subject: CN=Lab Root CA, O=FCSS Lab, C=US
  Validity: 3650 days

Issuing CA (sub-CA signed by Root):
  Name: Lab-Issuing-CA
  Signed By: Lab-Root-CA
  Key Size: 2048
  Validity: 1825 days

RADIUS Server Certificate:
  GUI: Certificate Management → Local Service Certs → Create New
  Name: RADIUS-Server-Cert
  Issued By: Lab-Issuing-CA
  Subject CN: radius.corp.local
  SANs: IP:10.99.0.50, DNS:radius.corp.local
```

---

## 4. RADIUS Clients (NAS)

```
GUI: Authentication → RADIUS Service → Clients → Create New

Client 1:
  Name: FGT-HQ
  IP: 10.99.0.1
  Secret: Fortinet123!
  NAS Type: FortiGate

Client 2:
  Name: FSW-01
  IP: 10.99.0.1    (FortiSwitch uses FGT-HQ as proxy — same IP)
  Secret: Fortinet123!
  NAS Type: FortiGate
```

---

## 5. RADIUS Policies

### Policy 1: 802.1X Wired (PEAP-MSCHAPv2)
```
GUI: Authentication → RADIUS Service → Policies → Create New

Name: Dot1X-Wired
Source: NAS = FGT-HQ
Called Station ID: (leave blank — match all)
Auth Type: EAP
  EAP Method: PEAP
  Inner Method: MSCHAPv2
User Source: Corp-AD (LDAP)

Authorization Rules:
  If member of: CN=Corp-Data-Users,OU=Groups,DC=corp,DC=local
    → Send RADIUS attributes:
      Tunnel-Type = VLAN (13)
      Tunnel-Medium-Type = IEEE-802 (6)
      Tunnel-Private-Group-ID = 10
  
  If member of: CN=Corp-Voice-Users,OU=Groups,DC=corp,DC=local
    → Tunnel-Private-Group-ID = 20
  
  If member of: CN=Corp-Guest-Users,OU=Groups,DC=corp,DC=local
    → Tunnel-Private-Group-ID = 40
```

### Policy 2: 802.1X Wireless (WPA3-Enterprise)
```
Name: Dot1X-Wireless
Source: NAS = FGT-HQ, Called-Station-ID contains "Corp-SSID" (or leave blank)
Auth Type: EAP
  EAP Method: PEAP (initially) / EAP-TLS (advanced exercise)
User Source: Corp-AD

Authorization:
  Corp users → VLAN 30 (Wireless Data)
  Guest users → VLAN 40
```

### Policy 3: MAB (MAC Authentication)
```
Name: MAB-Policy
Source: NAS = FGT-HQ
Auth Type: PAP (MAB sends MAC as username/password in PAP)
User Source: Local Users (MAC address whitelist)

Setup local users for MAB:
  Authentication → User Management → Local Users → Create New
  Username: aa-bb-cc-dd-ee-ff (MAC format used by FortiSwitch)
  Password: aa-bb-cc-dd-ee-ff
  RADIUS Attributes: Tunnel-Private-Group-ID = 50 (IoT VLAN)
```

---

## 6. FSSO Configuration

```
GUI: Fortinet SSO Methods → SSO → FortiGate Filtering

FSSO Settings:
  Listen on Port: 8000
  Password: Fortinet123!
  
DC Agent or Agentless:
  Method: Agentless
  Domain Controller: 10.99.0.10
  Bind User: svc-fac@corp.local
  Bind Password: Fortinet123!
  LDAP Base: DC=corp,DC=local
```

### Configure FSSO on FGT-HQ
```bash
config user fsso
    edit "FAC-FSSO"
        set server "10.99.0.50"
        set port 8000
        set password Fortinet123!
    next
end

config user group
    edit "FSSO-Corp-Users"
        set member "FAC-FSSO"
        config match
            edit 1
                set server-name "FAC-FSSO"
                set group-name "CN=Corp-Data-Users,OU=Groups,DC=corp,DC=local"
            next
        end
    next
end

# Identity-based policy using FSSO group
config firewall policy
    edit 20
        set name "FSSO-Corp-Internet"
        set srcintf "vlan10"
        set dstintf "virtual-wan-link"
        set srcaddr "VLAN10-Data"
        set dstaddr "all"
        set groups "FSSO-Corp-Users"
        set action accept
        set nat enable
        set logtraffic all
    next
end
```

---

## 7. Two-Factor Authentication

```
GUI: Authentication → User Management → Local Users → Edit admin user
  Enable Two-Factor Authentication: Yes
  Token Type: FortiToken Mobile
  → Provision Token → scan QR code with FortiToken app

For remote VPN users:
  GUI: Authentication → RADIUS Service → Policies → Edit VPN Policy
  Enable 2FA: Yes
  → RADIUS will send Access-Challenge requesting OTP
  → FortiClient prompts for OTP
```

---

## 8. Guest Portal

```
GUI: Guest Management → Portals → Create

Name: Guest-WiFi-Portal
Type: Self-registration
  Required Fields: First Name, Last Name, Email, Phone
  Email Verification: Required
  Max Session Duration: 8 hours
  Account Expiry: 1 day
  
SMS Gateway (optional):
  Provider: Twilio
  Account SID: <your-sid>
  Auth Token: <your-token>
  From Number: +1XXXXXXXXXX

Sponsor Approval: Disabled (auto-approve)
```

---

## 9. Verification Commands

### From FortiGate CLI
```bash
# Test RADIUS authentication
diagnose test authserver radius FortiAuth-RADIUS testuser Fortinet123!

# Live RADIUS debug
diagnose debug application fnbamd 255
diagnose debug enable
# (attempt 802.1X auth on wired port)
diagnose debug disable
diagnose debug reset

# Show FSSO logged-in users
diagnose firewall auth list

# Check FSSO connection to FAC
get user fsso
diagnose debug application authd 255
diagnose debug enable
```

### From FortiAuthenticator GUI
```
Logging → Log Access → Authentication Logs
  Filter: Authentication Result = Reject
  → Shows: User, NAS-IP, EAP-Type, Reject Reason

Monitoring → RADIUS Sessions
  → Active authenticated sessions with assigned VLAN

Fortinet SSO Methods → SSO → Monitor
  → Active FSSO sessions (user-to-IP mappings)
```

---

## 10. Lab Exercises — Authentication

### Exercise 1: 802.1X Wired PEAP
1. Connect Win-PC1 to FSW-01 port1 (802.1X enabled)
2. Configure Windows NIC: WPA2-Enterprise → PEAP-MSCHAPv2
3. Authenticate with corp\testuser
4. Verify VLAN 10 IP from DHCP
5. Check FAC RADIUS log → Access-Accept with VLAN 10

### Exercise 2: MAB for IoT Device
1. Connect Linux client to FSW-01 port4 (MAB-enabled)
2. No 802.1X supplicant → FSW sends MAC as RADIUS
3. Verify VLAN 50 assigned (IoT)
4. Test connectivity: ping 10.50.0.1 (gateway only)

### Exercise 3: EAP-TLS with Client Cert
1. Generate client cert from Lab-Issuing-CA via FAC
2. Install cert on Win-PC1
3. Configure PEAP → change to EAP-TLS
4. Authenticate → verify cert-based auth in FAC logs

### Exercise 4: FSSO Group Policy
1. Log in to Win-PC1 with domain credentials
2. Check FGT: `diagnose firewall auth list` → user visible
3. Create identity-based policy matching FSSO group
4. Verify policy hit counter increments
