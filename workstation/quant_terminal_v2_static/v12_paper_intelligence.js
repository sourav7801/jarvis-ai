(()=>{
  "use strict";
  const $=id=>document.getElementById(id);
  const esc=v=>String(v??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const num=(v,d=2)=>Number.isFinite(Number(v))?Number(v).toFixed(d):"—";
  const pct=v=>Number.isFinite(Number(v))?(Number(v)*100).toFixed(0)+"%":"—";
  let last=null;

  function installStyle(){
    if($("v12PaperIntelligenceStyle"))return;
    const s=document.createElement("style");s.id="v12PaperIntelligenceStyle";s.textContent=`
      #v12AdaptiveDecisionSummary{margin:8px 0 2px;display:grid;gap:5px}
      #v12AdaptiveDecisionSummary .v12-ad-row{display:grid;grid-template-columns:minmax(0,1.2fr) repeat(4,minmax(0,.8fr));gap:5px;border:1px solid #153746;border-radius:6px;background:#07141c;padding:6px;font-size:8px;min-width:0}
      #v12AdaptiveDecisionSummary .v12-ad-row b{font-size:9px;color:#d8f3ff;overflow-wrap:anywhere}#v12AdaptiveDecisionSummary .v12-ad-row span{color:#7ca3b1;overflow-wrap:anywhere}
      #v12AdaptiveDecisionSummary .primary{color:#78f2aa}.probe{color:#ffd27a}.wait{color:#ff9aa2}
      #paperDeskV4.paper-narrow #v12AdaptiveDecisionSummary .v12-ad-row{grid-template-columns:1fr 1fr}
      @container (max-width:520px){#v12AdaptiveDecisionSummary .v12-ad-row{grid-template-columns:1fr 1fr}}
    `;document.head.appendChild(s);
  }

  async function read(){
    try{const r=await fetch("/api/paper/portfolio-controller",{cache:"no-store"});const p=await r.json();if(r.ok&&p?.success){last=p;apply(p)}}catch{}
  }

  function mandate(key,p){
    const status=p?.mandates?.[key]||{},f=status.last_scan_funnel||{},stats=$(`mandateStats${key}`);if(!stats)return;
    const legacyScore=status.min_score==null?"—":Number(status.min_score).toFixed(0);
    const legacyRR=status.min_risk_reward==null?"—":Number(status.min_risk_reward).toFixed(1);
    const adaptive=f.adaptive_executable??f.qualified??0,primary=f.adaptive_primary??0,probe=f.adaptive_probe??0;
    stats.innerHTML=`
      <div class="mandate-stat">AUTHORITY<b>ADAPTIVE EV</b></div>
      <div class="mandate-stat">LEGACY GATES<b>${esc(legacyScore)} / ${esc(legacyRR)} OBS</b></div>
      <div class="mandate-stat">WATCH<b>${Array.isArray(status.universe)?status.universe.length:0}</b></div>
      <div class="mandate-stat">SCANNED<b>${Number(f.scanned||0)}</b></div>
      <div class="mandate-stat">ADAPTIVE<b>${Number(adaptive||0)}</b></div>
      <div class="mandate-stat">PRIMARY / PROBE<b>${Number(primary||0)} / ${Number(probe||0)}</b></div>
      <div class="mandate-stat">OPENED<b>${Number(f.opened||0)}</b></div>
      <div class="mandate-stat">RUNTIME<b>${status.running?"RUNNING":"STOPPED"}</b></div>`;
  }

  function summary(p){
    const wrap=document.querySelector("#paperDeskV4 .decision-wrap");if(!wrap)return;
    let host=$("v12AdaptiveDecisionSummary");if(!host){host=document.createElement("div");host.id="v12AdaptiveDecisionSummary";const funnel=$("paperDecisionFunnel");if(funnel)wrap.insertBefore(host,funnel);else wrap.appendChild(host)}
    const rows=(p.decision_board||[]).filter(r=>r.adaptive_action||r.adaptive_expected_value_r!=null).slice(0,8);
    host.innerHTML=rows.length?rows.map(r=>{const a=String(r.adaptive_action||"WAIT").toUpperCase(),cls=a==="PRIMARY"?"primary":a==="PROBE"?"probe":"wait";return `<div class="v12-ad-row"><b>${esc(r.symbol)} · ${esc(r.mandate)}${r.lane?" · "+esc(r.lane):""}</b><span class="${cls}">${esc(a)}</span><span>EV ${esc(num(r.adaptive_expected_value_r,3))}R</span><span>CONF ${esc(pct(r.adaptive_confidence))}</span><span>LEGACY ${esc(r.execution_score??"—")}</span></div>`}).join(""):'<div class="decision-empty">Adaptive engine has no recent evaluated rows yet.</div>';
  }

  function apply(p){
    installStyle();
    const eyebrow=document.querySelector("#paperDeskV4 > .eyebrow");if(eyebrow)eyebrow.textContent="JARVIS PAPER PORTFOLIO · V12 ADAPTIVE EXPECTED VALUE";
    const contract=document.querySelector("#paperDeskV4 .decision-head span");if(contract)contract.textContent="DISCOVERY SCORE ≠ EXECUTION AUTHORITY · 67/68/70 = OBSERVABILITY ONLY";
    ["INTRADAY","SWING","INVESTMENT"].forEach(k=>mandate(k,p));
    summary(p);
  }

  const observer=new MutationObserver(()=>{if(last)apply(last)});function boot(){const desk=$("paperDeskV4");if(desk){observer.observe(desk,{childList:true,subtree:true});read();setInterval(read,3500)}else setTimeout(boot,500)}boot();
})();
