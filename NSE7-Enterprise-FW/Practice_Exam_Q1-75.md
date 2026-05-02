# NSE 7 — Enterprise Firewall Administrator: Practice Exam Part 1 (Q1–Q75)

> One best answer unless marked **(Select 2)** or **(Select 3)**.

---

## Section 1: VDOM Architecture (Q1–20)

**Q1.** An administrator must isolate two business units on a single FortiGate so each has independent firewall policies and routing tables. Which feature achieves this?

- A) VRF (Virtual Routing and Forwarding)
- B) VDOM (Virtual Domain)
- C) VLAN segmentation
- D) Policy-based routing

---

**Q2.** A FortiGate is operating in multi-VDOM mode. An administrator logs in with an account restricted to "Finance-VDOM". Which operations can this administrator perform?

- A) Modify global system settings such as DNS and NTP
- B) Manage interfaces and policies only within Finance-VDOM
- C) View all VDOMs in read-only mode
- D) Manage HA cluster settings

---

**Q3.** Which CLI command switches the FortiGate from single-VDOM to multi-VDOM mode?

- A) `config system settings → set vdom-mode multi-vdom`
- B) `config system global → set vdom-mode multi-vdom`
- C) `execute vdom enable`
- D) `config vdom → edit root → set mode multi`

---

**Q4.** Two VDOMs need to communicate without using a physical interface. Which feature enables this?

- A) VLAN sub-interface
- B) IPsec tunnel
- C) Inter-VDOM link (vdom-link)
- D) Software switch

---

**Q5.** An inter-VDOM link is created named "corp-to-dmz". Which interfaces are automatically created?

- A) corp-to-dmz only (single interface)
- B) corp-to-dmz.0 and corp-to-dmz.1 (one per connected VDOM)
- C) corp-to-dmz-in and corp-to-dmz-out
- D) vlink0 and vlink1 (generic naming)

---

**Q6.** A FortiGate VDOM is configured in transparent mode. What is the primary characteristic?

- A) Performs NAT on all traffic
- B) Acts as a Layer 2 bridge; invisible to routing topology
- C) Requires IP addresses on all interfaces
- D) Only processes VPN traffic

---

**Q7.** In NGFW policy-based mode, how are application and user identity enforced?

- A) Via UTM profiles attached to firewall policies
- B) Directly as source/destination objects within the firewall policy itself
- C) Via a separate application firewall policy table
- D) Application control is not available in policy-based mode

---

**Q8.** Which inspection mode provides the deepest protocol analysis with full file buffering, enabling the highest AV detection rate?

- A) Flow-based inspection
- B) Proxy-based inspection
- C) Hardware offload inspection
- D) Stream-based IPS

---

**Q9.** An administrator needs to pass all VLAN tags transparently through a FortiGate without configuring individual sub-interfaces. Which feature achieves this?

- A) Transparent mode VDOM
- B) Virtual wire pair with `set wildcard-vlan enable`
- C) Software switch with VLAN forwarding
- D) MCLAG with FortiSwitch

---

**Q10.** A global administrator runs `diagnose sys vd list`. What does this output show?

- A) VLAN membership of all interfaces
- B) All VDOMs with their index, mode, and status
- C) Virtual MAC addresses of each VDOM
- D) BGP VRF tables per VDOM

---

**Q11.** Traffic shaping policies are evaluated at which point in the FortiGate packet processing order?

- A) After the firewall policy lookup
- B) Before the firewall policy lookup
- C) At the same time as the firewall policy lookup
- D) After NAT translation

---

**Q12.** An administrator configures `set per-policy enable` on a traffic shaper. What does this change?

- A) Applies the bandwidth limit to each matching policy independently
- B) Applies the bandwidth limit shared across all sessions matching that shaper
- C) Enables DSCP marking per policy
- D) Enables per-IP bandwidth tracking

---

**Q13.** What is the maximum number of VDOMs supported on a FortiGate 100F?

