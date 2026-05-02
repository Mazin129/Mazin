# NSE 7 — Enterprise Firewall Administrator: Practice Exam Part 2 (Q76–Q150) + Full Answer Key

---

## Section 5: Advanced Threat Protection (Q76–110)

**Q76.** SSL deep inspection is configured on a FortiGate. A browser shows an untrusted certificate warning when visiting HTTPS sites. What is the most likely cause?

- A) The website has an expired certificate
- B) The FortiGate's re-signing CA certificate has not been imported into client trust stores
- C) Deep inspection is blocking the site
- D) The SSL profile is set to certificate inspection only

---

**Q77.** Which two categories of websites should typically be EXEMPTED from SSL deep inspection? **(Select 2)**

- A) Social media sites
- B) Online banking / financial institutions (certificate pinning)
- C) News websites
- D) Health / medical portals where patient data privacy is required
- E) Video streaming

---

**Q78.** An IPS sensor has an entry: `set location server` `set severity critical` `set action block`. What traffic does this block?

- A) Client-side attacks targeting endpoints
- B) Critical severity attacks targeting server resources
- C) All critical attacks regardless of direction
- D) Only attacks from external (internet) sources

---

**Q79.** FortiGuard IPS signature updates are received via which communication method?

- A) SNMP traps from FortiGuard
- B) FortiGate pulls updates via HTTPS from FortiGuard Distribution Network (FDN)
- C) Push via FortiManager only
- D) Manual download and upload required

---

**Q80.** An administrator wants to capture the full packet payload when a specific IPS signature triggers. Which setting enables this?

- A) `set extended-log enable` on the IPS sensor
- B) `set packet-log enable` on the specific IPS sensor entry
- C) Enable full packet capture on the firewall policy
- D) Configure a sniffer filter for that signature ID

---

**Q81.** An application control profile has `set unknown-application-action pass`. What happens to traffic from applications not in the FortiGuard database?

- A) All unrecognized application traffic is blocked
- B) Unrecognized application traffic is allowed through
- C) Unrecognized traffic is sent to FortiSandbox
- D) Unrecognized traffic triggers a RADIUS CoA

---

**Q82.** Which feature removes malicious active content (macros, JavaScript) from files without blocking delivery entirely?

- A) FortiSandbox inline analysis
- B) CDR (Content Disarm and Reconstruction)
- C) AV archive scanning
- D) IPS stream-based scanning

---

**Q83.** FortiSandbox is configured in `inline-block` mode. How does this affect traffic flow?

- A) Files are delivered immediately; FortiSandbox analyzes asynchronously
- B) Files are held at FortiGate until FortiSandbox returns a verdict, then released or blocked
- C) Only HTTP traffic is blocked; HTTPS bypasses inline analysis
- D) FortiSandbox blocks all executable files regardless of verdict

---

**Q84.** A web filter profile is set to `action warning` for social media. What does the user experience?

- A) Access is silently blocked with a reset
- B) The user sees a warning page and can choose to proceed or go back
- C) The page loads normally with a logged warning
- D) The user is redirected to the HR acceptable-use policy

---

**Q85.** Which web filter feature prevents users from accessing sites based on a real-time DNS reputation check?

- A) Static URL filter
- B) FortiGuard category filter
- C) DNS filter with FortiGuard SDNS
- D) Botnet C&C IP filter

---

**Q86.** An administrator enables `set block-botnet enable` in a DNS filter profile. What is the effect?

- A) Blocks DNS queries to known botnet C2 domain names
- B) Blocks all DNS traffic from devices on the botnet IOC list
- C) Blocks DNS over HTTPS (DoH) traffic
- D) Enables deep inspection of DNS payloads

---

**Q87.** Flow-based AV scanning is preferred over proxy-based in which scenario?

- A) Maximum detection rate is required
- B) High-throughput networks where latency must be minimized
- C) PDF and Office macro analysis is required
- D) Full file buffering is needed for sandbox submission

---

**Q88.** An IPS entry is configured with `set status disable`. What is the result?

- A) The signature is monitored only (no block)
- B) The signature is completely inactive — no detection or logging
- C) The signature blocks but does not log
- D) The signature is deferred to FortiGuard cloud

---

**Q89.** Which protocol does FortiGate use to submit files to an on-premises FortiSandbox?

- A) HTTPS REST API
- B) ICAP (Internet Content Adaptation Protocol)
- C) SMTP relay
- D) FortiGuard submission protocol (proprietary)

---

**Q90.** A security administrator notices that SSL inspection is causing significant CPU load. Which two optimizations reduce SSL inspection overhead? **(Select 2)**

- A) Increase the number of SSL exemptions for trusted low-risk sites
- B) Switch from proxy-based to flow-based inspection mode
- C) Reduce the DH key size from 2048 to 1024
- D) Disable IPS on the SSL profile
- E) Use hardware-accelerated SSL inspection (NP/CP processors)

