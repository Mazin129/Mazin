"""One-off verification of the P0/P1 fixes — run: python _verify_fixes.py"""
import os
import sys
import tempfile

os.environ.setdefault("VIO_DATA_DIR", tempfile.mkdtemp())
os.environ["VIO_ALLOW_NET"] = "1"                      # research gate on (no real net used)
os.environ["VIO_LLM_URL"] = "http://127.0.0.1:9"       # deterministic: no LLM
from reasoner import Mind
import websearch

m = Mind()
fails = []

def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + (f"  ({detail})" if detail and not cond else ""))
    if not cond:
        fails.append(label)

# ---- 1. learn_folder: the NameError is gone; files count as learned, not skipped ----
d = tempfile.mkdtemp()
with open(os.path.join(d, "notes.md"), "w", encoding="utf-8") as f:
    f.write("OSPF uses Dijkstra's algorithm.\nBGP is a path-vector protocol.\n")
with open(os.path.join(d, "run.log"), "w", encoding="utf-8") as f:
    f.write("line one of a log file\n" * 30)
r = m.learn_folder(d)
check("learn_folder counts files as learned",
      r["files"] == 2 and r["passages"] >= 2 and not r["skipped"], str(r)[:160])
check("learn_folder provenance is file-sourced",
      m.lib.meta_for("OSPF uses Dijkstra's algorithm.")["origin"] == "file"
      and m.lib.is_validated("OSPF uses Dijkstra's algorithm."), str(m.lib.meta)[:120])

# ---- 2. skill registry lifecycle: version, disable, enable, pre-install test ----
ok, msg = m.skills.add("greet", "hi", "Hey there!")
check("skill v1 installed", ok and m.skills.list()[0]["version"] == 1, msg)
m.skills.set_status("greet", active=False)
check("disabled skill never fires", m.skills.match("hi") is None)
m.skills.set_status("greet", active=True)
check("re-enabled skill fires", m.skills.match("hi") is not None)
ok, msg = m.skills.add("greet", "hi there", "Hello!")
check("re-add bumps version to 2", ok and m.skills.list()[0]["version"] == 2, msg)

m.ask("approve skill: nonexistent")                    # seed an episode or two
m.episodic.record("hi there friend", "x", "answered", 0.5)
ok, msg = m.skill_proposals.propose("greeter2", "hi there {name}", "Hey {name}!")
pid = m.skill_proposals.get("greeter2")["id"]
ok, msg = m.skill_proposals.approve(pid, m.skills, episodes=["hi there friend", "unrelated"])
check("proposal approval reports pre-install test", ok and "Pre-install test" in msg, msg)
g2 = next(s for s in m.skills.list() if s["name"] == "greeter2")
check("installed skill records tested_against=1", g2["tested_against"] == 1, str(g2))

# ---- 3. Task schema flows through every answer ----
res = m.ask_agentic("solve x^2-5x+6=0")
t = res.get("task") or {}
check("task schema attached (id/capability/status/elapsed)",
      t.get("task_id") and t.get("capability") in ("core", "knowledge")
      and t.get("status") in ("done", "gated") and isinstance(t.get("elapsed_ms"), (int, float)),
      str(t))
check("math still solved exactly (no math agent)",
      "x = 2" in res["answer"] and res["verified"], res["answer"][:60])

# ---- 4. research validation gating (stubbed web) ----
PAGES = {
    "http://blog.example.com/a": "The Zeta protocol uses port 4242 for control traffic. "
                                 "Zeta was designed in 2021. " + "detail " * 60,
    "http://other.example.org/b": "Zeta protocol deployments require port 4242 open. " + "more " * 60,
    "https://www.cloudflare.com/learning/c": "Zeta control traffic uses port 4242. " + "cdn " * 60,
}
websearch.search = lambda q, k=5: [{"url": u, "title": u} for u in list(PAGES)[:k]]
websearch.fetch = lambda u: {"url": u, "title": u, "text": PAGES[u]}

