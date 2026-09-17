# Cisco networking and security platforms

Cisco IOS XE is a network operating system used on many Cisco enterprise routers and switches.
A Cisco Catalyst switch is commonly used for campus access and distribution layer switching.
Cisco Nexus switches are designed for datacenter leaf-and-spine fabrics and high throughput.
OSPF and BGP are routing protocols widely configured on Cisco routers for enterprise and WAN connectivity.
A VLAN on a Cisco switch segments a Layer 2 domain; trunks carry multiple VLANs between switches using 802.1Q tags.
Cisco ACI is an SDN fabric that uses a Cisco Application Policy Infrastructure Controller to define datacenter network policy.
Cisco SD-WAN, formerly Viptela, builds an overlay WAN with centralized policy across branches and clouds.
Cisco DNA Center, now part of Catalyst Center branding in many docs, automates campus network provisioning and assurance.
Cisco ISE is an identity services engine that provides AAA, 802.1X, guest access, and profiling for network admission.
RADIUS is the protocol Cisco ISE commonly uses with switches and wireless controllers to authorize endpoints.
Cisco ASA is a legacy adaptive security appliance firewall still found in many enterprises.
Cisco Secure Firewall Threat Defense, or FTD, is the modern NGFW platform managed by Firewall Management Center.
Firepower services add intrusion prevention and application visibility to Cisco firewall deployments.
Cisco Umbrella is a cloud DNS-layer security service that blocks requests to malicious domains before a connection starts.
Cisco Duo provides multi-factor authentication for users and applications.
Cisco AnyConnect, evolved into Cisco Secure Client, is used for remote access VPN to ASA or FTD headends.
Site-to-site IPsec VPNs on Cisco routers and firewalls connect branches over the internet with encryption.
A Cisco wireless LAN controller manages access points centrally for enterprise Wi-Fi.
CAPWAP tunnels carry wireless client traffic and control between access points and a controller in many Cisco designs.
Cisco Stealthwatch, now part of Cisco Secure Network Analytics, detects threats using NetFlow and telemetry.
NetFlow and IPFIX export traffic metadata that security tools use for anomaly detection.
Access control lists on Cisco devices filter traffic by address, port, and protocol at interfaces or elsewhere in the path.
Object-groups on ASA and FTD simplify firewall rules by naming sets of addresses and services.
High availability on Cisco firewalls uses failover pairs so a standby unit can take over when the active unit fails.
Cisco recommends defense in depth: segmentation, strong AAA, encrypted management, and continuous telemetry rather than a single perimeter control.
Secure device management means disabling unused services, using SSH instead of Telnet, and authenticating admins with ISE or TACACS+.
TACACS+ is often preferred for device administration accounting because it can authorize individual commands.
Spanning Tree Protocol prevents loops in Layer 2 Cisco campus networks; rapid variants converge faster after topology changes.
EtherChannel bundles multiple physical links into one logical link for bandwidth and redundancy.
Quality of service on Cisco platforms classifies and queues traffic so voice and critical apps keep priority during congestion.
