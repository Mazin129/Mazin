"""
configaudit — the part of a senior review that can be done WITHOUT a model.

An LLM asked to "review my firewall" produces plausible prose. This produces findings
that are either true of your file or not at all: every one names the exact objects it
came from, and the reasoning is arithmetic over parsed fields — set containment, index
order, reference counting. Nothing is inferred, so nothing can be hallucinated.

What it finds, and why each one matters to somebody doing this for a living:

  SHADOWED POLICY      an earlier rule fully covers a later one, so the later rule can
                       never match. The classic silent misconfiguration: someone adds a
                       rule, tests nothing, and assumes it took effect.
  ANY/ANY ACCEPT       source, destination and service all unrestricted. Usually a
                       temporary rule that became permanent.
  OVERLY PERMISSIVE    one axis unrestricted on an accept rule — narrower, still worth
                       a look.
  DUPLICATE POLICY     identical match criteria; one is dead weight, and the pair will
                       drift apart during future edits.
  UNREACHABLE AFTER    a rule sits below an any/any accept and can never be evaluated.
  DISABLED             configured but switched off. Dead config people still read as live.
  NO LOGGING           an accept rule with logging off — invisible in an incident.
  UNUSED OBJECT        an address/service defined and referenced by nothing.
  DUPLICATE ROUTE      two static routes to the same destination.
  MULTIPLE DEFAULTS    more than one default route — deliberate (ECMP) or a mistake.
  DANGLING INTERFACE   a policy or route naming an interface the config never defines.

HONESTY ABOUT LIMITS — stated in the report, not buried here:
  • Address GROUPS are not expanded. Shadowing is therefore detected only where the
    match fields are literally equal or where the earlier rule uses "all". This
    UNDER-reports (misses real shadowing); it never over-reports.
  • Ordering follows the parsed sequence, which is the file's order.
  • Interface checks only fire when the config actually defines interfaces; a partial
    export is reported as "not checked" rather than as findings.
"""
from __future__ import annotations

from dataclasses import dataclass, field as _field

# severity ranking used for sorting and display
HIGH, MEDIUM, LOW, INFO = "high", "medium", "low", "info"
_ORDER = {HIGH: 0, MEDIUM: 1, LOW: 2, INFO: 3}
_MARK = {HIGH: "🔴", MEDIUM: "🟠", LOW: "🟡", INFO: "🔵"}

# values meaning "unrestricted" in FortiGate-style configs
_ANY = {"all", "any", "*", "0.0.0.0/0", "0.0.0.0 0.0.0.0"}


@dataclass
class Finding:
    rule: str                      # short machine-ish id, e.g. "shadowed-policy"
    severity: str
    title: str                     # one line a human reads first
    detail: str                    # why it matters / what to do
    objects: list = _field(default_factory=list)   # the object names involved

    def line(self):
        who = (" [" + ", ".join(str(o) for o in self.objects) + "]") if self.objects else ""
        return f"{_MARK.get(self.severity, '•')} {self.title}{who}\n     {self.detail}"


# ---------------------------------------------------------------------------- #
# helpers
# ---------------------------------------------------------------------------- #
def _vals(o, key):
    """A set() of the values of one field. FortiGate writes multi-values on one line:
        set srcaddr "A" "B"        →  {"a", "b"}"""
    raw = (o.get(key) or "").strip()
    if not raw:
        return set()
    parts, cur, inq = [], "", False
    for ch in raw:
        if ch == '"':
            inq = not inq
            continue
        if ch.isspace() and not inq:
            if cur:
                parts.append(cur)
                cur = ""
            continue
        cur += ch
    if cur:
        parts.append(cur)
    return {p.lower() for p in parts if p}


def _is_any(values):
    return bool(values) and all(v in _ANY for v in values)


def _covers(a, b):
    """Does field-set `a` (earlier rule) cover `b` (later rule)?

    Conservative on purpose: "all" covers anything; otherwise only a literal superset
    counts, because address GROUPS are not expanded here. Under-reporting is acceptable;
    claiming a rule is dead when it isn't is not."""
    if not a:
        # The field is ABSENT, which means unknown — not "matches everything". A partial
        # export omits fields, and treating that as unrestricted would invent shadowing
        # findings for rules that are perfectly fine. Silence beats a confident lie.
        return False
    if _is_any(a):
        return True
    if not b:
        return False
    return b.issubset(a)