- A) 5
- B) 10
- C) 25
- D) Unlimited (license-based)

---

**Q14.** An administrator wants to allow VDOM admins to create firewall objects but NOT manage system interfaces. Which admin profile permission achieves this?

- A) Set `system-config` to read and `firewall-config` to read-write
- B) Set `netgrp` to none and `fwgrp` to read-write
- C) Use the built-in `prof_admin` profile
- D) Only super admins can create firewall objects

---

**Q15.** In transparent mode, which IP address is used to manage the FortiGate?

- A) The IP of the connected interface (bridge port)
- B) The `manageip` address configured in system settings
- C) No IP is needed; management is via serial console only
- D) The default 192.168.1.99 address

---

**Q16.** A FortiGate has VDOM-A (NAT mode) and VDOM-B (transparent mode). Traffic from VDOM-A needs to pass through VDOM-B for IPS inspection before reaching the DMZ. Which feature enables this chaining?

- A) Inter-VDOM link connecting VDOM-A → VDOM-B → DMZ
- B) IPsec between VDOMs
- C) Software switch spanning both VDOMs
- D) OSPF redistribution between VDOMs

---

**Q17.** Which command verifies that traffic is matching the correct firewall policy?

- A) `diagnose sys session list`
- B) `diagnose firewall iprope lookup <src> <dst> <proto> <sport> <dport>`
- C) `get router info routing-table all`
- D) `diagnose ip router ospf all enable`

---

**Q18.** A `per-ip-shaper` is configured with `set max-bandwidth 10240`. What does this limit?

- A) Total bandwidth of the interface to 10 Mbps
- B) Bandwidth per individual source IP address to 10 Mbps
- C) Total bandwidth across all IPs to 10 Mbps shared
- D) Burst bandwidth to 10 Mbps; sustained is unlimited

---

**Q19.** Which two modes are available for FortiGate VDOM operation? **(Select 2)**

- A) NAT/Route mode
- B) Layer 1 pass-through mode
- C) Transparent mode
- D) Proxy-only mode
- E) SD-WAN mode

---

**Q20.** An administrator wants to enable LLDP on a FortiGate interface to discover connected network devices. Which command enables LLDP transmission?

- A) `config system interface → edit port1 → set lldp-transmission enable`
- B) `config system lldp → set status enable`
- C) `config switch-controller global → set lldp-transmission enable`
- D) LLDP is always enabled and cannot be disabled

---

## Section 2: Routing — BGP & OSPF (Q21–40)

**Q21.** A BGP neighbor is stuck in the **Active** state. What does this indicate?

- A) The BGP session is fully established
- B) TCP connection to the neighbor is failing; BGP is retrying
- C) BGP OPEN messages are being exchanged
- D) The neighbor is in graceful restart

---

**Q22.** An administrator adds `set soft-reconfiguration enable` on a BGP neighbor. What does this enable?

- A) Automatic failover to a backup neighbor
- B) Storing received routes in memory, allowing `clear ip bgp soft` without dropping the session
- C) BGP route dampening
- D) Multipath load balancing

---

**Q23.** Which BGP attribute is used to influence **outbound** path selection from the local AS toward a remote AS?

- A) Local Preference
- B) MED (Multi-Exit Discriminator)
- C) Weight
- D) AS Path prepending

---

**Q24.** Which BGP attribute is used to influence **inbound** traffic from a remote AS back to the local AS?

- A) Local Preference
- B) Weight
- C) MED (Multi-Exit Discriminator)
- D) Origin

---

**Q25.** A FortiGate has two eBGP neighbors from different ISPs. The administrator wants ISP-A to be preferred for all outbound traffic. Which attribute should be set higher on routes learned from ISP-A?

- A) MED — set lower on ISP-A routes
- B) Local Preference — set higher on routes from ISP-A
- C) Weight — set higher on routes received from ISP-A
- D) AS Path — prepend ISP-B AS path

