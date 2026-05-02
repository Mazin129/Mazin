# NSE 6 — LAN Edge Architect: Practice Exam (120 Questions)

> Format mirrors the real exam. Each question has one best answer unless marked **(Select 2)**.
> Answers and detailed explanations follow each section.

---

## Section 1: FortiSwitch & FortiLink (Questions 1–30)

**Q1.** An administrator configures a FortiGate interface as type `fortilink`. Which protocol does FortiGate use to discover and manage connected FortiSwitch units?

- A) SNMP
- B) LLDP / FortiLink discovery
- C) CDP
- D) NetFlow

---

**Q2.** A FortiSwitch is operating in managed mode. The administrator wants to assign VLAN 20 as untagged on port5. Which configuration hierarchy on the FortiGate is correct?

- A) `config switch-controller managed-switch → edit <SN> → config ports → edit port5 → set vlan vlan20`
- B) `config system interface → edit port5 → set vlanid 20`
- C) `config switch-controller vlan → edit vlan20 → set port5 untagged`
- D) `config switch-controller managed-switch → edit <SN> → set default-vlan vlan20`

---

**Q3.** Which two statements about MCLAG are correct? **(Select 2)**

- A) MCLAG requires three FortiSwitch units minimum
- B) MCLAG eliminates STP blocking on uplink ports
- C) The ICL (Inter-Chassis Link) carries control and data traffic between MCLAG peers
- D) MCLAG only supports static LAG, not LACP
- E) MCLAG peers each maintain an independent LACP state machine

---

**Q4.** A FortiSwitch port is configured with `set stp-bpdu-guard enable`. What happens when a BPDU is received on that port?

- A) The BPDU is forwarded normally
- B) The port is placed in STP blocking state
- C) The port is disabled (err-disabled) immediately
- D) An alert is generated but traffic continues

---

**Q5.** What is the default STP mode on FortiSwitch?

- A) STP (802.1D)
- B) RSTP (802.1w)
- C) MSTP (802.1s)
- D) PVST+

---

**Q6.** An administrator notices that a FortiSwitch has been discovered by FortiGate but shows status "Unauthorized". What is the most likely reason?

- A) The FortiLink interface is down
- B) The switch serial number is not in the FortiGate trusted list
- C) LLDP is disabled on FortiGate
- D) The FortiSwitch firmware is too old

---

**Q7.** Which command on FortiGate shows the MAC address table of a managed FortiSwitch?

- A) `get switch mac-table all`
- B) `diagnose switch-controller switch-info mac-table <serial>`
- C) `show switch-controller mac <serial>`
- D) `diagnose netlink brctl host`

---

**Q8.** A FortiSwitch trunk port connects to a third-party router. The router uses VLAN 1 as the native VLAN. What security risk does this create?

- A) VLAN hopping via double-tagging attacks
- B) STP root bridge election manipulation
- C) MAC flooding attacks
- D) ARP spoofing across VLANs

---

**Q9.** Which FortiSwitch feature limits the number of MAC addresses learned on an access port?

- A) BPDU guard
- B) Storm control
- C) MAC address limiting (`set learning-limit`)
- D) Port isolation

---

**Q10.** An administrator needs to configure 802.1Q trunking between a FortiSwitch and a Cisco switch. Which VLANs must be explicitly allowed on the FortiSwitch trunk port?

- A) Only the native VLAN
- B) All VLANs exist automatically on trunk ports
- C) Only VLANs explicitly listed in `set allowed-vlans`
- D) VLANs 1–4094 are allowed by default; none need explicit configuration

---

**Q11.** What is the purpose of the `edge-port` setting on a FortiSwitch port?

- A) Enables BPDU forwarding to edge devices
- B) Enables PortFast — port transitions directly to forwarding without STP delay
- C) Marks the port as an ISL trunk
- D) Disables MAC learning on the port

---

**Q12.** In MSTP, what is an "instance"?

- A) A physical switch in the topology
- B) A group of VLANs that share the same spanning tree topology
- C) A single STP root bridge election domain
- D) A VLAN-specific BPDU packet

---

**Q13.** Storm control is configured with `set broadcast-rate 100` (pps). What happens when broadcast traffic exceeds 100 pps on a port?

- A) The port is shut down
- B) Excess broadcast frames are dropped
- C) Excess broadcasts are forwarded to the CPU for inspection
- D) A SNMP trap is generated only

---

**Q14.** Which port role in MSTP is responsible for forwarding traffic away from the root bridge?

- A) Root Port
- B) Designated Port
- C) Alternate Port
- D) Backup Port

---

**Q15.** An administrator wants to prevent a rogue switch from becoming the STP root bridge on access ports. Which two features should be enabled? **(Select 2)**

- A) BPDU Guard
- B) Root Guard
- C) Loop Guard
- D) UDLD
- E) Storm Control

---

**Q16.** FortiSwitch supports PoE (Power over Ethernet). Where is PoE power budget configured in managed mode?

- A) Directly on the FortiSwitch CLI
- B) `config switch-controller managed-switch → edit <SN> → config ports → edit <port> → set poe-standard`
- C) FortiSwitch standalone GUI only
- D) It is automatic and cannot be configured

---

**Q17.** An administrator wants all voice traffic (DSCP EF) to use the highest-priority queue. Where is this mapping configured on a managed FortiSwitch?

- A) `config switch-controller qos ip-dscp-map`
- B) `config system interface → edit vlan20 → set cos 7`
- C) DSCP-to-CoS mapping is automatic and fixed
- D) Only on the FortiGate firewall policy

---

**Q18.** Which command verifies the FortiLink physical connectivity from the FortiGate side?

- A) `get system interface physical`
- B) `diagnose netlink brctl host`
- C) `diagnose switch-controller switch-info port-stats <serial> <port>`
- D) `get switch-controller managed-switch`

