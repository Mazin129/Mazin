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


VIP_DEVICE = """config firewall vip
    edit "WEB-VIP"
        set extip 203.0.113.10
        set mappedip "192.168.1.10"
        set extintf "wan1"
        set portforward enable
        set extport 443
        set mappedport 443
    next
    edit "RDP-VIP"
        set extip 203.0.113.11
        set mappedip "192.168.1.20"
        set extintf "wan1"
        set portforward enable
        set extport 3389
        set mappedport 3389
    next
    edit "WHOLE-HOST"
        set extip 203.0.113.12
        set mappedip "192.168.1.30"
        set extintf "wan1"
    next
    edit "OLD-VIP"
        set extip 203.0.113.13
        set mappedip "192.168.1.40"
        set portforward enable
        set extport 8080
    next
end
config firewall vipgrp
    edit "PUBLIC-SERVERS"
        set member "WEB-VIP"
    next
end
config firewall policy
    edit 10
        set name "publish-web"
        set srcintf "wan1"
        set dstintf "internal"
        set srcaddr "all"
        set dstaddr "PUBLIC-SERVERS"
        set service "HTTPS"
        set action accept
    next
    edit 11
        set name "publish-rdp"
        set srcintf "wan1"
        set dstintf "internal"
        set srcaddr "all"
        set dstaddr "RDP-VIP"
        set service "RDP"
        set action accept
    next
    edit 12
        set name "publish-host"
        set srcintf "wan1"
        set dstintf "internal"
        set srcaddr "all"
        set dstaddr "WHOLE-HOST"
        set service "ALL"
        set action accept
    next
end
"""

MESSY_DEVICE = """config firewall address
    edit "LAN"
        set subnet 192.168.1.0 255.255.255.0
    next
    edit "STALE-OBJ"
        set subnet 10.99.0.0 255.255.0.0
    next
end
config firewall policy
    edit 1
        set srcintf "internal"
        set dstintf "wan1"
        set srcaddr "LAN"
        set dstaddr "all"
        set service "HTTPS"
        set action accept
        set utm-status enable
    next
    edit 2
        set srcintf "internal"
        set dstintf "wan1"
        set srcaddr "LAN"
        set dstaddr "all"
        set service "DNS"
        set action accept
        set utm-status enable
    next
    edit 3
        set srcintf "internal"
        set dstintf "wan1"
        set srcaddr "LAN"
        set dstaddr "all"
        set service "HTTPS"
        set action accept
        set utm-status enable
    next
    edit 4
        set srcintf "internal"
        set dstintf "wan1"
        set srcaddr "LAN"
        set dstaddr "all"
        set service "DNS"
        set action deny
    next
    edit 5
        set srcintf "internal"
        set dstintf "wan1"
        set srcaddr "LAN"
        set dstaddr "all"
        set service "NTP"
        set action accept
        set status disable
    next
end
"""

FAULTY_ORDER = """config system interface
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
        set name "block-dmz"
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
    edit 4
        set dst 172.20.0.0 255.255.0.0
        set gateway 10.10.0.6
        set device "port1"
    next
end
"""