---

**Q26.** What is the purpose of a BGP Route Reflector?

- A) Reflects static routes into BGP
- B) Eliminates the requirement for a full iBGP mesh by re-advertising routes to clients
- C) Provides NAT traversal for BGP sessions
- D) Summarizes BGP prefixes

---

**Q27.** An OSPF interface is configured with `set network-type point-to-point`. What is the effect?

- A) DR/BDR election is performed
- B) No DR/BDR election; both routers become fully adjacent directly
- C) Only one router can be active on the link
- D) OSPF is disabled on the interface

---

**Q28.** Which OSPF area type allows Type 5 (External) LSAs but converts them to Type 7 within the area?

- A) Stub area
- B) Totally Stub area
- C) NSSA (Not-So-Stubby Area)
- D) Backbone area

---

**Q29.** An OSPF ABR is generating excessive Type 3 LSAs flooding into Area 1. The administrator wants to block ALL inter-area routes and inject only a default route. Which area type achieves this?

- A) Stub
- B) Totally Stub
- C) NSSA
- D) Standard area with filter-list

---

**Q30.** What are the two OSPF neighbor states that indicate full adjacency has been formed? **(Select 2)**

- A) 2-Way
- B) ExStart
- C) Full
- D) Loading
- E) Exchange

---

**Q31.** An administrator configures OSPF MD5 authentication on one interface but leaves another without authentication. What happens on the interface without authentication?

- A) OSPF adjacency fails on that interface
- B) OSPF runs without authentication on that interface independently
- C) Authentication is applied globally to all OSPF interfaces
- D) OSPF automatically negotiates authentication type

---

**Q32.** Which command shows the OSPF LSDB on FortiGate?

- A) `get router info ospf neighbor`
- B) `get router info ospf database`
- C) `diagnose ip router ospf lsdb`
- D) `get router info routing-table ospf`

---

**Q33.** A FortiGate redistributes static routes into OSPF with `set metric-type 2`. What does metric-type 2 mean?

- A) The OSPF metric includes the internal path cost to reach the ASBR
- B) The metric is a flat external cost — internal OSPF cost is NOT added when the route propagates
- C) The route has lower preference than E1
- D) Type 2 is only for iBGP redistribution

---

**Q34.** Which two BGP communities are well-known and have defined behavior? **(Select 2)**

- A) `no-export` — do not advertise outside the local AS
- B) `no-advertise` — do not advertise to any BGP peer
- C) `local-as` — keep within confederation sub-AS
- D) `blackhole` — RFC 7999 community for null routing
- E) `origin-igp` — marks routes as IGP originated

---

**Q35.** An administrator needs to prevent a specific subnet received via BGP from being installed in the routing table. Which feature achieves this?

- A) Route map with `set action deny` on inbound
- B) Prefix list with `action deny` applied as `neighbor X.X.X.X prefix-list IN`
- C) BGP dampening
- D) Administrative distance adjustment

---

**Q36.** FortiGate has both OSPF and BGP routes to the same destination. By default, which protocol's route is installed in the routing table?

- A) OSPF (AD 110) is preferred over eBGP (AD 20)
- B) eBGP (AD 20) is preferred over OSPF (AD 110)
- C) BGP always wins regardless of AD
- D) The route with the longer prefix mask wins

---

**Q37.** What is the administrative distance of iBGP on FortiGate?

- A) 20
- B) 110
- C) 200
- D) 120

---

**Q38.** Which command on FortiGate clears a BGP session with neighbor 10.0.0.2 WITHOUT resetting the TCP connection?

- A) `execute router clear bgp ip 10.0.0.2`
- B) `execute router clear bgp ip 10.0.0.2 soft in`
- C) `diagnose ip router bgp flush 10.0.0.2`
- D) `config router bgp → delete neighbor 10.0.0.2`

---

**Q39.** An OSPF area is configured as a stub. A router in that area needs to reach external destinations. How does it get routing information?

