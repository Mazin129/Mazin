# Vio — 12-Week Skills Roadmap

The principle: an agent does not get stronger by being told it is strong.
It gets stronger by **(a)** ingesting domain content, **(b)** practicing on
realistic tasks, and **(c)** being graded by an eval suite that catches
regressions.

Each week below has: **Ingest → Practice → Grade**.

---

## Phase 1 — Foundation (Weeks 1–3)

### Week 1 — Identity & Memory Hardening
- **Ingest**: feed Vio the contents of this repo (`README.md`,
  `NSE6-LAN-Edge/`, `NSE7-Enterprise-FW/`, `Lab/`, `Resources/`) into the RAG
  store. Tag each chunk with `study,fortinet`.
- **Practice**: ask Vio 30 questions across the material; verify every answer
  cites a file path.
- **Grade**: from `EVALS.md` — "Recall accuracy" must be ≥ 90% on questions
  whose answer is literally in the corpus.

### Week 2 — Network Fundamentals Recall
- **Ingest**: Cisco/Juniper neutral basics — OSI, TCP/IP, subnetting, BGP
  attributes, OSPF LSAs, STP, VLANs, 802.1X. Use vendor docs (free).
- **Practice**: subnetting drills (20 random /24–/30 splits), BGP best-path
  selection (15 scenarios), OSPF LSA type identification (10 scenarios).
- **Grade**: 100% on subnetting, ≥ 85% on BGP/OSPF.

### Week 3 — Fortinet Deep
- **Ingest**: the Practice Exam Q&A files in this repo + Fortinet CLI
  reference (FortiOS 7.4 admin guide).
- **Practice**: 50 of the 270 practice questions, *closed-book*. Vio must
  produce the answer **and** the CLI command that proves it.
- **Grade**: ≥ 80% correct, with no fabricated CLI syntax.

## Phase 2 — Operational (Weeks 4–7)

### Week 4 — Troubleshooting Trees
- **Ingest**: `NETWORK_SECURITY_PLAYBOOK.md` (this repo).
- **Practice**: 10 synthetic incidents ("VPN tunnel up but no traffic", "AP
  associates but no DHCP", "BGP session flaps every 3 minutes"). Vio must walk
  the tree to root cause.
- **Grade**: time-to-RCA under 6 turns; correct first hypothesis ≥ 50%.

### Week 5 — Security Operations
- **Ingest**: MITRE ATT&CK enterprise matrix, CIS Controls v8, NIST CSF 2.0.
- **Practice**: triage 15 fake alerts (failed logins, beaconing, lateral
  movement). Vio must map each to ATT&CK technique and recommend next step.
- **Grade**: correct technique mapping ≥ 80%.

### Week 6 — Home Lab Automation
- **Ingest**: FortiGate REST API + FortiSwitch CLI scripting examples.
- **Practice**: have Vio author Python scripts that (a) pull config backups,
  (b) diff today vs. yesterday, (c) alert on policy changes outside business
  hours.
- **Grade**: scripts run in your lab without manual edits.

### Week 7 — Family Logistics
- **Ingest**: family-specific facts (school timetables, doctor appointments,
  recurring bills) — stored as `facts` tagged `family`.
- **Practice**: end-of-day briefing every evening for 7 days.
- **Grade**: zero hallucinated names/dates; the principal would have missed
  ≥ 2 things without Vio.

## Phase 3 — Force Multiplier (Weeks 8–10)

### Week 8 — Long-form Authoring
- Vio drafts: incident report, change request, exec summary, ar↔en bilingual
  network diagram captions.
- **Grade**: principal edits < 25% of the draft.

### Week 9 — Proactive Mode
- Vio runs on a 4×/day cron: pulls FortiAnalyzer top events, RSS of relevant
  CVEs, calendar of the day; posts a Telegram/Signal brief.
- **Grade**: principal opens the brief and acts on something at least 3 days
  out of 7.

### Week 10 — Red-team Drills (lab only)
- In a scoped lab, Vio designs and runs benign scenarios: misconfigured
  firewall policy, weak Wi-Fi PSK, unpatched FortiClient — and produces the
  detection rule that would have caught it.
- **Grade**: every scenario has both a "how it worked" and a "how to detect"
  artifact.

## Phase 4 — Compounding (Weeks 11–12)

### Week 11 — Self-eval
- Vio reads its own weekly reports for the prior 10 weeks, identifies its
  most common failure mode, and proposes a system prompt edit + an eval
  update.
- **Grade**: principal accepts at least one change.

### Week 12 — Cert Push
- Final 100-question simulation each for NSE6 and NSE7, closed-book, timed.
- **Grade**: ≥ 80% on both. If not, loop back to Phase 1 weak areas.

---

## Daily routine (after Week 2)

```
07:30  Morning brief (calendar + overnight FortiAnalyzer events + 1 cert Q)
12:30  One Fortinet practice question + one ATT&CK technique flashcard
21:00  Day recap: facts learned, followups due tomorrow, anything dropped
```

## What *not* to do

- ❌ Don't measure progress by Vio's confidence — confident wrong is worse
  than uncertain right.
- ❌ Don't skip the weekly self-eval. The compound interest lives there.
- ❌ Don't pile on tools before the memory is solid. A tool-rich agent with
  goldfish memory is still a goldfish.

## Skills to grow in *yourself* alongside Vio

| Skill | Why it makes Vio stronger |
|-------|---------------------------|
| Prompt engineering | You'll edit the system prompt weekly. Learn it. |
| Basic Python | You'll wire tools and write the memory classifier. |
| `jq` + SQL | You'll inspect Vio's memory and clean noise. |
| Cron / systemd timers | Proactive Vio needs scheduling. |
| FortiOS API + ansible-galaxy `fortinet.fortios` | Lets Vio operate, not just talk. |
| Threat modeling (STRIDE) | Teaches you what to ask Vio for. |