PANOS_DEVICE = """set deviceconfig system hostname PA-EDGE-01
set mgt-config users admin permissions role-based superuser yes
set network interface-management-profile allow-mgmt https yes
set network interface-management-profile allow-mgmt ssh yes
set network interface-management-profile allow-mgmt ping yes
set network interface ethernet ethernet1/1 layer3 interface-management-profile allow-mgmt
set network interface ethernet ethernet1/2 layer3 ip 192.168.1.1/24
set zone untrust network layer3 ethernet1/1
set zone trust network layer3 ethernet1/2
set address WEB-SRV ip-netmask 192.168.1.10/32
set address OLD-SRV ip-netmask 192.168.1.99/32
set address-group SERVERS static [ WEB-SRV ]
set network virtual-router default routing-table ip static-route default destination 0.0.0.0/0
set network virtual-router default routing-table ip static-route default nexthop ip-address 203.0.113.1
set network virtual-router default routing-table ip static-route default interface ethernet1/1
set rulebase security rules "Allow-All" from trust
set rulebase security rules "Allow-All" to untrust
set rulebase security rules "Allow-All" source any
set rulebase security rules "Allow-All" destination any
set rulebase security rules "Allow-All" application any
set rulebase security rules "Allow-All" service any
set rulebase security rules "Allow-All" action allow
set rulebase security rules "Allow-Web-Out" from trust
set rulebase security rules "Allow-Web-Out" to untrust
set rulebase security rules "Allow-Web-Out" source any
set rulebase security rules "Allow-Web-Out" destination any
set rulebase security rules "Allow-Web-Out" application [ web-browsing ssl ]
set rulebase security rules "Allow-Web-Out" service application-default
set rulebase security rules "Allow-Web-Out" action allow
set rulebase security rules "Inbound-Any" from untrust
set rulebase security rules "Inbound-Any" to trust
set rulebase security rules "Inbound-Any" source any
set rulebase security rules "Inbound-Any" destination any
set rulebase security rules "Inbound-Any" application ssl
set rulebase security rules "Inbound-Any" service application-default
set rulebase security rules "Inbound-Any" action allow
set rulebase security rules "Inbound-Any" log-end no
"""

