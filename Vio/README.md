# Vio — Personal AI Agent

> Mazin's personal AI agent: **Network & Security Lead + Family Assistant**.
> Deployed on a Hostinger VPS, designed to learn continuously and grow stronger.

---

## What Vio Is

Vio is a long-running AI agent built around three pillars:

1. **Domain expert** — Fortinet (FCSS), Cisco, firewalls, routing, NAC, wireless,
   SOC operations, incident response, vulnerability management.
2. **Family assistant** — schedules, reminders, school, bills, language help,
   travel planning, health follow-ups, document translation (AR ↔ EN).
3. **Learning loop** — every conversation feeds back into a memory store so Vio
   gets smarter about *you* and your home network over time.

## Files in this package

| File | Purpose |
|------|---------|
| `SYSTEM_PROMPT.md` | The master prompt that defines Vio's identity, tone, and rules. Paste this into your agent's system prompt slot. |
| `MEMORY_ARCHITECTURE.md` | How to give Vio persistent memory (short-term, long-term, episodic). Concrete schema + storage options. |
| `SKILLS_ROADMAP.md` | The 12-week plan to make Vio genuinely stronger — what to teach it and how to test it. |
| `NETWORK_SECURITY_PLAYBOOK.md` | Vio's core domain knowledge: troubleshooting trees, command cheat sheets, threat triage flow. |
| `FAMILY_ASSISTANT.md` | Privacy-first patterns for using Vio with family data. |
| `HOSTINGER_DEPLOYMENT.md` | How to deploy and harden Vio on a Hostinger VPS. |
| `TOOLS_INTEGRATION.md` | The toolset Vio needs (search, RAG, code exec, FortiGate API, calendar, email). |
| `EVALS.md` | Reproducible tests so you know Vio is *actually* getting better, not just sounding better. |

## Quick-start order

1. Read `SYSTEM_PROMPT.md` and adapt the personal section (your name, family
   names you want Vio to remember, network details).
2. Stand up the memory store from `MEMORY_ARCHITECTURE.md` (SQLite + a vector DB
   is enough to start).
3. Follow `HOSTINGER_DEPLOYMENT.md` to put Vio behind HTTPS with auth.
4. Wire the tools from `TOOLS_INTEGRATION.md`.
5. Run the Week 1 items in `SKILLS_ROADMAP.md` and grade Vio against `EVALS.md`.

---

*Strong agents are not magic. They are: a clear identity + reliable memory +
the right tools + an evaluation loop that catches regressions.*