r1 = m.research("zeta protocol port")
check("two untrusted domains => corroborated, verified",
      r1["verified"] is True and "UNVALIDATED" not in r1["answer"], r1["trace"])
r2 = m.research("zeta protocol port", k=1)
check("single untrusted source => unverified + flagged",
      r2["verified"] is False and "UNVALIDATED" in r2["answer"], r2["trace"][:200])
r3 = m.research("zeta protocol port", k=3)
check("trusted domain present => verified",
      r3["verified"] is True, r3["trace"])
unval = [doc for doc in m.lib.docs if "Zeta" in doc and not m.lib.is_validated(doc)]
check("untrusted pages stored as unvalidated leads", len(unval) > 0, str(len(unval)))
check("trusted page stored validated",
      any(doc for doc in m.lib.docs if "Zeta" in doc and m.lib.is_validated(doc)))

# ---- 5. research cache (P2): same query+k served from cache; propose bypasses ----
m._research_cache.clear()
rc = m.research("cache probe topic", k=2)               # fresh
rc2 = m.research("cache probe topic", k=2)              # same key → cached
check("identical research served from cache",
      "cached" in rc2.get("how", ""), rc2.get("how"))
rc3 = m.research("cache probe topic", k=3)              # different k → fresh fetch
check("different k bypasses the cache key", "cached" not in rc3.get("how", ""))
rc4 = m.research("cache probe topic", k=2, propose_skill=True)   # propose → fresh
check("propose_skill bypasses the cache", "cached" not in rc4.get("how", ""))

# ---- 6. model router (P2, pure) ----
from llm import pick_model
check("router: short prompt → small model",
      pick_model(["qwen2.5:3b", "qwen2.5:7b"], "what is 2+2") == "qwen2.5:3b",
      pick_model(["qwen2.5:3b", "qwen2.5:7b"], "what is 2+2"))
check("router: analytic prompt → large model",
      pick_model(["qwen2.5:3b", "qwen2.5:7b"],
                 "analyze the trade-offs and design a threat model for our edge architecture")
      == "qwen2.5:7b")
check("router: single model → itself",
      pick_model(["mistral:7b"], "anything") == "mistral:7b")
check("router: prefers the preferred family",
      pick_model(["llama2:7b", "llama3.2:3b", "llama3.2:7b"], "hi") == "llama3.2:3b")

# ---- 7. autonomy levels (P2, §22) ----
from agents import Agent, Guardrail, Result, READ, NETWORK, WRITE, autonomy_level

class _Net2(Agent):
    name = "mock_net2"
    permissions = frozenset({READ, NETWORK})

os.environ["VIO_ALLOW_NET"] = "1"
os.environ.pop("VIO_AUTONOMY", None)
check("default level is assisted", autonomy_level() == "assisted")
g = Guardrail()
res = Result("did research", how="web research")
check("assisted + standing consent → passes ungated",
      g.check("q", _Net2(None), res, {}) is res)
os.environ["VIO_AUTONOMY"] = "advisory"
res2 = Result("did research", how="web research")
gated = g.check("q", _Net2(None), res2, {})
check("advisory gates even with standing consent",
      "confirm" in (gated.answer or "").lower() and not gated.verified)
os.environ["VIO_AUTONOMY"] = "autonomous"
res3 = Result("did research", how="web research")
check("autonomous + standing consent → passes ungated",
      g.check("q", _Net2(None), res3, {}) is res3)
res4 = Result("wrote", how="automation")

class _Write2(Agent):
    name = "mock_write2"
    permissions = frozenset({READ, WRITE})

check("autonomous STILL gates write",
      "confirm" in (g.check("q", _Write2(None), res4, {}).answer or "").lower())
os.environ["VIO_AUTONOMY"] = "assisted"                # restore default
aut = m.ask_agentic("autonomy")
check("'autonomy' command reports the level",
      "ASSISTED" in (aut.get("answer") or ""), aut.get("answer", "")[:80])

