"""Tests for the structured config parser."""
import configparse as cp

SAMPLE = """
config firewall address
    edit "webserver"
        set subnet 10.0.0.5 255.255.255.255
        set type ipmask
    next
    edit "lan"
        set subnet 192.168.1.0 255.255.255.0
    next
end
config firewall policy
    edit 1
        set name "allow-web"
        set srcintf "lan"
        set dstintf "wan1"
        set srcaddr "lan"
        set dstaddr "all"
        set service "HTTPS"
        set action accept
        set nat enable
        set status enable
    next
    edit 2
        set name "deny-all"
        set srcintf "lan"
        set dstintf "wan1"
        set action deny
    next
end
"""


def _ok(label, cond):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}")
    assert cond, label


def main():
    print("=" * 56 + "\n  CONFIG PARSER TESTS")
    objs = cp.parse(SAMPLE)
    _ok("parses all 4 objects", len(objs) == 4)
    pol = cp.of_kind(objs, "policy")
    _ok("2 policies", len(pol) == 2)
    addr = cp.of_kind(objs, "address")
    _ok("2 addresses", len(addr) == 2)

    p1 = pol[0]
    _ok("policy name captured", p1.get("name") == '"allow-web"')
    _ok("policy dstintf captured", p1.get("dstintf") == '"wan1"')
    _ok("nat enable captured", p1.get("nat") == "enable")

    nat_on = cp.where(pol, nat="enable")
    _ok("filter nat=enable → 1", len(nat_on) == 1)
    accept = cp.where(pol, action="accept")
    _ok("filter action=accept → 1", len(accept) == 1)

    _ok("summary is structured one-liner",
        "firewall policy 1" in cp.summary(p1) and "action=accept" in cp.summary(p1))

    _ok("parse_many across docs",
        len(cp.parse_many([SAMPLE, "not config text"])) == 4)
    _ok("non-config → []", cp.parse("just some prose here") == [])
    _ok("looks_like_config", cp.looks_like_config(SAMPLE) and not cp.looks_like_config("hi"))

    # nested sub-tables (`config rules` inside a profile) are rows OF their owner
    nested = cp.parse(NESTED)
    rows = [o for o in nested if o.parent]
    _ok("nested rows record their parent",
        len(rows) == 2 and all(o.parent == "waf profile web-prof" for o in rows))
    _ok("nested rows get a qualified kind",
        all(o.kind == "waf profile > rules" for o in rows))
    _ok("nested row names carry the owner", {o.name for o in rows} ==
        {"web-prof/rule1", "web-prof/rule2"})
    prof = [o for o in nested if o.kind == "waf profile"]
    _ok("settings after a nested block land on the owner",
        len(prof) == 1 and prof[0].get("comment") == '"after rules"')
    _ok("no bogus nameless objects", all(o.name for o in nested))
    _ok("no top-level 'rules' objects", not [o for o in nested if o.kind == "rules"])

    print("\nALL PASS")


NESTED = """config waf profile
    edit "web-prof"
        set extended-log enable
        config rules
            edit "rule1"
                set action block
            next
            edit "rule2"
                set action allow
            next
        end
        set comment "after rules"
    next
end
"""


if __name__ == "__main__":
    main()
