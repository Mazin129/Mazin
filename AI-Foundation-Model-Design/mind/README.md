# The Mind — a neuro-symbolic reasoning engine (ours, not a market chatbot)

Market LLMs are pure neural nets: fluent but they **hallucinate math and facts** and
can't verify themselves. The Mind is different — it **reasons with real tools and
verifies every answer**. "Clever, not big": it runs on a laptop, is exact, shows its
work, and grows its knowledge and memory as you use it. (Blueprint section 1.7.)

```
python reasoner.py
```

## What it does today (all real, all tested)

- **Exact, self-verifying math** (sympy): `solve x^2-5x+6=0` → `x=2,3` and it
  *substitutes the answers back to prove them*; `integrate 1/x` → `log(x)+C` (verified
  by differentiating); also `derivative`, `simplify`, `factor`, `expand`, arithmetic —
  exact, no floating-point error, no hallucination.
- **Retrieval** ("small brain, big library"): `teach: <fact>` adds to a growing
  knowledge base; questions are answered from it with a match score and source.
- **Memory / continual learning**: `remember: <fact about you>` is stored forever and
  recalled; solved problems are cached. It learns as you use it — no retraining.
- **Honesty**: if it can't verify or retrieve an answer, it says *"I don't know yet"*
  and tells you how to teach it — it never bluffs. That's the opposite of a market LLM.

## Try

```
solve x^2 - 5x + 6 = 0
integrate 1/x
expand (x+1)^3
teach: The Nile is the longest river in Africa, about 6650 km.
longest river in africa?
remember: my name is Mazin
what is my name?
```

## Where this fits the 4 directions

This is directions 1 (reasoning), 2 (retrieval) and 4 (continual learning), working
now. Direction 3 — a natural-language front-end / our own trained model — plugs in on
top as the "language cortex" that turns free-form sentences into these tool calls; it
is the one piece that genuinely needs a trained model, and it's the next build.
Files `mind_memory.json` / `knowledge.json` hold your private memory & library (git-ignored).

## Talk to it in plain language — `talk.py`

`python talk.py` adds a natural-language front-end (English + العربية): it reads
free-form sentences, works out your intent, extracts the payload (even spoken math
like "x squared minus five x plus six"), and drives The Mind's verified tools.

```
you › what are the roots of x squared minus 5x plus 6      -> x = 2, 3  (verified)
you › what is 15 times 12 plus 7                            -> 187
you › remember that my favourite language is Arabic         -> stored
you › what is my favourite language                         -> recalled
you › who is the king of the moon                           -> honestly: "I don't know"
```

Honest note: this is a rule-based understander (patterns + normalisation), not a
neural language model — precise on math/teach/recall/question shapes, not open chat.
It is the "language cortex" slot (AXIOM direction 3); our own trained model replaces
these rules with learned routing later.

## Chat in your browser — `web.py` (recommended)

Prefer a browser chat window? Run:

```
python web.py
```
then open **http://localhost:8100**. It's the same verified reasoning + memory, in a
clean chat page (English / العربية, right-to-left aware), with a panel showing what it
remembers about you and everything in its library. **No Ollama, no external model** —
100% local. Each reply shows the tool used and a ✓ verified / … unverified badge.

### Easiest: double-click `Vio.bat`

On Windows, just **double-click `Vio.bat`** (in this `mind` folder). It starts Vio and
opens the browser automatically — no typing. A small console window stays open; close it
to stop Vio. (First time only: right-click → keep, if Windows asks.)

### One-time: make a Desktop icon

Double-click **`Create Vio Desktop Icon.bat`** once. It puts a **Vio** icon on your
Desktop. After that, just double-click the Desktop **Vio** icon to start chatting —
no folders, no commands.

## What Vio can do (all exact & verified)

- **Maths**: arithmetic, algebra (`solve x^2-5x+6=0`), calculus (`integrate 1/x`,
  `derivative of x^3`), `simplify`/`factor`/`expand`, and **systems** (`solve x+y=10, x-y=2`).
- **Percentages**: `15% of 200`, `what percent is 30 of 120`, `increase 200 by 15%`.
- **Statistics**: `average of 4, 8, 15, 16`, `median/sum/min/max/std of …`.
- **Unit conversions**: `5 km to miles`, `100 f to c`, `2 hours in minutes` (length, mass, time, temperature).
- **Time/date**: `what time is it in KSA`, `date today`.
- **Memory**: `remember that …` / `my name is …`, then `what do you know about me`.
- **Knowledge**: `teach: <a fact or a whole paragraph>` (paragraphs split into
  retrievable facts), then ask questions about it.
- **Honesty**: says *"I don't know"* rather than guessing. Everything is verified or
  taught by you.
