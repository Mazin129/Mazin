A VLAN is a virtual LAN that logically segments one physical network into separate broadcast domains.
A VLAN improves security and performance by keeping traffic from different groups isolated.
A trunk is a switch link that carries traffic for many VLANs at once using 802.1Q tags.
An access port belongs to a single VLAN and connects to one end device such as a PC or phone.
The native VLAN is the one VLAN whose frames are sent untagged across a trunk.
Inter-VLAN routing is the process of forwarding traffic between VLANs using a router or a layer 3 switch.
STP is the Spanning Tree Protocol that prevents loops in a switched network by blocking redundant paths.
STP elects one root bridge and disables backup links until they are needed.
A broadcast domain is the set of devices that receive a broadcast frame sent by any one of them.
A collision domain is a network segment where devices can interfere if they transmit at the same time.
A switch forwards frames using MAC addresses and creates a separate collision domain per port.
A router forwards packets between networks using IP addresses and separates broadcast domains.
A hub is a legacy device that repeats every signal to all ports and shares one collision domain.

The OSI model describes networking in seven layers: physical, data link, network, transport, session, presentation, and application.
Layer 1 is the physical layer and moves raw bits over cables, fiber, or radio.
Layer 2 is the data link layer and delivers frames between devices using MAC addresses.
Layer 3 is the network layer and routes packets between networks using IP addresses.
Layer 4 is the transport layer and provides end-to-end delivery using TCP or UDP.
The TCP/IP model has four layers: link, internet, transport, and application.

An IP address is a logical identifier that locates a device on a network.
IPv4 uses 32-bit addresses written as four decimal numbers separated by dots.
IPv6 uses 128-bit addresses written as eight groups of hexadecimal digits.
A subnet mask separates an IP address into its network portion and its host portion.
Subnetting is the practice of dividing one large network into smaller subnetworks.
CIDR notation writes a subnet mask as a slash and the number of network bits, such as /24.
A default gateway is the router a device uses to reach hosts on other networks.
A private IP address is used inside a local network and is not routable on the public internet.
NAT is Network Address Translation that maps private addresses to a public address so many hosts can share one public IP.

TCP is a connection-oriented protocol that guarantees reliable, ordered delivery of data.
TCP uses a three-way handshake of SYN, SYN-ACK, and ACK to establish a connection.
UDP is a connectionless protocol that sends data quickly without guaranteeing delivery.
UDP is used for voice, video, and DNS where speed matters more than reliability.
A port number identifies a specific service or application on a host.
HTTP uses port 80 and HTTPS uses port 443 for web traffic.

DNS is the Domain Name System that translates human-readable names into IP addresses.
DHCP is the Dynamic Host Configuration Protocol that automatically assigns IP addresses to devices.
ARP is the Address Resolution Protocol that maps an IP address to a MAC address on a local network.
ICMP is the protocol that ping and traceroute use to test reachability and report errors.

Routing is the process of selecting a path for traffic to travel between networks.
A routing table is the list of known destinations and the next hop a router uses to reach each one.
A static route is a path configured manually by an administrator.
A dynamic routing protocol lets routers learn paths automatically and adapt to changes.
OSPF is a link-state routing protocol that finds the shortest path using Dijkstra's algorithm.
OSPF is used inside a single autonomous system and converges quickly after a change.
When a link fails, OSPF recalculates the best route and updates the routing table.
BGP is the Border Gateway Protocol that routes traffic between autonomous systems across the internet.
BGP chooses paths based on policy and attributes rather than on shortest distance.
EIGRP is a Cisco routing protocol that combines fast convergence with low overhead.
Administrative distance is the value a router uses to prefer one routing source over another.
Convergence is the time a network takes for all routers to agree on the current topology.

A firewall is a security device that filters traffic between networks based on defined rules.
A stateful firewall tracks active connections and allows return traffic automatically.
A firewall policy is an ordered rule that permits or denies traffic by source, destination, and service.
A DMZ is a separated network zone that hosts public-facing servers away from the internal network.
A VPN is a Virtual Private Network that creates an encrypted tunnel across an untrusted network.
IPsec is a suite of protocols that secures VPN traffic with authentication and encryption.
An intrusion prevention system inspects traffic and blocks known attacks in real time.

Congestion is when a network link carries more traffic than it can handle.
Congestion causes packet loss because overloaded devices drop excess packets.
Packet loss causes retransmission because the sender must resend the dropped data.
Retransmission causes higher latency because delivering the data takes longer.
Latency is the time a packet takes to travel from source to destination.
Jitter is the variation in latency between packets and it degrades voice and video quality.
Bandwidth is the maximum rate at which a link can carry data.
Throughput is the actual rate of successful data delivery over a link.
Quality of Service prioritizes important traffic so latency-sensitive applications perform well.

A MAC address is a hardware identifier burned into a network interface.
A frame is the layer 2 unit of data that carries a source and destination MAC address.
A packet is the layer 3 unit of data that carries a source and destination IP address.
Encapsulation is the process of wrapping data with headers as it moves down the layers.
A protocol is a set of rules that lets devices communicate and understand each other.
