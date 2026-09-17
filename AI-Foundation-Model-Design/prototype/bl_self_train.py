"""
BL-Self-Train — a self-training / self-improvement loop on top of the oscillatory LM,
with checkpointing so a run survives interruption (container restart, timeout, etc).

Self-training here is classical pseudo-labeling / self-distillation (Scudder 1965; and,
closer to language models, STaR — Zelikman et al. 2022, Self-Instruct — Wang et al. 2022):
after an initial bootstrap on real text, the model generates its own continuations, keeps
only the ones it is most CONFIDENT about (its own average next-char probability on its own
output, teacher-forced), and folds those back into training as extra data. A control run
trains for the identical total step budget on real data only, so any self-training gain is
isolated honestly rather than assumed — matching this directory's ablation-first style.

Reuses the oscillatory cell from bl_language_real.py (learnable per-neuron damped-
oscillator dynamics). This file is self-contained (no imports across prototype files,
matching the rest of this directory).

    pip install torch
    python bl_self_train.py

Checkpointing: every bootstrap checkpoint and self-train round writes checkpoints/
self_train.pt. Re-running the script resumes from the latest checkpoint instead of
restarting from step 0 -- the actual failure mode this addresses is a long CPU/GPU run
getting killed mid-way (OOM, timeout, host restart) with nothing to show for it.
"""

import os
import urllib.request
import torch
import torch.nn as nn
import torch.nn.functional as F

torch.manual_seed(0)
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

D_EMB = 48
D_HID = 256                  # lower to 128 for a quicker CPU look
SEQ = 96
BATCH = 32
LR = 3e-3

BOOTSTRAP_STEPS = 1500        # initial training on real corpus only
SELF_TRAIN_ROUNDS = 4         # generate -> filter by self-confidence -> mix -> train
STEPS_PER_ROUND = 300
GEN_SAMPLES_PER_ROUND = 24    # candidate self-generated samples per round
GEN_LEN = 200                 # characters generated per candidate
KEEP_FRACTION = 0.5           # keep the most self-confident half as pseudo-labels
P_SELF = 0.25                 # fraction of each training batch drawn from self-generated data

CKPT_DIR = "checkpoints"
CKPT_PATH = os.path.join(CKPT_DIR, "self_train.pt")

CORPUS_URL = "https://raw.githubusercontent.com/karpathy/char-rnn/master/data/tinyshakespeare/input.txt"
FALLBACK = ("to be or not to be that is the question whether tis nobler in the mind "
            "to suffer the slings and arrows of outrageous fortune or to take arms "
            "against a sea of troubles and by opposing end them ") * 40


def get_corpus():
    try:
        with urllib.request.urlopen(CORPUS_URL, timeout=30) as r:
            text = r.read().decode("utf-8")
        return text, "tiny-shakespeare (downloaded)"
    except Exception as e:
        print(f"[download failed ({type(e).__name__}); using built-in fallback text]")
        return FALLBACK, "built-in fallback"


class OscillatoryCell(nn.Module):
    """Coupled damped oscillators, symplectic integration, learnable per-unit
    frequency/damping/timestep (same cell as bl_language_real.py)."""

    def __init__(self, d_in, d_hid):
        super().__init__()
        self.Wy = nn.Linear(d_hid, d_hid)
        self.Wu = nn.Linear(d_in, d_hid, bias=False)
        self.d_hid = d_hid
        self.log_gamma = nn.Parameter(torch.full((d_hid,), -0.7))
        self.log_alpha = nn.Parameter(torch.full((d_hid,), -2.3))
        self.log_dt = nn.Parameter(torch.full((d_hid,), -1.6))

    def forward(self, u):
        B, T, _ = u.shape
        y = torch.zeros(B, self.d_hid, device=u.device)
        z = torch.zeros(B, self.d_hid, device=u.device)
        g, a, dt = self.log_gamma.exp(), self.log_alpha.exp(), self.log_dt.exp()
        outs = []
        for t in range(T):
            drive = torch.tanh(self.Wy(y) + self.Wu(u[:, t]))
            z = z + dt * (drive - g * y - a * z)
            y = y + dt * z
            outs.append(y)
        return torch.stack(outs, dim=1)


class OscLM(nn.Module):
    def __init__(self, vocab, d_emb=D_EMB, d_hid=D_HID):
        super().__init__()
        self.emb = nn.Embedding(vocab, d_emb)
        self.cell1 = OscillatoryCell(d_emb, d_hid)
        self.norm = nn.LayerNorm(d_hid)
        self.cell2 = OscillatoryCell(d_hid, d_hid)
        self.head = nn.Linear(d_hid, vocab)

    def forward(self, x):
        h = self.cell1(self.emb(x))
        h = h + self.cell2(self.norm(h))
        return self.head(h)


