# 11. Business Audit & Market Valuation — Vio

**Prepared:** 2026-10-06 · **Perspective:** acquirer's due-diligence + owner's sell/don't-sell decision
**Asset reviewed:** the Vio system as it exists today (`mind/` + docs + tests + CI), the
86,941-passage knowledge library, and the trained 12.3M own-model. No revenue, no users,
no brand. One developer.

---

## 1. What an acquirer actually sees (due diligence summary)

**What's genuinely valuable (rare in this product class):**
- **Verification & honesty engineering.** Deterministic-before-LLM routing, an
  evidence-class planner that refuses unanswerable questions, provenance on every fact
  (validated vs unvalidated leads), a critic that abstains instead of bluffing, golden
  gate on self-modification. Most local-assistant projects have *none* of this; for
  regulated buyers (defense, finance, healthcare, government) it is the difference
  between a toy and a deployable system.
- **Domain depth with a real practitioner behind it.** Network/security is the
  specialization, and the owner is a working netsec engineer — the datasets, config
  parsers, audit rules, and troubleshooting agents encode practitioner knowledge.
- **Engineering hygiene.** 26k LOC, 22 test files, CI green, measured performance,
  honest debt register, provenance-joined user feedback. Auditable.
- **Complete vertical slice.** UI + dashboard + API + auth + scheduler + self-learning
  loop + deployment docs. It works, on one machine, today.

**Deal-killers as-is (an acquirer's red-flag list):**
1. **Single-user, single-process, GIL-bound.** Not a platform; a personal tool.
2. **Model ceiling.** Bounded by 2 GB GPU; the reasoning brain is a 3–4B local model.
   The valuable IP (architecture) runs on *any* model, but today's demo quality is
   capped.
3. **No moat that survives copying.** The 86k-passage library is reproducible in days
   (the ingestion pipeline is in the repo). The architecture is replicable by a funded
   team in 3–6 months. There is no proprietary data, no user network, no brand.
4. **Bus of one.** All knowledge in one head; no second maintainer, no support org.
5. **No revenue, no users, no distribution.** The hardest thing in software — go-to-
   market — hasn't started.
6. **License hygiene not yet done** (vendored MIT skill fine; dependency licenses need a
   formal audit before any sale).

---

## 2. Valuation — three approaches, honest numbers

### A. Replacement cost (what the code would cost to rebuild)
Rough build: architecture + implementation + tests + docs + tuning ≈ 500–800 focused
engineer-hours at senior-AI-engineer rates ($60–120/hr). With AI-assisted development
compressing this, market replacement cost today: **$30k–70k**. An acquirer pays this
only to skip time-to-market — and would rather hire the architect.

### B. Market comparables (what similar things sell for)
- Open-source local assistants (GPT4All-class, Open WebUI-class): free; monetize via
  hosted/enterprise tiers. Code alone ≈ $0 — buyers pay for users.
- Solo-built niche AI tools with small user bases: typically sell for **1–3× annual
  revenue** or **$5k–40k** as "working product" acquisitions on micro-acquisition
  marketplaces.
- Enterprise self-hosted knowledge-assistant deployments: **$10k–50k+/yr per customer**,
  but that's a company selling, not code selling.
- **Vio as-is (code + docs + model, no users): fair market value ≈ $8k–25k** to the
  right individual buyer (a netsec professional who wants the artifact and the
  head-start). A company would pay near-zero for the code alone and negotiate only for
  the architect.

### C. Income approach (what it could earn — the number that matters)
Realistic paths, ranked by fit:
1. **Niche prosumer product: "private AI netsec assistant"** ($15–25/mo or $150/yr).
   Target: SOC analysts, network engineers, defense/finance contractors who cannot send
   traffic data to cloud AI. Reach 300–1,500 subscribers in 12–24 months with real
   marketing → **$45k–300k ARR**. At a 3–5× ARR multiple for a working niche SaaS:
   **$150k–1M company value** — but that requires the productization below, plus you
   (the domain expert) continuing as the face.
2. **B2B self-hosted seat for MSPs/SOCs** ($3k–10k/yr per deployment, 10–40 customers):
   **$50k–300k ARR**, higher touch, slower.
3. **Career asset (often the biggest return):** this repository is a portfolio piece
   that demonstrably gets interviews and senior roles — the interview-prep use case it
   already serves is itself.

### Bottom line
| Scenario | Value |
|---|---|
| Sell the code as-is today | **$8k–25k** (realistic), $40k+ only to a motivated strategic individual |
| Value to *you* as a working private tool + career asset | arguably exceeds the sale price |
| Productized niche SaaS (6–12 months of work + marketing) | **$150k–1M** if it reaches ~$100k+ ARR; ~$0–50k if traction never comes |

**My recommendation as your "businessman": do not sell now.** You'd be selling the
recipe before baking the bread. The asset's value is concentrated in (a) the
verification/governance architecture — genuinely ahead of its class — and (b) *you*
being a netsec engineer who is the target user. The cheapest value-unlock is 10 paying
users, not an acquisition.

---

## 3. If you want to raise the value — the honest checklist

**Productization blockers (in order of buyer impact):**
1. Multi-user + auth hardening (the GIL/SQLite migration already on the debt register)
2. One-command install (Docker compose already scaffolded — finish it, add a landing page)
3. Model flexibility via API (already supported — make it a first-class option with
   cloud fallback; privacy stays default-local)
4. A license decision: open-core (MIT core + paid pro) is the standard path for this
   class and builds distribution faster than closed source
5. Ten design partners (offer it free to 10 netsec colleagues; their 👍/👎 telemetry
   becomes both the SFT data and the testimonial)

**What I would NOT spend on:** more corpus batches (diminishing at 12.3M params), a
bigger GPU before there are users, or more agents/features before distribution.

---

## 4. Risk disclosure (an acquirer will ask)

- Reliance on Ollama (mitigated: watchdog, model-agnostic interface, cloud fallback)
- LLM answer quality bounded by small models (mitigated: verification gates + routing)
- Single-maintainer risk (mitigated: docs quality is high; CI + tests ease handover)
- No patents; trade-secret protection only (the repo is private — keep it that way
  until a license strategy exists)
- Sales of the *knowledge library* content (Wikipedia/SQuAD-derived passages) must
  respect dataset licenses — for personal use fine; for a product, re-derive from
  primary sources per license terms.

---

*Prepared as an honest business audit, not a formal appraisal. Numbers are reasoned
ranges from standard valuation approaches applied to observable facts, not offers.*