- A) It receives Type 5 LSAs from the ASBR
- B) The ABR injects a default route (0.0.0.0/0) into the stub area
- C) It must use static routes directly
- D) It establishes a separate eBGP session

---

**Q40.** FortiGate OSPF is configured but adjacency is not forming on a broadcast segment. Which two mismatches most commonly cause this? **(Select 2)**

- A) Hello interval / Dead interval mismatch
- B) MTU mismatch (when `set mtu-ignore` is not set)
- C) Different OSPF process IDs
- D) Different router IDs
- E) Different default gateway

---

## Section 3: IPsec VPN & SD-WAN (Q41–60)

**Q41.** IKEv2 completes the full SA negotiation in how many messages?

- A) 6 (like IKEv1 Main Mode)
- B) 3 (like IKEv1 Quick Mode)
- C) 4 (IKE_SA_INIT + IKE_AUTH exchange, 2 messages each)
- D) 2 (one request, one response)

---

**Q42.** A site-to-site IPsec tunnel is established but traffic does not flow. Which two items should be checked first? **(Select 2)**

- A) Firewall policies allowing traffic in both directions on the tunnel interface
- B) Static route pointing destination subnet via the tunnel interface
- C) BGP route advertisement from the peer
- D) IKE version compatibility
- E) DPD configuration

---

**Q43.** An administrator enables `set net-device enable` on a phase1 interface. What does this setting enable?

- A) Allows the tunnel to carry multicast traffic
- B) Creates a dedicated tunnel interface for routing; required for ADVPN
- C) Enables NAT traversal
- D) Allows the tunnel to use dynamic DNS

---

**Q44.** What is the key functional difference between a route-based and a policy-based IPsec VPN on FortiGate?

- A) Route-based uses a tunnel interface with routes; policy-based uses encrypt action in firewall policy
- B) Policy-based is more secure than route-based
- C) Route-based only supports IKEv1
- D) Policy-based supports ADVPN; route-based does not

---

**Q45.** In ADVPN, what message does the Hub send to both spokes to trigger a direct spoke-to-spoke shortcut?

- A) IKE redirect
- B) ADVPN shortcut offer (IKE informational with shortcut attributes)
- C) BGP route update
- D) OSPF LSA Type 9

---

**Q46.** Which IPsec phase1 setting enables DPD (Dead Peer Detection)?

- A) `set dpd on-idle` or `set dpd on-demand`
- B) `set keepalive enable`
- C) `set pfs enable`
- D) `set nattraversal enable`

---

**Q47.** NAT-T (NAT Traversal) encapsulates ESP in which protocol/port?

- A) TCP 443
- B) UDP 500
- C) UDP 4500
- D) GRE (IP Protocol 47)

---

**Q48.** A VPN tunnel is failing at Phase 1. The debug shows "no proposal chosen". What is the most likely cause?

- A) PSK mismatch
- B) Phase 1 encryption/hash/DH group proposal does not match on both peers
- C) Phase 2 selector mismatch
- D) Firewall policy blocking the tunnel

---

**Q49.** An SD-WAN health check probe fails 3 times in a row. What happens to that SD-WAN member?

- A) The interface is administratively disabled
- B) The member is marked as down and traffic fails over to the next available SLA-compliant member
- C) A static route is removed from the routing table
- D) An alert is sent but traffic continues on the member

---

**Q50.** An SD-WAN service rule is configured with `set mode sla`. What does this mean?

- A) Traffic is always distributed evenly across all members
- B) Traffic is sent to members that currently meet the defined SLA thresholds (latency/jitter/loss)
- C) Traffic uses the member with the highest bandwidth
- D) Traffic is source-IP hashed across members

---

**Q51.** Which SD-WAN load-balancing algorithm ensures a specific source IP always uses the same WAN interface?

- A) Session
- B) Spillover
- C) Source IP
- D) Weighted

---