---

**Q91.** An administrator blocks the "Peer-to-Peer" application category. A user tunnels BitTorrent over HTTPS on port 443. Which IPS/AppCtrl feature detects this?

- A) Port-based application identification
- B) Protocol anomaly detection
- C) Deep packet inspection / behavioral application detection regardless of port
- D) Static URL filter

---

**Q92.** Which log category contains IPS, AV, web filter, and application control events?

- A) Traffic logs
- B) Event logs
- C) Security logs (UTM logs)
- D) System logs

---

**Q93.** Which SSL inspection setting causes FortiGate to re-sign server certificates using the untrusted CA when the server certificate is NOT trusted?

- A) `set caname "Fortinet_CA_SSL"`
- B) `set untrusted-caname "Fortinet_CA_Untrusted"`
- C) `set ssl-server-cert-log enable`
- D) `set client-cert-request bypass`

---

**Q94.** An AV profile has `set feature-set proxy`. Which scanning capability is ONLY available in proxy mode?

- A) File hash lookup against FortiGuard
- B) Full file buffering enabling scanning of encrypted archives and CDR
- C) Stream-based signature matching
- D) DNS-based malware detection

---

**Q95.** Which two firewall policy UTM profiles together provide the most comprehensive protection against web-based threats? **(Select 2)**

- A) IPS sensor
- B) Traffic shaper
- C) Antivirus profile
- D) Web filter profile
- E) Application control

---

**Q96.** A FortiGate proxy-based policy is performing deep SSL inspection. The server sends a certificate signed by a private CA that FortiGate does not trust. What happens by default?

- A) The connection is allowed; FortiGate re-signs with Fortinet_CA_SSL
- B) The connection is blocked
- C) FortiGate re-signs using Fortinet_CA_Untrusted, which causes a browser warning for the client
- D) FortiGate forwards the untrusted cert transparently

---

**Q97.** What is the purpose of `set extended-log enable` in an IPS sensor?

- A) Enables packet capture for each IPS event
- B) Includes additional IPS event details such as attack context, signature info, and raw data in the log
- C) Sends IPS logs to FortiAnalyzer in real-time
- D) Enables syslog forwarding for IPS events

---

**Q98.** Which two methods does FortiGate application control use to identify applications running on non-standard ports? **(Select 2)**

- A) Deep packet inspection using application signatures
- B) Port-based identification only
- C) Behavioral analysis (traffic pattern recognition)
- D) IP reputation lookup
- E) Certificate CN matching

---

**Q99.** An AV profile is configured with `set archive-block encrypted`. What happens when an encrypted ZIP file is received over HTTP?

- A) The file is delivered to the user with a warning
- B) The encrypted archive is blocked because the AV engine cannot scan inside it
- C) The file is submitted to FortiSandbox for analysis
- D) The connection is reset silently

---

**Q100.** Which DNS filter action prevents users from bypassing web filter by using public DNS servers (e.g., 8.8.8.8)?

- A) Block DNS category "Proxy and Filter Avoidance"
- B) Use a local DNS filter that redirects all external DNS queries to the internal DNS server
- C) Enable DoH (DNS over HTTPS) inspection
- D) Both B and C

---

## Section 6: Authentication & Troubleshooting (Q101–Q150)

**Q101.** An administrator configures FSSO. Users authenticate to Active Directory and FortiGate applies identity-based policies. Which two components are required for this to work? **(Select 2)**

- A) FortiAuthenticator or FSSO collector agent monitoring DC login events
- B) RADIUS server on each domain controller
- C) FortiGate configured with FSSO user groups referencing the AD groups
- D) FortiClient installed on every endpoint
- E) FortiAnalyzer for event correlation

---

**Q102.** A user authenticated via FSSO is mapped to IP 10.1.1.50. FortiGate shows the FSSO logon. However, identity-based policies are not matching. What should be checked first?

- A) FSSO collector agent version
- B) That the FortiGate user group DN exactly matches the AD group distinguished name
- C) RADIUS accounting packets from the switch
- D) FortiClient registration status

---

**Q103.** Which FortiGate command shows all currently logged-in FSSO users?

- A) `diagnose firewall auth list`
- B) `get user fsso`
- C) `diagnose test authserver fsso`
- D) `execute fsso list`

---

**Q104.** An administrator configures SAML SSO on FortiGate as a Service Provider (SP). The Identity Provider (IdP) is Azure AD. Which FortiGate object must be exported to Azure AD during setup?

- A) FortiGate admin certificate
- B) FortiGate SP metadata (Entity ID, ACS URL, certificate)
- C) FortiGate RADIUS client secret
- D) FortiGate FSSO password

---

**Q105.** A firewall policy uses `set groups "Corp-VPN-Users"`. The group source is RADIUS. What must be configured for this group matching to work?