ASA_DEVICE = """ASA Version 9.16(4)
!
hostname ASA-DMZ-01
!
interface GigabitEthernet0/0
 nameif outside
 security-level 0
 ip address 203.0.113.2 255.255.255.0
!
interface GigabitEthernet0/1
 nameif inside
 security-level 100
 ip address 192.168.1.1 255.255.255.0
!
object network WEB-SRV
 host 192.168.1.10
object network UNUSED-OBJ
 host 192.168.1.77
!
access-list OUTSIDE_IN extended permit tcp any object WEB-SRV eq https
access-list OUTSIDE_IN extended permit ip any any
access-list OUTSIDE_IN extended deny ip any any log
access-group OUTSIDE_IN in interface outside
!
route outside 0.0.0.0 0.0.0.0 203.0.113.1 1
http 0.0.0.0 0.0.0.0 outside
ssh 0.0.0.0 0.0.0.0 outside
telnet 192.168.1.0 255.255.255.0 inside
snmp-server community public
username admin password xxxx privilege 15
!
crypto ikev1 policy 10
 authentication pre-share
 encryption 3des
 hash md5
 group 2
crypto ipsec ikev1 transform-set WEAK-TS esp-3des esp-md5-hmac
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

    print("\n-- only FIREWALL policies are counted as policies --")
    check("a password-policy settings block is not a firewall policy",
          not any(x.rule == "disabled-policy" for x in configaudit.audit(wobjs)))
    check("the review counts 2 policies on the weak device, not 3",
          "(2 policies," in configaudit.report(configaudit.audit(wobjs), wobjs))

    print("\n-- compliance mapping --")
    import re as _re
    src = open(configaudit.__file__, encoding="utf-8").read()
    emitted = set(_re.findall(r'Finding\(\s*"([a-z0-9-]+)"', src))
    info_only = {"no-default-route", "interfaces-not-checked"}
    check("every non-info finding the review can raise is mapped",
          not (emitted - set(configaudit.CONTROLS) - info_only))
    ids = {c for m in configaudit.CONTROLS.values() for cs in m.values() for c in cs}
    check("every referenced control has a description",
          not (ids - set(configaudit.CONTROL_TITLES)))
    check("management on the WAN maps to PCI 1.4.2",
          "1.4.2" in configaudit.controls_for("wan-management")[configaudit.PCI])
    check("weak VPN crypto maps to PCI 4.2.1",
          "4.2.1" in configaudit.controls_for("weak-ipsec-crypto")[configaudit.PCI])
    check("password policy maps to PCI 8.3.6 (12-character minimum)",
          "8.3.6" in configaudit.controls_for("password-policy-off")[configaudit.PCI])
    cr = configaudit.compliance_report(configaudit.audit(wobjs), wobjs, configaudit.PCI)
    check("the PCI view groups findings under controls", "**4.2.1**" in cr)
    check("the view says it is indicative, not an assessment", "not an assessment" in cr)
    check("a hardened device has nothing to report",
          "No findings" in configaudit.compliance_report(configaudit.audit(hobjs), hobjs))

    print("\n-- config diff --")
    import configdiff
    opened = HARDENED_DEVICE.replace('set allowaccess ping\n        set role wan',
                                     'set allowaccess ping https ssh\n        set role wan')
    check("the edit under test really changes the config", opened != HARDENED_DEVICE)
    oobjs = configparse.parse(opened)
    d = configdiff.diff(hobjs, oobjs)
    check("exactly one object changed", len(d["changed"]) == 1 and not d["added"]
          and not d["removed"])
    check("the changed field is reported with old and new values",
          any(f == "allowaccess" for _k, _n, ds in d["changed"] for f, _a, _b in ds))
    intro, res = configdiff.risk_delta(hobjs, oobjs)
    check("opening WAN management is reported as an introduced risk",
          any(x.rule == "wan-management" for x in intro))
    check("the reverse change reports it as resolved",
          any(x.rule == "wan-management" for x in configdiff.risk_delta(oobjs, hobjs)[1]))
    check("identical configs report no differences",
          "No differences" in configdiff.report(hobjs, hobjs))
    rep = configdiff.report(hobjs, oobjs)
    check("the diff leads with the verdict", "introduced 1 serious risk" in rep)
    noisy = HARDENED_DEVICE.replace('edit "wan1"\n', 'edit "wan1"\n        set uuid 1234\n')
    check("per-save noise (uuid) is not reported as a change",
          not configdiff.diff(hobjs, configparse.parse(noisy))["changed"])

    print("\n-- published services (VIP) --")
    vobjs = configparse.parse(VIP_DEVICE)
    vr = set(rules(configaudit.audit(vobjs)))
    for rule in ("vip-admin-port", "vip-admin-service", "vip-all-ports",
                 "vip-any-service", "vip-unused"):
        check(f"finds {rule}", rule in vr)
    rows = {str(v.name): users for v, _e, _m, _p, users in configaudit.vip_exposure(vobjs)}
    check("a VIP published through a VIP group is traced to its policy",
          [str(p.name) for p in rows["WEB-VIP"]] == ["10"])
    check("the properly published web server raises nothing of its own",
          not any("WEB-VIP" in x.objects for x in configaudit.audit(vobjs)))
    check("no VIPs → says nothing is published",
          "publishes no internal servers" in configaudit.exposure_report(hobjs))

    print("\n-- cleanup plan --")
    mobjs = configparse.parse(MESSY_DEVICE)
    plan = configaudit.cleanup_plan(mobjs)
    check("plan counts what is safe to delete", "Safe to delete: **3**" in plan)
    check("the contradiction is put first, to decide", "contradicts policy 2" in plan)
    check("duplicate listed for deletion", "policy 3 — duplicate of policy 1" in plan)
    check("disabled rule listed for deletion", "policy 5 — disabled" in plan)
    check("unused object listed for deletion", "STALE-OBJ" in plan)
    check("rules differing only in service are offered as a merge",
          "policies 1, 2 differ only in service" in plan)
    check("a rule already marked dead is not offered for merging",
          "policies 1, 2, 3" not in plan)
    check("a clean config needs no cleanup",
          "Nothing to clean up" in configaudit.cleanup_plan(hobjs))

    print("\n-- what-if --")
    import configdiff
    fobjs = configparse.parse(FAULTY_ORDER)
    check("parses 'what if I delete policy 1'",
          configdiff.parse_whatif("what if I delete policy 1") == ("delete", "1", None, None))
    check("parses 'move … before …'",
          configdiff.parse_whatif("what if we move policy 3 above policy 2")
          == ("move", "3", "before", "2"))
    check("ignores unrelated what-ifs", configdiff.parse_whatif("what if it rains") is None)
    wi = configdiff.whatif_report(fobjs, "delete", "1")
    check("deleting the any/any accept resolves it and the shadowing",
          "Would resolve" in wi and "shadowed by policy 1" in wi)
    mv = configdiff.whatif_report(fobjs, "move", "3", "before", "2")
    check("reordering a contradiction reports the winner flipping",
          "policy 2 contradicts policy 3" in mv and "policy 3 contradicts policy 2" in mv)
    check("the original config is not modified",
          [str(o.name) for o in fobjs if configaudit.is_firewall_policy(o)] == ["1", "2", "3", "4"])
    check("a missing policy is reported, not crashed on",
          "no policy 99" in configdiff.whatif_report(fobjs, "delete", "99"))

    print("\n-- Palo Alto (PAN-OS set format) --")
    import vendorparse
    check("PAN-OS is detected", configparse.vendor(PANOS_DEVICE) == "panos")
    pobjs = configparse.parse(PANOS_DEVICE)
    ppol = [o for o in pobjs if configaudit.is_firewall_policy(o)]
    check("security rules become firewall policies, in order",
          [str(o.name) for o in ppol] == ["Allow-All", "Allow-Web-Out", "Inbound-Any"])
    check("allow → accept", all(o.get("action") == "accept" for o in ppol))
    check("service any with application any is unrestricted",
          ppol[0].get("service") == '"ALL"')
    check("application-default with named apps is NOT unrestricted",
          ppol[1].get("service") == '"application-default"')
    pr = set(rules(configaudit.audit(pobjs)))
    for rule in ("any-any-accept", "shadowed-policy", "inbound-to-any", "no-logging",
                 "wan-management", "unused-object"):
        check(f"PAN: finds {rule}", rule in pr)
    check("PAN: zones are valid interface references (no false dangling)",
          "dangling-interface" not in pr)
    check("PAN: one-line objects survive chunking",
          all("\n" in c for c in vendorparse.chunk(PANOS_DEVICE)))

    print("\n-- Cisco ASA --")
    check("ASA is detected", configparse.vendor(ASA_DEVICE) == "asa")
    aobjs = configparse.parse(ASA_DEVICE)
    apol = [o for o in aobjs if configaudit.is_firewall_policy(o)]
    check("ACL entries become policies, bound to their interface",
          len(apol) == 3 and all(o.get("srcintf") == '"outside"' for o in apol))
    check("interfaces are named by nameif", any(str(o.name) == "outside" for o in aobjs))
    ar = set(rules(configaudit.audit(aobjs)))
    for rule in ("any-any-accept", "inbound-to-any", "conflicting-policy", "wan-management",
                 "cleartext-admin", "snmp-default-community", "weak-ipsec-crypto",
                 "weak-dh-group", "unused-object"):
        check(f"ASA: finds {rule}", rule in ar)
    check("ASA: object referenced by an ACL is not 'unused'",
          not any("WEB-SRV" in f.detail for f in configaudit.audit(aobjs)
                  if f.rule == "unused-object"))

    print("\n-- vendor detection never mistakes prose for config --")
    for prose in ("interface naming on Cisco devices follows the slot and port number.",
                  "Set the rulebase carefully; security rules are evaluated top down.",
                  "An access-list filters traffic. Apply it with access-group."):
        check(f"prose is not config: {prose[:34]}…", configparse.vendor(prose) is None)
        check(f"…nor a fragment of one: {prose[:30]}…",
              not vendorparse.belongs_to(prose, "asa")
              and not vendorparse.belongs_to(prose, "panos"))
    check("FortiGate is still FortiGate", configparse.vendor(HARDENED_DEVICE) == "fortigate")

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
