# Packet analysis and troubleshooting

Packet analysis is the practice of capturing and examining network traffic to understand or troubleshoot what is happening.
Wireshark is a free tool that captures network traffic and displays every packet in detail for analysis.
tcpdump is a command-line tool that captures and displays network packets on a system.
A packet capture, or pcap, is a saved file containing recorded network traffic that can be opened and analyzed later.
A display filter in Wireshark shows only the packets that match a condition, such as a specific address or protocol.
A capture filter limits which packets Wireshark records in the first place, reducing the size of the capture.
The three-way handshake is the exchange of SYN, SYN-ACK, and ACK packets that opens a TCP connection.
A TCP reset, or RST, is a packet that abruptly ends a connection.
A retransmission happens when a sender resends a packet because it did not receive an acknowledgment in time.
Round-trip time is how long a packet takes to reach a destination and for the reply to return.
Latency is the delay before traffic reaches its destination.
Jitter is the variation in delay between packets, which harms voice and video quality.
Packet loss is when packets fail to reach their destination and must be resent or are lost.
A port mirror, or SPAN port, copies traffic from switch ports to another port so it can be captured and analyzed.
A network tap is a device inserted into a link to copy the traffic passing through it for monitoring.
NetFlow is a Cisco technology that records summary information about traffic flows for analysis.
A protocol analyzer decodes captured packets so a person can read the contents of each protocol layer.
The OSI model divides networking into seven layers, from the physical layer up to the application layer.
Encapsulation is the process of wrapping data with the headers of each protocol layer as it is sent.
A maximum transmission unit, or MTU, is the largest packet size that can be sent on a link without fragmentation.
Fragmentation splits a packet that is too large into smaller pieces to fit the MTU of a link.
