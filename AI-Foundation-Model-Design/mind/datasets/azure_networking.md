# Azure Networking

Microsoft Azure is Microsoft's cloud platform that provides computing, storage, and networking services on demand.
A virtual network, or VNet, is the fundamental building block of a private network in Azure.
A subnet divides an Azure virtual network into smaller address ranges so resources can be grouped and secured separately.
A network security group, or NSG, is a set of rules that allows or denies traffic to and from Azure resources.
An NSG rule matches traffic by source, destination, port, and protocol, and either allows or denies it.
Azure Firewall is a managed, cloud-based firewall that protects Azure virtual network resources with filtering and threat intelligence.
An application security group lets NSG rules reference groups of virtual machines by name instead of by IP address.
VNet peering connects two Azure virtual networks so resources in them can communicate directly and privately.
A route table in Azure contains user-defined routes that control where network traffic is directed.
A user-defined route overrides Azure's default routing to send traffic through a specific next hop, such as a firewall.
Azure Load Balancer distributes network traffic across virtual machines at the transport layer for high availability.
Azure Application Gateway is a layer 7 load balancer that routes web traffic and includes a web application firewall.
The Azure Web Application Firewall protects web applications from common exploits such as SQL injection and cross-site scripting.
Azure Front Door is a global service that delivers and secures web applications with fast routing at the network edge.
Azure Traffic Manager directs users to the best endpoint across regions using DNS-based routing.
A VPN gateway in Azure creates encrypted tunnels between an Azure virtual network and on-premises networks over the internet.
A site-to-site VPN connects an entire on-premises network to an Azure virtual network through an IPsec tunnel.
A point-to-site VPN connects an individual client device securely to an Azure virtual network.
ExpressRoute is a private, dedicated connection between an on-premises network and Azure that does not use the public internet.
An Azure Landing Zone is a preconfigured, secure environment that provides the foundation for deploying workloads in Azure at scale.
A hub-and-spoke topology places shared services in a central hub virtual network that connects to workload spoke networks.
Azure Bastion provides secure remote access to virtual machines through the browser without exposing them to the public internet.
A private endpoint gives a private IP address to an Azure service so it can be reached from a virtual network without going over the internet.
Azure DDoS Protection defends Azure resources against distributed denial-of-service attacks.
A public IP address in Azure allows a resource to be reached from the internet.
Network Watcher is an Azure service that monitors and diagnoses network conditions and traffic.