- A) The RADIUS server must return a class attribute matching the group name
- B) FortiGate must query LDAP independently to verify group membership
- C) The group must exist in FortiGate local user database
- D) FSSO must be configured

---

**Q106.** Which command shows the active firewall authentication sessions (users authenticated via captive portal or FSSO)?

- A) `get user info authentication`
- B) `diagnose firewall auth list`
- C) `get user fsso`
- D) `diagnose sys session list`

---

**Q107.** An administrator uses `diagnose debug flow` to trace a packet. The output shows `iprope_in_check fail`. What does this mean?

- A) The packet was accepted by a firewall policy
- B) The packet failed a reverse path forwarding (RPF) or policy check on ingress
- C) The IPS engine dropped the packet
- D) NAT translation failed

---

**Q108.** A packet trace shows `Allowed by Policy ID 0`. What does policy ID 0 indicate?

- A) Traffic is allowed by the implicit allow policy
- B) Traffic is allowed by the implicit deny policy (dropped)
- C) The implicit deny rule — traffic is actually being dropped
- D) Traffic matched the management traffic exception

---

**Q109.** Which debug flow filter command limits capture to traffic from a specific source host?

- A) `diagnose debug flow filter src 10.1.1.100`
- B) `diagnose debug flow filter addr 10.1.1.100`
- C) `diagnose debug flow filter host 10.1.1.100`
- D) `diagnose debug flow filter srcip 10.1.1.100`

---

**Q110.** An administrator runs a packet sniffer: `diagnose sniffer packet port1 "host 10.1.1.5" 4 0 l`. What does verbose level `4` provide?

- A) IP headers only
- B) IP + TCP headers
- C) IP + TCP + payload in hex
- D) Full Layer 2 frame including MAC headers, hex + ASCII

---

**Q111.** Which command clears all firewall sessions from a specific source IP?

- A) `diagnose sys session filter src 10.1.1.100 && diagnose sys session clear`
- B) `execute session-clear src 10.1.1.100`
- C) `diagnose sys session filter clear src 10.1.1.100`
- D) `diagnose firewall session clear 10.1.1.100`

---

**Q112.** An administrator sees `drop` in the debug flow output for traffic that should be allowed. Which two items are the most likely causes? **(Select 2)**

- A) No matching firewall policy (implicit deny)
- B) RPF (Reverse Path Forwarding) check failing due to asymmetric routing
- C) OSPF convergence in progress
- D) FortiGuard license expired
- E) SD-WAN health check failure

---

**Q113.** Which command verifies which physical interface a MAC address is learned on (useful for asymmetric routing troubleshooting)?

- A) `get system arp`
- B) `diagnose netlink brctl host`
- C) `diagnose netlink fdb show`
- D) `get switch-controller mac-table`

---

**Q114.** An admin needs to check if traffic between two hosts is being NATed. Which command shows the NAT session details including original and translated IPs?

- A) `diagnose sys session list` (shows pre/post NAT addresses)
- B) `get router info routing-table nat`
- C) `diagnose ip nat status`
- D) `get system nat-table`

---

**Q115.** The `diagnose debug application ike -1` command is used to debug which process?

- A) OSPF neighbor establishment
- B) IPsec IKE negotiation (Phase 1 and Phase 2)
- C) SSL-VPN authentication
- D) FortiGuard license updates

---

**Q116.** FortiGate is dropping packets with `ip-conn-count-exceeded` in the session table. What does this mean?

- A) The routing table is full
- B) The maximum concurrent sessions limit has been reached
- C) The CPU is overloaded
- D) An IPS rate-limit signature triggered

---

**Q117.** An administrator configures a captive portal on an interface. Users are redirected to the portal but authentication always fails. RADIUS is configured. Which command tests RADIUS from FortiGate?

- A) `diagnose test authserver radius <server-name> <user> <password>`
- B) `execute ping <radius-server-ip>`
- C) `diagnose ip firewall auth list`
- D) `diagnose debug application fnbamd 255 && diagnose debug enable`

---

**Q118.** Which two outputs does `get system performance status` display? **(Select 2)**

- A) CPU usage percentage
- B) Memory usage percentage
- C) BGP table size
- D) Current session count
- E) IPS signature version

---

**Q119.** An administrator wants to confirm that FortiGate is successfully receiving FortiGuard updates. Which command shows the last update time and version?

- A) `diagnose autoupdate status`
- B) `get system fortiguard`
- C) `execute update-now`
- D) `diagnose fortiguard info`

---

**Q120.** Which log type records traffic that is allowed or denied by firewall policies?

- A) Event log
- B) Security log (UTM)
- C) Traffic log
- D) System log

---

**Q121.** A FortiGate debug flow shows the packet entering on port1 but exiting on port3 instead of the expected port2. What should be investigated?

