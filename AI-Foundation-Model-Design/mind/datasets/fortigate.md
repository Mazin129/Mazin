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
