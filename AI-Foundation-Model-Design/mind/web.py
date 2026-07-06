"""
The Mind — browser chat.  Run this, open the URL, and talk to The Mind in your
browser (English + العربية). No Ollama, no external model — it runs entirely on the
local verified reasoning engine + memory.

    python web.py
    → open http://localhost:8100

Standard library only. Your memory/library live in mind_memory.json / knowledge.json.
"""

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from reasoner import Mind, KB_FILE
from talk import reply

PORT = int(os.environ.get("MIND_PORT", "8100"))
MIND = Mind()

PAGE = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>The Mind</title>
<style>
 :root{color-scheme:light dark}
 *{box-sizing:border-box}
 body{font-family:system-ui,Segoe UI,Arial,sans-serif;max-width:780px;margin:0 auto;
      padding:12px;background:#0f1115;color:#e8e8ec}
 h1{font-size:18px;margin:6px 0}
 .sub{font-size:12px;color:#9aa0ad;margin:2px 0 10px}
 #log{height:62vh;overflow-y:auto;border:1px solid #2a2d36;border-radius:12px;padding:12px;background:#151821}
 .msg{margin:8px 0;padding:10px 12px;border-radius:12px;max-width:88%;white-space:pre-wrap;line-height:1.45}
 .user{background:#2563eb;color:#fff;margin-left:auto}
 .bot{background:#232733}
 .rtl{direction:rtl;text-align:right}
 .tag{font-size:11px;color:#8b93a7;margin-top:4px}
 .ok{color:#3fb950}.no{color:#d29922}
 #row{display:flex;gap:8px;margin-top:10px}
 #inp{flex:1;padding:12px;border-radius:12px;border:1px solid #2a2d36;background:#151821;color:#e8e8ec;font-size:15px}
 button{padding:12px 16px;border:0;border-radius:12px;background:#2563eb;color:#fff;font-size:15px;cursor:pointer}
 details{margin-top:10px;font-size:12px;color:#9aa0ad}
 details summary{cursor:pointer}
</style></head><body>
<h1>🧠 <span id="who">Vio</span> <span class="sub">— your local assistant · reasons &amp; verifies · English / العربية</span></h1>
<div class="sub">Try: <b>solve x+y=10, x-y=2</b> · <b>15% of 200</b> · <b>average of 4,8,15,16</b> · <b>5 km to miles</b> ·
 <b>integrate 1/x</b> · <b>remember that my name is Mazin</b> · <b>teach: &lt;paste a paragraph&gt;</b> · <b>what time is it in KSA</b></div>
<div id="log"></div>
<div id="row"><input id="inp" placeholder="Ask, or tell me a fact… (English or العربية)" autofocus>
  <button onclick="send()">Send</button>
  <button onclick="document.getElementById('file').click()" title="Teach me from a .txt/.md file"
    style="background:#334155">📄</button>
  <input type="file" id="file" accept=".txt,.md,.text,.csv,.log" style="display:none" onchange="upload()"></div>
<details><summary>What I remember / have learned</summary><div id="mem"></div>
  <button onclick="forget()" style="background:#7a1f1f;margin-top:8px">Forget everything</button></details>
<script>
const log=document.getElementById('log'),inp=document.getElementById('inp');
const isAr=t=>/[\\u0600-\\u06FF]/.test(t);
function add(t,who,tag){const d=document.createElement('div');d.className='msg '+who+(isAr(t)?' rtl':'');
 d.textContent=t;if(tag){const s=document.createElement('div');s.className='tag';s.innerHTML=tag;d.appendChild(s);}
 log.appendChild(d);log.scrollTop=log.scrollHeight;return d}
async function send(){const t=inp.value.trim();if(!t)return;inp.value='';add(t,'user');
 const r=await fetch('/api/ask',{method:'POST',headers:{'Content-Type':'application/json'},
   body:JSON.stringify({message:t})});const j=await r.json();
 const badge=(j.verified?'<span class="ok">✓ verified</span>':'<span class="no">… unverified</span>')+' · '+j.how;
 add(j.answer,'bot',badge);loadMem()}
inp.addEventListener('keydown',e=>{if(e.key==='Enter')send()});
async function upload(){const f=document.getElementById('file').files[0];if(!f)return;
 add('📄 Learning from '+f.name+' …','user');const text=await f.text();
 const j=await(await fetch('/api/learn',{method:'POST',headers:{'Content-Type':'application/json'},
   body:JSON.stringify({name:f.name,text})})).json();
 add(j.answer,'bot','<span class="ok">✓</span> · learned from file');loadMem();
 document.getElementById('file').value=''}
async function loadMem(){const j=await(await fetch('/api/memory')).json();
 if(j.name){document.getElementById('who').textContent=j.name;document.title=j.name;}
 document.getElementById('mem').innerHTML=
  '<b>About you:</b><br>'+((j.facts||[]).map(f=>'• '+f).join('<br>')||'(nothing yet)')+
  '<br><br><b>Library:</b><br>'+((j.library||[]).map(d=>'• '+d).join('<br>')||'(empty)')}
async function forget(){await fetch('/api/forget',{method:'POST'});loadMem();
 log.innerHTML='';add('Memory and library cleared.','bot')}
loadMem();
</script></body></html>"""


class H(BaseHTTPRequestHandler):
    def _s(self, code, body, ctype="application/json"):
        b = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code); self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

    def do_GET(self):
        if self.path == "/":
            self._s(200, PAGE, "text/html; charset=utf-8")
        elif self.path == "/api/memory":
            lib = json.load(open(KB_FILE, encoding="utf-8")) if os.path.exists(KB_FILE) else []
            self._s(200, json.dumps({"name": MIND.name(), "facts": MIND.mem["facts"],
                                     "library": lib}, ensure_ascii=False))
        else:
            self._s(404, "{}")

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(n) or "{}")
        if self.path == "/api/ask":
            r = reply(MIND, (body.get("message") or "").strip())
            self._s(200, json.dumps(r, ensure_ascii=False))
        elif self.path == "/api/learn":
            msg = MIND.learn_text(body.get("text") or "", body.get("name") or "a file")
            self._s(200, json.dumps({"answer": msg}, ensure_ascii=False))
        elif self.path == "/api/forget":
            MIND.mem = {"facts": [], "solved": {}}; MIND._save()
            if os.path.exists(KB_FILE):
                os.remove(KB_FILE)
            MIND.lib.docs = []; MIND.lib.vec = None
            self._s(200, "{}")
        else:
            self._s(404, "{}")

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    import threading
    import webbrowser
    url = f"http://localhost:{PORT}"
    print(f"🧠 {MIND.name()} is starting — opening {url} in your browser...")
    print("   Runs entirely locally (verified reasoning + memory). No external model.")
    print("   Keep this window open while you chat; close it to stop Vio.")
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()   # auto-open the browser
    try:
        ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
    except KeyboardInterrupt:
        pass