---

**Q19.** What happens to a managed FortiSwitch if the FortiLink connection to FortiGate is severed?

- A) The switch resets to factory defaults immediately
- B) The switch continues operating with its last known configuration
- C) All ports are shut down for security
- D) The switch switches to standalone mode automatically

---

**Q20.** Which VLAN ID should NEVER be used on trunk ports for production traffic?

- A) VLAN 100
- B) VLAN 999
- C) VLAN 1
- D) VLAN 4094

---

**Q21.** An administrator configures MCLAG between FSW-A and FSW-B. The ICL port on both switches is port24. What VLAN range should the ICL trunk carry?

- A) Only the native VLAN
- B) Only VLANs used by MCLAG LAG members
- C) All VLANs present in the topology
- D) Only management VLAN

---

**Q22.** Which protocol does FortiGate use to authorize managed FortiSwitch units in the Security Fabric?

- A) SNMP v3
- B) FortiLink with device serial verification
- C) RADIUS MAC authentication
- D) IEEE 802.1AR DevID certificates

---

**Q23.** A FortiSwitch port is configured with `set port-security port-security-mode 802.1X`. An endpoint that does NOT support 802.1X connects. Which feature allows network access for this device?

- A) Guest VLAN
- B) MAC Authentication Bypass (MAB)
- C) RADIUS fallback
- D) Open authentication

---

**Q24.** What is the maximum number of FortiSwitch units that can be stacked in a single FortiLink domain?

- A) 8
- B) 16
- C) 24
- D) 48

---

**Q25.** An administrator notices traffic looping between two FortiSwitch units. MSTP appears to be running. What is the most likely cause?

- A) Incorrect MSTP region name or revision number causing different regions
- B) PortFast enabled on trunk ports
- C) Storm control threshold too high
- D) ICL port not configured

---

**Q26.** Which CLI command on FortiGate authorizes a newly discovered FortiSwitch?

- A) `execute switch-controller authorize <serial>`
- B) `config switch-controller managed-switch → edit <SN> → set fsw-wan1-peer-port auto`
- C) `execute switch-controller get-conn-status`
- D) Authorization is only possible via GUI

---

**Q27.** An administrator wants to mirror all traffic from port3 of a FortiSwitch to port8 for analysis. Which feature is used?

- A) RSPAN
- B) Port mirroring (SPAN)
- C) NetFlow export
- D) sFlow

---

**Q28.** The FortiLink interface on FortiGate is a LAG (802.3ad). What is the benefit of this configuration?

- A) Provides VLAN separation between FortiGate and FortiSwitch
- B) Provides redundancy and increased bandwidth for the FortiLink uplink
- C) Enables MCLAG functionality
- D) Required for 802.1X to work on FortiSwitch

---

**Q29.** Which statement about FortiSwitch VLANs in managed mode is correct?

- A) VLANs must be created on FortiSwitch CLI first, then referenced on FortiGate
- B) VLANs are created on FortiGate as interface objects and pushed to FortiSwitch via FortiLink
- C) VLANs are synchronized from FortiAnalyzer
- D) FortiSwitch VLANs are independent from FortiGate VLANs

---

**Q30.** An administrator needs to isolate two ports on the same VLAN from communicating directly. Which FortiSwitch feature achieves this?

- A) Private VLAN
- B) Port isolation / intra-VLAN blocking
- C) BPDU guard
- D) MAC address limiting

---

## Section 2: FortiAP & Wireless (Questions 31–60)

**Q31.** Which UDP port does the CAPWAP control channel use?

- A) 443
- B) 5246
- C) 5247
- D) 8443

---

**Q32.** An AP is in **tunnel mode**. Where is wireless client traffic processed (firewall policies applied)?

- A) On the AP itself
- B) On the FortiGate managing the AP
- C) On the nearest L3 switch
- D) Traffic bypasses the firewall in tunnel mode

---

**Q33.** Which wireless security standard provides forward secrecy and resistance to offline dictionary attacks?

- A) WPA2-Personal (PSK)
- B) WPA2-Enterprise (802.1X)
- C) WPA3-Personal (SAE)
- D) WEP

---

**Q34.** What does OWE (Opportunistic Wireless Encryption) provide on an open SSID?

- A) Authentication with username and password
- B) Per-client encryption without authentication
- C) Certificate-based mutual authentication
- D) MAC address filtering

---

**Q35.** An AP profile has `set pmf required`. Which clients will be REFUSED association?

- A) Clients using WPA3-Personal
- B) Clients that do not support 802.11w (PMF)
- C) Clients on 5 GHz band only
- D) Clients using EAP-TLS

---

**Q36.** Which CAPWAP channel carries wireless client data traffic in tunnel mode?

- A) UDP 5246 (control)
- B) UDP 5247 (data)
- C) TCP 443
- D) GRE tunnel

---

**Q37.** An administrator wants to prevent wireless clients on the same SSID from communicating with each other. Which VAP setting achieves this?

- A) `set local-bridging disable`
- B) `set intra-vap-privacy enable`
- C) `set vlan-pooling enable`
- D) `set dhcp-option82 enable`

---

**Q38.** Which 802.11 amendment introduces OFDMA and BSS Coloring for high-density deployments?

- A) 802.11ac (WiFi 5)
- B) 802.11n (WiFi 4)
- C) 802.11ax (WiFi 6)
- D) 802.11be (WiFi 7)

---

**Q39.** In a high-density wireless deployment, an administrator limits channel width to 20 MHz on the 2.4 GHz radio. What is the primary benefit?

- A) Higher maximum throughput per client
- B) Reduced co-channel interference; more non-overlapping channels
- C) Enables MU-MIMO
- D) Increases DTLS encryption strength

---

**Q40.** A wireless client is experiencing roaming delays of over 50ms between APs. Which 802.11 amendment resolves this?