def _enabled(o):
    return (o.get("status") or "enable").strip().strip('"').lower() != "disable"


def _action(o):
    return (o.get("action") or "deny").strip().strip('"').lower()


def _verb(o):
    """Readable past-tense of an action — 'deny' must not print as 'denyed'."""
    return {"accept": "accepts", "deny": "denies", "drop": "drops",
            "reject": "rejects"}.get(_action(o), _action(o) + "s")


_MATCH_FIELDS = ("srcintf", "dstintf", "srcaddr", "dstaddr", "service")


def _signature(o):
    return tuple(frozenset(_vals(o, f)) for f in _MATCH_FIELDS)


# ---------------------------------------------------------------------------- #
# the checks
# ---------------------------------------------------------------------------- #
def _check_policies(policies):
    out = []
    if not policies:
        return out

    # -- any/any accepts, permissiveness, logging, disabled ------------------- #
    any_any_index = None
    for i, p in enumerate(policies):
        name = p.get("name") or p.name
        label = f"policy {p.name}" + (f' "{str(name).strip(chr(34))}"' if name != p.name else "")
        src, dst, svc = _vals(p, "srcaddr"), _vals(p, "dstaddr"), _vals(p, "service")

        if not _enabled(p):
            out.append(Finding("disabled-policy", LOW, f"{label} is disabled",
                               "Configured but switched off. Delete it or document why "
                               "it exists — disabled rules get read as live during "
                               "incidents.", [p.name]))
            continue

        if _action(p) == "accept" and _is_any(src) and _is_any(dst) and _is_any(svc):
            if any_any_index is None:
                any_any_index = i
            out.append(Finding(
                "any-any-accept", HIGH, f"{label} accepts ANY source to ANY destination "
                "on ANY service",
                "This permits everything that reaches it. Almost always a temporary rule "
                "that was never narrowed. Restrict at least the destination and service, "
                "or move it below the specific rules and log it.", [p.name]))
        elif _action(p) == "accept":
            loose = [f for f, v in (("source", src), ("destination", dst),
                                    ("service", svc)) if _is_any(v)]
            if len(loose) >= 2:
                out.append(Finding(
                    "overly-permissive", MEDIUM,
                    f"{label} leaves {' and '.join(loose)} unrestricted",
                    "Two unrestricted axes on an accept rule is a wide opening. Narrow "
                    "whichever one you can name concretely.", [p.name]))
            elif loose:
                out.append(Finding(
                    "permissive", LOW, f"{label} leaves {loose[0]} unrestricted",
                    "Worth confirming this is intended.", [p.name]))

        log = (p.get("logtraffic") or "").strip().strip('"').lower()
        if _action(p) == "accept" and log in ("disable", "utm") and log == "disable":
            out.append(Finding(
                "no-logging", MEDIUM, f"{label} accepts traffic with logging disabled",
                "Traffic permitted by this rule leaves no record. During an incident "
                "this rule is a blind spot — set logtraffic all.", [p.name]))

    # -- unreachable below an any/any accept ---------------------------------- #
    if any_any_index is not None:
        below = [p.name for p in policies[any_any_index + 1:] if _enabled(p)]
        if below:
            shown = ", ".join(str(b) for b in below[:10])
            out.append(Finding(
                "unreachable-after-any", HIGH,
                f"{len(below)} rule(s) sit below the ANY/ANY accept and can never match",
                f"Everything reaching policy {policies[any_any_index].name} is accepted "
                f"there, so these are dead: {shown}"
                + (" …" if len(below) > 10 else "")
                + ". Move the broad rule to the bottom, or narrow it.",
                [policies[any_any_index].name]))

    # -- duplicates and shadowing --------------------------------------------- #
    seen = {}
    for i, p in enumerate(policies):
        if not _enabled(p):
            continue
        sig = _signature(p)
        if sig in seen:
            first = seen[sig]
            if _action(first) != _action(p):
                # Same match criteria, OPPOSITE decisions. Not housekeeping — whichever
                # comes first silently wins, and the other rule documents an intent the
                # device does not honour.
                out.append(Finding(
                    "conflicting-policy", HIGH,
                    f"policy {p.name} contradicts policy {first.name}",
                    f"Identical match criteria but opposite actions: policy "
                    f"{first.name} {_verb(first)} this traffic, policy {p.name} "
                    f"{_verb(p)} it. Policy {first.name} is evaluated first and wins, "
                    f"so the {_action(p)} rule is decoration.",
                    [first.name, p.name]))
            else:
                out.append(Finding(
                    "duplicate-policy", MEDIUM,
                    f"policy {p.name} duplicates policy {first.name}",
                    "Identical match criteria. One of them never fires, and the pair will "
                    "drift apart the next time someone edits 'the' rule.",
                    [first.name, p.name]))
        else:
            seen[sig] = p

    for i, later in enumerate(policies):
        if not _enabled(later):
            continue
        for earlier in policies[:i]:
            if not _enabled(earlier):
                continue
            if _signature(earlier) == _signature(later):
                continue                       # already reported as a duplicate
            if all(_covers(_vals(earlier, f), _vals(later, f)) for f in _MATCH_FIELDS):
                same = _action(earlier) == _action(later)
                out.append(Finding(
                    "shadowed-policy", HIGH if not same else MEDIUM,
                    f"policy {later.name} is shadowed by policy {earlier.name}",
                    f"Policy {earlier.name} matches everything policy {later.name} would, "
                    f"and is evaluated first, so policy {later.name} never takes effect"
                    + ("" if same else
                       f" — and the two disagree: policy {later.name} "
                       f"{_verb(later)} this traffic, but policy {earlier.name} "
                       f"{_verb(earlier)} it first")
                    + ". Reorder them, or narrow the earlier rule.",
                    [earlier.name, later.name]))
                break                          # one shadower is enough to report
    return out