- A) HA failover state
- B) The routing table — an unexpected route may be directing traffic to port3
- C) SSL inspection profile
- D) Application control profile

---

**Q122.** Which command shows all static and dynamic routes in the FortiGate routing table?

- A) `get router info routing-table all`
- B) `diagnose ip route list`
- C) `get system route`
- D) `diagnose netlink route list`

---

**Q123.** A FortiGate has two default routes: one via wan1 (distance 10) and one via wan2 (distance 20). Both interfaces are up. Which route is used?

- A) Both routes — ECMP load balancing
- B) The wan1 route (lower administrative distance)
- C) The wan2 route (higher metric preferred)
- D) The route installed first wins

---

**Q124.** A SAML-authenticated admin loses access after a certificate renewal on the IdP. Which FortiGate configuration must be updated?

- A) The admin account password
- B) The IdP metadata / IdP certificate imported into FortiGate SAML settings
- C) The RADIUS server certificate
- D) The FortiGate SSL-VPN server cert

---

**Q125.** Which FortiGate feature provides role-based access control for administrators using RADIUS-assigned profiles?

- A) FSSO group policy
- B) RADIUS admin authentication with `remote-auth enable` and `set accprofile-override enable`
- C) SAML IdP group assignment
- D) LDAP admin authentication only

---

**Q126.** An administrator wants to log all traffic (allowed and denied) but is concerned about storage. Which two log optimizations reduce storage consumption? **(Select 2)**

- A) Enable `set logtraffic-start enable` to log session start only
- B) Send logs to FortiAnalyzer instead of local disk
- C) Enable session sampling (log 1 in every N sessions)
- D) Use `set logtraffic disable` on low-risk internal policies
- E) Reduce IPS log verbosity

---

**Q127.** What is the correct order of FortiGate packet processing for inbound traffic?

- A) Routing → Firewall Policy → NAT → UTM → Egress
- B) Ingress → DoS Policy → Firewall Policy → UTM → Routing → NAT → Egress
- C) Firewall Policy → Routing → UTM → NAT → Egress
- D) NAT → Routing → Firewall Policy → UTM → Egress

---

**Q128.** An admin runs `diagnose debug enable` but sees no output. What is likely missing?

- A) A debug application flag must be set first (e.g., `diagnose debug application ike -1`)
- B) The console connection speed is too slow
- C) Debug is only available via FortiAnalyzer
- D) The FortiGate must be in transparent mode

---

**Q129.** FortiGate is deployed behind a NAT device. An administrator is accessing the GUI via the NAT external IP. After a firmware upgrade, the GUI is unreachable. Which recovery method is safest?

- A) Factory reset via console
- B) Connect via console cable, use `execute factoryreset`
- C) Connect via console cable, boot into BIOS, restore previous firmware or verify new image boots
- D) Send a magic packet to wake the unit

---

**Q130.** Which two features allow FortiGate to authenticate VPN users against Active Directory WITHOUT a FortiAuthenticator? **(Select 2)**

- A) LDAP server object configured on FortiGate, used directly in SSL-VPN auth
- B) RADIUS server pointing to Windows NPS/IAS which queries AD
- C) FSSO agent (transparent auth — not suitable for VPN challenge auth)
- D) Local user database mirroring AD
- E) SAML with Azure AD as IdP

---

**Q131.** An SSL-VPN user can connect but receives a "host check failed" message. What is the likely cause?

- A) Wrong VPN portal assigned
- B) The client device does not meet the FortiClient host check requirements (e.g., AV not compliant)
- C) RADIUS authentication timed out
- D) Split tunneling is misconfigured

---

**Q132.** Which command shows the current CPU and memory usage breakdown by process on FortiGate?

- A) `get system performance status`
- B) `diagnose sys top`
- C) `diagnose hardware deviceinfo cpu`
- D) `get system resource`

---

**Q133.** A policy route is configured to send traffic from 10.10.10.0/24 via wan2. A static route exists for the same destination via wan1. Which takes precedence?

- A) Static route (lower AD)
- B) Policy route (evaluated before routing table lookup)
- C) The more specific route wins
- D) BGP route overrides both

---

**Q134.** An administrator enables `set logtraffic-start enable` on a policy. What additional log is generated?

- A) A log at session END with full byte counts
- B) A log at session START (before full inspection); useful for detecting connection attempts
- C) A log for each packet in the session
- D) No additional logs; this disables the session-end log

---

**Q135.** FortiGate shows high memory usage. Which command identifies the processes consuming the most memory?

- A) `diagnose sys top` (sort by memory)
- B) `get system performance status`
- C) `diagnose hardware deviceinfo mem`
- D) `diagnose sys process list`

---

**Q136.** Which two protocols does FortiGate use for centralized logging to FortiAnalyzer? **(Select 2)**

- A) Syslog (UDP 514)
- B) OFTP (port 514 TCP — FortiAnalyzer proprietary)
- C) HTTPS (port 443) — secure log streaming
- D) SNMP traps
- E) NetFlow

