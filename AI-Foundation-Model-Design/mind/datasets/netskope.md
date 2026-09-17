# Netskope

Netskope is a Security Service Edge, or SSE, vendor that delivers cloud access security broker, secure web gateway, and Zero Trust network access from the cloud.
A cloud access security broker, or CASB, sits between users and cloud apps to enforce policy, detect threats, and report on usage.
Netskope's CASB can operate in API mode to scan data already stored in SaaS apps and in inline mode to control traffic in real time.
A secure web gateway, or SWG, inspects web traffic to block malicious sites, enforce acceptable use, and decrypt HTTPS when policy allows.
Netskope NewEdge is the company's private global network built to deliver SSE services with low latency.
Netskope Private Access provides Zero Trust network access so users reach private apps without a traditional full-tunnel VPN into the corporate network.
Steering in Netskope means directing user traffic to the Netskope cloud using a client, PAC file, GRE, IPsec, or reverse proxy.
The Netskope Client is endpoint software that authenticates the user and steers selected traffic to Netskope for inspection.
SSL decryption, or TLS interception, on Netskope lets the service see inside HTTPS so DLP and threat engines can inspect payloads.
Enterprises must distribute the Netskope certificate authority to managed devices so SSL decryption does not break trust.
Data loss prevention, or DLP, policies detect sensitive data such as credit cards or source code leaving sanctioned or unsanctioned apps.
Cloud Confidence Index style ratings help compare the security posture of cloud applications.
Shadow IT discovery finds unsanctioned cloud apps employees are using from logs and traffic metadata.
An SSE architecture typically combines SWG, CASB, and ZTNA; SASE adds SD-WAN on the networking side.
Netskope can integrate with identity providers so access policies use user and group claims.
API connectors for SaaS platforms let Netskope inventory files, revoke shares, and quarantine malware without inline traffic.
Threat protection in Netskope uses signatures, sandboxing, and machine learning to find malware in cloud uploads and downloads.
Remote browser isolation can render risky web content away from the endpoint when policy requires it.
A common design is to steer only web and cloud app traffic to Netskope while keeping voice or large trusted CDN flows direct.
When SSL decryption is enabled, pinning and mutual TLS apps may need exceptions so they are not broken.
Admin roles in Netskope separate policy design, incident response, and tenant configuration for least privilege.
Audit logs record admin changes and are important for compliance investigations.
Netskope Real-time Protection policies decide allow, block, alert, or coach actions as users access cloud and web destinations.
Forensic and incident workflows use alerts, file hashes, user identity, and app context to triage cloud threats.
A healthy Netskope deployment continuously tunes steering exceptions, certificate distribution, and DLP false positives.
