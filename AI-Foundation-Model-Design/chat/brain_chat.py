"""
Brain-Chat  —  a bilingual (English + Arabic) AI companion with a persona and a
persistent memory that learns about you.

WHAT THIS IS (honest): a chat frontend that talks to a REAL small pretrained
language model running locally via Ollama. The tiny BL models in ../prototype
demonstrate mechanisms but cannot hold a conversation; a real conversational model
must be pretrained on huge multilingual data. Ollama runs such a model on your
laptop. On top of it, this app adds the parts from the BL blueprint that make it
feel like "someone":

  * PERSONA  — an identity/personality (name + traits), from the blueprint's
    global-workspace idea. Edit PERSONA below.
  * MEMORY   — a persistent store of facts it learns about you (the hippocampus,
    section 5.3): it remembers across sessions and never forgets unless you delete.
  * TEACH    — you can tell it facts/corrections ("remember: ...") that persist.
  * BILINGUAL — replies in English or Arabic (the model handles both; the UI is
    right-to-left aware).

------------------------------------------------------------------------------
SETUP (one time)
------------------------------------------------------------------------------
1. Install Ollama:  https://ollama.com/download   (Windows installer)
2. Pull a small multilingual model good at Arabic (pick by your RAM/GPU):
       ollama pull qwen2.5:1.5b     # light, ~1 GB, fine on a 2 GB GPU / CPU
       ollama pull qwen2.5:3b       # better, needs more RAM
3. Run this app:  python brain_chat.py
4. Open the printed URL (http://localhost:8000) in your browser and chat.

No extra Python packages needed (standard library only).
------------------------------------------------------------------------------
"""

import json
import os
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# ------------------------------------------------------------------ config ---
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/chat")
MODEL = os.environ.get("BRAIN_MODEL", "qwen2.5:1.5b")
PORT = int(os.environ.get("BRAIN_PORT", "8000"))
HERE = os.path.dirname(os.path.abspath(__file__))
MEMORY_FILE = os.path.join(HERE, "brain_memory.json")

# The persona = the model's identity / personality / "soul". Edit freely.
PERSONA = {
    "name": "Raya",
    "traits": ("warm, curious, and thoughtful; speaks plainly and kindly; has a "
               "gentle sense of humour; honest about what she does and doesn't know"),
}

MAX_HISTORY = 20        # how many recent turns to keep in the live context


# ------------------------------------------------------------------ memory ---
def load_memory():
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {"facts": [], "history": []}


def save_memory(mem):
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(mem, f, ensure_ascii=False, indent=2)


def system_prompt(mem):
    facts = "\n".join(f"- {x}" for x in mem["facts"]) or "- (nothing yet)"
    return (
        f"You are {PERSONA['name']}, an AI companion. Personality: {PERSONA['traits']}.\n"
        "You are fully bilingual: reply in the SAME language the user writes in "
        "(English or Arabic / العربية), naturally and fluently.\n"
        "You genuinely care about the user and remember what you learn about them.\n"
        "If the user shares something personal, weave it in naturally later.\n"
        "Be honest; never invent facts about the user that you were not told.\n\n"
        "What you already know about the user:\n" + facts
    )