---

**Q137.** An admin needs to generate a traffic log for all sessions matching a specific policy, including bytes transferred. Which policy setting achieves this?

- A) `set logtraffic all`
- B) `set logtraffic utm`
- C) `set logtraffic disable`
- D) `set logtraffic-start enable`

---

**Q138.** What does `diagnose sys session stat` display?

- A) Per-session packet byte counts
- B) Global session table statistics (total, TCP/UDP/ICMP counts, session rates)
- C) Per-interface session distribution
- D) Session synchronization status with HA peer

---

**Q139.** An administrator confirms a firewall policy exists and matches traffic via `diagnose firewall iprope lookup`, but traffic is still being dropped. Which two additional causes should be investigated? **(Select 2)**

- A) DoS policy blocking traffic before the firewall policy is evaluated
- B) UTM profile (IPS/AV) blocking the traffic within the policy
- C) SD-WAN health check marking the egress interface down
- D) BGP route not advertised
- E) FortiAnalyzer log storage full

---

**Q140.** Which CLI command shows whether NP (Network Processor) hardware offload is active for a session?

- A) `diagnose sys session list` — look for `offload` flag in session output
- B) `get system np6`
- C) `diagnose hardware npu npu0 session`
- D) `diagnose npu session list`

---

**Q141.** An administrator enables two-factor authentication for an admin account using FortiToken. The admin loses their phone. Which action allows emergency access?

- A) The admin uses their backup email OTP
- B) A super admin can generate a temporary token bypass code or disable 2FA on the account
- C) Factory reset is required
- D) Contact Fortinet TAC to unlock the account

---

**Q142.** Which FortiGate feature generates a score-based security report covering admin accounts, logging, firmware, and policy configurations?

- A) FortiAnalyzer compliance report
- B) Security Rating (Security Fabric → Security Rating)
- C) FortiManager audit trail
- D) IPS coverage report

---

**Q143.** An admin wants to restrict GUI and SSH management access to FortiGate to only a specific subnet (10.0.0.0/8). Where is this configured?

- A) Firewall policy with dstintf "management"
- B) `config system admin → edit admin → set trusthost1 10.0.0.0/8`
- C) `config system interface → edit mgmt → set allowaccess https ssh → set restricted-ip 10.0.0.0/8`
- D) SD-WAN management routing policy

---

**Q144.** OSPF is redistributing connected routes into the OSPF domain. An administrator wants to exclude the HA heartbeat interface subnet from redistribution. Which method achieves this?

- A) Configure a route map that denies the heartbeat subnet during redistribution
- B) Remove the interface from OSPF area assignment
- C) Set OSPF metric to 65535 on the heartbeat interface
- D) Use a prefix list to filter it from LSDB

---

**Q145.** Which two factors determine which route FortiGate installs when multiple routing protocols provide a route to the same prefix? **(Select 2)**

- A) Administrative distance (lower wins first)
- B) Protocol preference (static > BGP > OSPF regardless of AD)
- C) Metric (lower wins among routes of same AD)
- D) Route age (oldest wins)
- E) Interface bandwidth

---

**Q146.** An ADVPN deployment has 20 spokes. All spoke-to-spoke shortcuts form correctly, but after 1 hour they drop and must be re-established through the hub. What setting controls this?

- A) Phase 1 `keylife` (IKE SA lifetime)
- B) Phase 2 `keylifeseconds` (IPsec SA lifetime) — when Phase 2 renegotiates, shortcuts are cleared
- C) DPD timeout
- D) BGP hold timer

---

**Q147.** A FortiGate is acting as a RADIUS server for network access. Which FortiGate feature provides this?

- A) FortiGate cannot act as a RADIUS server; use FortiAuthenticator
- B) `config user radius` — defines FortiGate as RADIUS client only
- C) FortiGate can act as a RADIUS server via `config user setting → set auth-type radius`
- D) FortiAuthenticator is the RADIUS server; FortiGate is the NAS/authenticator

---

**Q148.** Which two debug commands together diagnose SSL-VPN authentication failures? **(Select 2)**

- A) `diagnose debug application sslvpn -1`
- B) `diagnose debug application fnbamd 255`
- C) `diagnose debug application ike -1`
- D) `diagnose vpn tunnel list`
- E) `diagnose sys session list`

---

**Q149.** An administrator adds a secondary IP to a FortiGate interface. What is the primary use case for secondary IPs?

- A) Enable HA heartbeat communication
- B) Host multiple subnet gateways on a single physical interface for VIP or policy purposes
- C) Provide redundancy if the primary IP fails
- D) Used exclusively for management traffic

---

**Q150.** A FortiGate policy has `set nat enable`. Traffic is sourced from 192.168.1.50. What source IP does the destination server see?

