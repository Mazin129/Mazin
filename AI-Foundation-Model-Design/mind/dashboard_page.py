"""
dashboard_page  —  Vio's live Cognitive Dashboard (served at /dashboard).

A visual view of the CORTEX-OS architecture and live telemetry from the running brain:
the module map, the calibration reliability plot, memory tiers, System-1/2 split, answer
quality, domain usage, the confidence histogram, and the curiosity wishlist. Reads real
numbers from /api/telemetry — it grows as you use Vio. Self-contained (inline SVG, no
libraries), theme-aware.
"""

DASHBOARD = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Vio — Cognitive Dashboard</title>
<style>
 :root{--bg:#0a0d14;--panel:#141b28;--panel2:#0f151f;--line:#26314a;--ink:#e7ecf3;--dim:#8b97ad;
   --accent:#5b8cff;--violet:#9d84ff;--ok:#37d67a;--warn:#f4b740;--bad:#f0687f;--grid:#26314a;
   --mono:ui-monospace,"SF Mono",Menlo,Consolas,monospace;--sans:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;}
 @media(prefers-color-scheme:light){:root{--bg:#eef1f7;--panel:#fff;--panel2:#f5f7fc;--line:#dbe2ee;
   --ink:#141a24;--dim:#586377;--accent:#3f6ef5;--violet:#7c5cff;--ok:#129d5a;--warn:#c9871a;--bad:#d64562;--grid:#e4e9f2;}}
 *{box-sizing:border-box}
 body{margin:0;background:radial-gradient(1000px 560px at 85% -10%,color-mix(in srgb,var(--violet) 14%,transparent),transparent 60%),var(--bg);
   color:var(--ink);font-family:var(--sans);line-height:1.5}
 .wrap{max-width:1080px;margin:0 auto;padding:26px 20px 60px}
 header{display:flex;align-items:center;gap:12px;margin-bottom:6px}
 .logo{width:34px;height:34px;border-radius:10px;display:grid;place-items:center;font-size:18px;
   background:linear-gradient(135deg,var(--accent),var(--violet))}
 h1{font-size:20px;margin:0;letter-spacing:-.01em}
 .sub{font-size:12px;color:var(--dim);font-family:var(--mono)}
 .refresh{margin-left:auto;border:1px solid var(--line);background:var(--panel);color:var(--ink);
   border-radius:9px;padding:7px 12px;font-size:13px;cursor:pointer}
 .refresh:hover{border-color:var(--accent)}
 .tiles{display:grid;grid-template-columns:repeat(6,1fr);gap:12px;margin:20px 0}
 @media(max-width:820px){.tiles{grid-template-columns:repeat(3,1fr)}}
 @media(max-width:480px){.tiles{grid-template-columns:repeat(2,1fr)}}
 .tile{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:13px 14px}
 .tile .v{font-size:24px;font-weight:700;font-variant-numeric:tabular-nums;letter-spacing:-.02em}
 .tile .l{font-size:11px;color:var(--dim);margin-top:2px;text-transform:uppercase;letter-spacing:.06em}
 .grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}
 @media(max-width:820px){.grid{grid-template-columns:1fr}}
 .card{background:var(--panel);border:1px solid var(--line);border-radius:16px;padding:16px 18px}
 .card.full{grid-column:1/-1}
 .card h2{font-size:13px;margin:0 0 3px;letter-spacing:.02em}
 .card .cap{font-size:12px;color:var(--dim);margin:0 0 14px}
 svg{display:block;width:100%;overflow:visible}
 .axis{stroke:var(--grid);stroke-width:1}
 .gridln{stroke:var(--grid);stroke-width:1;stroke-dasharray:2 4;opacity:.6}
 .lbl{fill:var(--dim);font-size:11px;font-family:var(--mono)}
 .val{fill:var(--ink);font-size:11px;font-family:var(--mono);font-weight:600}
 .empty{color:var(--dim);font-size:13px;padding:24px 4px;text-align:center}
 /* architecture map */
 .flow{display:flex;flex-direction:column;gap:8px}
 .lane{display:flex;gap:8px;flex-wrap:wrap;align-items:stretch}
 .mod{flex:1;min-width:96px;background:var(--panel2);border:1px solid var(--line);border-radius:10px;
   padding:9px 10px;position:relative}
 .mod .n{font-size:12.5px;font-weight:600}
 .mod .m{font-size:11px;color:var(--dim);font-family:var(--mono);margin-top:2px}
 .mod.hl{border-color:color-mix(in srgb,var(--accent) 55%,var(--line))}
 .arrowdn{text-align:center;color:var(--dim);font-size:13px;line-height:1}
 .legend{display:flex;gap:14px;flex-wrap:wrap;font-size:12px;color:var(--dim);margin-top:10px}
 .legend b{color:var(--ink)}
 .dot{display:inline-block;width:9px;height:9px;border-radius:2px;margin-right:5px;vertical-align:middle}
 .wish{font-size:13px;color:var(--dim);line-height:1.7}
 .wish b{color:var(--ink)}
 .foot{margin-top:26px;font-size:12px;color:var(--dim);font-family:var(--mono)}
 a{color:var(--accent)}
</style></head><body>
<div class="wrap">
 <header>
  <div class="logo">🧠</div>
  <div><h1 id="who">Vio — Cognitive Dashboard</h1>
    <div class="sub">live view of the CORTEX-OS brain · <span id="ts"></span></div></div>
  <button class="refresh" onclick="load()">↻ Refresh</button>
 </header>

 <div class="tiles" id="tiles"></div>

 <div class="card full">
  <h2>Cognitive architecture</h2>
  <p class="cap">A question flows top→bottom; numbers are live counts from this brain.</p>
  <div class="flow" id="arch"></div>
 </div>

 <div class="grid" style="margin-top:16px">
  <div class="card">
   <h2>Confidence calibration</h2>
   <p class="cap">Are the “% sure” numbers honest? Points on the dashed line = perfectly
     calibrated. Above = underconfident, below = overconfident. Grade answers 👍/👎 to fill this in.</p>
   <div id="calib"></div>
  </div>
  <div class="card">
   <h2>Answer confidence</h2>
   <p class="cap">How sure Vio has been, across all answers.</p>
   <div id="hist"></div>
  </div>
  <div class="card">
   <h2>Memory tiers</h2>
   <p class="cap">What Vio is holding, by store.</p>
   <div id="tiers2"></div>
  </div>
  <div class="card">
   <h2>Answer quality</h2>
   <p class="cap">How answers resolved.</p>
   <div id="quality"></div>
  </div>
  <div class="card">
   <h2>Fast vs. deliberate</h2>
   <p class="cap">System-1 (instant, verified) vs System-2 (deliberated).</p>
   <div id="systems"></div>
  </div>
  <div class="card">
   <h2>Domains &amp; curiosity</h2>
   <p class="cap">Where questions land, and what Vio most wants to learn.</p>
   <div id="domains"></div>
   <div class="wish" id="wish" style="margin-top:12px"></div>
  </div>
 </div>
 <div class="foot">Served locally by Vio · <a href="/">← back to chat</a></div>
</div>

<script>
const $=id=>document.getElementById(id);
const esc=s=>(''+s).replace(/&/g,'&amp;').replace(/</g,'&lt;');
const css=v=>getComputedStyle(document.documentElement).getPropertyValue(v).trim();

function tile(v,l){return `<div class="tile"><div class="v">${v}</div><div class="l">${l}</div></div>`}

function hbar(el,rows,{unit='',color='--accent',max=null}={}){
 // rows: [{label, value}]  single-hue horizontal bars, direct value labels
 if(!rows.length){el.innerHTML='<div class="empty">No data yet — use Vio, then refresh.</div>';return}
 const m=max||Math.max(...rows.map(r=>r.value),1), W=100, rowH=30, pad=4;
 const h=rows.length*rowH+pad*2, labW=34;
 let s=`<svg viewBox="0 0 100 ${h}" preserveAspectRatio="none" style="height:${h}px">`;
 rows.forEach((r,i)=>{const y=pad+i*rowH+7, bw=(r.value/m)*(100-labW-16);
   s+=`<rect x="${labW}" y="${y}" width="${Math.max(bw,0.5)}" height="12" rx="3" fill="var(${color})"/>`;});
 s+=`</svg>`;
 // overlay labels via HTML for crisp text
 let ov=`<div style="position:relative">${s}<div style="position:absolute;inset:0">`;
 rows.forEach((r,i)=>{const top=(pad+i*rowH+2)/h*100;
   ov+=`<div style="position:absolute;left:0;top:${top}%;font:600 11px var(--mono);color:var(--dim)">${esc(r.label)}</div>`;
   const bw=(r.value/m)*(100-labW-16);
   ov+=`<div style="position:absolute;left:calc(${labW}% + ${bw}% + 4px);top:${top}%;font:600 11px var(--mono);color:var(--ink);white-space:nowrap">${r.value}${unit}</div>`;});
 ov+=`</div></div>`;
 el.innerHTML=ov;
}

function calib(el,rel,scalar){
 if(!rel.length){el.innerHTML='<div class="empty">No graded answers yet.<br>Mark answers 👍/👎 in chat, then refresh.</div>';return}
 const S=300,P=34;
 const X=v=>P+v*(S-P-8), Y=v=>(S-P)-v*(S-P-8);
 let g='';for(let t=0;t<=10;t+=2){const p=t/10;
   g+=`<line class="gridln" x1="${X(p)}" y1="${Y(0)}" x2="${X(p)}" y2="${Y(1)}"/>`;
   g+=`<line class="gridln" x1="${X(0)}" y1="${Y(p)}" x2="${X(1)}" y2="${Y(p)}"/>`;
   g+=`<text class="lbl" x="${X(p)}" y="${S-P+16}" text-anchor="middle">${t*10}</text>`;
   g+=`<text class="lbl" x="${P-8}" y="${Y(p)+4}" text-anchor="end">${t*10}</text>`;}
 const diag=`<line x1="${X(0)}" y1="${Y(0)}" x2="${X(1)}" y2="${Y(1)}" stroke="var(--dim)" stroke-width="2" stroke-dasharray="4 4" opacity=".7"/>`;
 let pts='';rel.forEach(r=>{const rad=6+Math.min(r.n,8);
   pts+=`<circle cx="${X(r.stated)}" cy="${Y(r.accuracy)}" r="${Math.min(rad,12)}" fill="var(--accent)" fill-opacity=".25" stroke="var(--accent)" stroke-width="2"/>`;
   pts+=`<text class="val" x="${X(r.stated)}" y="${Y(r.accuracy)-Math.min(rad,12)-4}" text-anchor="middle">${Math.round(r.accuracy*100)}%</text>`;});
 el.innerHTML=`<svg viewBox="0 0 ${S} ${S+6}" style="max-width:340px;margin:0 auto">${g}${diag}${pts}
   <text class="lbl" x="${S/2}" y="${S+2}" text-anchor="middle">stated confidence →</text></svg>
   <div class="legend"><span><span class="dot" style="background:var(--accent)"></span>observed accuracy</span>
   <span>correction ×${scalar.toFixed(2)}</span></div>`;
}

function statusBars(el,rows){
 // rows: [{label, value, color, icon}] — status colors WITH label+icon (secondary encoding)
 const tot=rows.reduce((a,r)=>a+r.value,0);
 if(!tot){el.innerHTML='<div class="empty">No data yet.</div>';return}
 let bar='<div style="display:flex;height:16px;border-radius:6px;overflow:hidden;gap:2px;background:var(--panel2)">';
 rows.forEach(r=>{if(r.value)bar+=`<div style="flex:${r.value};background:var(${r.color})"></div>`});
 bar+='</div>';
 let leg='<div class="legend" style="margin-top:12px">';
 rows.forEach(r=>{if(r.value)leg+=`<span><span class="dot" style="background:var(${r.color})"></span>${r.icon||''} <b>${esc(r.label)}</b> ${r.value}</span>`});
 leg+='</div>';
 el.innerHTML=bar+leg;
}

async function load(){
 let d;try{d=await(await fetch('/api/telemetry')).json()}catch(e){return}
 $('who').textContent=d.name+' — Cognitive Dashboard';
 $('ts').textContent=new Date().toLocaleTimeString();
 const t=d.tiers;
 $('tiles').innerHTML=
   tile(t.episodic,'Memories')+tile(t.semantic,'Passages')+tile(d.graph.edges,'Graph edges')+
   tile(d.gaps,'Open gaps')+tile('×'+d.calibration.scalar.toFixed(2),'Conf. correction')+
   tile(d.vocab,'Vocabulary');

 // architecture map with live counts
 const A=[
  [['Attention','filters input']],
  [['Executive','two-clock router']],
  [['Working mem',t.working+' slots'],['Semantic',t.semantic+' passages'],['Episodic',t.episodic+' memories'],['Procedural',t.procedural+' skills']],
  [['Reasoning','graph · rules'],['World model',d.graph.edges+' causal'],['Planner','grounded steps']],
  [['Confidence','×'+d.calibration.scalar.toFixed(2)],['Self-critic','conflict · re-search']],
  [['Language','grounded realizer'],['Learning','+ consolidation']],
 ];
 $('arch').innerHTML=A.map((lane,i)=>{
   const row='<div class="lane">'+lane.map(m=>`<div class="mod ${i<2?'hl':''}"><div class="n">${m[0]}</div><div class="m">${esc(m[1]||'')}</div></div>`).join('')+'</div>';
   return row+(i<A.length-1?'<div class="arrowdn">▼</div>':'');
 }).join('');

 calib($('calib'),d.calibration.reliability,d.calibration.scalar);

 hbar($('hist'),d.confidence_hist.filter(h=>h.n).map(h=>({label:h.band+'%',value:h.n})));
 hbar($('tiers2'),[
   {label:'Sem',value:t.semantic},{label:'Epi',value:t.episodic},
   {label:'Proc',value:t.procedural},{label:'WM',value:t.working}]);

 const q=d.quality||{};
 statusBars($('quality'),[
   {label:'solved',value:q.solved||0,color:'--ok',icon:'✓'},
   {label:'answered',value:q.answered||0,color:'--accent',icon:'•'},
   {label:'learned',value:q.learned||0,color:'--violet',icon:'✎'},
   {label:'correct',value:q.correct||0,color:'--ok',icon:'👍'},
   {label:'wrong',value:q.wrong||0,color:'--bad',icon:'👎'},
   {label:'unknown',value:q.unknown||0,color:'--warn',icon:'?'}]);

 const sy=d.systems||{};
 statusBars($('systems'),[
   {label:'System 1 (fast)',value:sy['System 1']||0,color:'--accent',icon:'⚡'},
   {label:'System 2 (deliberate)',value:sy['System 2']||0,color:'--violet',icon:'🧠'}]);

 const dm=Object.entries(d.domains||{});
 hbar($('domains'),dm.map(([k,v])=>({label:k.slice(0,4),value:v})));
 const wl=d.wishlist||[];
 $('wish').innerHTML=wl.length?('<b>Wants to learn:</b> '+wl.map(w=>esc(w.topic)+` (${w.count}×)`).join(', ')):'';
}
load();
</script></body></html>"""
