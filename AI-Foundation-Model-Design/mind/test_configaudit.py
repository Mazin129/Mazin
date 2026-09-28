"""
test_configaudit — pins the configuration review.

A review is only worth anything if it finds real defects AND stays silent on a clean
config. Both halves are tested: a config with planted faults must yield exactly those
findings, and a correct config must yield none. False positives are the failure mode
that would make the feature worthless, so they are checked explicitly.
"""
from __future__ import annotations

import sys

import configaudit
import configparse

PASS, FAIL = [], []


def check(name, cond):
    (PASS if cond else FAIL).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name}")


FAULTY = """
config system interface
    edit "port1"
        set ip 10.10.0.2 255.255.255.0
    next
    edit "port2"
        set ip 192.168.1.1 255.255.255.0
    next
end
config firewall address
    edit "LAN_SUBNET"
        set subnet 192.168.1.0 255.255.255.0
    next
    edit "OLD_DMZ"
        set subnet 172.16.9.0 255.255.255.0
    next
end
config firewall policy
    edit 1
        set name "broad-allow"
        set srcintf "port2"
        set dstintf "port1"
        set srcaddr "all"
        set dstaddr "all"
        set service "ALL"
        set action accept
        set logtraffic disable
    next
    edit 2
        set name "web-only"
        set srcintf "port2"
        set dstintf "port1"
        set srcaddr "LAN_SUBNET"
        set dstaddr "all"
        set service "HTTPS"
        set action accept
    next
    edit 3
        set name "block-same"
        set srcintf "port2"
        set dstintf "port1"
        set srcaddr "LAN_SUBNET"
        set dstaddr "all"
        set service "HTTPS"
        set action deny
    next
    edit 4
        set name "old-rule"
        set srcintf "port9"
        set dstintf "port1"
        set srcaddr "all"
        set dstaddr "all"
        set service "ALL"
        set action accept
        set status disable
    next
end
config router static
    edit 1
        set dst 0.0.0.0 0.0.0.0
        set gateway 10.10.0.1
        set device "port1"
    next
    edit 2
        set dst 0.0.0.0 0.0.0.0
        set gateway 10.10.0.9
        set device "port1"
    next
    edit 3
        set dst 172.20.0.0 255.255.0.0
        set gateway 10.10.0.5
        set device "port7"
    next
end
"""

CLEAN = """
config system interface
    edit "port1"
        set ip 10.10.0.2 255.255.255.0
    next
    edit "port2"
        set ip 192.168.1.1 255.255.255.0
    next
end
config firewall address
    edit "LAN_SUBNET"
        set subnet 192.168.1.0 255.255.255.0
    next
    edit "DB_TIER"
        set subnet 10.50.1.0 255.255.255.0
    next
end
config firewall policy
    edit 1
        set name "lan-to-db"
        set srcintf "port2"
        set dstintf "port1"
        set srcaddr "LAN_SUBNET"
        set dstaddr "DB_TIER"
        set service "MYSQL"
        set action accept
        set logtraffic all
    next
    edit 2
        set name "lan-web"
        set srcintf "port2"
        set dstintf "port1"
        set srcaddr "LAN_SUBNET"
        set dstaddr "DB_TIER"
        set service "HTTPS"
        set action accept
        set logtraffic all
    next
end
config router static
    edit 1
        set dst 0.0.0.0 0.0.0.0
        set gateway 10.10.0.1
        set device "port1"
    next
end
"""


WEAK_DEVICE = """config system global
    set hostname "SA-OCC-FW01"
    set admin-https-ssl-versions tlsv1-0 tlsv1-1 tlsv1-2
    set strong-crypto disable
    set admintimeout 480
end
config system password-policy
    set status disable
end
config system interface
    edit "wan1"
        set ip 203.0.113.2 255.255.255.0
        set allowaccess ping https ssh http
        set role wan
    next
    edit "internal"
        set ip 192.168.1.1 255.255.255.0
        set allowaccess ping https ssh telnet
    next
end
config system admin
    edit "admin"
        set accprofile "super_admin"
    next
end
config system snmp community
    edit 1
        set name "public"
    next
end
config vpn ipsec phase1-interface
    edit "branch-vpn"
        set interface "wan1"
        set mode aggressive
        set proposal 3des-md5 aes128-sha1
        set dhgrp 2 5
    next
end
config vpn ipsec phase2-interface
    edit "branch-p2"
        set phase1name "branch-vpn"
        set proposal aes128-sha1
        set pfs disable
    next
end
config vpn ssl settings
    set ssl-min-proto-ver tls1-0
end
config firewall address
    edit "WEB-SRV"
        set subnet 192.168.1.10 255.255.255.255
    next
end
config firewall policy
    edit 1
        set name "inbound-any"
        set srcintf "wan1"
        set dstintf "internal"
        set srcaddr "all"
        set dstaddr "all"
        set service "HTTPS"
        set action accept
    next
    edit 2
        set name "lan-out"
        set srcintf "internal"
        set dstintf "wan1"
        set srcaddr "all"
        set dstaddr "all"
        set service "HTTPS"
        set action accept
    next
end
"""

