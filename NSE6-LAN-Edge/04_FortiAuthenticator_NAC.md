# FortiAuthenticator & NAC Deep Dive — NSE 6 LAN Edge

## FortiAuthenticator Overview

FortiAuthenticator is an identity and access management (IAM) appliance that provides:
- **RADIUS** server (802.1X, MAB, VPN auth)
- **LDAP** proxy / local user store
- **SAML IdP** (Identity Provider)
- **Certificate Authority** (for EAP-TLS)
- **Two-Factor Authentication** (TOTP, FortiToken)
- **Guest Portal** management
- **FSSO** (Fortinet Single Sign-On) collector

---

## RADIUS Architecture

### RADIUS Message Flow (802.1X)
```
Supplicant        Authenticator           RADIUS Server
(Client)          (FortiSwitch/FGT)       (FortiAuthenticator)
    │                   │                       │
    │── EAPOL-Start ───>│                       │
    │<── EAP-Request ───│                       │
    │── EAP-Response ──>│                       │
    │                   │── RADIUS Access-Req ──>│
    │                   │<── RADIUS Access-Chal ─│
    │<── EAP-Request ───│                       │
    │── EAP-Response ──>│                       │
    │                   │── RADIUS Access-Req ──>│
    │                   │<── RADIUS Access-Accept│
    │<── EAP-Success ───│                       │
    │                   │── RADIUS Accounting ──>│
    │  (802.1X opens)   │                       │
```

### RADIUS Port Reference
| Port | Protocol | Purpose |
|------|----------|---------|
| UDP 1812 | RADIUS | Authentication |
| UDP 1813 | RADIUS | Accounting |
| UDP 3799 | RADIUS CoA | Change of Authorization |

---

## FortiAuthenticator Configuration

### RADIUS Client (NAS) Setup
```
FortiAuthenticator GUI:
Authentication → RADIUS Service → Clients
    → Add Client:
        Name: FortiGate-Core
        IP: 10.0.0.1
        Secret: <strong-shared-secret>
        NAS Type: FortiGate
```

### RADIUS Policy
```
Authentication → RADIUS Service → Policies
    → Add Policy:
        Name: Dot1X-Corporate
        Source: Wired-NAD-Group
        Auth Type: EAP
        EAP Type: PEAP-MSCHAPv2 / EAP-TLS
        User Source: AD-Domain / Local-Users
        → Authorization:
            VLAN Assignment: by Group
              - Domain\Corp-Users → VLAN 10
              - Domain\Voice-Users → VLAN 20
              - Domain\Guest-Users → VLAN 40
```

---

## EAP-TLS Configuration

### Certificate Requirements
```
CA Certificate (Root CA)
├── FortiAuthenticator Server Certificate
│   └── Subject: CN=radius.corp.local
└── Client Certificates
    └── Subject: CN=<username>, UPN=user@corp.local
```

### FortiAuthenticator CA Setup
```
Certificate Management → Local CAs → Create
    Name: Corp-Root-CA
    Key Algorithm: RSA-4096
    Validity: 10 years
    → Create Issuing CA:
        Name: Corp-Issuing-CA
        Signed by: Corp-Root-CA
```

### Client Certificate Enrollment
- **Auto-enrollment**: Via SCEP or EST protocol
- **Manual**: Download .p12 bundle from portal
- **Group Policy**: Deploy via AD Certificate Services + GPO

---

## LDAP Integration

### LDAP Connector Setup
```bash
# FortiAuthenticator GUI:
Authentication → User Management → Remote Auth Servers → LDAP
    Server: dc.corp.local
    Port: 389 (or 636 for LDAPS)
    Base DN: DC=corp,DC=local
    Bind DN: CN=svc-fac,OU=Service Accounts,DC=corp,DC=local
    Bind Password: <password>
    Username Attr: sAMAccountName
    Group Membership Attr: memberOf
```

### Security Groups → RADIUS VLAN Mapping
```
AD Group                    → VLAN    → Access Level
──────────────────────────────────────────────────────
Corp-WiFi-Data              → 10       Data
Corp-WiFi-Voice             → 20       Voice
Corp-WiFi-Guest             → 40       Internet only
Corp-WiFi-BYOD              → 50       IoT/Restricted
```

