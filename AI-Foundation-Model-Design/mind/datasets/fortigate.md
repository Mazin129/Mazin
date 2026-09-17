# FortiGate and FortiOS

FortiGate is a next-generation firewall made by Fortinet that combines firewall, VPN, intrusion prevention, antivirus, and web filtering in one device.
FortiOS is the operating system that runs on every FortiGate device and provides its security and networking features.
A next-generation firewall inspects traffic at the application layer, not just by port and address, so it can identify and control specific applications.
Fortinet is the company that develops FortiGate firewalls, FortiOS, and the wider Fortinet Security Fabric.
The Fortinet Security Fabric is an architecture that links FortiGate and other Fortinet products so they share information and coordinate their response to threats.
A FortiGate can run as a physical appliance, a virtual machine, or a cloud instance, all using the same FortiOS.
The FortiGate GUI is a web-based interface used to configure and monitor the firewall through a browser.
The FortiGate CLI is a command-line interface used to configure the firewall by typing commands, reached through SSH or the console port.

## Firewall policies

A firewall policy is a rule on a FortiGate that decides whether traffic is allowed or denied between a source and a destination.
FortiGate evaluates firewall policies from top to bottom and uses the first policy that matches the traffic.
A firewall policy matches traffic by incoming interface, outgoing interface, source address, destination address, service, and schedule.
The action of a firewall policy is either accept, which allows the traffic, or deny, which blocks it.
An implicit deny policy at the bottom of the list blocks any traffic that does not match an earlier policy.
A firewall policy can apply security profiles to scan the traffic it allows for threats.
A policy route, also called policy-based routing, forwards traffic based on its source or service rather than only its destination.

## Interfaces, zones, and VDOMs

An interface on a FortiGate is a physical or virtual port that connects the firewall to a network.
A zone groups several interfaces together so that one firewall policy can apply to all of them.
A virtual domain, or VDOM, splits one physical FortiGate into several independent virtual firewalls, each with its own policies and routing.
The root VDOM is the default virtual domain that exists on every FortiGate.
Virtual IPs, or VIPs, are used on FortiGate to publish an internal server to the internet by mapping a public address to a private one.

## Security profiles

A security profile is a set of inspection settings that a firewall policy applies to traffic, such as antivirus or web filtering.
The antivirus profile on a FortiGate scans files in traffic and blocks those that contain malware.
The intrusion prevention system, or IPS, detects and blocks network attacks by matching traffic against known attack signatures.
The web filter profile controls which websites users can visit by blocking categories or specific URLs.
Application control identifies applications inside traffic and allows or blocks them regardless of the port they use.
An SSL inspection profile lets FortiGate decrypt and scan encrypted HTTPS traffic for hidden threats.
Deep inspection decrypts SSL traffic to inspect its contents, while certificate inspection only checks the certificate without decrypting.
A DNS filter blocks access to malicious or unwanted domains by inspecting DNS requests.
FortiGuard is Fortinet's subscription service that delivers antivirus, IPS, web filtering, and application updates to FortiGate devices.

## NAT

Network address translation, or NAT, changes the source or destination IP address of traffic as it passes through the FortiGate.
Source NAT changes the source address of outgoing traffic, usually to the firewall's public address, so internal devices can reach the internet.
Destination NAT changes the destination address of incoming traffic to send it to an internal server.
An IP pool is a range of addresses that FortiGate uses as the translated source address for outgoing NAT.
Central NAT separates NAT rules from firewall policies so they can be managed independently.

## VPN

A virtual private network, or VPN, creates an encrypted tunnel that carries private traffic securely across the public internet.
IPsec VPN is a site-to-site tunnel that securely connects two networks, such as a branch office and a headquarters.
SSL VPN lets remote users connect securely to the internal network through a web browser or the FortiClient application.
SSL VPN web mode gives remote users access to internal resources through a web portal without installing software.
SSL VPN tunnel mode gives remote users full network access through the FortiClient VPN client.
A phase 1 configuration in IPsec sets up the secure channel and authenticates the two VPN peers.
A phase 2 configuration in IPsec defines which traffic is encrypted and sent through the tunnel.
FortiClient is Fortinet's endpoint software that provides VPN access, antivirus, and web filtering on user devices.

## High availability

High availability, or HA, links two or more FortiGate units so that if one fails another takes over with no loss of service.
In active-passive HA, one FortiGate handles all traffic while the others stand by ready to take over.
In active-active HA, several FortiGate units share the traffic load at the same time.
A heartbeat interface is a dedicated link that HA FortiGate units use to monitor each other and synchronize their configuration.
Failover is the process where a standby FortiGate takes over when the active unit stops responding.

## Routing and SD-WAN

A static route on a FortiGate manually defines the path to a destination network through a chosen interface and gateway.
FortiGate supports dynamic routing protocols such as OSPF and BGP to learn routes automatically.
SD-WAN on a FortiGate combines several internet links and steers traffic across them based on performance and rules.
An SD-WAN rule chooses which link to use for an application based on latency, jitter, packet loss, or bandwidth.
Link health monitoring in SD-WAN measures the quality of each link by sending probes to a server.

## Logging and monitoring