- A) 192.168.1.50 (original source IP — NAT is bypass)
- B) The outgoing interface IP of the FortiGate (source NAT to interface IP)
- C) A dedicated NAT pool IP if configured; otherwise the egress interface IP
- D) The virtual IP (VIP) address

---

# Full Answer Key — NSE 7 (Q1–Q150)

## Section 1: VDOM Architecture (Q1–Q20)

| Q | A | Explanation |
|---|---|-------------|
| 1 | B | VDOMs create independent virtual firewall instances on one physical device |
| 2 | B | VDOM admin is restricted to managing only that VDOM's policies/objects |
| 3 | B | `config system global → set vdom-mode multi-vdom` |
| 4 | C | Inter-VDOM link creates a virtual pair connecting two VDOMs internally |
| 5 | B | Creates `.0` and `.1` endpoints, one assigned to each VDOM |
| 6 | B | Transparent mode = L2 bridge; no routing changes needed on existing network |
| 7 | B | Policy-based NGFW mode: application and user ID embedded directly in policy |
| 8 | B | Proxy-based = full file buffering → highest AV/inspection depth |
| 9 | B | Virtual wire pair with wildcard VLAN passes all VLANs transparently |
| 10 | B | `diagnose sys vd list` shows all VDOMs with index, mode, status |
| 11 | B | Shaping policies are evaluated BEFORE firewall policy lookup |
| 12 | A | `per-policy enable` = each policy gets its own shaping bucket independently |
| 13 | B | FG-100F supports up to 10 VDOMs (base; expandable with license) |
| 14 | B | `netgrp = none` removes interface management; `fwgrp = read-write` allows policy objects |
| 15 | B | Transparent mode management IP = `manageip` in system settings |
| 16 | A | Inter-VDOM links chain VDOMs: LAN-VDOM → VDOM-B (transparent IPS) → DMZ |
| 17 | B | `diagnose firewall iprope lookup` shows which policy matches a given 5-tuple |
| 18 | B | Per-IP shaper limits each individual source IP to 10 Mbps |
| 19 | A, C | NAT/Route and Transparent are the two VDOM operating modes |
| 20 | A | `config system interface → edit portX → set lldp-transmission enable` |

## Section 2: Routing — BGP & OSPF (Q21–Q40)

| Q | A | Explanation |
|---|---|-------------|
| 21 | B | Active state = TCP connection failing; BGP actively retrying TCP SYN |
| 22 | B | Soft-reconfiguration stores RIB-in; allows soft clear without session reset |
| 23 | B | MED influences inbound traffic FROM neighbor AS back to local AS |
| 24 | C | MED is sent to external peers to influence how they send traffic back |
| 25 | B | Local Preference influences outbound path selection within the local AS |
| 26 | B | Route Reflector re-advertises iBGP routes, eliminating full mesh requirement |
| 27 | B | Point-to-point network type: direct adjacency, no DR/BDR election |
| 28 | C | NSSA: allows external routes as Type 7 LSAs within the area |
| 29 | B | Totally Stub: blocks all Type 3/4/5 LSAs; ABR injects only a default route |
| 30 | A, C | 2-Way (non-DR/BDR peers) and Full (DR/BDR adjacency) = complete adjacency |
| 31 | B | OSPF authentication is per-interface; interfaces without auth run without it |
| 32 | B | `get router info ospf database` shows the LSDB |
| 33 | B | E2 (metric-type 2) = flat external cost; internal OSPF cost NOT added |
| 34 | A, B | `no-export` and `no-advertise` are well-known mandatory BGP communities |
| 35 | B | Prefix list applied as `neighbor X prefix-list IN` filters routes from RIB |
| 36 | B | eBGP AD = 20; OSPF AD = 110; lower AD wins → eBGP route installed |
| 37 | C | iBGP administrative distance = 200 on FortiGate |
| 38 | B | `clear bgp ip X soft in` = soft inbound reset; no TCP session drop |
| 39 | B | ABR injects default route (0.0.0.0/0) into stub area for external reach |
| 40 | A, B | Hello/Dead timer mismatch and MTU mismatch are top OSPF adjacency failures |

## Section 3: IPsec VPN & SD-WAN (Q41–Q60)

