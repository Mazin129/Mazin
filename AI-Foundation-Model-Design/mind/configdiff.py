"""
configdiff — what changed between two versions of a configuration, and whether the
change made the device safer or riskier.

A text diff of two FortiGate exports is mostly noise: reordered blocks, UUIDs,
timestamps. This compares PARSED objects instead, keyed by (kind, name), and reports
changes field by field. Then it runs the full configuration review on both versions
and reports the difference in FINDINGS — so a change is judged by its effect
("this edit opened management on wan1"), not just by which lines moved.

Deterministic: no model, same answer every time.
"""
from __future__ import annotations

import configaudit

# fields that change on every save and carry no meaning for a review
_NOISE = {"uuid", "uuid-idx", "_scope", "comments-updated"}


def _key(o):
    return ((o.kind or "").strip().lower(), str(o.name))


def _label(kind, name):
    return f"{kind} {name}".strip() if name else kind


def _fields(o):
    return {k: v for k, v in o.fields.items() if k not in _NOISE}


def diff(old_objects, new_objects):
    """Object- and field-level differences. Returns a dict with lists:
        added    [(kind, name)]
        removed  [(kind, name)]
        changed  [(kind, name, [(field, old_value, new_value)])]
    A value of None means the field was absent on that side."""
    old = {_key(o): o for o in old_objects}
    new = {_key(o): o for o in new_objects}
    added = sorted(k for k in new if k not in old)
    removed = sorted(k for k in old if k not in new)
    changed = []
    for k in sorted(set(old) & set(new)):
        a, b = _fields(old[k]), _fields(new[k])
        deltas = [(f, a.get(f), b.get(f)) for f in sorted(set(a) | set(b))
                  if a.get(f) != b.get(f)]
        if deltas:
            changed.append((k[0], k[1], deltas))
    return {"added": added, "removed": removed, "changed": changed}


def _finding_key(f):
    return (f.rule, f.title)


def risk_delta(old_objects, new_objects):
    """Findings the change INTRODUCED and RESOLVED, worst first."""
    before = {_finding_key(f): f for f in configaudit.audit(old_objects)}
    after = {_finding_key(f): f for f in configaudit.audit(new_objects)}
    order = lambda f: (configaudit._ORDER.get(f.severity, 9), f.rule)   # noqa: E731
    introduced = sorted((after[k] for k in after if k not in before), key=order)
    resolved = sorted((before[k] for k in before if k not in after), key=order)
    return introduced, resolved


# ---------------------------------------------------------------------------- #
# WHAT-IF — the effect of a proposed edit, before anyone makes it
# ---------------------------------------------------------------------------- #
import copy
import re

_WHATIF = re.compile(
    r"\bwhat\s+(?:if|happens\s+if|would\s+happen\s+if)\s+(?:i|we)?\s*"
    r"(delete|remove|disable|enable|move)\s+(?:firewall\s+)?polic(?:y|ies)\s+(\S+)"
    r"(?:\s+(?:to\s+(?:the\s+)?(top|bottom|first|last)|(before|after|above|below)\s+"
    r"(?:policy\s+)?(\S+)))?", re.I)


def parse_whatif(q):
    """('delete'|'disable'|'enable'|'move', policy, where, anchor) or None."""
    m = _WHATIF.search(q or "")
    if not m:
        return None
    op, pid, end, rel, anchor = (g.lower().strip("?.,") if g else g for g in m.groups())
    op = {"remove": "delete"}.get(op, op)
    if op == "move" and not (end or rel):
        return None
    where = {"first": "top", "last": "bottom", "above": "before",
             "below": "after"}.get(end or rel, end or rel)
    return op, pid, where, anchor


def apply_whatif(objects, op, pid, where=None, anchor=None):
    """A modified COPY of the config with the edit applied. Raises KeyError when the
    policy (or the anchor policy) does not exist."""
    objs = copy.deepcopy(list(objects))
    pol_idx = [i for i, o in enumerate(objs) if configaudit.is_firewall_policy(o)]
    target = next((i for i in pol_idx if str(objs[i].name) == pid), None)
    if target is None:
        raise KeyError(f"policy {pid}")
    if op == "delete":
        del objs[target]
    elif op == "disable":
        objs[target].fields["status"] = "disable"
    elif op == "enable":
        objs[target].fields["status"] = "enable"
    elif op == "move":
        moving = objs.pop(target)
        pol_idx = [i for i, o in enumerate(objs) if configaudit.is_firewall_policy(o)]
        if where == "top":
            at = pol_idx[0] if pol_idx else len(objs)
        elif where == "bottom":
            at = pol_idx[-1] + 1 if pol_idx else len(objs)
        else:
            a = next((i for i in pol_idx if str(objs[i].name) == anchor), None)
            if a is None:
                raise KeyError(f"policy {anchor}")
            at = a if where == "before" else a + 1
        objs.insert(at, moving)
    return objs