- A) 802.11k
- B) 802.11r (FT — Fast BSS Transition)
- C) 802.11v
- D) 802.11w

---

**Q41.** What role does 802.11k play in the roaming process?

- A) Encrypts management frames
- B) Reduces re-authentication time during roaming
- C) Provides neighbor AP reports so clients can make informed roaming decisions
- D) Allows the AP to push clients to roam (BSS transition management)

---

**Q42.** A WIDS profile detects more than 10 deauthentication frames per second from an unknown BSSID. What type of attack is this?

- A) EAPOL replay
- B) Deauth flood (DoS attack against wireless clients)
- C) Beacon flood
- D) Rogue AP

---

**Q43.** Which WIDS detection method identifies a rogue AP that is broadcasting a legitimate corporate SSID from an unauthorized device?

- A) Deauth flood detection
- B) EAPOL replay detection
- C) Spoofed/evil twin AP detection
- D) Beacon interval anomaly

---

**Q44.** WIPS active containment sends which type of frame to disconnect clients from rogue APs?

- A) Probe response
- B) Disassociation / Deauthentication frame
- C) Beacon with wrong SSID
- D) CTS-to-Self frame

---

**Q45.** An administrator enables DTLS on the CAPWAP data channel. What is the impact?

- A) AP management traffic is encrypted
- B) Wireless client data traffic between AP and FortiGate is encrypted
- C) DTLS only applies to the control channel; data channel cannot be encrypted
- D) Increases roaming speed

---

**Q46.** Which AP operating mode uses another AP as a wireless uplink instead of a wired connection?

- A) Bridge mode
- B) Tunnel mode
- C) Mesh mode
- D) Monitor mode

---

**Q47.** An AP radio is configured in **monitor mode**. What functionality does the AP provide?

- A) Serves wireless clients as normal
- B) Scans all channels for rogue devices and WIDS events only
- C) Provides mesh backhaul
- D) Bridges wireless clients to a local VLAN

---

**Q48.** What is the purpose of the **handoff-rssi** setting in a WTP profile?

- A) Sets maximum transmit power
- B) Defines the RSSI threshold below which clients are encouraged to roam to a better AP
- C) Sets the minimum signal strength for AP discovery
- D) Controls the CAPWAP heartbeat interval

---

**Q49.** A guest SSID uses a captive portal managed by FortiAuthenticator. A guest connects to the SSID and opens a browser. What happens first?

- A) RADIUS authentication occurs
- B) DNS resolution succeeds, and the browser is redirected to the captive portal URL
- C) The client receives a self-signed certificate warning
- D) The client is placed in quarantine VLAN immediately

---

**Q50.** An administrator wants to schedule the guest SSID to only be available Monday–Friday 08:00–18:00. Which VAP setting achieves this?

- A) `set schedule "business-hours"` referencing a recurring schedule object
- B) `set time-on 0800 time-off 1800`
- C) `set vlan-pooling schedule`
- D) Schedule is only configurable per-AP profile, not per SSID

---

**Q51.** Which two 802.11ax (WiFi 6) features specifically improve performance in high-density environments? **(Select 2)**

- A) OFDMA (Orthogonal Frequency Division Multiple Access)
- B) MU-MIMO downlink only
- C) BSS Coloring
- D) Beamforming (802.11ac feature)
- E) Channel bonding up to 160 MHz

---

**Q52.** WPA3-Enterprise 192-bit mode is based on which suite of algorithms?

- A) AES-128/SHA-256
- B) CNSA (Commercial National Security Algorithm Suite) — AES-256/SHA-384/ECDHE-384
- C) Suite B (NSA) — AES-128/SHA-1
- D) FIPS 140-2 Level 3 only

---

**Q53.** An administrator notices that AP auto-power is pushing transmit power to maximum (20 dBm) on all APs. What is the likely cause?

- A) 802.11r is disabled
- B) AP density is too low, or neighboring APs are too far apart; auto-power sees low RSSI from neighbors
- C) DTLS is consuming too much CPU
- D) 2.4 GHz and 5 GHz are on the same radio

---

**Q54.** In FortiAP bridge mode, where does wireless client traffic exit the network?

- A) Tunneled to FortiGate for policy enforcement
- B) Directly on the local LAN segment of the AP — bypasses FortiGate
- C) Through FortiAnalyzer
- D) Through FortiAuthenticator

---

**Q55.** Which command lists all wireless clients currently associated to managed APs?

- A) `get wireless-controller wtp`
- B) `diagnose wireless-controller wlac -c sta`
- C) `get wireless-controller vap`
- D) `diagnose sys csf topology`

---

**Q56.** A WPA2-Enterprise SSID uses PEAP-MSCHAPv2. An administrator wants to upgrade to EAP-TLS for stronger security. What additional infrastructure is required?

- A) Nothing; EAP-TLS uses the same username/password as PEAP
- B) A PKI with client certificates enrolled on each device
- C) A second RADIUS server for redundancy
- D) FortiAnalyzer integration

---

**Q57.** Which feature prevents wireless clients from being discovered by other clients on the same AP/SSID?

- A) WIDS monitoring
- B) Intra-VAP privacy (`set intra-vap-privacy enable`)
- C) AP isolation at the switch level
- D) PMF (802.11w)

---

**Q58.** An administrator wants to load-balance wireless clients between 2.4 GHz and 5 GHz radios on a dual-band AP. Which feature enables this?

- A) 802.11k neighbor reports
- B) Band steering
- C) MU-MIMO
- D) 802.11r fast transition

---

**Q59.** What is the default CAPWAP discovery method used by FortiAPs?

- A) Unicast to a manually configured FortiGate IP
- B) Layer 2 broadcast/multicast on the management VLAN, then DHCP option 138
- C) DNS lookup of "fortiwlc.local"
- D) Anycast discovery via FortiGuard