def make_batch_fn(data_tensor, seq, batch, device):
    def get_batch(n=batch):
        ix = torch.randint(0, len(data_tensor) - seq - 1, (n,), device=device)
        x = torch.stack([data_tensor[i:i + seq] for i in ix])
        y = torch.stack([data_tensor[i + 1:i + seq + 1] for i in ix])
        return x, y
    return get_batch


@torch.no_grad()
def generate(model, stoi, seq_len, prompt, n_gen, temp, device):
    model.eval()
    idx = [stoi.get(c, 0) for c in prompt]
    for _ in range(n_gen):
        x = torch.tensor(idx[-seq_len:], device=device)[None]
        logits = model(x)[0, -1] / temp
        idx.append(int(torch.multinomial(F.softmax(logits, -1), 1)))
    model.train()
    return idx


@torch.no_grad()
def self_confidence(model, idx_tensor, prompt_len):
    """Average next-char probability the model assigns to its OWN generated
    continuation (teacher-forced) -- the pseudo-label confidence score used to
    filter self-generated data in classical self-training / STaR."""
    model.eval()
    x = idx_tensor[None, :-1]
    y = idx_tensor[None, 1:]
    logits = model(x)[0]
    probs = F.softmax(logits, dim=-1)
    p_correct = probs.gather(1, y[0][:, None]).squeeze(1)
    model.train()
    gen_part = p_correct[prompt_len - 1:]        # score only the generated tail
    return gen_part.mean().item()