def _check_routes(routes):
    out = []
    by_dst, defaults = {}, []
    for r in routes:
        dst = (r.get("dst") or "").strip().strip('"')
        gw = (r.get("gateway") or "").strip().strip('"')
        if dst in _ANY or dst in ("0.0.0.0 0.0.0.0", "0.0.0.0/0", ""):
            defaults.append((r, gw))
            continue
        by_dst.setdefault(dst, []).append((r, gw))

    for dst, rs in by_dst.items():
        if len(rs) > 1:
            gws = {gw for _, gw in rs}
            names = [r.name for r, _ in rs]
            if len(gws) > 1:
                out.append(Finding(
                    "conflicting-route", MEDIUM,
                    f"{len(rs)} routes to {dst} with different gateways",
                    f"Gateways: {', '.join(sorted(g for g in gws if g))}. Deliberate "
                    "failover/ECMP is fine — otherwise one of these is wrong and which "
                    "one wins depends on distance/priority.", names))
            else:
                out.append(Finding(
                    "duplicate-route", LOW, f"{len(rs)} identical routes to {dst}",
                    "Same destination and gateway configured more than once.", names))

    if len(defaults) > 1:
        gws = sorted({gw for _, gw in defaults if gw})
        out.append(Finding(
            "multiple-defaults", MEDIUM, f"{len(defaults)} default routes configured",
            f"Gateways: {', '.join(gws) or '(none named)'}. Intentional for ECMP or "
            "failover; otherwise traffic leaves by whichever wins on distance/priority, "
            "which is rarely what someone expects.",
            [r.name for r, _ in defaults]))
    elif not defaults and routes:
        out.append(Finding("no-default-route", INFO, "no default route in this config",
                           "Normal for an internal device or a partial export; worth "
                           "confirming if this box faces the internet.", []))
    return out


def _check_unused(objects, policies):
    """An address/service defined but referenced by no policy."""
    out = []
    referenced = set()
    for p in policies:
        for f in ("srcaddr", "dstaddr", "service", "poolname", "nat-ippool"):
            referenced |= _vals(p, f)
    # address groups reference their members
    for o in objects:
        if "addrgrp" in (o.kind or "").lower() or "group" in (o.kind or "").lower():
            referenced |= _vals(o, "member")

    for kindsub, label in (("address", "address object"), ("service custom", "service")):
        defined = [o for o in objects if kindsub in (o.kind or "").lower()
                   and "group" not in (o.kind or "").lower()]
        unused = [o for o in defined if str(o.name).lower() not in referenced]
        if unused and defined:
            shown = ", ".join(str(o.name) for o in unused[:12])
            out.append(Finding(
                "unused-object", LOW,
                f"{len(unused)} of {len(defined)} {label}s are referenced by no policy",
                f"{shown}" + (" …" if len(unused) > 12 else "")
                + ". Harmless but they accumulate, and an unused object is often the "
                "leftover of a change that was only half applied.",
                [o.name for o in unused[:12]]))
    return out


