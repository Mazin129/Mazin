# AWS Networking

Amazon Web Services, or AWS, is Amazon's cloud platform that provides computing, storage, and networking on demand.
A virtual private cloud, or VPC, is an isolated private network inside AWS where you launch your resources.
A subnet divides a VPC into a smaller range of addresses within a single availability zone.
A public subnet is a subnet whose traffic can reach the internet through an internet gateway.
A private subnet is a subnet with no direct route to the internet.
An internet gateway lets resources in a VPC communicate with the internet.
A NAT gateway lets resources in a private subnet reach the internet while staying unreachable from it.
A security group is a stateful firewall that controls inbound and outbound traffic for an AWS resource such as an EC2 instance.
A security group is stateful, so if it allows a request out, the reply is automatically allowed back in.
A network access control list, or network ACL, is a stateless firewall that controls traffic at the subnet boundary.
A network ACL is stateless, so both the request and the reply must be allowed by separate rules.
A route table in a VPC contains rules that determine where network traffic is directed.
VPC peering connects two VPCs so their resources can communicate using private addresses.
A transit gateway is a hub that connects many VPCs and on-premises networks through a single gateway.
AWS Direct Connect is a dedicated private network connection between an on-premises network and AWS.
A VPN connection in AWS creates an encrypted IPsec tunnel between an on-premises network and a VPC.
Elastic Load Balancing distributes incoming traffic across multiple targets such as EC2 instances.
An Application Load Balancer routes web traffic at layer 7 based on the content of the request.
A Network Load Balancer distributes traffic at layer 4 for very high performance and low latency.
Amazon Route 53 is the AWS Domain Name System service that routes users to applications by resolving names.
AWS WAF is a web application firewall that protects web applications from common attacks.
AWS Shield protects AWS applications against distributed denial-of-service attacks.
An elastic IP address is a static public IP address that you can assign to AWS resources.
A VPC endpoint lets resources connect privately to AWS services without using the public internet.
An availability zone is an isolated data center location within an AWS region.
A region in AWS is a geographic area that contains multiple availability zones.
AWS Network Firewall is a managed firewall service that filters traffic at the VPC boundary.
Amazon CloudFront is a content delivery network that serves content quickly from edge locations near users.
