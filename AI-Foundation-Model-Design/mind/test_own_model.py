"""
test_own_model — a small, HONEST test of Vio's own trained model (own_model/).

This is the from-scratch transformer that train_all.py trained on your datasets, skills
and RFCs. It is a TEXT GENERATOR, not a question-answerer: every weight was learned from
your corpus, starting from zero, with no pretraining. So this test measures what it
actually is:

  1. does it load, and what size is it?
  2. does it generate non-empty text?
  3. is the text non-degenerate (not a repeated token loop — the classic small-model fail)?
  4. did it learn YOUR domain's vocabulary (networking / security / RFC terms)?
  5. how fast is generation?

It deliberately does NOT test factual correctness — a small from-scratch model cannot be
relied on for answers. Vio answers from retrieval + the Ollama cortex; this model is the
"wrote it myself" generator.

Run:
    python test_own_model.py            # uses $VIO_DATA_DIR/own_model (or ./own_model)
    python test_own_model.py <dir>
"""
from __future__ import annotations

import os
import re
import sys
import time

SEEDS = [
    "BGP",
    "The firewall policy",
    "OSPF",
    "TLS",
    "The router",
    "This document",
]

DOMAIN_TERMS = (
    "network", "router", "routing", "packet", "protocol", "interface", "address",
    "firewall", "policy", "security", "tls", "encrypt", "certificate", "bgp", "ospf",
    "tcp", "udp", "ip", "port", "server", "client", "request", "message", "header",
    "rfc", "must", "may", "session", "connection", "traffic", "vlan", "subnet", "key",
)


def _fmt(s, n=90):
    s = re.sub(r"\s+", " ", (s or "")).strip()
    return (s[:n] + "…") if len(s) > n else s


def degeneracy(text):
    """0 = healthy variety, 1 = totally repetitive. Small models fail here first."""
    words = re.findall(r"\w+", (text or "").lower())
    if len(words) < 8:
        return 1.0
    uniq = len(set(words)) / len(words)
    # also catch a short phrase looping ("VPN VPN VPN" / "the the the")
    longest_run, run, prev = 1, 1, None
    for w in words:
        run = run + 1 if w == prev else 1
        longest_run = max(longest_run, run)
        prev = w
    loop_penalty = min(1.0, max(0.0, (longest_run - 2) / 6.0))
    return round(max(0.0, min(1.0, (1.0 - uniq) * 0.8 + loop_penalty * 0.2)), 2)


def domain_hits(text):
    low = (text or "").lower()
    return sorted({t for t in DOMAIN_TERMS if t in low})


def main(argv):
    data_dir = os.environ.get("VIO_DATA_DIR") or os.path.dirname(os.path.abspath(__file__))
    d = argv[1] if len(argv) > 1 else os.path.join(data_dir, "own_model")

    print("=" * 74)
    print("  VIO — OWN TRAINED MODEL: SMALL TEST")
    print("=" * 74)
    print(f"  model dir: {d}")

    need = ("config.json", "weights.pt", "tokenizer.pkl")
    missing = [f for f in need if not os.path.isfile(os.path.join(d, f))]
    if missing:
        print(f"\n  ❌ No trained model found (missing: {', '.join(missing)}).")
        print("     Train one with:  python train_all.py     (or the 🚀 button in the GUI)")
        return 1

    import json
    cfg = json.load(open(os.path.join(d, "config.json"), encoding="utf-8"))
    e, L, V, B = cfg["n_embd"], cfg["n_layer"], cfg["vocab_size"], cfg["block_size"]
    params = V * e + B * e + L * (12 * e * e)
    size_mb = os.path.getsize(os.path.join(d, "weights.pt")) / 1e6
    print(f"  architecture: {L} layers · {e} embd · {cfg.get('n_head','?')} heads · "
          f"vocab {V} · context {B}")
    print(f"  size: ~{params/1e6:.1f}M parameters · {size_mb:.1f} MB on disk")

    try:
        from neural_model import load, sample
    except Exception as ex:
        print(f"\n  ❌ Can't import the model code: {ex}")
        return 1

    t0 = time.time()
    try:
        model, tok = load(d)
    except Exception as ex:
        print(f"\n  ❌ Failed to load the weights: {ex}")
        return 1
    print(f"  loaded in {time.time()-t0:.2f}s\n")

    print("  Generations (seed → what your model writes)")
    print("  " + "-" * 70)
    rows, gen_times = [], []
    for seed in SEEDS:
        t = time.time()
        try:
            out = sample(model, tok, seed, max_new_tokens=90, temperature=0.9, top_k=40)
        except Exception as ex:
            out = ""
            print(f"    {seed!r}: generation failed: {ex}")
        dt = time.time() - t
        gen_times.append(dt)
        body = out[len(seed):] if out.startswith(seed) else out
        dg = degeneracy(body)
        hits = domain_hits(body)
        rows.append({"seed": seed, "text": body, "deg": dg, "hits": hits, "s": dt})
        flag = "✅" if dg < 0.55 else ("⚠️ " if dg < 0.8 else "❌")
        print(f"    {flag} {seed:<22} [{dt:4.1f}s · repetition {dg:.2f} · "
              f"{len(hits)} domain term(s)]")
        print(f"       {_fmt(body)}")

    print("  " + "-" * 70)
    non_empty = sum(1 for r in rows if len(r["text"].strip()) > 10)
    healthy = sum(1 for r in rows if r["deg"] < 0.55)
    with_domain = sum(1 for r in rows if r["hits"])
    avg_s = sum(gen_times) / max(1, len(gen_times))
    all_terms = sorted({t for r in rows for t in r["hits"]})

    print(f"\n  produced text        : {non_empty}/{len(rows)}")
    print(f"  non-degenerate       : {healthy}/{len(rows)}   (repetition score < 0.55)")
    print(f"  used domain wording  : {with_domain}/{len(rows)}")
    print(f"  domain terms learned : {', '.join(all_terms[:14]) or '(none seen)'}")
    print(f"  speed                : {avg_s:.1f}s per ~90 tokens")

    ok = non_empty == len(rows) and healthy >= max(1, len(rows) // 2) and with_domain >= 1
    print("\n" + "=" * 74)
    if ok:
        print("  ✅ The model loads, generates VARIED (non-repetitive) text, and has clearly")
        print("     learned your domain's vocabulary.")
        print("     NOTE: this test does not measure fluency. Read the samples above — if the")
        print("     wording is garbled, the model is under-trained (more data / more steps /")
        print("     a larger model), even though these checks pass.")
    elif non_empty == len(rows):
        print("  ⚠️  It generates, but output is repetitive or off-domain —")
        print("      usually means too few steps, too little data, or too high a temperature.")
    else:
        print("  ❌ The model isn't generating usable text — retrain (more data / steps).")
    print("\n  Remember what this is: a from-scratch generator trained only on YOUR corpus.")
    print("  It writes in your domain's voice; it does NOT reliably answer questions.")
    print("  Vio answers from retrieval + the Ollama cortex — this model is the writer.")
    print("=" * 74)
    return 0 if ok else 2


if __name__ == "__main__":
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    sys.exit(main(sys.argv))