def whatif_report(objects, op, pid, where=None, anchor=None):
    """Findings the proposed edit would introduce and resolve."""
    try:
        changed = apply_whatif(objects, op, pid, where, anchor)
    except KeyError as e:
        return f"There is no {e.args[0]} in the loaded configuration."
    edit = {"delete": f"deleting policy {pid}", "disable": f"disabling policy {pid}",
            "enable": f"enabling policy {pid}",
            "move": f"moving policy {pid} "
                    + (f"to the {where}" if where in ("top", "bottom")
                       else f"{where} policy {anchor}")}[op]
    introduced, resolved = risk_delta(objects, changed)
    lines = [f"**What-if: {edit}**", ""]
    if not introduced and not resolved:
        lines.append("No change in findings: the review sees nothing better or worse "
                     "after this edit.")
    if introduced:
        lines += [f"**Would introduce {len(introduced)} finding(s):**"]
        lines += [f.line() for f in configaudit.group(introduced)]
    if resolved:
        lines += ([""] if introduced else []) + [f"**Would resolve {len(resolved)} finding(s):**"]
        lines += [f"✔️ {f.title}" for f in resolved]
    lines += ["", "---", "*Applied to a copy of your configuration and reviewed both "
              "ways. Your config is unchanged. This judges the edit by review findings "
              "(shadowing, exposure, hygiene) — it does not trace individual traffic "
              "flows.*"]
    return "\n".join(lines)


def report(old_objects, new_objects, old_name="previous", new_name="current", limit=60):
    """A change review a human can act on: verdict first, then risk, then the edits."""
    d = diff(old_objects, new_objects)
    introduced, resolved = risk_delta(old_objects, new_objects)
    n_changes = len(d["added"]) + len(d["removed"]) + len(d["changed"])
    serious = [f for f in introduced if f.severity in (configaudit.HIGH, configaudit.MEDIUM)]

    if not n_changes:
        verdict = "**No differences.** The two configurations define the same objects."
    elif serious:
        verdict = (f"**⚠️ This change introduced {len(serious)} serious risk(s)** "
                   f"across {n_changes} change(s).")
    elif introduced:
        verdict = (f"**{n_changes} change(s); no serious new risk** — "
                   f"{len(introduced)} minor observation(s).")
    else:
        verdict = f"**{n_changes} change(s); no new risk introduced.**"
    if resolved:
        verdict += f" It also resolved {len(resolved)} earlier finding(s)."

    lines = [f"**Configuration diff** — {old_name} → {new_name}", "", verdict]

    if introduced:
        lines += ["", "**Risks introduced by this change:**"]
        lines += [f.line() for f in configaudit.group(introduced)[:20]]
    if resolved:
        lines += ["", "**Findings resolved by this change:**"]
        lines += [f"✔️ {f.title}" for f in resolved[:20]]

    shown = 0
    if d["added"]:
        lines += ["", f"**Added ({len(d['added'])}):**"]
        for kind, name in d["added"][:limit]:
            lines.append(f"  + {_label(kind, name)}")
            shown += 1
    if d["removed"]:
        lines += ["", f"**Removed ({len(d['removed'])}):**"]
        for kind, name in d["removed"][:limit]:
            lines.append(f"  − {_label(kind, name)}")
            shown += 1
    if d["changed"]:
        lines += ["", f"**Changed ({len(d['changed'])}):**"]
        for kind, name, deltas in d["changed"][:limit]:
            lines.append(f"  ~ {_label(kind, name)}")
            for field, a, b in deltas[:8]:
                if a is None:
                    lines.append(f"      + set {field} {b}")
                elif b is None:
                    lines.append(f"      − set {field} {a}")
                else:
                    lines.append(f"      {field}: {a}  →  {b}")
            if len(deltas) > 8:
                lines.append(f"      … {len(deltas) - 8} more field(s)")
    if n_changes > limit:
        lines.append(f"\n… output limited; {n_changes} change(s) in total.")

    lines += ["", "---", "*Compared parsed objects, not text, so re-ordering and "
              "per-save fields (UUIDs) are ignored. Risks come from the same review as "
              "`audit my config`, run on both versions. No model was involved.*"]
    return "\n".join(lines)