---

**Q60.** An AP shows status "Downloading" in the FortiGate wireless controller. What is happening?

- A) The AP is receiving its SSID configuration
- B) The AP is downloading a firmware upgrade from FortiGate
- C) The AP is downloading threat intelligence
- D) The AP is synchronizing WIDS signatures

---

## Section 3: FortiAuthenticator & NAC (Questions 61–85)

**Q61.** Which RADIUS attribute combination is used to dynamically assign a VLAN to an 802.1X authenticated port?

- A) `Tunnel-Type=VLAN`, `Tunnel-Medium-Type=IEEE-802`, `Tunnel-Private-Group-Id=<VLAN-ID>`
- B) `Framed-IP-Address=<IP>`, `Framed-Subnet-Mask=<mask>`
- C) `Class=VLAN:<VLAN-ID>`
- D) `Filter-Id=VLAN<VLAN-ID>`

---

**Q62.** A network printer does not support 802.1X. Which mechanism allows it to gain network access through a FortiSwitch port configured for 802.1X?

- A) Guest VLAN assignment
- B) MAC Authentication Bypass (MAB)
- C) Open authentication fallback
- D) Static VLAN assignment override

---

**Q63.** In EAP-TLS, which certificates are required? **(Select 2)**

- A) CA certificate on the RADIUS server
- B) Client certificate on each supplicant
- C) RADIUS server certificate
- D) Intermediate CA certificate must be self-signed

---

**Q64.** Which EAP method uses a PAC (Protected Access Credential) file instead of a certificate?

- A) EAP-TLS
- B) PEAP
- C) EAP-FAST
- D) EAP-TTLS

---

**Q65.** FortiAuthenticator is configured as an LDAP proxy. A RADIUS request arrives for user `jsmith`. In what order does FortiAuthenticator process authentication?

- A) Local user check → LDAP bind → RADIUS policy match
- B) RADIUS policy match → local user or LDAP bind based on realm
- C) LDAP bind first → RADIUS policy last
- D) 2FA check → LDAP bind → policy match

---

**Q66.** Which port does RADIUS CoA (Change of Authorization) use?

- A) UDP 1812
- B) UDP 1813
- C) UDP 3799
- D) TCP 49 (TACACS+)

---

**Q67.** A user has been authenticated and assigned to VLAN 10. A security scan detects the device is non-compliant. Which mechanism allows the network to move the user to a quarantine VLAN without disconnecting them physically?

- A) Re-authentication timer
- B) RADIUS CoA (Change of Authorization) with new VLAN attributes
- C) SNMP trap to FortiSwitch
- D) FortiClient EMS policy push

---

**Q68.** FSSO DC agent monitors which Windows event log for user login events?

- A) Application Log
- B) Security Log (Event ID 4624 — successful logon)
- C) System Log
- D) PowerShell Operational Log

---

**Q69.** An administrator configures FSSO with a Collector Agent. The FortiGate group policy references `CN=Corp-Users,OU=Groups,DC=corp,DC=local`. Wireless clients authenticate via 802.1X but FSSO policies do not apply. What is the most likely cause?

- A) FSSO only works with wired connections
- B) The FSSO group DN does not match the actual AD group DN exactly
- C) FortiAuthenticator is not configured as FSSO source
- D) CAPWAP is blocking FSSO traffic

---

**Q70.** What is the purpose of FortiToken Mobile in a 2FA deployment?

- A) Provides hardware-based VPN token
- B) Generates TOTP codes on a mobile device for use as a second factor
- C) Acts as a SAML Identity Provider
- D) Stores client certificates

---

**Q71.** Which LDAP attribute is typically used as the username for AD authentication in FortiAuthenticator?

- A) `cn`
- B) `sAMAccountName`
- C) `userPrincipalName` (only)
- D) `distinguishedName`

---

**Q72.** An administrator wants to allow self-registered guest users to authenticate with email verification only (no sponsor approval). Which portal type is appropriate?

- A) Sponsored guest portal
- B) Self-registration portal with email verification
- C) Pre-provisioned voucher portal
- D) Social login portal

---

**Q73.** A RADIUS server sends `Access-Reject` to a FortiSwitch port. What happens to the 802.1X supplicant by default?

- A) Assigned to Auth-Fail VLAN if configured; otherwise port remains unauthorized
- B) Assigned to Guest VLAN automatically
- C) Port is shut down
- D) Client is assigned to VLAN 1

---

**Q74.** FortiAuthenticator SAML IdP is configured for a cloud application. Which protocol flow does SAML 2.0 SP-initiated SSO use?

- A) SP → User Browser → IdP (FAC) → User Browser → SP
- B) IdP → SP → User directly
- C) RADIUS challenge-response
- D) OAuth2 authorization code flow

---

**Q75.** Which feature of FortiAuthenticator generates one-time passwords delivered via SMS for users without a smartphone?

- A) FortiToken Mobile
- B) FortiToken Hardware (FTK)
- C) SMS token delivery via connected SMS gateway
- D) Email OTP

---

**Q76.** An administrator needs to allow wired 802.1X authenticated users to access network resources before completing full authentication (e.g., to download a RADIUS client). Which feature provides limited access during authentication?

- A) Auth-Fail VLAN
- B) Guest VLAN
- C) MAB fallback
- D) Pre-auth VLAN (Restricted VLAN)

---

**Q77.** Which two FSSO deployment modes require NO software installation on domain controllers? **(Select 2)**

- A) DC Agent mode
- B) Agentless polling (FortiAuthenticator polls DC via WMI)
- C) NTLM authentication
- D) Collector Agent mode
- E) Syslog listening

---

**Q78.** An 802.1X authenticated session expires due to re-authentication timeout. What happens next by default?