| Q | A | Explanation |
|---|---|-------------|
| 41 | C | IKEv2: 4 messages total (2 for IKE_SA_INIT + 2 for IKE_AUTH) |
| 42 | A, B | Tunnel up but no traffic = missing firewall policy or missing static route |
| 43 | B | `net-device enable` creates a routable tunnel interface; required for ADVPN shortcuts |
| 44 | A | Route-based = tunnel interface + routes; policy-based = encrypt action in policy |
| 45 | B | Hub sends IKE informational shortcut offer to both spokes |
| 46 | A | `set dpd on-idle` or `on-demand` enables Dead Peer Detection |
| 47 | C | NAT-T encapsulates ESP in UDP 4500 to traverse NAT devices |
| 48 | B | "No proposal chosen" = Phase 1 proposal mismatch (encryption/hash/DH group) |
| 49 | B | After `failtime` probe failures, SD-WAN marks member down and fails over |
| 50 | B | SLA mode = use member meeting latency/jitter/loss SLA thresholds |
| 51 | C | Source IP algorithm = consistent mapping of src IP to same WAN member |
| 52 | B | SD-WAN service rule matches Teams app, MPLS priority, internet fallback |
| 53 | B | `diagnose sys sdwan health-check` shows real-time per-member SLA metrics |
| 54 | B | SSL-VPN traffic must have policy with `srcintf "ssl.root"` (virtual tunnel i/f) |
| 55 | B | Web mode = clientless browser-based portal; no FortiClient required |
| 56 | B | PFS = new DH exchange per Phase 2; past sessions safe if long-term key exposed |
| 57 | B | `auto-discovery-receiver` = spoke accepts hub shortcut offers to form direct tunnels |
| 58 | B | Spillover = use secondary WAN when primary bandwidth usage exceeds threshold |
| 59 | B | Split tunnel = only corp subnets via VPN; internet goes direct from client |
| 60 | B, C | MOBIKE and native EAP in IKE are IKEv2-only features |

## Section 4: High Availability (Q61–Q75)

| Q | A | Explanation |
|---|---|-------------|
| 61 | B | A/P: primary handles all traffic; secondary is hot standby |
| 62 | B | Override enabled: original primary reclaims primary role after recovery |
| 63 | B | Heartbeat interface carries HA control and session sync between members |
| 64 | C, E | Admin management sessions and local-out (FGT-initiated) sessions are not synced |
| 65 | B | Override + priority 200 beats uptime; FGT-A wins primary election |
| 66 | B | `set ha-mgmt-status enable` creates per-unit OOB management access |
| 67 | B | FGSP handles asymmetric flows where entry/exit paths differ between FGTs |
| 68 | A | `execute ha failover set 1` forces failover to secondary |
| 69 | B | A/A: primary distributes sessions to members via HA link; upstream sees one MAC |
| 70 | C | Upgrade secondary first → failover → upgrade old primary = zero-downtime upgrade |
| 71 | B | `execute ha synchronize config` pushes full config from primary to secondary |
| 72 | B | Virtual MAC prevents upstream MAC table update during failover |
| 73 | C | Virtual clustering = different VDOMs can have different primary unit |
| 74 | B | `ha-priority` reduction may cause peer with higher effective priority to become primary |
| 75 | A, B | Same group name/password AND same firmware version are required for clustering |

## Section 5: Advanced Threat Protection (Q76–Q100)