---

## FSSO (Fortinet Single Sign-On)

### FSSO Collector Agent Flow
```
User Login → AD DC → DC Agent / Collector Agent → FortiGate
                ↓
         Security Event Log (Event ID 4624)
                ↓
         FSSO: IP → Username → Group mapping
                ↓
         FortiGate policy: identity-based
```

### FSSO Modes
| Mode | Component | Description |
|------|-----------|-------------|
| DC Agent | Agent on each DC | Real-time monitoring of login events |
| Collector Agent | Central agent | Polls DCs via WMI/DCOM |
| Agentless | FortiAuthenticator | Polls DC directly — no agent needed |
| NTLM | Browser redirect | Browser-based transparent auth |

### FortiGate FSSO Setup
```bash
config user fsso
    edit "FAC-FSSO"
        set server "10.0.0.50"          # FortiAuthenticator IP
        set port 8000
        set password <fsso-password>
    next
end

config user group
    edit "Corp-Data-Users"
        set member "FAC-FSSO"
        config match
            edit 1
                set server-name "FAC-FSSO"
                set group-name "CN=Corp-WiFi-Data,OU=Groups,DC=corp,DC=local"
            next
        end
    next
end
```

---

## Two-Factor Authentication (2FA)

### FortiToken Mobile (TOTP)
- Time-based One-Time Password (RFC 6238)
- 30-second rotation
- Works offline
- Provisioned via QR code from FortiAuthenticator

### 2FA Enforcement Policy
```
Authentication → Portals → Local Services
    → FortiGate Admin Portal:
        Require 2FA: Yes
        Token Delivery: FortiToken Mobile / Email OTP / SMS
```

### RADIUS Challenge (for VPN 2FA)
```
Flow:
1. User sends username/password
2. RADIUS → Access-Challenge (requesting OTP)
3. VPN client prompts for OTP
4. User enters OTP → RADIUS → Access-Accept
```

---

## Guest Portal Management

### Guest VLAN Workflow
```
Guest connects to Guest-SSID
    ↓
Redirect to Captive Portal (FortiAuthenticator or FortiGate)
    ↓
Options:
  a) Self-registration → email/SMS verification
  b) Sponsor approval → employee approves guest
  c) Pre-created voucher → receptionist provides
    ↓
RADIUS Access-Accept → VLAN 40 (Guest Internet)
    ↓
Internet access with time limit (e.g., 8 hours)
```

### Guest Portal Config (FortiAuthenticator)
```
Guest Management → Portals → Create
    Name: Guest-WiFi-Portal
    Type: Self-registration
    Max Session Duration: 8 hours
    Required Fields: Name, Email, Phone
    Approval Required: No (auto-approve)
    SMS Gateway: Twilio / Nexmo
```

---

## Diagnostics & Troubleshooting

### FortiGate RADIUS Debug
```bash
# Test RADIUS connectivity
diagnose test authserver radius <server-name> <username> <password>

# Live RADIUS debug
diagnose debug application fnbamd 255
diagnose debug enable
# → Then attempt authentication

# Check RADIUS accounting
diagnose test authserver radius-accounting <server-name>
```

### FortiAuthenticator Logs
```
Logging → Log Access → RADIUS Logs
    Filter: Authentication Result = Reject
    → Shows: User, NAS-IP, Reason for reject
```

### 802.1X Port Debug (FortiGate)
```bash
# Check port auth state
diagnose switch-controller switch-info port-stats <serial> <port>

# 802.1X auth debug
diagnose debug application dot1xd 255
diagnose debug enable
```

### Common Authentication Issues
| Symptom | Root Cause | Fix |
|---------|-----------|-----|
| User authenticated but wrong VLAN | Group mapping incorrect | Fix RADIUS group → VLAN mapping |
| EAP-TLS fails | Client cert not trusted | Import CA cert into authenticator |
| PEAP fails | Wrong inner method | Match EAP type in supplicant and server |
| MAB fails | MAC not in whitelist | Add MAC to FortiAuthenticator |
| FSSO users not in policy | FSSO group name mismatch | Verify DN format |
| 2FA loop | NPS not forwarding challenge | Use FortiAuthenticator as primary RADIUS |