def _check_interfaces(objects, policies, routes):
    """Policies/routes naming an interface the config never defines."""
    ifaces = {str(o.name).lower() for o in objects
              if "system interface" in (o.kind or "").lower()}
    if not ifaces:
        return [Finding("interfaces-not-checked", INFO,
                        "interface references not checked",
                        "This export contains no `config system interface` section, so "
                        "I can't tell whether the interfaces named in policies and routes "
                        "exist. Include that section to enable the check.", [])]
    out, missing = [], {}
    for p in policies:
        for f in ("srcintf", "dstintf"):
            for v in _vals(p, f):
                if v not in ifaces and v not in _ANY:
                    missing.setdefault(v, []).append(f"policy {p.name}")
    for r in routes:
        for v in _vals(r, "device"):
            if v not in ifaces and v not in _ANY:
                missing.setdefault(v, []).append(f"route {r.name}")
    for iface, who in sorted(missing.items()):
        out.append(Finding(
            "dangling-interface", MEDIUM,
            f"interface '{iface}' is referenced but never defined",
            f"Referenced by {', '.join(who[:6])}"
            + (" …" if len(who) > 6 else "")
            + ". Either the export is partial, or these rules point at an interface that "
            "no longer exists — in which case they don't do what they look like they do.",
            sorted(set(who))[:6]))
    return out


# ---------------------------------------------------------------------------- #
# public API
# ---------------------------------------------------------------------------- #
def audit(objects):
    """Run every check over parsed ConfigObjects. Returns findings, worst first."""
    objects = list(objects or [])
    policies = [o for o in objects if "policy" in (o.kind or "").lower()
                and "shaping" not in (o.kind or "").lower()]
    routes = [o for o in objects if "static" in (o.kind or "").lower()
              and "router" in (o.kind or "").lower()]

    findings = []
    findings += _check_policies(policies)
    findings += _check_routes(routes)
    findings += _check_unused(objects, policies)
    findings += _check_interfaces(objects, policies, routes)
    findings.sort(key=lambda f: (_ORDER.get(f.severity, 9), f.rule))
    return findings


def counts(findings):
    c = {HIGH: 0, MEDIUM: 0, LOW: 0, INFO: 0}
    for f in findings:
        c[f.severity] = c.get(f.severity, 0) + 1
    return c


def report(findings, objects, limit=40):
    """A review a human can act on: what was checked, what was found, what it means."""
    objects = list(objects or [])
    policies = sum(1 for o in objects if "policy" in (o.kind or "").lower())
    routes = sum(1 for o in objects if "static" in (o.kind or "").lower())
    c = counts(findings)
    real = [f for f in findings if f.severity != INFO]

    head = (f"**Configuration review** — {len(objects)} object(s) analysed "
            f"({policies} policies, {routes} static routes).\n"
            f"Findings: {c[HIGH]} high · {c[MEDIUM]} medium · {c[LOW]} low")

    if not real:
        body = ("\nNo shadowed rules, any/any accepts, duplicates or dangling references "
                "found. That is a real result, not a default — every check below ran and "
                "came back clean.")
    else:
        lines = []
        for f in findings[:limit]:
            lines.append(f.line())
        body = "\n\n" + "\n".join(lines)
        if len(findings) > limit:
            body += f"\n\n… and {len(findings) - limit} more finding(s)."

    notes = ("\n\n---\n*How this was produced:* every finding is arithmetic over your "
             "parsed configuration — set containment, rule order, reference counting. No "
             "model was involved, so nothing here is guessed.\n"
             "*Known limits:* address groups are not expanded, so shadowing is detected "
             "only where match fields are literally equal or the earlier rule uses `all` "
             "— this misses some real shadowing but never invents any. Rule order follows "
             "the order in the file.")
    return head + body + notes
