(()=>{
  "use strict";
  const $=id=>document.getElementById(id);
  const esc=v=>String(v??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const n=(v,d=3)=>Number.isFinite(Number(v))?Number(v).toFixed(d):"—";

  function selectedSymbol(){
    const value=String($("scanSymbol")?.textContent||"BTC").trim().toUpperCase();
    return value&&value!=="WAITING"&&value!=="NO SCAN"?value:"BTC";
  }

  function style(){
    if($("v15ReasoningStyle"))return;
    const s=document.createElement("style");
    s.id="v15ReasoningStyle";
    s.textContent=`
      #v15ReasoningCard{border:1px solid #2b6174;background:#06171e;border-radius:8px;padding:8px;margin-top:7px;font-size:9px}
      #v15ReasoningGrid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:5px;margin-top:6px}
      #v15ReasoningGrid div{border:1px solid #173b49;background:#07131a;border-radius:5px;padding:5px}
      #v15ReasoningGrid span{display:block;color:#789da9;font-size:8px}#v15ReasoningGrid b{display:block;color:#e4f9ff;margin-top:2px;overflow-wrap:anywhere}
      #v15Hypotheses{margin-top:6px;display:grid;gap:4px}.v15-hyp{border-left:2px solid #2c6c82;padding:4px 6px;background:#08141a}.v15-hyp small{color:#7395a0}
      .v15-ok{color:#7bf0a9!important}.v15-warn{color:#ffd27a!important}.v15-bad{color:#ff9b9b!important}
    `;
    document.head.appendChild(s);
  }

  async function j(url){const r=await fetch(url,{cache:"no-store"});if(!r.ok)throw new Error(String(r.status));return await r.json()}

  function render(trace){
    style();
    const best=trace?.best_sample||{};
    const d=best?.decision||{};
    const r=best?.market_reasoning||{};
    const b=r?.market_belief||{};
    const h=Array.isArray(r?.hypotheses)?r.hypotheses:[];
    const diagnostics=Array.isArray(r?.data_provenance)?r.data_provenance:[];
    const noEvidence=r?.success!==true||r?.hypotheses_suppressed_no_verified_evidence===true;
    const dominant=h[0]||{};
    const alt=h[1]||{};
    const stages=best?.stages||{};
    const reason=String(best?.pipeline_stop_reason||"NO_EXECUTION_TRACE");
    const providerState=String(r?.provider_state||((reason==="DATA_UNAVAILABLE")?"DATA_UNAVAILABLE":"READY"));
    const providerCode=r?.provider_code;
    let card=$("v15ReasoningCard");
    if(!card){
      card=document.createElement("section");
      card.id="v15ReasoningCard";
      card.className="intel-card";
      const panel=document.querySelector(".intel-panel");
      if(panel)panel.insertBefore(card,panel.children[1]||null);
    }
    if(!card)return;
    const state=stages.SIZE_PLANNED?"READY FOR PAPER DESK":stages.ACTIONABLE?"ACTIONABLE":stages.RISK_MODEL_BUILT?"REASONED / WAIT":"BLOCKED";
    const stateClass=stages.SIZE_PLANNED||stages.ACTIONABLE?"v15-ok":stages.RISK_MODEL_BUILT?"v15-warn":"v15-bad";
    const dominantLabel=noEvidence?"NO VERIFIED MARKET EVIDENCE":`${esc(dominant.name||"UNAVAILABLE")} · ${n((Number(dominant.probability)||0)*100,1)}%`;
    const alternativeLabel=noEvidence?"SUPPRESSED · DATA UNAVAILABLE":`${esc(alt.name||"UNAVAILABLE")} · ${n((Number(alt.probability)||0)*100,1)}%`;
    const providerLabel=`${esc(providerState)}${providerCode!==null&&providerCode!==undefined?` · ${esc(providerCode)}`:""}`;
    const hypothesisHtml=noEvidence
      ? `<div class="v15-hyp"><b>HYPOTHESES SUPPRESSED</b><br><small>No verified timeframe evidence is available, so V15 does not publish model probability percentages.</small></div>${diagnostics.slice(0,5).map(x=>`<div class="v15-hyp"><b>${esc(x.timeframe||"DATA")} · ${esc(x.provider_state||x.source||"UNAVAILABLE")}</b><br><small>${esc(x.message||"Verified market data unavailable")}</small></div>`).join("")}`
      : h.slice(0,4).map(x=>`<div class="v15-hyp"><b>${esc(x.name)}</b> · ${n((Number(x.probability)||0)*100,1)}%<br><small>${esc((x.evidence_for||[])[0]||"No additional evidence")}</small></div>`).join("");

    card.innerHTML=`
      <div class="eyebrow">V15 AUTONOMOUS MARKET REASONING · ${esc(trace?.symbol||selectedSymbol())}</div>
      <b class="${stateClass}">${esc(state)}</b>
      <div id="v15ReasoningGrid">
        <div><span>MARKET BELIEF</span><b>${esc(b.trend_direction||"UNKNOWN")} · ${esc(b.regime||"UNKNOWN")}</b></div>
        <div><span>DOMINANT HYPOTHESIS</span><b>${dominantLabel}</b></div>
        <div><span>ALTERNATIVE HYPOTHESIS</span><b>${alternativeLabel}</b></div>
        <div><span>PORTFOLIO UTILITY</span><b>${n(d.portfolio_adjusted_utility,4)}</b></div>
        <div><span>EXPECTED VALUE</span><b>${n(d.expected_value_r,3)}R</b></div>
        <div><span>UNCERTAINTY</span><b>${n((Number(d.uncertainty)||0)*100,1)}%</b></div>
        <div><span>RISK ALLOCATION</span><b>${n((Number(d.risk_multiplier)||0)*100,2)}% OF BASE RISK</b></div>
        <div><span>POSITION ACTION</span><b>${esc(d.action||"WAIT")}</b></div>
        <div><span>LEGACY SCORE · OBSERVATION</span><b>${best.legacy_score??"—"}</b></div>
        <div><span>EXECUTION STAGE</span><b class="${reason==="READY_FOR_PAPER_DESK_OPEN"?"v15-ok":"v15-warn"}">${esc(reason)}</b></div>
        <div><span>DATA PROVIDER</span><b class="${providerState==="READY"?"v15-ok":"v15-bad"}">${providerLabel}</b></div>
        <div><span>LIQUIDITY / VOLATILITY</span><b>${esc(b.liquidity_state||"UNKNOWN")} / ${esc(b.volatility_state||"UNKNOWN")}</b></div>
        <div><span>LIVE BROKER</span><b class="v15-ok">LOCKED</b></div>
      </div>
      <div id="v15Hypotheses">${hypothesisHtml}</div>`;

    const signal=$("signalReason");
    if(signal)signal.textContent=noEvidence
      ?`V15 WAIT: ${providerState}. Verified market evidence is unavailable; hypothesis probabilities are suppressed and risk remains zero.`
      :`V15 ${String(d.action||"WAIT").toUpperCase()}: ${reason}. Portfolio-adjusted contextual utility is authoritative; legacy score remains observation only.`;
    const score=$("signalScore");
    if(score)score.textContent=`${best.legacy_score??"—"} SCORE OBS`;
    window.JARVIS_V15_REASONING_TRACE=trace;
  }

  async function read(){
    try{render(await j(`/api/v15/reasoning-trace?symbol=${encodeURIComponent(selectedSymbol())}&persist=1`))}catch{}
  }
  function boot(){read();setInterval(read,3500)}
  if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",boot);else boot();
})();
