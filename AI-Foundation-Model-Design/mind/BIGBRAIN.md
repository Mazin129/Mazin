# Breaking the model-quality ceiling

Vio's reasoning and diagrams are only as good as the model behind them. On a 2 GB GPU the
local ceiling is **qwen2.5:7b** (CPU, slow-ish) — fine for everyday answers, not for
senior-architect correlation questions or editorial SVG. You break that ceiling by
pointing Vio at a **bigger model**, without changing any other part of Vio.

Three paths, cheapest-first. All use the same switch — no redeploy.

---

## A. Bigger LOCAL model (free, needs hardware)
If you get a machine with a real GPU (≥16–24 GB VRAM), just pull a bigger local model and
select it in the dashboard **🧠 Brain** dropdown:
```
ollama pull qwen2.5:32b        # or llama3.1:70b on 48 GB+
```
Free, fully private, fast on the GPU. Nothing else changes.

## B. HOSTED big model on demand (paid, no hardware)  ← the "big brain on demand"
Point Vio at any **OpenAI-compatible** endpoint — OpenRouter, Together, Groq, Fireworks,
DeepInfra, Azure OpenAI, or your own rented vLLM. Set four env vars and restart:
```
set VIO_LLM_API=openai
set VIO_LLM_URL=https://openrouter.ai/api/v1
set VIO_LLM_KEY=sk-your-key
set VIO_LLM_MODEL=meta-llama/llama-3.1-70b-instruct
python web.py
```
The startup banner will read `🧠 model: … (hosted — data leaves this PC)`.

- **Cost:** pay-per-token, typically cents per answer (a 70B on OpenRouter is ~$0.3–0.9
  per 1M tokens). Set spend limits on the provider.
- **Privacy:** your prompts (including any retrieved private context) go to that provider.
  So it's **off by default**; use it only for questions you're comfortable sending out.
- **Everything else stays local:** retrieval, memory, corrections, the pipeline, the
  guardrail — only the final reasoning call goes to the hosted model.

## C. Rented GPU (paid, private-ish, fast)
Rent a GPU box (RunPod, Vast, Lambda), run `ollama serve` or vLLM on it, and point Vio at
it over Tailscale:
```
set VIO_LLM_URL=http://<gpu-box>:11434        # Ollama on the rented box
set VIO_LLM_MODEL=qwen2.5:32b
```
Fast and under your control; you pay by the hour and shut it down when done. If it exposes
an OpenAI API instead, add `VIO_LLM_API=openai` and `VIO_LLM_KEY`.

---

## Use the big brain only when you need it
Keep `qwen2.5:3b`/`7b` as the default for speed and privacy, and flip to the big model for
the hard questions:
- **Env way:** set the four vars (path B) in a separate launcher, e.g. `start_vio_big.bat`.
- **Dashboard way:** once a hosted/bigger endpoint is configured, its models appear in the
  **🧠 Brain** dropdown — select and **Use this brain**, ask, then switch back.

## Env vars (added for this)
| Var | Meaning |
|---|---|
| `VIO_LLM_API` | `openai` to use an OpenAI-compatible endpoint; unset = local Ollama |
| `VIO_LLM_URL` | endpoint base (…/v1 for OpenAI-compatible; :11434 for Ollama) |
| `VIO_LLM_KEY` | API key for the hosted endpoint (kept out of git; never commit it) |
| `VIO_LLM_MODEL` | the model id to use |

Recommendation: pull `qwen2.5:32b` if you ever get a GPU (best free path); otherwise wire
an OpenRouter key for on-demand depth. Either way, Vio itself doesn't change — you're just
giving it a stronger brain.
