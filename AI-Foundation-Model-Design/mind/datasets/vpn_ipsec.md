# VPN and IPsec

A virtual private network, or VPN, extends a private network across a public network by carrying traffic through an encrypted tunnel.
A VPN tunnel is the encrypted path through which private data travels safely over the public internet.
A site-to-site VPN connects two whole networks, such as two offices, so their devices communicate as if on one network.
A remote-access VPN connects an individual user's device securely to a private network.
IPsec is a suite of protocols that secures IP traffic by authenticating and encrypting each packet.
IPsec can run in tunnel mode, which encrypts the entire original packet, or transport mode, which encrypts only the payload.
Tunnel mode is used for site-to-site VPNs because it protects and hides the original IP header.
The Encapsulating Security Payload, or ESP, is the IPsec protocol that encrypts and authenticates packet data.
The Authentication Header, or AH, is an IPsec protocol that authenticates packets but does not encrypt them.
Internet Key Exchange, or IKE, is the protocol that negotiates keys and sets up an IPsec tunnel between two peers.
IKE phase 1 authenticates the two peers and builds a secure channel for further negotiation.
IKE phase 2 negotiates the keys and parameters that protect the actual user traffic.
A security association, or SA, is an agreed set of keys and settings that two IPsec peers use to protect traffic.
A pre-shared key is a secret that both VPN peers know in advance and use to authenticate each other.
Diffie-Hellman is a method that lets two peers agree on a shared secret key over an insecure channel.
Perfect forward secrecy generates a fresh key for each session so that compromising one key does not expose past traffic.
A VPN concentrator is a device that handles many VPN connections at once for remote users or sites.
SSL VPN uses the TLS protocol to give users secure remote access through a web browser or a lightweight client.
Split tunneling sends only some traffic through the VPN while the rest goes directly to the internet.
Full tunneling sends all of a user's traffic through the VPN for inspection and control.
NAT traversal lets IPsec VPN traffic pass through devices that perform network address translation.
A dead peer detection mechanism lets a VPN notice when the other end has stopped responding and tear down the tunnel.