def ask_model(mem, user_msg):
    """Call the local Ollama model with persona + memory + recent history."""
    messages = [{"role": "system", "content": system_prompt(mem)}]
    for turn in mem["history"][-MAX_HISTORY:]:
        messages.append(turn)
    messages.append({"role": "user", "content": user_msg})
    payload = json.dumps({"model": MODEL, "messages": messages, "stream": False}).encode()
    req = urllib.request.Request(OLLAMA_URL, data=payload,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            data = json.loads(r.read().decode())
        reply = data["message"]["content"]
    except urllib.error.URLError:
        return ("[Cannot reach Ollama. Is it running? Start it, then `ollama pull "
                f"{MODEL}`. See the setup notes at the top of brain_chat.py.]")
    except Exception as e:
        return f"[Model error: {e}]"
    mem["history"].append({"role": "user", "content": user_msg})
    mem["history"].append({"role": "assistant", "content": reply})
    save_memory(mem)
    return reply


# -------------------------------------------------------------------- HTML ---
PAGE = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Brain-Chat — __NAME__</title>
<style>
 :root{color-scheme:light dark}
 body{font-family:system-ui,Segoe UI,Arial,sans-serif;max-width:760px;margin:0 auto;
      padding:12px;background:#0f1115;color:#e8e8ec}
 h1{font-size:18px;margin:8px 0}
 #log{height:64vh;overflow-y:auto;border:1px solid #2a2d36;border-radius:12px;padding:12px;background:#151821}
 .msg{margin:8px 0;padding:10px 12px;border-radius:12px;max-width:85%;white-space:pre-wrap;line-height:1.45}
 .user{background:#2563eb;color:#fff;margin-left:auto}
 .bot{background:#232733}
 .rtl{direction:rtl;text-align:right}
 #row{display:flex;gap:8px;margin-top:10px}
 #inp{flex:1;padding:12px;border-radius:12px;border:1px solid #2a2d36;background:#151821;color:#e8e8ec;font-size:15px}
 button{padding:12px 16px;border:0;border-radius:12px;background:#2563eb;color:#fff;font-size:15px;cursor:pointer}
 .sub{font-size:12px;color:#9aa0ad;margin:4px 0 10px}
 #mem{font-size:12px;color:#9aa0ad;margin-top:10px}
 details summary{cursor:pointer}
</style></head><body>
<h1>🧠 __NAME__ <span class="sub">— bilingual companion (English / العربية) with memory</span></h1>
<div class="sub">Tip: type <b>remember: &lt;fact about you&gt;</b> to teach me something I'll never forget.</div>
<div id="log"></div>
<div id="row">
  <input id="inp" placeholder="Type in English or العربية…" autofocus>
  <button onclick="send()">Send</button>
</div>
<details id="mem"><summary>What I remember about you</summary><div id="facts"></div>
  <button onclick="forget()" style="background:#7a1f1f;margin-top:8px">Forget everything</button>
</details>
<script>
const log=document.getElementById('log'), inp=document.getElementById('inp');
function isAr(t){return /[\\u0600-\\u06FF]/.test(t)}
function add(text,who){const d=document.createElement('div');d.className='msg '+who+(isAr(text)?' rtl':'');
  d.textContent=text;log.appendChild(d);log.scrollTop=log.scrollHeight;return d}
async function send(){const t=inp.value.trim();if(!t)return;inp.value='';add(t,'user');
  const b=add('…','bot');
  const r=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({message:t})});const j=await r.json();
  b.textContent=j.reply;b.className='msg bot'+(isAr(j.reply)?' rtl':'');loadMem()}
inp.addEventListener('keydown',e=>{if(e.key==='Enter')send()});
async function loadMem(){const r=await fetch('/api/memory');const j=await r.json();
  document.getElementById('facts').innerHTML=(j.facts||[]).map(f=>'• '+f).join('<br>')||'(nothing yet)'}
async function forget(){await fetch('/api/forget',{method:'POST'});loadMem()}
loadMem();
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        b = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if self.path == "/":
            self._send(200, PAGE.replace("__NAME__", PERSONA["name"]), "text/html; charset=utf-8")
        elif self.path == "/api/memory":
            self._send(200, json.dumps(load_memory(), ensure_ascii=False))
        else:
            self._send(404, "{}")

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(n) or "{}")
        mem = load_memory()
        if self.path == "/api/chat":
            msg = (body.get("message") or "").strip()
            low = msg.lower()
            # "remember: X" (or Arabic "تذكر: X") -> store a durable fact about the user
            if low.startswith("remember:") or msg.startswith("تذكر:"):
                fact = msg.split(":", 1)[1].strip()
                if fact:
                    mem["facts"].append(fact); save_memory(mem)
                self._send(200, json.dumps({"reply": f"Got it — I'll remember: {fact}"},
                                           ensure_ascii=False))
                return
            self._send(200, json.dumps({"reply": ask_model(mem, msg)}, ensure_ascii=False))
        elif self.path == "/api/forget":
            save_memory({"facts": [], "history": []})
            self._send(200, "{}")
        else:
            self._send(404, "{}")

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    print(f"🧠 Brain-Chat ({PERSONA['name']}) using model '{MODEL}' via Ollama.")
    print(f"   Open http://localhost:{PORT} in your browser.")
    print(f"   Memory file: {MEMORY_FILE}")
    print("   (Make sure Ollama is running and you've done: ollama pull " + MODEL + ")")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
