"""
Think  —  Vio's open-ended thinking engine (local, no market model).

Two honest capabilities, both running 100% on your laptop with no internet and no
downloaded model:

  1. SYNTHESIS ("reason over what I know").  For an open question, Vio gathers the
     sentences across its whole library + memory that actually bear on the question,
     ranks them, removes duplicates, and composes ONE grounded answer that draws on
     several sources at once — instead of dumping a single passage. Every sentence is
     traceable to something you taught it, so it still never hallucinates.

  2. GENERATION ("write / continue / imagine …").  Vio trains a small word-level
     n-gram language model ON THE BOOKS YOU TEACH IT and can generate new text in that
     style. This is a REAL (small) language model that is *yours* and learns from your
     documents. It is not GPT-sized — it is the laptop-native seed of the "language
     cortex", and it grows sharper the more you teach it.

No eval, no exec — it only ever consumes text already in the library. Pure stdlib.
"""

import random
import re
from collections import Counter, defaultdict

_STOP = {"the", "a", "an", "is", "are", "was", "were", "be", "of", "to", "in", "on",
         "for", "and", "or", "but", "with", "as", "by", "at", "from", "that", "this",
         "these", "those", "it", "its", "into", "than", "then", "so", "such", "can",
         "will", "would", "do", "does", "did", "has", "have", "had", "what", "who",
         "where", "when", "why", "how", "which", "about", "you", "your", "i", "me",
         "my", "we", "they", "he", "she", "them", "their"}


def _sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?؟])\s+|\n+", text.strip())
            if len(s.strip().split()) >= 3]


def _keywords(q):
    return [w for w in re.findall(r"[a-zA-Z؀-ۿ]+", q.lower())
            if len(w) > 2 and w not in _STOP]


