"""
sources — a curated catalog of TRUSTED network & security knowledge, and a one-command
way to teach it to Vio.

Each entry is (name, kind, ref, topic):
  * kind "github" → learned via Mind.learn_github (docs only; never runs repo code)
  * kind "url"    → fetched by the web research agent (needs VIO_ALLOW_NET=1)

Chosen for signal-to-noise: authoritative docs and doc-heavy repos (Markdown/cheat
sheets/awesome-lists), not giant codebases. Extend freely — this is just a starting set.
"""

SECURITY_SOURCES = [
    # ── Kubernetes / service mesh ─────────────────────────────────────────────
    ("Istio security concepts", "url",
     "https://istio.io/latest/docs/concepts/security/", "k8s/mesh"),
    ("Istio PeerAuthentication", "url",
     "https://istio.io/latest/docs/reference/config/security/peer_authentication/", "k8s/mesh"),
    ("Kubernetes NetworkPolicy", "url",
     "https://kubernetes.io/docs/concepts/services-networking/network-policies/", "k8s"),
    ("Kubernetes hardening (NSA/CISA)", "url",
     "https://media.defense.gov/2022/Aug/29/2003066362/-1/-1/0/CTR_KUBERNETES_HARDENING_GUIDANCE_1.2_20220829.PDF",
     "k8s"),

    # ── Cloud ─────────────────────────────────────────────────────────────────
    ("AWS IAM best practices", "url",
     "https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html", "cloud/aws"),
    ("AWS IMDSv2 (metadata)", "url",
     "https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/configuring-instance-metadata-service.html",
     "cloud/aws"),

    # ── Frameworks & playbooks ───────────────────────────────────────────────
    ("OWASP Cheat Sheet Series", "github", "OWASP/CheatSheetSeries", "appsec"),
    ("OWASP Top 10", "url", "https://owasp.org/www-project-top-ten/", "appsec"),
    ("MITRE ATT&CK (enterprise)", "url",
     "https://attack.mitre.org/matrices/enterprise/", "ttp"),
    ("NIST Cybersecurity Framework", "url",
     "https://www.nist.gov/cyberframework", "governance"),
    ("CIS Controls", "url", "https://www.cisecurity.org/controls", "governance"),

    # ── Networking ────────────────────────────────────────────────────────────
    ("Cloudflare Learning: BGP", "url",
     "https://www.cloudflare.com/learning/security/glossary/what-is-bgp/", "networking"),
    ("RFC 4271 — BGP-4", "url", "https://www.rfc-editor.org/rfc/rfc4271", "networking"),

    # ── Doc-heavy reference repos (Markdown) ─────────────────────────────────
    ("Awesome Security (list)", "github", "sbilly/awesome-security", "reference"),
    ("The Book of Secret Knowledge", "github",
     "trimstray/the-book-of-secret-knowledge", "reference"),
]

TOPICS = sorted({t for _, _, _, t in SECURITY_SOURCES})


def catalog(topic=None):
    """Return the source entries, optionally filtered by a topic substring."""
    if not topic:
        return list(SECURITY_SOURCES)
    t = topic.lower()
    return [s for s in SECURITY_SOURCES if t in s[3].lower() or t in s[0].lower()]


def summary(topic=None):
    """Human-readable listing of what Vio can learn."""
    rows = catalog(topic)
    if not rows:
        return f"No trusted sources match '{topic}'. Topics: {', '.join(TOPICS)}."
    lines = [f"Trusted network & security sources I can learn "
             f"({len(rows)}{' for ' + topic if topic else ''}):"]
    for name, kind, ref, tp in rows:
        tag = "📦 repo" if kind == "github" else "🌐 doc"
        lines.append(f"  • {name}  [{tag} · {tp}]  {ref}")
    lines.append("\nTeach me all of them with:  learn essentials"
                 "   (needs VIO_ALLOW_NET=1 for the 🌐 docs).")
    return "\n".join(lines)
