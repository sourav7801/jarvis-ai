(()=>{
  "use strict";
  const $=id=>document.getElementById(id);
  const esc=v=>String(v??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const n=(v,d=2)=>Number.isFinite(Number(v))?Number(v).toFixed(d):"—";

  function selectedSymbol(){
    const value=String($("scanSymbol")?.textContent||"BTC").trim().toUpperCase();
    return value&&value!=="WAITING"&&value!=="NO SCAN"?value:"BTC";
  }

  function style(){
    if($("v141Style"))return;
    const s=document.createElement("style");
    s.id="v141Style";
    s.textContent=`
      #v141TraceCard{border:1px solid #23556b;background:#061820;border-radius:7px;padding:8px;margin-top:7px;font-size:9px}
      #v141TraceGrid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:5px;margin-top:6px}
      #v141TraceGrid div{border:1px solid #173c4c;background:#07141b;border-radius:5px;padding:5px}
      #v141TraceGrid span{display:block;color:#789eac;font-size:8px}#v141TraceGrid b{display:block;color:#e1f7ff;margin-top:2px;overflow-wrap:anywhere}
      .v141-ok{color:#7cf0aa!important}.v141-warn{color:#ffd27a!important}.v141-bad{color:#ff9c9c!important}
    `;
    document.head.appendChild(s);
  }

  async function fetchTrace(){
    const symbol=encodeURIComponent(selectedSymbol());
    const r=await fetch(`/api/v14.1/execution-trace?symbol=${symbol}`,{cache:'no-store'});
    if(!r.ok)throw new Error(String(r.status));
    return await r.json();
  }

  function render(trace){
    style();
    const best=trace?.best_sample||{};
    const decision=best?.decision||{};
    const geometry=best?.risk_geometry||{};
    const sizing=best?.sizing||{};
    const stages=best?.stages||{};
    const reason=String(best?.pipeline_stop_reason||"NO_EXECUTION_TRACE");
    const action=String(decision?.action||"WAIT").toUpperCase();
    const executable=decision?.executable===true;
    const geometryReady=stages?.RISK_MODEL_BUILT===true;
    const sizeReady=stages?.SIZE_PLANNED===true;

    const signal=$("liveSignal");
    if(signal){
      signal.textContent=executable?action:"WAIT";
      signal.className=`signal-badge ${executable?(action==="PRIMARY"?"long":"wait"):"wait"}`;
    }
    const score=$("signalScore");
    if(score)score.textContent=`${best?.legacy_score??"—"} SCORE OBS`;
    const regime=$("signalRegime");
    if(regime)regime.textContent=`V14.1 ${geometryReady?"RISK MODEL READY":"RISK MODEL BLOCKED"}`;
    const reasonEl=$("signalReason");
    if(reasonEl){
      reasonEl.textContent=executable
        ?`V14.1 ${action}: contextual EV ${n(decision?.expected_value_r,3)}R. Risk geometry is valid; confidence scales paper size only. ${sizeReady?"Sizing is ready for Paper Desk.":`Sizing not ready: ${reason}.`}`
        :`V14.1 WAIT: ${reason}. Legacy score ${best?.legacy_score??"—"} is observation only; risk geometry and contextual EV now determine the execution path.`;
    }

    const setup=$("setupState");
    if(setup)setup.textContent=geometryReady?(geometry?.derived?"V14.1 DERIVED VERIFIED SETUP":"VERIFIED SETUP"):`NO EXECUTABLE RISK MODEL · ${reason}`;
    const entry=$("entryRef"); if(entry)entry.textContent=n(best?.entry);
    const stop=$("stopRef"); if(stop)stop.textContent=n(best?.stop);
    const target=$("targetRef"); if(target)target.textContent=n(best?.target);
    const rr=$("rrRef"); if(rr)rr.textContent=Number.isFinite(Number(best?.risk_reward))?`${n(best.risk_reward)} : 1`:"—";

    let card=$("v141TraceCard");
    if(!card){
      card=document.createElement("section");
      card.id="v141TraceCard";
      card.className="intel-card";
      const panel=document.querySelector(".intel-panel");
      if(panel)panel.insertBefore(card,panel.children[1]||null);
    }
    if(card){
      const state=sizeReady?"READY FOR PAPER DESK":executable?"ACTIONABLE":geometryReady?"GEOMETRY READY / EV WAIT":"BLOCKED";
      const stateClass=sizeReady||executable?"v141-ok":geometryReady?"v141-warn":"v141-bad";
      card.innerHTML=`<div class="eyebrow">V14.1 EXECUTION TRACE · ${esc(trace?.symbol||selectedSymbol())}</div>
        <b class="${stateClass}">${esc(state)}</b>
        <div id="v141TraceGrid">
          <div><span>PROFILE</span><b>${esc(best?.profile||"—")}</b></div>
          <div><span>DIRECTION</span><b>${esc(best?.candidate_side||"—")}</b></div>
          <div><span>GEOMETRY</span><b class="${geometryReady?"v141-ok":"v141-bad"}">${esc(geometry?.state||"UNAVAILABLE")}</b></div>
          <div><span>EV / ACTION</span><b>${n(decision?.expected_value_r,3)}R · ${esc(action)}</b></div>
          <div><span>FRACTIONAL SIZE</span><b class="${sizeReady?"v141-ok":"v141-warn"}">${sizeReady?esc(sizing?.quantity??"READY"):"NOT READY"}</b></div>
          <div><span>STOP REASON</span><b class="${reason==="READY_FOR_PAPER_DESK_OPEN"?"v141-ok":"v141-warn"}">${esc(reason)}</b></div>
        </div>`;
    }
    window.JARVIS_V141_EXECUTION_TRACE=trace;
  }

  async function read(){try{render(await fetchTrace())}catch{}}
  function boot(){read();setInterval(read,3000)}
  if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",boot);else boot();
})();
