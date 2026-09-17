# Brain-Chat — a bilingual AI companion with memory

A chat frontend (English + العربية) with a **persona** and a **persistent memory**
that learns about you and never forgets. It runs on a real small pretrained model
locally via **Ollama**.

## Honest scope

The tiny models in `../prototype` demonstrate *mechanisms* (memory, no-backprop
learning, oscillator+attention) but cannot chat or understand language at scale —
that needs a model pretrained on huge multilingual data. Ollama runs such a model
on your laptop; this app adds the blueprint's human-like layer on top:

- **Persona / identity** — a name + personality (edit `PERSONA` in `brain_chat.py`).
- **Memory (the hippocampus, §5.3)** — remembers facts about you across sessions.
- **Teaching** — type `remember: <fact>` (or `تذكر: <fact>`) to store something forever.
- **Bilingual** — replies in whatever language you write (English or Arabic, RTL-aware).

## Setup

```
1) Install Ollama:            https://ollama.com/download
2) Pull a small Arabic-capable model:
       ollama pull qwen2.5:1.5b     (light — good for a 2 GB GPU / CPU)
       ollama pull qwen2.5:3b       (better, needs more RAM)
3) Run the chat:              python brain_chat.py
4) Open http://localhost:8000 and talk to it.
```

Change the model with `set BRAIN_MODEL=qwen2.5:3b` before running (Windows), or edit
`MODEL` in the file. Your memory lives in `brain_memory.json` (git-ignored, private).

## "Make it train itself" — what's real

- **Learning about you**: real and working — the memory grows as you teach/correct it,
  and it's used in every reply. This is continual, forgetting-free learning (it's data,
  not weights).
- **Fine-tuning on your conversations** (changing the model's own weights): possible as a
  next step — log the chats and periodically LoRA-fine-tune the base model. This needs
  more setup and compute; it is not automatic. Fully autonomous self-improvement is a
  research frontier, not a laptop feature.

## Testing what it knows

Open the "What I remember about you" panel in the UI, or just ask it — e.g. *"what do
you know about me?"* / *"ماذا تعرف عني؟"*. It answers from its memory.
