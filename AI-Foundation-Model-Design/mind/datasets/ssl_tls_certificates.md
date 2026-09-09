# SSL, TLS, certificates, OpenSSL, and PKI

TLS is the modern protocol that encrypts traffic between a client and a server so eavesdroppers cannot read or alter the data.
SSL is the older name for the same family of protocols; SSL 2.0 and SSL 3.0 are obsolete and must be disabled.
TLS 1.2 and TLS 1.3 are the versions that should be used on the public internet today.
A digital certificate binds a public key to an identity such as a domain name and is signed by a trusted certificate authority.
A certificate authority, or CA, is an organization that issues and signs certificates after verifying the requester.
A public key infrastructure, or PKI, is the set of CAs, certificates, policies, and tools used to manage trust.
An X.509 certificate is the standard format used for TLS server and client certificates.
The subject of a certificate is the identity the certificate claims to represent.
A subject alternative name, or SAN, lists extra hostnames or identities that the certificate covers.
A common name, or CN, is an older field for the primary hostname; modern clients rely more on the SAN list.
A certificate chain is the leaf certificate plus the intermediate certificates that link it back to a trusted root CA.
A root CA certificate is a trust anchor that browsers and operating systems ship with or that an enterprise installs.
An intermediate CA certificate is signed by a root or another intermediate and is used to sign leaf certificates.
A leaf certificate, also called an end-entity certificate, is the certificate presented by a server or client.
A self-signed certificate is signed by its own key instead of a public CA and is useful in labs but not trusted by default on the internet.
A wildcard certificate covers a domain and all first-level subdomains, such as *.example.com.
Certificate transparency is a public logging system that records issued certificates so mis-issuance can be detected.
OCSP is a protocol clients can use to check whether a certificate has been revoked.
A certificate revocation list, or CRL, is a signed list of revoked certificate serial numbers published by a CA.
OCSP stapling lets a server fetch an OCSP response and send it with the handshake so clients do not need a separate OCSP query.
Perfect forward secrecy means past session keys remain safe even if the server's long-term private key is later stolen.
In TLS 1.3, handshake encryption and a reduced set of cipher suites remove many legacy options that weakened older SSL and TLS.
A cipher suite names the algorithms used for key exchange, bulk encryption, and integrity in a TLS session.
HTTPS is HTTP carried over TLS, usually on TCP port 443.
SNI, or Server Name Indication, lets a client tell the server which hostname it wants during the TLS handshake so one IP can host many certificates.
mTLS, or mutual TLS, means both the client and the server present certificates and authenticate each other.
A private key must stay secret; if it is leaked, anyone can impersonate the certificate holder until the certificate is revoked or replaced.
OpenSSL is a widely used open-source toolkit that implements TLS, certificate creation, and cryptographic algorithms.
The openssl command-line tool can create keys, certificate signing requests, self-signed certificates, and inspect PEM or DER files.
A PEM file usually holds Base64-encoded certificates or keys between BEGIN and END markers.
A DER file holds the same cryptographic objects in a binary encoding.
A CSR, or certificate signing request, contains the public key and identity fields and is sent to a CA to request a signed certificate.
Let's Encrypt is a free public CA that issues short-lived domain-validated certificates using the ACME protocol.
ACME is the automated protocol clients like Certbot use to prove domain control and obtain certificates from Let's Encrypt.
Certbot is a popular ACME client that obtains and renews Let's Encrypt certificates on web servers.
Domain validation, or DV, proves control of a domain name but does not verify the legal organization behind it.
Organization validation, or OV, and extended validation, or EV, add stronger identity checks by the CA.
A weak certificate practice is to use outdated protocols such as SSL 3.0, TLS 1.0, or TLS 1.1 on production services.
A strong TLS practice is to prefer TLS 1.2+ with modern cipher suites, enable HSTS where appropriate, and automate renewal before expiry.
Certificate expiry is a common outage cause; monitoring notAfter dates and automating renewal prevents sudden HTTPS failures.
Pinning a certificate or public key can harden trust but is risky if rotation is mishandled; HTTP Public Key Pinning is deprecated in browsers.
A reverse proxy or load balancer often terminates TLS and presents the certificate on behalf of backend servers.
In enterprise networks, an internal private CA issues certificates for intranet names that public CAs will not sign.
Trust store mismanagement, such as missing intermediate certificates on the server, causes clients to report untrusted certificate errors even when the leaf is valid.
The openssl s_client command can connect to a host on port 443 and print the certificate chain the server presents.
The openssl x509 command can display certificate fields such as subject, issuer, SAN, and validity dates.
Heartbleed was a serious OpenSSL vulnerability that could leak memory, including private keys, from affected servers.
Keeping OpenSSL and TLS libraries patched is as important as choosing strong cipher suites.