**Q52.** An administrator needs to steer all Microsoft Teams traffic over a low-latency MPLS link, with internet as fallback. Which SD-WAN configuration achieves this?

- A) A static route with metric priority for MPLS
- B) SD-WAN service rule matching Teams application, with MPLS as priority member and SLA failover to internet
- C) Policy-based routing for port 443 to MPLS
- D) BGP community-based routing to MPLS

---

**Q53.** Which FortiGate command shows real-time SD-WAN member SLA status (latency, jitter, loss)?

- A) `get system sdwan`
- B) `diagnose sys sdwan health-check`
- C) `get router info routing-table sdwan`
- D) `diagnose netlink interface list`

---

**Q54.** An SSL-VPN client is assigned an IP from the tunnel IP pool but cannot reach any internal resources. Firewall policies exist. What is the most likely missing configuration?

- A) RADIUS accounting
- B) A firewall policy with `srcintf "ssl.root"` (the SSL-VPN virtual interface)
- C) SSL-VPN user certificate
- D) FortiClient version too old

---

**Q55.** Which SSL-VPN mode allows users to access web-based applications from any browser without installing FortiClient?

- A) Tunnel mode
- B) Web mode (clientless portal)
- C) Split-tunnel mode
- D) ZTNA mode

---

**Q56.** Perfect Forward Secrecy (PFS) in IPsec means:

- A) Session keys are the same as the IKE master key
- B) A new DH exchange is performed for Phase 2, so compromise of long-term keys does not expose past session keys
- C) The PSK is rotated automatically every hour
- D) PFS only applies to IKEv1

---

**Q57.** A spoke FortiGate uses `set auto-discovery-receiver enable`. What does this allow?

- A) The spoke to advertise its routes to other spokes via the hub
- B) The spoke to accept and establish ADVPN shortcuts initiated by the hub's shortcut offer
- C) The spoke to discover the hub automatically via DNS
- D) The spoke to forward hub traffic without establishing a tunnel

---

**Q58.** SD-WAN `spillover` mode triggers use of secondary WAN when:

- A) Packet loss on primary exceeds threshold
- B) Bandwidth usage on primary exceeds the configured threshold
- C) Latency on primary exceeds SLA
- D) Primary WAN is administratively down

---

**Q59.** An administrator configures split tunneling on SSL-VPN with `set split-tunneling-routing-address "Corp-Subnets"`. What happens to internet-bound traffic from VPN clients?

- A) All traffic goes through the VPN tunnel
- B) Only Corp-Subnets traffic goes through VPN; internet traffic exits directly from the client's local internet
- C) Internet traffic is blocked
- D) Internet traffic is NATed through the FortiGate

---

**Q60.** Which two IKEv2 features are NOT available in IKEv1? **(Select 2)**

- A) PSK authentication
- B) MOBIKE (mobility and multihoming)
- C) EAP authentication natively in IKE
- D) Main Mode negotiation
- E) DH group negotiation

---

## Section 4: High Availability (Q61–75)

**Q61.** In an A/P HA cluster, which unit processes all production traffic?

- A) Both units process traffic simultaneously
- B) The primary unit processes all traffic; the secondary is on standby
- C) The secondary unit processes traffic; primary is standby
- D) Traffic is distributed based on VLAN assignment

---

**Q62.** An HA cluster is configured with `set override enable` on the primary. The primary fails and recovers. What happens?

- A) The secondary remains primary even after the original primary recovers
- B) The original primary reclaims the primary role once it rejoins the cluster
- C) Both units claim the primary role causing a split-brain
- D) The cluster must be manually reset

---

**Q63.** What is the purpose of the HA heartbeat interface?

- A) Carries production traffic between cluster members
- B) Carries HA control messages and session synchronization between cluster members
- C) Provides management access to the standby unit
- D) Synchronizes FortiGuard license status

---

**Q64.** Which sessions are NOT synchronized in an A/P HA cluster? **(Select 2)**

