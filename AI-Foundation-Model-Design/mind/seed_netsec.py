"""
seed_netsec — Vio's built-in NETWORK & SECURITY knowledge base.

Accurate, self-contained, encyclopaedia-level passages across networking, firewalls,
VPN/TLS, Kubernetes & service mesh, cloud/IAM, security concepts, incident response,
threat modeling, and protocols. Loaded into the library so Vio actually KNOWS this
domain out of the box (grounded retrieval + the network_engineering expert use it).

Load into an existing install with the chat command:  load knowledge
Your own documents (teach: / 📄 / learn essentials) sit alongside these.
"""

NETSEC = [
    # ── Routing ──────────────────────────────────────────────────────────────
    "BGP (Border Gateway Protocol) is the path-vector routing protocol that runs the "
    "internet, exchanging reachability between autonomous systems (AS). eBGP peers between "
    "different ASes; iBGP between routers in the same AS. BGP chooses routes by attributes "
    "in order: highest weight (Cisco-local), highest local-preference, locally originated, "
    "shortest AS-path, lowest origin, lowest MED, then eBGP over iBGP. A route flap is a "
    "prefix repeatedly withdrawn and re-advertised; route-flap damping and BFD reduce churn.",
    "OSPF (Open Shortest Path First) is a link-state interior gateway protocol. Routers "
    "flood link-state advertisements (LSAs) within an area, build an identical topology "
    "database, and run Dijkstra's shortest-path-first algorithm to compute routes. Area 0 "
    "is the backbone; all other areas must connect to it. When a link fails, OSPF floods "
    "the change and recalculates the shortest path. Adjacencies form via Hello packets.",
    "BFD (Bidirectional Forwarding Detection) is a lightweight hello protocol that detects "
    "a failed forwarding path in milliseconds and tells routing protocols (BGP, OSPF) to "
    "reconverge far faster than their native timers. 'Strict mode' BFD requires the session "
    "up before the routing adjacency is allowed to form.",
    "ECMP (Equal-Cost Multi-Path) load-balances traffic across multiple next hops of equal "
    "cost, usually by hashing the 5-tuple so each flow stays on one path (avoiding "
    "reordering). Static routes have an administrative distance; the lowest wins.",
    "A default route (0.0.0.0/0) is the route of last resort, used when no more specific "
    "prefix matches. Longest-prefix match always wins: 10.1.1.0/24 is preferred over "
    "10.0.0.0/8 for 10.1.1.5.",

    # ── Switching / L2 ───────────────────────────────────────────────────────
    "A VLAN (Virtual LAN) segments one physical switch into multiple isolated broadcast "
    "domains, each a separate subnet. Ports are access (one VLAN, untagged) or trunk "
    "(many VLANs, 802.1Q-tagged). Inter-VLAN traffic must be routed. VLANs limit broadcast "
    "scope and separate tenants or security zones.",
    "Spanning Tree Protocol (STP, 802.1D and RSTP 802.1w) prevents Layer-2 loops by "
    "blocking redundant links, leaving one active path per segment. A loop without STP "
    "causes a broadcast storm that saturates the network.",
    "MTU (Maximum Transmission Unit) is the largest frame payload a link carries, typically "
    "1500 bytes on Ethernet, 9000 for jumbo frames. If a packet exceeds the path MTU and "
    "the Don't-Fragment bit is set, it is dropped and an ICMP 'fragmentation needed' is "
    "returned; blocking that ICMP causes silent PMTUD black holes.",
    "ARP (Address Resolution Protocol) maps an IPv4 address to a MAC address on a local "
    "segment. ARP spoofing lets an attacker on the same L2 segment impersonate the gateway "
    "for a man-in-the-middle attack; dynamic ARP inspection mitigates it.",
    "VXLAN encapsulates Layer-2 frames in UDP to stretch VLANs across a routed Layer-3 "
    "fabric, giving 16 million segments (24-bit VNI) instead of 4094 VLANs — the basis of "
    "modern data-center and overlay networks.",

    # ── IP / transport ───────────────────────────────────────────────────────
    "A subnet mask (e.g. /24 = 255.255.255.0) splits an IP into network and host portions. "
    "A /24 has 256 addresses, 254 usable (network and broadcast reserved). CIDR notation "
    "shows the prefix length; /30 (4 addresses, 2 usable) is common for point-to-point links.",
    "TCP is connection-oriented and reliable: a three-way handshake (SYN, SYN-ACK, ACK) "
    "sets up the session, sequence/ack numbers and retransmission guarantee delivery, and "
    "windowing plus congestion control (slow start, congestion avoidance) pace the sender. "
    "UDP is connectionless and unreliable, used for DNS, DHCP, VoIP, and QUIC.",
    "NAT (Network Address Translation) rewrites source/destination IPs and ports. PAT "
    "(overload) maps many private hosts to one public IP by port. NAT keeps a state/session "
    "table; each translation is an entry that times out. It breaks end-to-end addressing "
    "and complicates inbound connections (hence port forwarding).",
    "A firewall state (conntrack) table tracks every active connection so return traffic is "
    "allowed without a separate rule. State-table exhaustion — from a flood of half-open "
    "connections (SYN flood) or too many sessions — drops new legitimate connections; SYN "
    "cookies and connection limits mitigate it.",
    "DNS resolves names to IP addresses using a hierarchy (root, TLD, authoritative). "
    "Records include A (IPv4), AAAA (IPv6), CNAME (alias), MX (mail), TXT, and NS. DNS "
    "tunneling smuggles data in queries/answers as a covert exfiltration channel; DNSSEC "
    "signs records to prevent spoofing.",
    "DHCP leases IP configuration to clients through the DORA exchange (Discover, Offer, "
    "Request, Acknowledge). A rogue DHCP server can hand out a malicious gateway/DNS for a "
    "man-in-the-middle; DHCP snooping on switches blocks untrusted servers.",

    # ── Firewalls (incl. FortiGate) ─────────────────────────────────────────
    "A stateful firewall allows or denies traffic by policy and tracks connection state so "
    "replies are permitted automatically. Policies match source/destination interface and "
    "address, service (port/protocol), schedule, and action (accept/deny). Order matters: "
    "the first matching rule wins, so specific rules go above broad ones.",
    "On FortiGate, a firewall policy is defined under 'config firewall policy' with fields "
    "srcintf, dstintf, srcaddr, dstaddr, service, action, schedule, nat, and status. "
    "'set nat enable' source-NATs outbound traffic to the egress interface IP. A policy "
    "with dstintf wan1, dstaddr all, action accept, nat enable is a typical internet-access "
    "rule. UUIDs identify objects; 'set status disable' turns a policy off without deleting.",
    "Defense in depth layers independent controls (perimeter firewall, segmentation, host "
    "firewall, EDR, IAM, monitoring) so no single failure is fatal. Least privilege grants "
    "each user, service, and rule only the access it needs. An over-permissive 'any/any "
    "accept' rule is the classic misconfiguration.",
    "Zero Trust assumes no implicit trust from network location: every request is "
    "authenticated, authorized, and encrypted, and access is least-privilege and "
    "continuously verified. Microsegmentation enforces per-workload policy rather than a "
    "flat trusted internal network.",

    # ── VPN / TLS / crypto ───────────────────────────────────────────────────
    "IPsec secures IP traffic with two protocols: AH (integrity/authentication) and ESP "
    "(encryption + integrity). IKE (Internet Key Exchange) negotiates the security "
    "association and keys in two phases. A site-to-site tunnel uses a pre-shared key (PSK) "
    "or certificates; mismatched Phase-1/Phase-2 parameters (encryption, DH group, "
    "lifetime) are the usual cause of a tunnel that won't come up.",
    "TLS secures data in transit with a handshake that authenticates the server (via an "
    "X.509 certificate signed by a trusted CA), agrees a cipher suite, and derives session "
    "keys. TLS 1.3 removes weak ciphers and cuts the handshake to one round trip. mTLS "
    "(mutual TLS) also authenticates the client with its own certificate.",
    "Symmetric encryption (AES) uses one shared key and is fast; asymmetric (RSA, ECDSA) "
    "uses a public/private key pair for key exchange and signatures. Hashing (SHA-256) is "
    "one-way and verifies integrity. Never store passwords as plaintext or fast hashes — "
    "use a slow salted KDF like bcrypt, scrypt, or Argon2.",
    "WireGuard is a modern VPN using fixed modern cryptography (Curve25519, ChaCha20-"
    "Poly1305), a tiny codebase, and per-peer public keys — simpler and faster than IPsec "
    "or OpenVPN, with roaming support.",

    # ── Kubernetes & service mesh ───────────────────────────────────────────
    "In a service mesh (Istio, Linkerd), a sidecar proxy (Envoy) is injected next to each "
    "pod and transparently intercepts traffic to enforce mTLS, routing, and policy. It "
    "captures traffic via iptables/eBPF redirection, so an app that bypasses the sidecar "
    "(host network, direct egress) escapes mesh controls.",
    "Istio mTLS has modes set by PeerAuthentication: STRICT (only mTLS accepted), "
    "PERMISSIVE (both mTLS and plaintext), and DISABLE. A workload can override per-port "
    "with portLevelMtls — e.g. STRICT mesh-wide but PERMISSIVE on an external-facing port. "
    "A PERMISSIVE or plaintext port is a common way traffic bypasses mesh interception.",
    "Kubernetes NetworkPolicy controls pod-to-pod and egress traffic by label selectors; "
    "by default all pods can talk to all pods. A policy is enforced by the CNI (Calico, "
    "Cilium). Without an egress NetworkPolicy, a compromised pod can reach any external IP "
    "and exfiltrate data — the mesh only sees traffic that goes through the sidecar.",
    "Kubernetes RBAC grants API permissions via Roles/ClusterRoles bound to subjects. "
    "Over-broad bindings (cluster-admin to a service account, or a token mounted in every "
    "pod) let a compromised pod escalate. Pod Security Standards (restricted) block "
    "privileged pods, host mounts, and hostNetwork.",
    "A compromised Kubernetes pod can exfiltrate to an external IP without tripping the "
    "service mesh if its egress leaves outside the sidecar's interception: a PERMISSIVE/"
    "plaintext port, hostNetwork, a direct socket the sidecar doesn't capture, or DNS/ICMP "
    "tunneling. Egress NetworkPolicy, an egress gateway, and DNS monitoring are the "
    "controls; correlate the egress spike with firewall state growth and any BGP/route "
    "changes it triggers.",

    # ── Cloud / IAM ──────────────────────────────────────────────────────────
    "AWS IAM grants access via policies (identity- and resource-based) evaluated as: an "
    "explicit deny always wins, otherwise an explicit allow is required. Least privilege, "
    "roles over long-lived keys, MFA, and no wildcard '*' actions are the baseline. Access "
    "keys (AKIA…) that leak are a top breach cause; rotate and use short-lived STS creds.",
    "The cloud instance metadata service (IMDS) at 169.254.169.254 returns instance "
    "credentials and data. IMDSv1 is request/response and is abusable via SSRF: a "
    "vulnerable app is tricked into fetching the metadata URL, leaking the role's "
    "credentials. IMDSv2 requires a session token (PUT + header) and hop limit, blocking "
    "most SSRF paths — enforce it.",
    "An S3 bucket is private by default; exposure comes from public ACLs, permissive bucket "
    "policies, or 'Block Public Access' disabled. Enable Block Public Access account-wide, "
    "use bucket policies with least privilege, encrypt at rest (SSE-KMS), and log access "
    "with CloudTrail + server access logs.",
    "Cloud security groups are stateful allow-lists attached to instances; NACLs are "
    "stateless subnet-level filters evaluated by rule number. Exposure usually means a "
    "security group open to 0.0.0.0/0 on SSH (22), RDP (3389), or a database port — scope "
    "ingress to known CIDRs or a bastion.",

    # ── Security concepts ────────────────────────────────────────────────────
    "The CIA triad is the core of security: Confidentiality (only authorized access), "
    "Integrity (data isn't tampered), and Availability (systems are usable when needed). "
    "Controls map to one or more: encryption serves confidentiality, hashing/signatures "
    "integrity, redundancy and DDoS protection availability.",
    "Authentication proves who you are (password, MFA, certificate); authorization decides "
    "what you may do (RBAC/ABAC); accounting/audit records what you did. MFA — something "
    "you know, have, and are — stops the majority of credential-stuffing and phishing "
    "account takeovers.",
    "STRIDE is a threat-modeling framework: Spoofing, Tampering, Repudiation, Information "
    "disclosure, Denial of service, and Elevation of privilege — one category per trust-"
    "boundary crossing. You identify assets, draw data-flow diagrams with trust boundaries, "
    "enumerate threats per element, and rank mitigations by likelihood × impact.",
    "MITRE ATT&CK is a knowledge base of adversary tactics (the why: Initial Access, "
    "Execution, Persistence, Privilege Escalation, Defense Evasion, Credential Access, "
    "Discovery, Lateral Movement, Collection, Command and Control, Exfiltration, Impact) "
    "and the techniques under each. Map detections and gaps to ATT&CK to measure coverage.",
    "The OWASP Top 10 lists the most critical web risks: Broken Access Control, "
    "Cryptographic Failures, Injection (incl. SQLi/XSS), Insecure Design, Security "
    "Misconfiguration, Vulnerable Components, Identification/Authentication Failures, "
    "Software/Data Integrity Failures, Logging/Monitoring Failures, and SSRF.",
    "The CISA KEV (Known Exploited Vulnerabilities) catalog lists CVEs confirmed exploited "
    "in the wild — the priority patch list. A CVE is a unique vulnerability identifier; "
    "CVSS scores severity. Patch KEV entries first regardless of CVSS, because exploitation "
    "is proven.",

    # ── Incident response / threat hunting ──────────────────────────────────
    "Incident response follows a lifecycle: Preparation, Identification, Containment, "
    "Eradication, Recovery, and Lessons Learned (NIST / SANS). Containment isolates the "
    "affected hosts (network quarantine, disable credentials) before eradication removes "
    "the foothold; preserve evidence (memory, logs) before wiping.",
    "Indicators of Compromise (IOCs) include suspicious IPs/domains, file hashes, unusual "
    "processes, new persistence, and anomalous egress. Command-and-control (C2) beaconing "
    "shows as regular, small outbound connections to the same host; data exfiltration shows "
    "as a large or sustained egress spike, often over DNS, HTTPS, or an allowed port.",
    "Lateral movement is how an attacker pivots from an initial foothold to other hosts — "
    "stolen credentials, pass-the-hash, RDP/SSH, or exploiting internal services. Detect it "
    "with east-west monitoring, unusual authentication patterns, and segmentation that "
    "limits blast radius.",

    # ── Protocols quick facts ────────────────────────────────────────────────
    "Common ports: 22 SSH, 23 Telnet (insecure), 25 SMTP, 53 DNS, 80 HTTP, 110 POP3, "
    "143 IMAP, 443 HTTPS, 389 LDAP, 636 LDAPS, 3389 RDP, 3306 MySQL, 5432 PostgreSQL, "
    "161 SNMP, 123 NTP, 500/4500 IPsec/IKE. Only expose what is needed and prefer the "
    "encrypted variant.",
    "ICMP carries control messages: echo request/reply (ping), time exceeded (traceroute), "
    "and destination unreachable (incl. fragmentation-needed for PMTUD). Blocking all ICMP "
    "breaks path-MTU discovery and troubleshooting; rate-limit rather than drop entirely.",
    "HTTP is stateless request/response; HTTPS is HTTP over TLS. Security headers matter: "
    "HSTS forces HTTPS, Content-Security-Policy limits script sources, X-Frame-Options "
    "prevents clickjacking, and Secure/HttpOnly/SameSite protect cookies.",
]