| Q | A | Explanation |
|---|---|-------------|
| 76 | B | Browser warns because FortiGate re-signing CA is not in client's trust store |
| 77 | B, D | Banking (cert pinning) and medical/health (privacy compliance) = exempt |
| 78 | B | `location server` = attacks targeting servers only; critical = highest severity |
| 79 | B | FortiGate pulls IPS updates via HTTPS from FortiGuard FDN |
| 80 | B | `set packet-log enable` on IPS entry captures packet payload on trigger |
| 81 | B | `unknown-application-action pass` = unrecognized apps are allowed |
| 82 | B | CDR strips active content; delivers sanitized clean document |
| 83 | B | Inline-block: file held at FGT until sandbox verdict; then allow/block |
| 84 | B | Warning action = user sees warning page with option to proceed |
| 85 | C | DNS filter with FortiGuard SDNS checks domain reputation at DNS resolution time |
| 86 | A | `block-botnet` in DNS filter blocks DNS queries to C2 botnet domains |
| 87 | B | Flow-based = stream scan = low latency; best for high-throughput links |
| 88 | B | `status disable` = signature completely inactive (no detect, no log, no block) |
| 89 | A | FortiGate uses HTTPS REST API to submit files to FortiSandbox |
| 90 | A, E | Adding SSL exemptions and using hardware NP/CP SSL offload reduce CPU |
| 91 | C | Deep packet inspection detects BitTorrent by signature regardless of port |
| 92 | C | Security logs (UTM logs) contain IPS, AV, webfilter, app control events |
| 93 | B | `untrusted-caname` = CA used to re-sign certs when server cert is not trusted |
| 94 | B | Proxy-mode only: full file buffering → CDR, encrypted archive scanning |
| 95 | A, D | IPS + Web Filter together cover exploit delivery AND malicious content access |
| 96 | C | Untrusted server cert → FGT re-signs with Fortinet_CA_Untrusted → browser warns |
| 97 | B | `extended-log` adds rich attack context, raw data, signature info to IPS logs |
| 98 | A, C | Deep packet inspection + behavioral analysis detect apps on non-standard ports |
| 99 | B | `archive-block encrypted` = encrypted archives blocked (can't scan inside) |
| 100 | D | Redirect all external DNS to internal DNS server AND inspect DoH traffic |

## Section 6: Authentication & Troubleshooting (Q101–Q150)

| Q | A | Explanation |
|---|---|-------------|
| 101 | A, C | FSSO collector/DC agent + FortiGate FSSO groups referencing AD groups |
| 102 | B | FSSO group DN must exactly match AD group distinguished name |
| 103 | A | `diagnose firewall auth list` shows all authenticated users including FSSO |
| 104 | B | FortiGate SP metadata (Entity ID, ACS URL, cert) must be registered in Azure AD |
| 105 | A | RADIUS must return Class attribute or VSA matching FortiGate group name |
| 106 | B | `diagnose firewall auth list` shows active portal/FSSO authentication sessions |
| 107 | B | `iprope_in_check fail` = RPF check or ingress policy dropped the packet |
| 108 | C | Policy ID 0 in debug flow = implicit deny (packet dropped) |
| 109 | B | `diagnose debug flow filter addr` filters by IP address (src or dst) |
| 110 | D | Verbose 4 = full Layer 2 frame with MAC, IP, payload in hex and ASCII |
| 111 | A | Set filter then `diagnose sys session clear` clears matching sessions |
| 112 | A, B | No matching policy (implicit deny) and RPF failure are top drop causes |
| 113 | C | `diagnose netlink fdb show` shows MAC-to-interface mappings |
| 114 | A | `diagnose sys session list` shows original src/dst and NATed src/dst |
| 115 | B | `ike` application = IKE daemon; debug shows Phase 1/2 negotiation |
| 116 | B | `ip-conn-count-exceeded` = session table at maximum capacity |
| 117 | A | `diagnose test authserver radius` tests RADIUS auth from FGT CLI |
| 118 | A, B | `get system performance status` shows CPU% and memory% usage |
| 119 | A | `diagnose autoupdate status` shows last update time and current versions |
| 120 | C | Traffic logs record allow/deny decisions per firewall policy |
| 121 | B | Unexpected egress interface = routing table sending to wrong next-hop |
| 122 | A | `get router info routing-table all` shows all active routes |
| 123 | B | Lower administrative distance (10 < 20) → wan1 route installed |
| 124 | B | IdP cert change → update IdP metadata/certificate imported in FGT SAML config |
| 125 | B | RADIUS with `accprofile-override enable` assigns admin profile from RADIUS VSA |
| 126 | A, D | Log session start only (reduce log count) + disable logging on low-risk policies |
| 127 | B | Correct order: Ingress → DoS Policy → Firewall Policy → UTM → Routing → NAT → Egress |
| 128 | A | Must set debug application flag first; `debug enable` alone produces no output |
| 129 | C | Console → verify boot, check image integrity, restore previous if needed |
| 130 | A, B | LDAP directly on FGT or RADIUS pointing to Windows NPS (which queries AD) |
| 131 | B | Host check fail = endpoint does not meet AV/patch compliance requirements |
| 132 | B | `diagnose sys top` shows per-process CPU/memory (like Unix `top`) |
| 133 | B | Policy routes are evaluated BEFORE the routing table; they always take precedence |
| 134 | B | `logtraffic-start` adds a session-START log at connection initiation |
| 135 | A | `diagnose sys top` sorted by memory shows high-memory processes |
| 136 | B, C | FortiAnalyzer uses OFTP (TCP 514) and HTTPS (443) for secure log streaming |
| 137 | A | `set logtraffic all` logs all sessions with full byte counts at session end |
| 138 | B | `diagnose sys session stat` = global stats: total sessions, TCP/UDP/ICMP, rates |
| 139 | A, B | DoS policy (evaluated before firewall policy) and UTM (inline block) can drop traffic |
| 140 | A | Session list shows `offload` flag indicating NP hardware acceleration is active |
| 141 | B | Super admin can disable 2FA or generate bypass code for locked-out admin |
| 142 | B | Security Rating in Security Fabric provides scored security posture report |
| 143 | B | `set trusthost1 10.0.0.0/8` on admin account restricts management source IPs |
| 144 | A | Route map denying heartbeat subnet applied during OSPF redistribution |
| 145 | A, C | Administrative distance first; then metric as tiebreaker for same-AD routes |
| 146 | B | Phase 2 SA lifetime expiry forces renegotiation, clearing ADVPN shortcuts |
| 147 | D | FortiGate is the NAS (authenticator); FortiAuthenticator is the RADIUS server |
| 148 | A, B | `sslvpn` debug for tunnel/portal issues + `fnbamd` for authentication failures |
| 149 | B | Secondary IPs allow multiple gateways/VIPs on one physical interface |
| 150 | C | NAT enabled = SNAT to egress interface IP unless a NAT pool is configured |