def save_ckpt(path, model, opt, stoi, itos, stage, step, extra=None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    torch.save({
        "model": model.state_dict(), "opt": opt.state_dict(),
        "stoi": stoi, "itos": itos, "stage": stage, "step": step,
        "extra": extra or {},
    }, path)


def load_ckpt(path, device):
    if not os.path.exists(path):
        return None
    return torch.load(path, map_location=device, weights_only=False)


def val_loss_fn(model, get_val_batch, vocab, n=5):
    model.eval()
    tot = 0.0
    with torch.no_grad():
        for _ in range(n):
            xb, yb = get_val_batch()
            tot += F.cross_entropy(model(xb).reshape(-1, vocab), yb.reshape(-1)).item()
    model.train()
    return tot / n


def main():
    text, src = get_corpus()
    chars = sorted(set(text))
    stoi = {c: i for i, c in enumerate(chars)}
    itos = {i: c for c, i in stoi.items()}
    V = len(chars)
    data = torch.tensor([stoi[c] for c in text], dtype=torch.long, device=DEVICE)
    n = int(0.95 * len(data))
    train_data, val_data = data[:n], data[n:]
    print(f"Device: {DEVICE.upper()}   corpus: {src}, {len(text)} chars, vocab {V}\n")

    get_train_batch = make_batch_fn(train_data, SEQ, BATCH, DEVICE)
    get_val_batch = make_batch_fn(val_data, SEQ, BATCH, DEVICE)

    ckpt = load_ckpt(CKPT_PATH, DEVICE)

    model = OscLM(V).to(DEVICE)
    opt = torch.optim.Adam(model.parameters(), lr=LR)
    start_stage, start_step = "bootstrap", 0
    pseudo_chars = []          # accepted self-generated chars, growing pool
    history = {"bootstrap_val": None, "rounds": []}

    if ckpt is not None and ckpt["stoi"] == stoi:
        model.load_state_dict(ckpt["model"])
        opt.load_state_dict(ckpt["opt"])
        start_stage, start_step = ckpt["stage"], ckpt["step"]
        pseudo_chars = ckpt["extra"].get("pseudo_chars", [])
        history = ckpt["extra"].get("history", history)
        print(f"Resumed from checkpoint: stage={start_stage}, step={start_step}\n")

    nparam = sum(p.numel() for p in model.parameters())
    print(f"Oscillatory LM: {nparam/1e6:.2f}M params, {D_HID} hidden.\n")

    # ---- stage 1: bootstrap on real data only ----
    if start_stage == "bootstrap":
        print(f"[bootstrap] training on real corpus, {BOOTSTRAP_STEPS} steps...")
        for step in range(start_step + 1, BOOTSTRAP_STEPS + 1):
            x, y = get_train_batch()
            loss = F.cross_entropy(model(x).reshape(-1, V), y.reshape(-1))
            opt.zero_grad(); loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            if step % 250 == 0:
                vl = val_loss_fn(model, get_val_batch, V)
                print(f"  step {step:5d}   train {loss.item():.3f}   val {vl:.3f}")
                save_ckpt(CKPT_PATH, model, opt, stoi, itos, "bootstrap", step,
                          {"pseudo_chars": pseudo_chars, "history": history})
        history["bootstrap_val"] = val_loss_fn(model, get_val_batch, V)
        start_stage, start_step = "selftrain", 0
        save_ckpt(CKPT_PATH, model, opt, stoi, itos, "selftrain", 0,
                  {"pseudo_chars": pseudo_chars, "history": history})
        print(f"[bootstrap] done. val loss = {history['bootstrap_val']:.3f}\n")

    # ---- stage 2: self-training rounds ----
    # generate -> keep the self-confident half -> mix into training -> continue training
    completed_rounds = len(history["rounds"])
    for r in range(completed_rounds, SELF_TRAIN_ROUNDS):
        print(f"[self-train round {r+1}/{SELF_TRAIN_ROUNDS}] generating {GEN_SAMPLES_PER_ROUND} candidates...")
        candidates = []
        prompts = ["ROMEO:", "JULIET:", "\n\n", "KING:", "First "]
        for i in range(GEN_SAMPLES_PER_ROUND):
            prompt = prompts[i % len(prompts)]
            idx = generate(model, stoi, SEQ, prompt, GEN_LEN, temp=0.8, device=DEVICE)
            idx_t = torch.tensor(idx, device=DEVICE)
            score = self_confidence(model, idx_t, len(prompt))
            candidates.append((score, idx[len(prompt):]))   # keep only the generated tail

        candidates.sort(key=lambda c: c[0], reverse=True)
        keep_n = max(1, int(len(candidates) * KEEP_FRACTION))
        kept = candidates[:keep_n]
        mean_kept_score = sum(s for s, _ in kept) / len(kept)
        mean_all_score = sum(s for s, _ in candidates) / len(candidates)
        for _, chars_idx in kept:
            pseudo_chars.extend(chars_idx)
        print(f"  kept {keep_n}/{len(candidates)} candidates "
              f"(mean self-confidence kept={mean_kept_score:.3f} vs all={mean_all_score:.3f})")

        pseudo_tensor = torch.tensor(pseudo_chars, device=DEVICE) if len(pseudo_chars) > SEQ + 1 else None
        get_pseudo_batch = make_batch_fn(pseudo_tensor, SEQ, BATCH, DEVICE) if pseudo_tensor is not None else None

        def get_mixed_batch():
            if get_pseudo_batch is None or torch.rand(1).item() > P_SELF:
                return get_train_batch()
            return get_pseudo_batch()

        print(f"  training {STEPS_PER_ROUND} steps on real+self-generated mix (p_self={P_SELF})...")
        for step in range(1, STEPS_PER_ROUND + 1):
            x, y = get_mixed_batch()
            loss = F.cross_entropy(model(x).reshape(-1, V), y.reshape(-1))
            opt.zero_grad(); loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()

        vl = val_loss_fn(model, get_val_batch, V)
        print(f"  round {r+1} done. val loss (real held-out) = {vl:.3f}\n")
        history["rounds"].append({"val": vl, "kept_conf": mean_kept_score, "all_conf": mean_all_score})
        save_ckpt(CKPT_PATH, model, opt, stoi, itos, "selftrain", 0,
                  {"pseudo_chars": pseudo_chars, "history": history})

    # ---- control: identical total step budget, real data only, fresh model ----
    print("=" * 66)
    print("CONTROL: same total steps, real data only (no self-training) -- fair comparison")
    print("=" * 66)
    total_steps = BOOTSTRAP_STEPS + SELF_TRAIN_ROUNDS * STEPS_PER_ROUND
    control = OscLM(V).to(DEVICE)
    copt = torch.optim.Adam(control.parameters(), lr=LR)
    for step in range(1, total_steps + 1):
        x, y = get_train_batch()
        loss = F.cross_entropy(control(x).reshape(-1, V), y.reshape(-1))
        copt.zero_grad(); loss.backward()
        nn.utils.clip_grad_norm_(control.parameters(), 1.0)
        copt.step()
        if step % 500 == 0:
            print(f"  step {step:5d}   train {loss.item():.3f}")
    control_val = val_loss_fn(control, get_val_batch, V)

    print("\n" + "=" * 66)
    print("RESULTS")
    print("=" * 66)
    print(f"Bootstrap val loss:                 {history['bootstrap_val']:.3f}")
    for i, rd in enumerate(history["rounds"]):
        print(f"  round {i+1}: val={rd['val']:.3f}  self-confidence kept={rd['kept_conf']:.3f} "
              f"vs all={rd['all_conf']:.3f}")
    print(f"Self-trained final val loss:         {history['rounds'][-1]['val']:.3f}   "
          f"({total_steps} total steps)")
    print(f"Control (real-data-only) val loss:   {control_val:.3f}   ({total_steps} total steps)")
    print("=" * 66)
    print("SAMPLE (self-trained model, prompt 'ROMEO:'):")
    idx = generate(model, stoi, SEQ, "ROMEO:", 300, temp=0.8, device=DEVICE)
    print("".join(itos[i] for i in idx))
    print("=" * 66)


if __name__ == "__main__":
    main()
