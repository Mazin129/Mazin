# Cloudflare

Cloudflare is a global cloud platform that provides CDN, DNS, DDoS protection, WAF, and Zero Trust services in front of internet-facing applications.
A content delivery network, or CDN, caches content at edge locations so users fetch it from a nearby PoP instead of the origin every time.
Cloudflare DNS is an authoritative DNS service that answers domain queries and can proxy traffic through the Cloudflare network.
When an orange-cloud proxy is enabled in Cloudflare DNS, visitor traffic goes to Cloudflare first and then to the origin server.
When the proxy is grey-cloud DNS only, Cloudflare answers DNS but does not terminate HTTP at the edge.
Cloudflare terminates TLS at the edge using certificates it manages for proxied hostnames.
Full Strict SSL mode on Cloudflare requires a valid certificate on the origin that matches the hostname.
Flexible SSL mode encrypts the client-to-Cloudflare path but may use cleartext between Cloudflare and the origin, which is weaker.
Cloudflare Tunnel, formerly Argo Tunnel, creates an outbound-only connection from an origin connector to Cloudflare so you can publish apps without opening inbound firewall ports.
Cloudflare Access is a Zero Trust access control service that authenticates users before they reach an application.
Cloudflare Gateway is a secure web gateway that filters DNS, HTTP, and network traffic for corporate users and devices.
A Web Application Firewall, or WAF, inspects HTTP requests and blocks common attacks such as SQL injection and cross-site scripting.
Cloudflare Bot Management helps distinguish automated traffic from real users.
DDoS protection on Cloudflare absorbs or filters volumetric and application-layer floods before they reach the origin.
Workers are serverless functions that run on Cloudflare's edge near the user.
Cloudflare Pages hosts static sites and Jamstack applications on the edge network.
Spectrum extends Cloudflare's proxying and DDoS protection to non-HTTP TCP and UDP applications.
Origin CA certificates issued by Cloudflare can be installed on the origin for Full Strict mode without buying a public certificate for every host.
Authenticated Origin Pulls require the origin to accept only TLS clients that present a Cloudflare client certificate.
Always Use HTTPS and HSTS settings on Cloudflare help force browsers onto encrypted connections.
Rate limiting rules reduce abuse by capping how many requests a client can send in a time window.
Firewall custom rules let administrators allow, block, challenge, or log traffic based on IP, country, ASN, path, or other fields.
Cache rules control what the CDN stores and how long it is considered fresh.
A cache purge removes selected or all cached objects so the edge refetches them from the origin.
Cloudflare Load Balancing steers traffic across multiple origins based on health checks and geographic policy.
Magic Transit extends Cloudflare DDoS protection to entire IP networks using BGP.
Zero Trust Network Access concepts in Cloudflare replace many traditional VPN use cases with identity-aware application access.
Security teams often place Cloudflare in front of public websites to hide the origin IP and reduce direct attacks on the datacenter edge.
Correct origin firewalling still matters: allow Cloudflare IP ranges or Tunnel connectors and deny the rest of the internet to the origin.