- A) Port is shut down
- B) Supplicant silently re-authenticates using cached credentials
- C) Port is placed in unauthorized state and EAP re-authentication is triggered
- D) User is assigned to Guest VLAN

---

**Q79.** Which command tests RADIUS authentication from FortiGate CLI?

- A) `diagnose debug application fnbamd 255`
- B) `diagnose test authserver radius <server> <user> <password>`
- C) `execute test radius <server>`
- D) `diagnose test authserver ldap <server>`

---

**Q80.** A FortiAuthenticator has a local CA. What is required to enable EAP-TLS on a RADIUS policy?

- A) Import the CA cert to FortiGate only
- B) Upload the server certificate to FAC signed by the local CA, and distribute the CA cert to all supplicants
- C) EAP-TLS does not require a CA on FortiAuthenticator
- D) The CA must be from a public trusted CA (DigiCert, etc.)

---

**Q81.** Which FortiNAC feature uses RADIUS accounting to track device location on the network?

- A) Device profiling
- B) Network Access Policy
- C) RADIUS accounting listener for port/switch/VLAN correlation
- D) Passive fingerprinting

---

**Q82.** An IoT device is identified as non-compliant by FortiNAC. What action does FortiNAC take to isolate it?

- A) Sends SNMP write to FortiSwitch to disable the port
- B) Sends RADIUS CoA to reassign the device to the quarantine VLAN
- C) Pushes a firewall policy to FortiGate to block the device's IP
- D) Emails the network administrator

---

**Q83.** Which protocol does FortiNAC use to discover network topology from FortiSwitch/routers?

- A) NetFlow
- B) sFlow
- C) SNMP (read-only community or SNMPv3)
- D) IPFIX

---

**Q84.** An administrator wants FortiAuthenticator to proxy RADIUS requests to a Microsoft NPS server for a specific realm. Which feature enables this?

- A) RADIUS relay / RADIUS proxy
- B) LDAP proxy
- C) SAML federation
- D) FSSO relay

---

**Q85.** A FortiSwitch port is configured with 802.1X. The administrator also enables the Auth-Fail VLAN. What is the purpose of Auth-Fail VLAN?

- A) Assigns clients a VLAN when 802.1X times out (no RADIUS response)
- B) Assigns clients a VLAN when authentication fails (wrong credentials)
- C) Assigns clients a VLAN while 802.1X is in progress
- D) Replaces the need for MAB

---

## Section 4: Security Fabric & FortiNAC (Questions 86–120)

**Q86.** What TCP port is used for Security Fabric communication between FortiGate devices?

- A) 443
- B) 8013
- C) 8443
- D) 541

---

**Q87.** Which component is mandatory for FortiGate to join a Security Fabric as a root device?

- A) FortiManager connectivity
- B) FortiAnalyzer connectivity (logging must be configured)
- C) FortiClient EMS
- D) FortiAuthenticator

---

**Q88.** An administrator runs `diagnose sys csf topology`. The output shows a downstream FortiGate as "UNAUTHORIZED". What must be done?

- A) Upgrade the downstream FortiGate firmware
- B) Authorize the downstream FortiGate's serial number in the root FGT trusted list
- C) Reconfigure the upstream-ip on the downstream FGT
- D) Restart the csfd process

---

**Q89.** Which two trigger types are available in Security Fabric Automation Stitches? **(Select 2)**

- A) IOC (Indicator of Compromise) match
- B) Scheduled time trigger
- C) BGP route change
- D) Security Rating failure
- E) OSPF neighbor down

---

**Q90.** A ZTNA access proxy is configured on FortiGate. What does ZTNA verify before granting application access?

- A) Only username and password
- B) Device identity (certificate) AND device posture (ZTNA tags from EMS)
- C) Source IP address only
- D) VLAN membership

---

**Q91.** Which FortiGate feature provides automatic dynamic address objects populated from AWS EC2 instance tags?

- A) FSSO connector
- B) SDN connector with dynamic address filter
- C) FortiNAC device profiling
- D) BGP community tagging

---

**Q92.** Which Security Fabric component provides endpoint visibility including application inventory and posture assessment?

- A) FortiAnalyzer
- B) FortiAuthenticator
- C) FortiClient EMS
- D) FortiNAC

---

**Q93.** An automation stitch should quarantine a host when a high-severity IOC is matched. Which action type achieves this in FortiGate?

- A) `action-type webhook`
- B) `action-type quarantine`
- C) `action-type email`
- D) `action-type script`

---

**Q94.** What does the Security Rating "Fabric Coverage" category check?

- A) That all FortiGate policies have logging enabled
- B) That all network segments have at least one Fortinet device as a member
- C) That FortiAnalyzer is receiving all required log types
- D) That all admin accounts use 2FA

---

**Q95.** FortiNAC device profiling uses passive fingerprinting. Which three data sources are used? **(Select 3)**

- A) DHCP option 55 (parameter request list)
- B) HTTP User-Agent string
- C) MAC OUI (Organizationally Unique Identifier)
- D) Windows Registry query
- E) BGP AS path

---

**Q96.** Which command on FortiGate verifies that the Security Fabric automation stitches are firing correctly?

- A) `diagnose sys automation-stitch test <name>`
- B) `diagnose sys csf check`
- C) `get system automation-stitch`
- D) `execute automation test`

---

**Q97.** An administrator wants to enforce that all FortiGate admins use two-factor authentication. Where is this configured to apply globally across the fabric?

- A) Each FortiGate admin account individually
- B) Security Fabric → Fabric Settings → Enforce 2FA
- C) FortiManager policy package
- D) RADIUS server policy

---

**Q98.** Which ZTNA tag indicates a device passed the FortiClient EMS antivirus compliance check?

- A) `ems-tag: AV-compliant` (configured in EMS tag policy)
- B) `av=pass` (hardcoded)
- C) ZTNA tags are free-form and defined by EMS admin in tag policies
- D) ZTNA does not check antivirus status