HARDENED_DEVICE = """config system global
    set hostname "FW-GOOD"
    set admin-https-ssl-versions tlsv1-2 tlsv1-3
    set strong-crypto enable
    set admintimeout 10
end
config system password-policy
    set status enable
    set minimum-length 14
end
config system interface
    edit "wan1"
        set ip 203.0.113.2 255.255.255.0
        set allowaccess ping
        set role wan
    next
    edit "internal"
        set ip 192.168.1.1 255.255.255.0
        set allowaccess ping https ssh
    next
end
config system admin
    edit "netops"
        set trusthost1 192.168.1.0 255.255.255.0
    next
end
config vpn ipsec phase1-interface
    edit "branch-vpn"
        set interface "wan1"
        set ike-version 2
        set proposal aes256gcm-prfsha384
        set dhgrp 20 21
    next
end
config vpn ipsec phase2-interface
    edit "branch-p2"
        set phase1name "branch-vpn"
        set proposal aes256gcm
        set pfs enable
    next
end
config vpn ssl settings
    set ssl-min-proto-ver tls1-2
end
config firewall address
    edit "WEB-SRV"
        set subnet 192.168.1.10 255.255.255.255
    next
    edit "LAN"
        set subnet 192.168.1.0 255.255.255.0
    next
end
config firewall policy
    edit 1
        set name "publish-web"
        set srcintf "wan1"
        set dstintf "internal"
        set srcaddr "all"
        set dstaddr "WEB-SRV"
        set service "HTTPS"
        set action accept
        set utm-status enable
        set ips-sensor "default"
        set logtraffic all
    next
    edit 2
        set name "lan-out"
        set srcintf "internal"
        set dstintf "wan1"
        set srcaddr "LAN"
        set dstaddr "all"
        set service "HTTPS"
        set action accept
        set utm-status enable
        set av-profile "default"
        set logtraffic all
    next
end
"""


def rules(findings):
    return [f.rule for f in findings]