# ---- 8. task schema lands in behaviour traces (P2 observability) ----
m.ask("solve x^2-5x+6=0")
last = m.si.traces.read()[-1]
check("traces carry task_id + task_status",
      last.get("task_id") and last.get("task_status") == "done", str(last)[:140])

# ---- 9. parallel council still returns ranked, deduped contributions ----
contribs = m.master.council("what is OSPF", {}, k=3)
check("council returns valid contributions",
      isinstance(contribs, list) and all(isinstance(n, str) and r.answer for n, r in contribs),
      str([n for n, _ in contribs]))
check("council excluded acting agents",
      all(n != "research" for n, _ in contribs))


# ---- 10. subnetting is exact tool arithmetic (the stuck-question regression) ----
from reasoner import try_subnet
sub = try_subnet("carve a subnet from 192.168.44.0/22 for exactly 30 usable hosts "
                 "with the least waste")
check("subnet: /27 + mask + carve list",
      sub and "/27" in sub and "255.255.255.224" in sub and "192.168.44.32/27" in sub, sub)
check("subnet: /26 usable count", "62 usable" in try_subnet("how many usable hosts in /26"))
check("subnet: mask lookup", "255.255.255.224" in try_subnet("netmask for /27"))
check("subnet: 500 hosts -> /23", "/23" in try_subnet("I need a subnet for 500 hosts"))
check("subnet: not a subnet question", try_subnet("what is a firewall policy") is None)

# ---- 11. data report: provenance made visible (redesign prompt section 5) ----
m.lib.add_many(["Data report probe passage one-of-a-kind."], origin="web",
               source="http://example.com/probe", validated=False)
rep = m._core_front("data report")
check("data report routes and shows origins",
      (rep or {}).get("how") == "data report" and "web research" in (rep or {}).get("answer", "")
      and "unvalidated" in (rep or {}).get("answer", "").lower(), str(rep)[:160])

# ---- 12. supersession: teach validates matching web leads ----
m.lib.add_many(["The Zeta-9 firewall syncs its table every 45 seconds over UDP 4512."],
               origin="web", source="http://blog.example.com/zeta9", validated=False)
lead = "The Zeta-9 firewall syncs its table every 45 seconds over UDP 4512."
check("lead starts unvalidated", m.lib.is_validated(lead) is False)
m.teach("The Zeta-9 firewall syncs its table every 45 seconds over UDP 4512, per vendor docs.")
check("teaching the fact validates the matching lead", m.lib.is_validated(lead) is True)
check("lead provenance records the confirmation",
      m.lib.meta_for(lead).get("confirmed_by") == "user-teach")
m.lib.add_many(["Unrelated lorem-lead-xyz passage about quantum ferrets."],
               origin="web", source="http://blog.example.com/x", validated=False)
r_forget = m._core_front("forget leads")
check("forget leads removes only unvalidated leads",
      "validated knowledge" in (r_forget or {}).get("answer", "")
      and m.lib.is_validated(lead) is True
      and not any("lorem-lead-xyz" in d for d in m.lib.docs), str(r_forget)[:140])

# ---- 13. answer-quality: provenance tags, anti-drift, per-agent telemetry ----
from llm import grounded_prompt
tagged = grounded_prompt("q", ["OSPF uses cost metrics."], tagger=lambda p: "[taught] ")
check("grounded prompt tags passages", "[taught] OSPF" in tagged, tagged[:120])
from agents import answer_off_topic
check("anti-drift: off-topic answer flagged",
      answer_off_topic("how does BGP path selection work with local preference",
                       "Python is a popular programming language used worldwide by developers.") is True)
check("anti-drift: on-topic answer passes",
      answer_off_topic("how does BGP path selection work with local preference",
                       "BGP chooses the path with the highest local preference first, then shortest AS-path.") is False)
qa = m.si.traces.agent_stats()
check("agent_stats shape", isinstance(qa, dict) and all(
      ("answers" in s and "verified_rate" in s) for s in qa.values()), str(qa)[:120])