---

**Q99.** FortiNAC receives a RADIUS accounting Start message. What information does FortiNAC extract from this message?

- A) User credentials
- B) NAS-IP, NAS-Port, MAC address, assigned VLAN — used to map device to switch port
- C) Device vulnerability scan results
- D) FortiClient posture data

---

**Q100.** An SDN connector is configured for VMware NSX-T. FortiGate creates dynamic address objects. What must be configured on NSX-T for this integration?

- A) NSX-T must have the FortiGate public IP in its allow list
- B) NSX-T Manager API credentials must be provided to the SDN connector
- C) FortiGate must be registered as a VMware partner service
- D) SNMP community string must match

---

**Q101.** A Security Fabric automation stitch uses a webhook action. The webhook calls an external SIEM API. Which HTTP method is typically used to submit event data?

- A) GET
- B) POST
- C) PUT
- D) DELETE

---

**Q102.** Which feature allows FortiGate to push Security Fabric policies to all downstream FortiGate devices simultaneously?

- A) FortiManager policy packages
- B) Security Fabric policy synchronization from root FortiGate
- C) FSSO group sync
- D) Automation stitches

---

**Q103.** What is the primary difference between FortiNAC and 802.1X NAC?

- A) FortiNAC cannot enforce 802.1X
- B) FortiNAC provides agentless device profiling and policy enforcement for ALL devices including those that cannot run 802.1X supplicants
- C) 802.1X provides better IoT device support
- D) FortiNAC only works with FortiSwitch

---

**Q104.** An administrator notices that the Security Fabric topology shows a FortiSwitch as "disconnected" even though it is operational. What is the likely cause?

- A) The FortiSwitch firmware is too old
- B) FortiLink is down between FortiGate and FortiSwitch
- C) FortiAnalyzer is not reachable
- D) The FortiSwitch license has expired

---

**Q105.** Which two actions can a FortiNAC Security Policy enforce? **(Select 2)**

- A) Assign VLAN based on device type
- B) Block device from DHCP
- C) Send RADIUS CoA to quarantine non-compliant device
- D) Reboot the endpoint remotely
- E) Push FortiClient to endpoint

---

**Q106.** The Security Fabric SAML configuration sync feature is enabled on the root FortiGate. What does this synchronize?

- A) Firewall policies
- B) SAML SP/IdP configurations to all fabric members
- C) RADIUS server configurations
- D) FortiSwitch VLAN assignments

---

**Q107.** An administrator wants to detect when a new, unknown device joins the network and automatically place it in a guest VLAN pending approval. Which solution combination achieves this?

- A) FortiNAC device profiling + Isolation Policy + RADIUS CoA
- B) FortiGate MAC filter + static VLAN assignment
- C) FortiAuthenticator MAB + pre-auth VLAN
- D) FortiSwitch BPDU guard + storm control

---

**Q108.** Which Security Fabric feature allows FortiGate to display a "topology map" showing all connected devices, their OS, and risk posture?

- A) Security Rating dashboard
- B) Physical/Logical Topology view in Security Fabric → Physical Topology
- C) FortiAnalyzer topology widget
- D) NOC/SOC view

---

**Q109.** A downstream FortiGate branch site is behind NAT. It cannot reach the root FortiGate on TCP 8013. Which workaround enables Security Fabric participation?

- A) Use HTTPS (443) for Fabric communication — configure fabric-object-unification via HTTPS
- B) Open TCP 8013 inbound on the upstream NAT device
- C) Use FortiManager as a fabric proxy
- D) Downstream FGTs behind NAT cannot join Security Fabric

---

**Q110.** Which FortiGate log category contains Security Fabric automation stitch execution events?

- A) Traffic logs
- B) Event logs → Automation category
- C) Security logs → Application Control
- D) System logs → Admin

---

**Q111.** An IoT thermostat connects to the network. FortiNAC profiles it via DHCP fingerprinting. Which policy action ensures it can ONLY reach the building automation server (10.10.1.5)?

- A) Assign it to VLAN 50 and configure a FortiGate policy allowing VLAN 50 only to 10.10.1.5
- B) Apply a MAC filter on FortiSwitch
- C) Place it in VLAN 1 with no routing
- D) Use WIDS to isolate the device

---

**Q112.** What is the purpose of FortiClient EMS "ZTNA Connection Rules"?

- A) Define which applications require ZTNA access vs. VPN
- B) Define the posture tags sent to FortiGate for each client
- C) Control which SSID FortiClient connects to
- D) Push firewall rules to FortiClient

---

**Q113.** A Security Fabric stitch is configured to trigger on "Security Rating: Failed — Posture". Which configuration issue typically triggers this?

- A) FortiGate firmware is outdated
- B) Admin account without 2FA, or unrestricted trusted hosts
- C) FortiSwitch port VLAN mismatch
- D) FortiAP profile missing WIDS

---

**Q114.** Which command shows the Security Fabric certificate trust status between FortiGate members?

- A) `get certificate ca`
- B) `diagnose sys csf check`
- C) `diagnose cert ca-chain`
- D) `get system csf`

---

**Q115.** FortiNAC scans the network and finds 500 devices. 50 are profiled as "Unknown". What should the administrator do?

- A) Delete unknown devices immediately
- B) Create custom profiling rules or manually classify devices, then apply appropriate access policies
- C) Place all unknown devices in VLAN 1
- D) Enable WIDS monitoring for unknown devices

---

**Q116.** An administrator uses a FortiGate automation stitch to call a webhook when a user is quarantined. The webhook notifies ServiceNow to create an incident. This is an example of which security concept?

- A) SOAR (Security Orchestration, Automation and Response)
- B) SIEM correlation
- C) Threat hunting
- D) Penetration testing

---

**Q117.** Which two components are part of the Fortinet Security Fabric but do NOT run FortiOS? **(Select 2)**

