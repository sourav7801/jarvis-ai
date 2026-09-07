(()=>{
  "use strict";
  const $=id=>document.getElementById(id);
  const esc=v=>String(v??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const num=(v,d=2)=>Number.isFinite(Number(v))?Number(v).toFixed(d):"—";
  const pct=v=>Number.isFinite(Number(v))?(Number(v)*100).toFixed(1)+"%":"—";
  let last=null,fetching=false,rendering=false;

  function style(){
    if($("v12PaperIntelligenceStyle"))return;
    const s=document.createElement("style");s.id="v12PaperIntelligenceStyle";s.textContent=`
      #paperDeskV4 .v12-authority{display:flex;gap:7px;align-items:center;flex-wrap:wrap;margin:8px 0 3px;padding:7px;border:1px solid #245266;border-radius:7px;background:#071922;font-size:9px;color:#86aab8}#paperDeskV4 .v12-authority b{color:#80e9ff;letter-spacing:.06em}
      #paperDeskV4 .v12-primary{color:#78f2aa}.v12-probe{color:#ffd27a}.v12-wait{color:#ff9aa2}
      #paperDeskV4 .v12-evidence{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:5px;margin-top:7px}#paperDeskV4 .v12-evidence div{border:1px solid #12313d;border-radius:5px;padding:5px;min-width:0}#paperDeskV4 .v12-evidence span{display:block;color:#678d9c;font-size:8px}#paperDeskV4 .v12-evidence b{display:block;color:#d8f4ff;font-size:9px;margin-top:2px;overflow-wrap:anywhere}
      #paperDeskV4.paper-narrow .v12-evidence{grid-template-columns:1fr 1fr}@container (max-width:520px){#paperDeskV4 .v12-evidence{grid-template-columns:1fr 1fr}}
    `;document.head.appendChild(s);
  }
  function actionClass(a){a=String(a||"WAIT").toUpperCase();return a==="PRIMARY"?"v12-primary":a==="PROBE"?"v12-probe":"v12-wait"}
  function activeFilter(group,def="ALL"){const b=document.querySelector(`${group} button.active`);return String(b?.dataset?.filter||def).toUpperCase()}

  function mandate(key,p){
    const status=p?.mandates?.[key]||{},f=status.last_scan_funnel||{},stats=$(`mandateStats${key}`);if(!stats)return;
    const legacyScore=status.min_score==null?"—":Number(status.min_score).toFixed(0),watch=Array.isArray(status.universe)?status.universe.length:0;
    const laneNames=status?.lanes?Object.entries(status.lanes).filter(([,v])=>v?.running).map(([name])=>name).join(" / "):"";
    stats.innerHTML=`
      <div class="mandate-stat">AUTHORITY<b>ADAPTIVE EV</b></div><div class="mandate-stat">LEGACY SCORE<b>${esc(legacyScore)} · OBS ONLY</b></div>
      <div class="mandate-stat">WATCH<b>${watch}</b></div><div class="mandate-stat">SCANNED<b>${Number(f.scanned||0)}</b></div>
      <div class="mandate-stat">PRIMARY<b>${Number(f.adaptive_primary||0)}</b></div><div class="mandate-stat">PROBE<b>${Number(f.adaptive_probe||0)}</b></div>
      <div class="mandate-stat">ADAPTIVE EDGE<b>${Number(f.adaptive_executable||0)}</b></div><div class="mandate-stat">OPENED<b>${Number(status.positions_opened??f.opened??0)}</b></div>
      ${laneNames?`<div class="mandate-stat" style="grid-column:1/-1">ACTIVE LANES<b>${esc(laneNames)}</b></div>`:""}`;
  }

  function board(p){
    const host=$("paperDecisionBoard");if(!host)return;
    const all=Array.isArray(p?.decision_board)?p.decision_board:[],mf=activeFilter("#paperMandateFilters"),sf=activeFilter("#paperStateFilters");
    const rows=all.filter(r=>{const m=String(r.mandate||"").toUpperCase(),ok=Boolean(r.qualified);return (mf==="ALL"||m===mf)&&(sf==="ALL"||(sf==="QUALIFIED"&&ok)||(sf==="BLOCKED"&&!ok))});
    const funnel=$("paperDecisionFunnel");if(funnel){const primary=all.filter(r=>String(r.adaptive_action||"").toUpperCase()==="PRIMARY").length,probe=all.filter(r=>String(r.adaptive_action||"").toUpperCase()==="PROBE").length,wait=all.filter(r=>!r.qualified).length;funnel.innerHTML=`<div><span>SCANNED</span><b>${all.length}</b></div><div><span>PRIMARY</span><b>${primary}</b></div><div><span>PROBE</span><b>${probe}</b></div><div><span>WAIT</span><b>${wait}</b></div>`}
    if(!rows.length){host.innerHTML='<div class="decision-empty">No adaptive decisions match the selected filters.</div>';return}
    host.innerHTML=rows.slice(0,30).map(r=>{const action=String(r.adaptive_action||r.decision||(r.qualified?"PRIMARY":"WAIT")).toUpperCase(),hard=Array.isArray(r.hard_blockers)?r.hard_blockers:(Array.isArray(r.blockers)?r.blockers:[]),soft=Array.isArray(r.soft_evidence)?r.soft_evidence:[];return `<article class="decision-card"><div class="decision-card-head"><strong>${esc(r.symbol||"UNKNOWN")}</strong><em class="${actionClass(action)}">${esc(action)}</em></div><div class="decision-meta">${esc(r.mandate||"UNROUTED")}${r.lane?` · ${esc(r.lane)}`:""} · 67/68/70 OBSERVABILITY ONLY</div><div class="v12-evidence"><div><span>LEGACY SCORE</span><b>${esc(num(r.execution_score,1))}</b></div><div><span>EXPECTED VALUE</span><b>${esc(num(r.adaptive_expected_value_r,3))}R</b></div><div><span>CONFIDENCE</span><b>${esc(pct(r.adaptive_confidence))}</b></div><div><span>RISK</span><b>×${esc(num(r.adaptive_risk_multiplier,2))}</b></div></div><div class="decision-reason"><b>HARD BLOCKERS</b><br>${hard.length?esc(hard.join(" · ")):"NONE"}</div><div class="decision-next"><b>SOFT / CONTRADICTORY EVIDENCE</b><br>${soft.length?esc(soft.join(" · ")):"NONE"}</div></article>`}).join("");
  }

  function apply(p){
    if(rendering)return;rendering=true;try{style();const root=$("paperDeskV4");if(!root)return;const eyebrow=root.querySelector(":scope > .eyebrow");if(eyebrow)eyebrow.textContent="JARVIS PAPER PORTFOLIO · V12 ADAPTIVE EXPECTED VALUE";let authority=root.querySelector(".v12-authority");if(!authority){authority=document.createElement("div");authority.className="v12-authority";const grid=root.querySelector(".mandate-grid");grid?.parentNode?.insertBefore(authority,grid)}authority.innerHTML='<b>ADAPTIVE EV AUTHORITY</b><span>67/68/70 scores and legacy R:R thresholds are observations, not binary entry gates. Data, accounting and portfolio risk remain hard boundaries.</span>';const contract=root.querySelector(".decision-head span");if(contract)contract.textContent="DISCOVERY ≠ EXECUTION · PRIMARY / PROBE / WAIT";["INTRADAY","SWING","INVESTMENT"].forEach(k=>mandate(k,p));board(p)}finally{rendering=false}}
  async function read(){if(fetching)return;fetching=true;try{const r=await fetch("/api/paper/portfolio-controller",{cache:"no-store"}),p=await r.json();if(r.ok&&p?.success){last=p;apply(p)}}catch{}finally{fetching=false}}
  document.addEventListener("click",e=>{if(e.target?.closest?.("#paperMandateFilters,#paperStateFilters"))setTimeout(()=>last&&apply(last),30)},true);
  function boot(){if($("paperDeskV4")){read();setInterval(read,1900);setInterval(()=>last&&apply(last),700)}else setTimeout(boot,400)}boot();
})();