class Thinker:
    """Synthesises grounded answers and generates text learned from the library."""

    def __init__(self):
        self.order = 3
        self.models = [defaultdict(Counter) for _ in range(self.order)]  # backoff n-grams
        self.starts = []            # sentence-start contexts, for seeding generation
        self._trained_on = 0

    # ---- learning: build the n-gram language model from the library text ----
    def train(self, docs):
        self.models = [defaultdict(Counter) for _ in range(self.order)]
        self.starts = []
        for doc in docs:
            for sent in _sentences(doc):
                toks = re.findall(r"[A-Za-z0-9'؀-ۿ]+|[.,;:!?،؛؟]", sent)
                if len(toks) < 3:
                    continue
                toks = toks + ["</s>"]
                self.starts.append(tuple(toks[:2]))
                for i in range(len(toks)):
                    for o in range(1, self.order + 1):     # unigram..trigram contexts
                        if i - o < 0:
                            continue
                        ctx = tuple(toks[i - o:i])
                        self.models[o - 1][ctx][toks[i]] += 1
        self._trained_on = len(docs)
        return self._trained_on

    def stats(self):
        """Real, inspectable size of the trained language model."""
        contexts = sum(len(m) for m in self.models)
        vocab = set()
        for m in self.models:
            for ctx, dist in m.items():
                vocab.update(dist.keys())
        return {"passages": self._trained_on, "contexts": contexts,
                "vocab": len(vocab), "order": self.order}

    def _next(self, history):
        """Pick the next word using the longest context we have data for (backoff)."""
        for o in range(self.order, 0, -1):
            ctx = tuple(history[-o:])
            dist = self.models[o - 1].get(ctx)
            if dist:
                words, weights = zip(*dist.items())
                return random.choices(words, weights=weights)[0]
        return "</s>"

    def generate(self, prompt="", max_words=40):
        if not self.starts:
            return None
        # topic-aware seeding: start from a real context that mentions the topic word
        kws = [w for w in re.findall(r"[a-z'؀-ۿ]+", prompt.lower())
               if len(w) > 2 and w not in _STOP]
        history = None
        if kws:
            cands = [list(ctx) for ctx in self.models[1]
                     if any(k in w.lower() for w in ctx for k in kws)]
            if cands:
                history = random.choice(cands)
        if history is None:
            seed = re.findall(r"[A-Za-z0-9'؀-ۿ]+|[.,;:!?،؛؟]", prompt)
            history = seed[-2:] if len(seed) >= 2 else list(random.choice(self.starts))
        out = list(history)
        for _ in range(max_words):
            nxt = self._next(history)
            if nxt == "</s>":
                if len(out) >= 6:
                    break
                history = list(random.choice(self.starts)); out += history; continue
            out.append(nxt); history.append(nxt)
        text = " ".join(out)
        text = re.sub(r"\s+([.,;:!?])", r"\1", text)          # tidy punctuation spacing
        text = re.sub(r"\s+", " ", text).strip()
        if text and text[-1] not in ".!?":
            text += " …"
        return text[0].upper() + text[1:] if text else None

    # ---- synthesis: compose a grounded, natural-language answer ----
    @staticmethod
    def _tidy_sentence(s):
        s = re.sub(r"\s+", " ", s.strip())
        s = re.sub(r"\s+([.,;:!?])", r"\1", s)
        if s and s[-1] not in ".!?:":
            s += "."
        return s

    _DEF_CUE = re.compile(r"\b(is|are|means?|refers to|description|defined|used to|"
                          r"lets you|allows|enables|tests?|displays?|configures?)\b", re.I)
    _LABEL = re.compile(r"^\s*(syntax|example|examples|usage|parameters?|options?|"
                        r"description|note|notes|default|arguments?|values?)\s*[:\-]", re.I)

    def _subject(self, question):
        """The thing being asked about, e.g. 'what does execute ping do?' -> 'execute
        ping'. Strips leading question words and trailing filler verbs."""
        q = question.strip().lower().rstrip("?.! ")
        q = re.sub(r"^(what('?s| is| are| does| do)?|who('?s| is| are)?|define|explain|"
                   r"tell me about|how do(es)?|how to)\s+", "", q)
        q = re.sub(r"\s+(do|does|mean|means|work|works|used for|used|for|is|are)$", "", q)
        return re.sub(r"^(the|a|an)\s+", "", q).strip()

    def _lead(self, question):
        """A short, natural opener matched to a clean 'what is X' / 'how' question.
        It only frames the retrieved facts — it never adds information."""
        q = question.strip().lower()
        if re.match(r"(what\s+(is|are|does|do)|who\s+(is|are)|define|explain)\b", q):
            subj = self._subject(question)
            if 0 < len(subj.split()) <= 5:
                return f"{subj[:1].upper()}{subj[1:]} — "
        # only procedural "how do/to/can…" gets this lead — NOT "how many/much/long"
        if re.match(r"how\s+(do|to|can|could|would|should|does|did|will|i)\b", q):
            return "Here's how: "
        return ""

    @staticmethod
    def _first_word(s):
        w = re.findall(r"[A-Za-z؀-ۿ]+", s)
        return w[0].lower() if w else ""

    @staticmethod
    def _format_body(text):
        """Light structure for reference-style answers: put field labels
        (Syntax:, Example:, …) on their own line. Plain prose is unaffected."""
        text = re.sub(r"\s+(Syntax|Example|Examples|Usage|Parameters?|Options?|"
                      r"Note|Notes|Default|Arguments?|Values?)\s*:",
                      r"\n\1:", text, flags=re.I)
        return text.strip()

    def _related(self, passages, used_pi, per, subj):
        """Short titles of OTHER retrieved entries the user might ask about next —
        the leading words of passages that didn't feed the answer."""
        out = []
        seen = set()
        for pi, sents in enumerate(per):
            if pi in used_pi or not sents:
                continue
            title = re.split(r"\b(description|syntax|parameter|type|size|note|example|"
                             r"usage|default)\b|[:\-–]", sents[0], 1, re.I)[0]
            title = " ".join(re.sub(r"\s+", " ", title).strip(" .,:;").split()[:6])
            key = title.lower()
            if not title or len(title) <= 2 or key in seen:
                continue
            if subj and (subj in key or key in subj):      # skip what they already asked
                continue
            seen.add(key)
            out.append(title)
            if len(out) >= 3:
                break
        return out

    _NOISE = re.compile(r"on page\s+\d+|this topic includes the following", re.I)

    def _is_noise(self, s):
        # only true navigation cruft — NOT table headers like "Parameter Description
        # Type Size", which sit next to real content and were over-filtering entries.
        return bool(self._NOISE.search(s))

    def synthesize(self, question, passages, facts=()):
        kw = set(_keywords(question))
        if not kw:
            return None
        subj = self._subject(question)
        # exact-phrase matcher: 'execute ping' must NOT also fire on 'execute ping-options'
        phrase_rx = None
        if subj and 1 <= len(subj.split()) <= 5:
            phrase_rx = re.compile(r"\b" + re.escape(subj) + r"\b(?![-\w])", re.I)
        # definition matcher: for "what is X", the sentence "X is a …" should LEAD, not a
        # "to configure X …" sentence that merely mentions X.
        ql = question.strip().lower()
        defn_rx = None
        if subj and re.match(r"(what\s+(is|are)|who\s+(is|are)|define|explain)\b", ql):
            # anchored at the sentence start: "A VLAN is a…" matches, "The native VLAN
            # is…" does NOT (so the real definition leads, not a tangential mention).
            defn_rx = re.compile(r"^\s*(?:a|an|the)?\s*" + re.escape(subj) +
                                 r"\b\s*(?:\([^)]*\))?\s*"
                                 r"(is|are|means?|refers?\s+to|stands?\s+for)\b", re.I)

        per = [_sentences(p) for p in passages]        # sentences per passage
        scored = []                                    # (score, passage_idx, sent_idx)
        for pi, sents in enumerate(per):
            for si, s in enumerate(sents):
                if self._is_noise(s):                  # drop TOC/index/table cruft
                    continue
                ov = len(kw & set(_keywords(s)))
                if not ov:
                    continue
                if phrase_rx and phrase_rx.search(s):  # exact command/subject present
                    ov += 3                            # strongly prefer the real entry
                if defn_rx and defn_rx.search(s):      # "X is a …" — the actual definition
                    ov += 4                            # leads over "to configure X …"
                scored.append((ov, pi, si))
        rel_facts = [f for f in facts if kw & set(_keywords(f))]
        if not scored and not rel_facts:
            return None

        picked = []                                    # (pi, si) in reading order
        chosen = set()
        used_pi = set()
        if scored:
            best = max(o for o, _, _ in scored)
            anchors = [(o, pi, si) for o, pi, si in scored if o >= best]
            if len(anchors) < 2:                       # broaden slightly if too thin
                anchors = [(o, pi, si) for o, pi, si in scored if o >= best - 1]
            # rank: most query-keyword overlap first, then the higher-ranked passage
            # (passages arrive in retrieval-score order), then a defining sentence,
            # then document order. Overlap must dominate so the most on-topic sentence
            # leads — not a lower-overlap sentence that merely contains "is".
            anchors.sort(key=lambda t: (-t[0], t[1],
                                        0 if self._DEF_CUE.search(per[t[1]][t[2]]) else 1,
                                        t[2]))
            starters = {self._first_word(p) for p in passages if p}
            for _o, pi, si in anchors[:3]:
                if (pi, si) in chosen:
                    continue
                picked.append((pi, si)); chosen.add((pi, si)); used_pi.add(pi)
                # RICHER: pull the immediate follow-on detail from the SAME passage
                # (e.g. "The host can be an IP address…" after a Syntax line), but
                # stop at the next entry so we never bleed into another command.
                j, added = si + 1, 0
                while j < len(per[pi]) and added < 2:
                    nxt = per[pi][j]
                    # a sentence that opens with an entry-starter word (e.g. another
                    # "execute …" command) begins a NEW entry — stop, so one command's
                    # answer never bleeds into the next. Label lines (Syntax:/Example:)
                    # are part of the SAME entry, so they don't count as a boundary.
                    starts_new = (self._first_word(nxt) in starters
                                  and not self._LABEL.match(nxt))
                    if starts_new:
                        break
                    if (pi, j) not in chosen:
                        picked.append((pi, j)); chosen.add((pi, j))
                        added += 1
                    j += 1

        # assemble, de-duplicated, in reading order
        sentences, seen = [], set()
        for pi, si in picked:
            t = self._tidy_sentence(per[pi][si])
            k = t.lower()[:50]
            if k not in seen:
                seen.add(k); sentences.append(t)
        sentences = sentences[:5]

        parts = []
        if rel_facts:
            parts.append(" ".join(self._tidy_sentence(f) for f in rel_facts))
        if sentences:
            lead = self._lead(question) if not rel_facts else ""
            if lead and sentences[0].lower().startswith(lead.rstrip(" —").lower()):
                lead = ""
            parts.append(self._format_body(lead + " ".join(sentences)))
        answer = "\n\n".join(parts) if parts else None
        if answer:
            related = self._related(passages, used_pi, per, subj)
            if related:
                answer += "\n\nRelated topics I can explain: " + ", ".join(related) + "."
        return answer


if __name__ == "__main__":
    t = Thinker()
    t.train([
        "The brain learns by strengthening connections between neurons that fire together.",
        "Memory is stored across many neurons, not in one place. Recall reactivates the pattern.",
        "Sleep helps the brain consolidate memories and clear waste from the day.",
    ])
    print("GENERATE:", t.generate("the brain"))
    print("SYNTHESIZE:\n", t.synthesize("how does the brain store memory?",
          ["Memory is stored across many neurons, not in one place. Recall reactivates the pattern.",
           "Sleep helps the brain consolidate memories and clear waste from the day."]))