FortiGate can send its logs to memory, disk, FortiAnalyzer, or a remote syslog server.
FortiAnalyzer is a Fortinet product that collects, stores, and analyzes logs from many FortiGate devices.
FortiManager is a Fortinet product that centrally manages the configuration of many FortiGate devices.
A log message on a FortiGate records an event such as an allowed session, a blocked attack, or a system change.
The forward traffic log records sessions that passed through firewall policies.

## Administration

An administrator account on a FortiGate is used to log in and manage the device, with a profile that limits what it can change.
A configuration backup saves the full FortiGate configuration to a file so it can be restored later.
A firmware upgrade replaces the FortiOS version on a FortiGate to add features or fix security issues.
Trusted hosts restrict administrator logins to specific source IP addresses for extra security.
The factory reset command returns a FortiGate to its default configuration and erases all settings.

## Deployment modes

NAT mode is the default FortiGate operating mode where the firewall routes traffic between networks and each interface has its own IP address.
Transparent mode lets a FortiGate inspect traffic like a bridge without changing the existing IP addressing of the network.
In transparent mode the whole FortiGate is reached through a single management IP address.
A one-arm sniffer configuration lets a FortiGate inspect a copy of traffic from a switch mirror port without being in the traffic path.

## Objects

An address object on a FortiGate represents a host, a subnet, an IP range, or a fully qualified domain name so it can be reused in policies.
An address group combines several address objects so a policy can reference them together.
A service object defines a protocol and port, such as HTTP on TCP 80, so policies can match specific traffic.
A schedule object defines the times when a firewall policy is active, either as a recurring window or a one-time period.
An internet service object is a Fortinet-maintained list of IP addresses for a known cloud or web service, used to match traffic without typing addresses.

## Authentication and identity

Firewall authentication requires users to prove their identity before a policy allows their traffic.
A user group on a FortiGate collects users so that policies and VPNs can grant access to the whole group at once.
LDAP lets a FortiGate check user credentials against a directory server such as Microsoft Active Directory.
RADIUS lets a FortiGate authenticate users against a central RADIUS server, often for VPN or administrator logins.
Fortinet Single Sign-On, or FSSO, lets a FortiGate learn which user is logged in to which device so policies can apply by user without a second login.
A captive portal is a web page that intercepts users and asks them to log in before granting network access.
Two-factor authentication adds a second proof of identity, such as a one-time code, on top of a password.
FortiToken is a hardware or mobile app token that generates one-time codes for two-factor authentication on FortiGate.

## Zero Trust Network Access

Zero Trust Network Access, or ZTNA, grants access to an application only after checking the user's identity and the security posture of their device, for every session.
A ZTNA access proxy on a FortiGate brokers connections to internal applications so users never connect to the network directly.
A ZTNA tag describes the security state of a device, such as whether antivirus is running, and is used to allow or deny access.
The principle of least privilege gives each user only the access they need, which is the foundation of Zero Trust.

## Traffic shaping

Traffic shaping controls how much bandwidth different types of traffic can use on a FortiGate.
A shared traffic shaper limits the total bandwidth for all traffic that matches a policy.
A per-IP traffic shaper limits the bandwidth available to each individual user.
Quality of Service, or QoS, prioritizes important traffic such as voice and video over less urgent traffic.
DSCP marking tags packets with a priority value so other network devices can also handle them by priority.

## Proxy and web security

An explicit web proxy makes user browsers send their web traffic directly to the FortiGate for inspection and caching.
A transparent proxy inspects web traffic without requiring any settings on the user's browser.
A web application firewall, or WAF, protects web servers by blocking attacks such as SQL injection and cross-site scripting.
FortiWeb is Fortinet's dedicated web application firewall product for protecting web applications.
A DoS policy on a FortiGate detects and blocks denial-of-service floods before they reach firewall policies.
FortiSandbox analyzes suspicious files by running them in an isolated environment to detect unknown malware.

## Wireless and switching

FortiAP is a Fortinet wireless access point that a FortiGate manages and configures centrally.
An SSID is the name of a wireless network that a FortiAP broadcasts for clients to join.
FortiGate can act as a wireless controller that manages many FortiAP units across a site.
FortiSwitch is a Fortinet network switch that a FortiGate can manage directly through the Security Fabric.
FortiLink is the protocol that lets a FortiGate manage FortiSwitch units as if they were its own ports.

## Certificates and services

A digital certificate on a FortiGate proves the identity of the device or a server and enables encrypted connections.
A certificate authority, or CA, is a trusted entity that issues and signs digital certificates.
FortiGate can act as a DHCP server that assigns IP addresses to devices on a connected network.
FortiGate can act as a DNS server or DNS forwarder that resolves names for clients on the network.
SNMP lets a monitoring system read status and performance information from a FortiGate.
A local-in policy controls traffic destined for the FortiGate itself, such as management and VPN connections.

## Sessions

The session table on a FortiGate lists every active connection passing through the firewall.
A session records the source, destination, protocol, and state of a connection so return traffic is allowed automatically.
Stateful inspection means the FortiGate tracks the state of each connection and only allows packets that belong to a known session.
The conserve mode is a protective state a FortiGate enters when memory runs low, during which it stops accepting new sessions to stay stable.