- A) Established TCP sessions
- B) IPsec SAs
- C) Administrator SSH sessions to the FortiGate management IP
- D) SSL-VPN tunnels
- E) Local-out traffic initiated by the FortiGate itself

---

**Q65.** The HA primary selection criteria states "override enabled, then priority, then monitored interfaces up, then uptime". A cluster has two FortiGates: FGT-A (priority 200, override enabled) and FGT-B (priority 100). Both have all interfaces up. FGT-A has been running for 10 minutes, FGT-B for 3 hours. Which is primary?

- A) FGT-B — higher uptime wins
- B) FGT-A — higher priority with override enabled
- C) FGT-B — uptime overrides priority
- D) FGT-A — it was primary first

---

**Q66.** An administrator wants to manage each HA cluster member independently via separate IPs without affecting production traffic. Which feature provides this?

- A) VDOM management interface
- B) HA management interface (`set ha-mgmt-status enable`)
- C) FortiManager centralized management
- D) Out-of-band switch with port mirroring

---

**Q67.** FGSP is used instead of standard HA clustering in which scenario?

- A) Two FortiGates in the same rack sharing a single configuration
- B) Two independent FortiGates handling asymmetric traffic flows (different entry and exit points)
- C) Two FortiGates with identical configurations behind a load balancer
- D) A FortiGate pair operating in transparent mode only

---

**Q68.** Which command forces an A/P cluster to fail over from the current primary to the secondary?

- A) `execute ha failover set 1`
- B) `execute ha switch-over`
- C) `diagnose sys ha force-failover`
- D) `config system ha → set priority 1`

---

**Q69.** In an A/A HA cluster, how are sessions from external clients distributed to cluster members?

- A) DNS round-robin from FortiGate
- B) The primary receives all sessions and distributes them to members via the HA link
- C) An external load balancer distributes sessions before they reach FortiGate
- D) Sessions are ECMP load-balanced via upstream routing

---

**Q70.** What is the recommended method to perform a FortiGate firmware upgrade in an A/P HA cluster with minimal traffic disruption?

- A) Upgrade both units simultaneously
- B) Upgrade the primary first, then secondary
- C) Upgrade the secondary first, then force failover, then upgrade the old primary
- D) Use FortiManager to push the upgrade to both simultaneously

---

**Q71.** An HA cluster shows "out of sync" status. Which command forces a full configuration sync from primary to secondary?

- A) `diagnose sys ha checksync`
- B) `execute ha synchronize config`
- C) `diagnose sys ha push-config`
- D) `config system ha → set sync-config enable`

---

**Q72.** Virtual MAC addresses in HA clustering serve which purpose?

- A) Provide unique MAC addresses for each VLAN
- B) Prevent MAC table updates in upstream switches during failover, enabling seamless traffic continuation
- C) Used for heartbeat packet identification
- D) Provide Layer 3 identification for routing

---

**Q73.** An administrator configures virtual clustering. VDOM-Finance is primary on FGT-A and VDOM-HR is primary on FGT-B. What is this configuration called?

- A) Active/Active HA
- B) FGSP
- C) Virtual clustering with per-VDOM primary assignment
- D) VDOM failover group

---

**Q74.** A link monitor is configured on `wan1` pinging 8.8.8.8 with `set ha-priority 10`. If 8.8.8.8 becomes unreachable, what happens?

- A) The FortiGate immediately fails over
- B) The HA priority of this unit is reduced by 10, potentially triggering failover if the peer has higher effective priority
- C) Only the wan1 interface is shut down
- D) A syslog alert is generated only

---

**Q75.** Which two HA cluster requirements must be met for the cluster to form? **(Select 2)**

- A) Both units must have the same HA group name and password
- B) Both units must have the same firmware version
- C) Both units must have the same IP address on all interfaces
- D) Both units must be the same FortiGate hardware model
- E) Both units must have the same serial number prefix

---