- A) FortiGate
- B) FortiAnalyzer
- C) FortiAuthenticator
- D) FortiSwitch (standalone)
- E) FortiManager

---

**Q118.** An administrator wants to ensure that all Security Fabric devices use the same NTP server. Where is this enforced?

- A) Individually on each device
- B) Security Fabric → Fabric Settings → NTP synchronization (root pushes NTP config to members)
- C) FortiManager global settings
- D) FortiAnalyzer system settings

---

**Q119.** FortiNAC uses RADIUS CoA. Which RFC defines RADIUS CoA?

- A) RFC 2865
- B) RFC 2866
- C) RFC 3576
- D) RFC 4945

---

**Q120.** An administrator wants to integrate FortiNAC with Active Directory so that device ownership is determined by the logged-in user. Which integration method enables this?

- A) LDAP group membership only
- B) FSSO (FortiNAC reads user-to-IP/port mappings from FSSO or DC agent)
- C) SNMP polling of AD
- D) FortiNAC cannot integrate with Active Directory

---

## Answer Key with Explanations

### Section 1: FortiSwitch & FortiLink

| Q | A | Explanation |
|---|---|-------------|
| 1 | B | FortiLink uses LLDP for discovery; FortiGate sends FortiLink-specific LLDP TLVs |
| 2 | A | Managed switch port VLANs are configured under `config switch-controller managed-switch` |
| 3 | B, C | MCLAG eliminates STP blocking on uplinks and requires ICL between peer switches |
| 4 | C | BPDU Guard err-disables the port immediately upon BPDU receipt |
| 5 | C | MSTP (802.1s) is the FortiSwitch default |
| 6 | B | New switches must be authorized; serial must be in FGT trusted list |
| 7 | B | `diagnose switch-controller switch-info mac-table <serial>` |
| 8 | A | Native VLAN 1 on trunk enables double-tagging VLAN hopping |
| 9 | C | `set learning-limit` limits MACs per port |
| 10 | C | Only VLANs in `set allowed-vlans` are permitted on trunk |
| 11 | B | Edge-port = PortFast; bypasses STP timers |
| 12 | B | MSTP instance = group of VLANs sharing one STP topology |
| 13 | B | Storm control drops excess frames silently |
| 14 | B | Designated port forwards traffic away from root |
| 15 | A, B | BPDU Guard on access ports; Root Guard on ports where root should never appear |
| 16 | B | PoE configured per-port under managed-switch config on FortiGate |
| 17 | A | `config switch-controller qos ip-dscp-map` maps DSCP to CoS queues |
| 18 | B | `diagnose netlink brctl host` shows FortiLink bridge and members |
| 19 | B | Managed FortiSwitch continues with last config if FortiLink is lost |
| 20 | C | VLAN 1 is native default — susceptible to attacks; never use for production |
| 21 | C | ICL must carry ALL VLANs so MCLAG peers can pass any client traffic |
| 22 | B | FortiLink authorization uses serial number verification |
| 23 | B | MAB uses MAC as credentials for non-802.1X devices |
| 24 | D | Up to 48 FortiSwitches per FortiLink domain (model-dependent) |
| 25 | A | Different region names/revisions create separate MSTP regions causing loops |
| 26 | A | `execute switch-controller authorize <serial>` |
| 27 | B | Port mirroring (SPAN) copies traffic to a monitor port |
| 28 | B | LAG FortiLink provides redundancy + bandwidth aggregation |
| 29 | B | VLANs created on FGT as interfaces, pushed via FortiLink to FSW |
| 30 | B | Port isolation / intra-VLAN blocking prevents same-VLAN direct L2 communication |

### Section 2: FortiAP & Wireless

| Q | A | Explanation |
|---|---|-------------|
| 31 | B | CAPWAP control = UDP 5246 |
| 32 | B | Tunnel mode: all traffic tunneled to FortiGate for policy enforcement |
| 33 | C | WPA3-SAE provides forward secrecy and resists offline dictionary attacks |
| 34 | B | OWE encrypts per-client without requiring authentication |
| 35 | B | PMF required = clients without 802.11w support are refused |
| 36 | B | CAPWAP data = UDP 5247 |
| 37 | B | `intra-vap-privacy enable` blocks client-to-client on same SSID |
| 38 | C | 802.11ax (WiFi 6) introduces OFDMA and BSS Coloring |
| 39 | B | 20 MHz on 2.4 GHz = 3 non-overlapping channels; reduces co-channel interference |
| 40 | B | 802.11r (FT) reduces roaming to ~2ms |
| 41 | C | 802.11k provides neighbor reports for informed roaming decisions |
| 42 | B | Deauth flood = DoS attack sending spoofed deauth frames to disconnect clients |
| 43 | C | Evil twin/spoofed SSID detection |
| 44 | B | WIPS sends deauth/disassoc frames to disconnect rogue clients |
| 45 | B | DTLS on data channel encrypts client traffic between AP and FGT |
| 46 | C | Mesh mode uses wireless backhaul |
| 47 | B | Monitor mode = full-time WIDS scanning; no client service |
| 48 | B | handoff-rssi = threshold for AP to encourage roaming |
| 49 | B | Captive portal: DNS resolves, HTTP redirect triggers portal |
| 50 | A | `set schedule` on VAP referencing FortiGate recurring schedule object |
| 51 | A, C | OFDMA (multi-user orthogonal channels) and BSS Coloring (spatial reuse) are WiFi 6 HD features |
| 52 | B | WPA3-Enterprise 192-bit = CNSA suite (AES-256-GCM/SHA-384/ECDHE-384) |
| 53 | B | Low AP density → auto power increases TX; APs can't hear neighbors well |
| 54 | B | Bridge mode: traffic exits locally on AP's wired LAN — bypasses FortiGate |
| 55 | B | `diagnose wireless-controller wlac -c sta` |
| 56 | B | EAP-TLS requires client certificates (PKI infrastructure) |
| 57 | B | Intra-VAP privacy prevents client discovery on same SSID |
| 58 | B | Band steering moves capable clients to 5 GHz |
| 59 | B | FortiAP default: Layer 2 broadcast/multicast, then DHCP option 138 |
| 60 | B | "Downloading" = AP upgrading firmware from FortiGate image repository |

