(()=>{
  "use strict";
  const $=id=>document.getElementById(id);
  const esc=v=>String(v??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const n=(v,d=3)=>Number.isFinite(Number(v))?Number(v).toFixed(d):"—";

  function style(){
    if($("v141GeometryStyle"))return;
    const s=document.createElement("style");
    s.id="v141GeometryStyle";
    s.textContent=`
      #v141GeometryStrip{display:grid;grid-template-columns:repeat(auto-fit,minmax(135px,1fr));gap:5px;margin:7px 0}
      #v141GeometryStrip div{border:1px solid #24546b;background:#071a23;border-radius:5px;padding:6px;font-size:8px}
      #v141GeometryStrip span{display:block;color:#86acba}#v141GeometryStrip b{display:block;color:#e5f8ff;margin-top:2px;overflow-wrap:anywhere}
      .v141-on{color:#7df4ae!important}.v141-warn{color:#ffd47d!important}.v141-off{color:#ff9f9f!important}
    `;
    document.head.appendChild(s);
  }

  async function j(url){const r=await fetch(url,{cache:'no-store'});if(!r.ok)throw new Error(String(r.status));return await r.json()}
  async function read(){try{apply(await j('/api/v14.1/execution-trace?symbol=BTC'))}catch{}}

  function apply(trace){
    style();
    const desk=$("paperDeskV4");
    if(!desk)return;
    let strip=$("v141GeometryStrip");
    if(!strip){strip=document.createElement('div');strip.id='v141GeometryStrip';const target=desk.querySelector('.decision-wrap');if(target)target.prepend(strip)}
    const best=trace?.best_sample||{};
    const d=best?.decision||{};
    const g=best?.risk_geometry||{};
    const s=best?.sizing||{};
    const stages=best?.stages||{};
    const geometryReady=Boolean(stages.RISK_MODEL_BUILT);
    const actionReady=Boolean(stages.ACTIONABLE);
    const sizeReady=Boolean(stages.SIZE_PLANNED);
    const state=sizeReady?'SIZE READY':actionReady?'ACTIONABLE':geometryReady?'GEOMETRY READY':'BLOCKED';
    const stateClass=sizeReady||actionReady?'v141-on':geometryReady?'v141-warn':'v141-off';
    strip.innerHTML=`
      <div><span>V14.1 BTC PIPELINE</span><b class="${stateClass}">${esc(state)}</b></div>
      <div><span>BEST PROFILE</span><b>${esc(best.profile||'—')}</b></div>
      <div><span>DIRECTION</span><b>${esc(best.candidate_side||'—')}</b></div>
      <div><span>RISK GEOMETRY</span><b class="${geometryReady?'v141-on':'v141-off'}">${esc(g.state|| (geometryReady?'VALID':'UNAVAILABLE'))}</b></div>
      <div><span>ENTRY / STOP / TARGET</span><b>${n(best.entry,2)} / ${n(best.stop,2)} / ${n(best.target,2)}</b></div>
      <div><span>EV / ACTION</span><b>${n(d.expected_value_r)}R · ${esc(d.action||'WAIT')}</b></div>
      <div><span>LEGACY SCORE</span><b>${esc(best.legacy_score??'—')} OBS</b></div>
      <div><span>SIZE PLAN</span><b class="${sizeReady?'v141-on':'v141-warn'}">${sizeReady?esc(s.quantity??'READY'):'NOT READY'}</b></div>
      <div><span>PIPELINE STOP REASON</span><b class="${best.pipeline_stop_reason==='READY_FOR_PAPER_DESK_OPEN'?'v141-on':'v141-warn'}">${esc(best.pipeline_stop_reason||'—')}</b></div>
      <div><span>DATA PASS ≠ EXECUTION PASS</span><b class="v141-on">EXPLICIT</b></div>
      <div><span>INVALID_RISK_LEVELS</span><b class="v141-on">HARD ONLY IF GEOMETRY UNAVAILABLE</b></div>
      <div><span>LIVE BROKER</span><b class="v141-on">LOCKED</b></div>`;
    window.JARVIS_V141_RISK_GEOMETRY_STATE=trace;
  }

  function boot(){read();setInterval(read,3000)}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot);else boot();
})();