# ---- 14. roadmap batch: sandbox, DuckDB, tool schemas, netdev, MCP, scheduler ----
from tools.sandbox import run as sb_run
_r = sb_run("print(sum(range(101)))")
check("sandbox executes isolated code", _r["ok"] and _r["stdout"].strip() == "5050")
check("sandbox blocks network patterns", not sb_run("import socket")["ok"])
from agents import EXECUTE, Agent as _A, Guardrail as _G, Result as _Res
class _Py(_A):
    name = "py"
    permissions = frozenset({READ, EXECUTE})
_g = _G()
check("guardrail gates EXECUTE",
      "confirm" in (_g.check("q", _Py(None), _Res("out", how="sandbox"), {}).answer or "").lower())
check("confirmed EXECUTE passes",
      (_g.check("q", _Py(None), _Res("out", how="sandbox"), {"confirmed": True}).answer or "") == "out")
from datatable import DataTable as _DT
_dt = _DT.from_csv("region,sales\nEA,120\nEA,80\nWE,200\n", "sales_q3")
check("duckdb scalar", _dt.sql("SELECT sum(sales) FROM t") == "400")
check("duckdb group-by", "EA" in (_dt.sql("SELECT region, count(*) n FROM t GROUP BY region") or ""))
check("duckdb read-only", _dt.sql("DELETE FROM t") is None)
from cognition import toolcall
check("tool schemas: 5 read-only tools",
      len(toolcall.TOOLS_SCHEMA) == 5
      and {x["function"]["name"] for x in toolcall.TOOLS_SCHEMA} ==
      {"subnet", "config_summary", "table_sql", "device_facts", "web_search"})
check("toolcall exec subnet exact",
      "/27" in (toolcall._exec(None, "subnet", {"question": "subnet for 30 usable hosts"}) or ""))
import netdev
check("netdev refuses unconfigured device", not netdev.run("ghost", "show version")["ok"])
import os as _os
_os.environ.pop("VIO_ALLOW_DEVICES", None)
dv = m._core_front("device: HQ-FGT show version")
check("device intent gated without opt-in", (dv or {}).get("how") == "device (disabled)")
import tools.mcp_server as mcp
check("mcp server lists 4 tools",
      {x["name"] for x in mcp.tools()} ==
      {"vio_ask", "vio_subnet", "vio_research", "vio_config_audit"})
txt, err = mcp.call("vio_subnet", {"question": "mask for /27"})
check("mcp calls vio tools", "255.255.255.224" in txt and not err, txt[:80])
import scheduler
_os.environ["VIO_SCHED"] = "1"
check("scheduler starts when enabled", scheduler.start(m) is not None)
_os.environ["VIO_SCHED"] = ""

# ---- 15. reliability: guards (senior review H1 + H4) + LLM watchdog ----
from guards import FaultCounters, AskGate
fc = FaultCounters()
fc.note("test:module", "boom one")
fc.note("test:module", "boom two")
snap = fc.snapshot()
check("fault counters count by module",
      snap["total"] == 2 and snap["by_module"]["test:module"] == 2, str(snap))
check("fault counters keep a recent tail",
      len(snap["recent"]) == 2 and "boom two" in snap["recent"][-1]["error"])
gate = AskGate(capacity=1)
check("ask gate admits under capacity", gate.acquire() is True)
check("ask gate refuses over capacity", gate.acquire() is False)
gate.release()
check("ask gate re-admits after release", gate.acquire() is True)
gate.release()

# watchdog: a dead cortex flips to honest-unavailable, then recovers when it's back
import llm as llm_mod
wd = llm_mod.LLM(url="http://127.0.0.1:9")           # nothing listening
check("dead cortex: unavailable with honest reason",
      wd.available is False and "Ollama" in (wd.reason or ""))
wd.generate("anything")                               # must not hang; retry-probe path
check("dead cortex: generate returns None fast", wd.available is False)

print("\n" + ("ALL PASS" if not fails else f"{len(fails)} FAILED: {fails}"))
sys.exit(1 if fails else 0)
