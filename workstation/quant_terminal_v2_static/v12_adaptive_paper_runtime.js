(()=>{
  "use strict";
  const esc=v=>String(v??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const n=(v,d=2)=>Number.isFinite(Number(v))?Number(v).toFixed(d):"—";
  const pct=v=>Number.isFinite(Number(v))?(Number(v)*100).toFixed(1)+"%":"—";
  let latest=null,fetching=false;

  function style(){
    if(document.getElementById("v12PaperStyle"))return;
    const node=document.createElement("style");node.id="v12PaperStyle";node.textContent=`
      #paperDeskV4 .v12-authority{display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin-top:7px;padding:6px 7px;border:1px solid #235064;border-radius:7px;background:#071922;font-size:9px;color:#87adba}
      #paperDeskV4 .v12-authority b{color:#7fe7ff;letter-spacing:.06em}.v12-primary{color:#79f1ab}.v12-probe{color:#ffd070}.v12-wait{color:#ff9ca6}
      #paperDeskV4 .v12-evidence{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:5px;margin-top:7px}
      #paperDeskV4 .v12-evidence div{border:1px solid #12313d;border-radius:5px;padding:5px;min-width:0}.v12-evidence span{display:block;color:#678d9c;font-size:8px}.v12-evidence b{display:block;color:#d8f4ff;font-size:9px;margin-top:2px;overflow-wrap:anywhere}
      #paperDeskV4.paper-narrow .v12-evidence{grid-template-columns:1fr 1fr}
    `;document.head.appendChild(node);
  }

  function actionClass(action){return action==="PRIMARY"?"v12-primary":action==="PROBE"?"v12-probe":"v12-wait"}
  function activeFilter(group,def="ALL"){
    const btn=document.querySelector(`${group} button.active`);return String(btn?.dataset?.filter||def).toUpperCase();
  }
  function funnel(status){return status?.last_scan_funnel||{}}

  function renderMandate(key,status){
    const stats=document.getElementById(`mandateStats${key}`);if(!stats)return;
    const f=funnel(status), lanes=status?.lanes||{};
    const laneNames=Object.entries(lanes).filter(([,v])=>v?.running).map(([k])=>k).join(" / ");
    const watch=Array.isArray(status?.universe)?status.universe.length:0;
    const primary=Number(f.adaptive_primary||0),probe=Number(f.adaptive_probe||0),opened=Number(status?.positions_opened??f.opened??0);
    stats.innerHTML=`
      <div class="mandate-stat">AUTHORITY<b>ADAPTIVE EV</b></div>
      <div class="mandate-stat">LEGACY SCORE<b>${esc(n(status?.min_score,0))} · OBS ONLY</b></div>
      <div class="mandate-stat">WATCH<b>${watch}</b></div>
      <div class="mandate-stat">SCANNED<b>${Number(f.scanned||0)}</b></div>
      <div class="mandate-stat">PRIMARY<b>${primary}</b></div>
      <div class="mandate-stat">PROBE<b>${probe}</b></div>
      <div class="mandate-stat">ADAPTIVE EDGE<b>${Number(f.adaptive_executable||0)}</b></div>
      <div class="mandate-stat">OPENED<b>${opened}</b></div>
      ${laneNames?`<div class="mandate-stat" style="grid-column:1/-1">ACTIVE LANES<b>${esc(laneNames)}</b></div>`:""}`;
  }

  function renderBoard(controller){
    const host=document.getElementById("paperDecisionBoard");if(!host)return;
    const all=Array.isArray(controller?.decision_board)?controller.decision_board:[];
    const mandateFilter=activeFilter("#paperMandateFilters"),stateFilter=activeFilter("#paperStateFilters");
    const rows=all.filter(row=>{
      const mandate=String(row.mandate||"").toUpperCase(),action=String(row.adaptive_action||row.decision||"WAIT").toUpperCase();
      const executable=Boolean(row.qualified);
      if(mandateFilter!=="ALL"&&mandate!==mandateFilter)return false;
      if(stateFilter==="QUALIFIED"&&!executable)return false;
      if(stateFilter==="BLOCKED"&&executable)return false;
      return true;
    });
    const f=document.getElementById("paperDecisionFunnel");
    if(f){
      const primary=all.filter(r=>String(r.adaptive_action||"").toUpperCase()==="PRIMARY").length;
      const probe=all.filter(r=>String(r.adaptive_action||"").toUpperCase()==="PROBE").length;
      const wait=all.filter(r=>!r.qualified).length;
      f.innerHTML=`<div><span>SCANNED</span><b>${all.length}</b></div><div><span>PRIMARY</span><b>${primary}</b></div><div><span>PROBE</span><b>${probe}</b></div><div><span>WAIT</span><b>${wait}</b></div>`;
    }
    if(!rows.length){host.innerHTML='<div class="decision-empty">No adaptive decisions match the selected filters.</div>';return}
    host.innerHTML=rows.slice(0,30).map(row=>{
      const action=String(row.adaptive_action||row.decision||(row.qualified?"PRIMARY":"WAIT")).toUpperCase();
      const hard=Array.isArray(row.hard_blockers)?row.hard_blockers:Array.isArray(row.blockers)?row.blockers:[];
      const soft=Array.isArray(row.soft_evidence)?row.soft_evidence:[];
      return `<article class="decision-card">
        <div class="decision-card-head"><strong>${esc(row.symbol||"UNKNOWN")}</strong><em class="${actionClass(action)}">${esc(action)}</em></div>
        <div class="decision-meta">${esc(row.mandate||"UNROUTED")}${row.lane?` · ${esc(row.lane)}`:""} · 67/68/70 OBSERVABILITY ONLY</div>
        <div class="v12-evidence">
          <div><span>LEGACY SCORE</span><b>${esc(n(row.execution_score,1))}</b></div>
          <div><span>EXPECTED VALUE</span><b>${esc(n(row.adaptive_expected_value_r,3))}R</b></div>
          <div><span>CONFIDENCE</span><b>${esc(pct(row.adaptive_confidence))}</b></div>
          <div><span>RISK</span><b>×${esc(n(row.adaptive_risk_multiplier,2))}</b></div>
        </div>
        <div class="decision-reason"><b>HARD BLOCKERS</b><br>${hard.length?esc(hard.join(" · ")):"NONE"}</div>
        <div class="decision-next"><b>SOFT / CONTRADICTORY EVIDENCE</b><br>${soft.length?esc(soft.join(" · ")):"NONE"}</div>
      </article>`;
    }).join("");
  }

  function render(){
    if(!latest)return;style();
    const root=document.getElementById("paperDeskV4");if(!root)return;
    let authority=root.querySelector(".v12-authority");
    if(!authority){authority=document.createElement("div");authority.className="v12-authority";const grid=root.querySelector(".mandate-grid");grid?.parentNode?.insertBefore(authority,grid)}
    authority.innerHTML='<b>V12 ADAPTIVE EV AUTHORITY</b><span>67/68/70 score and legacy R:R gates are observations, not binary execution authority. Data/accounting/portfolio safety remains hard.</span>';
    const mandates=latest.mandates||{};["INTRADAY","SWING","INVESTMENT"].forEach(key=>renderMandate(key,mandates[key]||{}));
    renderBoard(latest);
    const state=document.getElementById("paperAutoState");if(state)state.title=`V12 ${latest.decision_authority||"ADAPTIVE"} · ${String(latest.score_contract?.execution_score||"")}`;
  }

  async function refresh(){
    if(fetching)return;fetching=true;
    try{const r=await fetch("/api/paper/portfolio-controller",{cache:"no-store"});const p=await r.json();if(r.ok&&p?.success){latest=p;render()}}catch{}finally{fetching=false}
  }

  document.addEventListener("click",e=>{if(e.target?.closest?.("#paperMandateFilters,#paperStateFilters"))setTimeout(render,25)},true);
  setInterval(render,700);setInterval(refresh,1900);setTimeout(refresh,300);
})();