### Section 3: FortiAuthenticator & NAC

| Q | A | Explanation |
|---|---|-------------|
| 61 | A | RFC 3580 defines Tunnel-Type/Medium-Type/Private-Group-Id for VLAN assignment |
| 62 | B | MAB: switch uses MAC address as RADIUS username/password |
| 63 | B, C | EAP-TLS requires server cert (on RADIUS) AND client cert (on supplicant) |
| 64 | C | EAP-FAST uses PAC files instead of certificates |
| 65 | B | FAC matches RADIUS policy first, then authenticates against configured user source |
| 66 | C | RADIUS CoA = UDP 3799 (RFC 3576) |
| 67 | B | RADIUS CoA sends new VLAN attributes to switch → device moved to quarantine VLAN |
| 68 | B | Security Log Event ID 4624 = successful user logon |
| 69 | B | FSSO group DN must exactly match the AD group DN including OU path |
| 70 | B | FortiToken Mobile generates TOTP codes as second factor |
| 71 | B | `sAMAccountName` is the standard AD username attribute |
| 72 | B | Self-registration with email verification = no sponsor needed |
| 73 | A | Auth-Fail VLAN assigns limited access on reject; otherwise port stays unauthorized |
| 74 | A | SP-initiated: User → SP → redirect to IdP → authenticate → redirect back to SP |
| 75 | C | SMS OTP delivery via configured SMS gateway (Twilio, etc.) |
| 76 | D | Pre-auth / Restricted VLAN = limited access during authentication process |
| 77 | B, C | Agentless (WMI polling) and NTLM require no DC agent software |
| 78 | C | Re-auth timeout: port goes unauthorized, EAP restart initiated |
| 79 | B | `diagnose test authserver radius <server> <user> <pass>` |
| 80 | B | Server cert on FAC signed by local CA; CA cert distributed to all clients |
| 81 | C | RADIUS accounting provides switch/port/VLAN for device location mapping |
| 82 | B | FortiNAC sends RADIUS CoA to reassign device to quarantine VLAN |
| 83 | C | FortiNAC uses SNMP (read community) to discover switch topology |
| 84 | A | RADIUS proxy/relay forwards requests to backend RADIUS (NPS) |
| 85 | B | Auth-Fail VLAN = assigned when credentials are wrong (authentication fails) |

### Section 4: Security Fabric & FortiNAC

| Q | A | Explanation |
|---|---|-------------|
| 86 | B | Security Fabric inter-device communication = TCP 8013 |
| 87 | B | Root FortiGate requires FortiAnalyzer for logging before fabric activation |
| 88 | B | Downstream FGT serial must be in root FGT trusted-list |
| 89 | A, D | IOC match and Security Rating failure are fabric automation triggers |
| 90 | B | ZTNA checks device certificate + EMS posture tags before allowing access |
| 91 | B | SDN connector creates dynamic address objects from cloud provider tags |
| 92 | C | FortiClient EMS provides endpoint visibility, app inventory, posture |
| 93 | B | `action-type quarantine` isolates the source host |
| 94 | B | Fabric Coverage checks all network segments have a fabric member |
| 95 | A, B, C | DHCP option 55, HTTP User-Agent, MAC OUI = passive fingerprinting sources |
| 96 | A | `diagnose sys automation-stitch test <name>` fires stitch manually |
| 97 | B | Security Fabric settings can enforce 2FA across fabric members |
| 98 | C | ZTNA tags are custom, defined by EMS admin in tag compliance policies |
| 99 | B | RADIUS accounting Start carries NAS-IP, port, MAC, VLAN — used for port mapping |
| 100 | B | SDN connector requires NSX-T Manager API credentials |
| 101 | B | Webhooks typically use HTTP POST to submit JSON event data |
| 102 | B | Root FortiGate can push policies to downstream fabric members |
| 103 | B | FortiNAC profiles ALL devices including IoT/OT without requiring a supplicant |
| 104 | B | FortiLink down = FortiSwitch shows as disconnected in fabric topology |
| 105 | A, C | FortiNAC can assign VLAN by device type and send CoA for quarantine |
| 106 | B | SAML config sync distributes SP/IdP configurations to all fabric members |
| 107 | A | FortiNAC profiling + isolation policy + RADIUS CoA for guest pending approval |
| 108 | B | Physical/Logical Topology view shows all devices with OS and risk |
| 109 | B | TCP 8013 must be forwarded through NAT for downstream FGT to join fabric |
| 110 | B | Event logs → Automation category for stitch execution |
| 111 | A | VLAN + FortiGate micro-segmentation policy restricts IoT to specific server |
| 112 | A | ZTNA Connection Rules define which apps require ZTNA vs direct/VPN |
| 113 | B | Admin without 2FA is the most common Security Rating posture failure |
| 114 | B | `diagnose sys csf check` verifies fabric trust including certificates |
| 115 | B | Create custom profiling rules for unknown devices; assign appropriate policy |
| 116 | A | SOAR = security automation with ticketing/response system integration |
| 117 | B, C | FortiAnalyzer and FortiAuthenticator run their own OS, not FortiOS |
| 118 | B | Security Fabric settings can push NTP config to all fabric members |
| 119 | C | RFC 3576 defines RADIUS Change of Authorization (CoA) |
| 120 | B | FSSO provides user-to-device mapping enabling device ownership tracking |