def main():
    print("=" * 72)
    print("  CONFIG REVIEW")
    print("=" * 72)

    objs = configparse.parse(FAULTY)
    f = configaudit.audit(objs)
    r = rules(f)
    print(f"\n-- planted faults ({len(objs)} objects, {len(f)} findings) --")
    check("any/any accept found", "any-any-accept" in r)
    check("shadowed policy found", "shadowed-policy" in r)
    check("contradiction found (same match, opposite action)", "conflicting-policy" in r)
    check("rules below any/any reported unreachable", "unreachable-after-any" in r)
    check("disabled policy found", "disabled-policy" in r)
    check("accept without logging found", "no-logging" in r)
    check("two default routes found", "multiple-defaults" in r)
    check("unused address object found", "unused-object" in r)
    check("undefined interface found", "dangling-interface" in r)

    high = [x for x in f if x.severity == configaudit.HIGH]
    check("the any/any accept is ranked high", any(x.rule == "any-any-accept" for x in high))
    check("the contradiction is ranked high",
          any(x.rule == "conflicting-policy" for x in high))

    print("\n-- findings name the objects they came from --")
    # A finding either names its objects, or carries them as "Examples:" in the detail
    # (grouped and list-style findings do the latter so ids are not printed twice).
    check("every finding names its objects, in the title or the detail",
          all(x.objects or "Examples:" in x.detail
              or x.rule in ("no-default-route", "interfaces-not-checked")
              for x in f))
    contra = next(x for x in f if x.rule == "conflicting-policy")
    check("contradiction names both policies", len(contra.objects) == 2)
    check("contradiction reads correctly (not 'denyed')",
          "denyed" not in contra.detail and "denies" in contra.detail)

    print("\n-- a clean config produces NO false positives --")
    cobjs = configparse.parse(CLEAN)
    cf = configaudit.audit(cobjs)
    serious = [x for x in cf if x.severity != configaudit.INFO]
    for x in serious:
        print(f"      unexpected: [{x.severity}] {x.rule} — {x.title}")
    check("clean config yields no findings", not serious)
    check("clean config still reports what it checked",
          "object(s) analysed" in configaudit.report(cf, cobjs))

    print("\n-- a big config must not become a 120-line dump --")
    # 120 policies that all share one wide axis. The old report printed the same
    # sentence 120 times, which buried everything that mattered underneath it.
    many = ["config firewall policy"]
    for i in range(1, 121):
        many.append(f'  edit {i}\n   set srcintf "port2"\n   set dstintf "port1"\n'
                    f'   set srcaddr "NET-{i}"\n   set dstaddr "all"\n'
                    f'   set service "HTTPS"\n   set action accept\n'
                    f'   set logtraffic all\n  next')
    many.append("end")
    big = configparse.parse("\n".join(many))
    bf = configaudit.audit(big)
    grouped = configaudit.group(bf, {"policies": 120, "routes": 0})
    check("120 repeats collapse to one finding",
          sum(1 for x in grouped if x.rule == "permissive") == 1)
    g = next(x for x in grouped if x.rule == "permissive")
    check("the grouped finding states the real population", "120 of 120 policies" in g.title)
    check("a universal pattern is demoted to an observation",
          g.severity == configaudit.INFO)
    check("grouped finding shows examples", "Examples:" in g.detail)
    check("grouped finding does not print the same ids twice", not g.objects)

    big_report = configaudit.report(bf, big)
    check("big report stays short (< 2500 chars)", len(big_report) < 2500)
    check("big report does not repeat one line many times",
          big_report.count("leaves one axis unrestricted") <= 1)
    check("big report leads with a verdict",
          any(v in big_report for v in ("Nothing serious found", "worth acting on",
                                        "**Clean.**")))

    faulty_report = configaudit.report(f, objs)
    check("a faulty config leads with what needs acting on",
          "worth acting on" in faulty_report)
    check("few occurrences are still listed individually",
          faulty_report.count("is shadowed by") >= 1)

    print("\n-- device hardening: every planted weakness is found --")
    wobjs = configparse.parse(WEAK_DEVICE)
    wrules = set(rules(configaudit.audit(wobjs)))
    for rule in ("wan-management", "cleartext-admin", "admin-no-trusthost",
                 "default-admin-name", "weak-admin-tls", "strong-crypto-off",
                 "long-admin-timeout", "password-policy-off", "snmp-default-community",
                 "weak-ipsec-crypto", "weak-dh-group", "ike-aggressive-mode",
                 "sha1-ipsec", "no-pfs", "weak-sslvpn-tls", "inbound-to-any",
                 "no-inspection"):
        check(f"finds {rule}", rule in wrules)
    wf = configaudit.audit(wobjs)
    check("internet-reachable management is ranked high",
          any(x.rule == "wan-management" and x.severity == configaudit.HIGH for x in wf))
    check("SNMP 'public' is ranked high",
          any(x.rule == "snmp-default-community" and x.severity == configaudit.HIGH
              for x in wf))

    print("\n-- device hardening: a hardened device produces NO findings --")
    hobjs = configparse.parse(HARDENED_DEVICE)
    hf = [x for x in configaudit.audit(hobjs) if x.severity != configaudit.INFO]
    for x in hf:
        print(f"      unexpected: [{x.severity}] {x.rule} — {x.title}")
    check("hardened device yields no findings", not hf)
    check("outbound browsing (destination all to the WAN) is not flagged",
          "permissive" not in rules(configaudit.audit(hobjs)))

    print("\n-- settings blocks (no edit line) are parsed --")
    g = [o for o in wobjs if o.kind == "system global"]
    check("config system global becomes an object", len(g) == 1)
    check("its settings are kept", g and g[0].get("strong-crypto") == "disable")

    print("\n-- the report states its own limits --")
    rep = configaudit.report(f, objs)
    check("report says no model was involved", "No model was involved" in rep
          or "no model was involved" in rep)
    check("report discloses the address-group limitation",
          "address groups are not expanded" in rep)
    check("report gives severity counts", "high," in rep and "medium," in rep)

    print("\n-- multi-value fields parse correctly --")
    p = configparse.parse('config firewall policy\n edit 1\n'
                          '  set service "HTTP" "HTTPS" "DNS"\n next\nend')[0]
    check('set service "A" "B" "C" → 3 values',
          configaudit._vals(p, "service") == {"http", "https", "dns"})
    check("empty field → empty set", configaudit._vals(p, "srcaddr") == set())
    check("'all' recognised as unrestricted", configaudit._is_any({"all"}) is True)
    check("a named object is not unrestricted",
          configaudit._is_any({"lan_subnet"}) is False)

    print("=" * 72)
    print(f"  {len(PASS)} passed, {len(FAIL)} failed")
    for x in FAIL:
        print(f"    FAILED: {x}")
    print("\nALL PASS" if not FAIL else "\nFAILURES")
    return 1 if FAIL else 0


if __name__ == "__main__":
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    sys.exit(main())
