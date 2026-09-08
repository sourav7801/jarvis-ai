(()=>{
  "use strict";
  const content=()=>document.getElementById("content");
  const esc=v=>String(v??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const n=(v,d=3)=>Number.isFinite(Number(v))?Number(v).toFixed(d):"—";
  async function j(url){const r=await fetch(url,{cache:"no-store"});if(!r.ok)throw new Error(String(r.status));return await r.json()}

  function nav(){
    const aside=document.querySelector(".nav");
    if(!aside||document.getElementById("marketReasoningV15Nav"))return;
    const b=document.createElement("button");
    b.id="marketReasoningV15Nav";
    b.textContent="MARKET REASONING V15";
    const anchor=document.getElementById("autonomousExecutionNav");
    aside.insertBefore(b,anchor||aside.firstChild);
    b.addEventListener("click",show);
  }

  async function show(){
    const title=document.getElementById("sectionTitle");
    const kicker=document.getElementById("sectionKicker");
    const msg=document.getElementById("sectionMessage");
    if(title)title.textContent="AUTONOMOUS MARKET REASONING";
    if(kicker)kicker.textContent="V15 MARKET BELIEFS · HYPOTHESES · PORTFOLIO UTILITY";
    if(msg)msg.textContent="Loading BTC reasoning trace, persistent beliefs, position intelligence and causal review…";
    if(content())content().innerHTML='<div class="loading">Loading V15 reasoning…</div>';
    try{
      const [trace,pos,review]=await Promise.all([
        j('/api/v15/reasoning-trace?symbol=BTC'),
        j('/api/v15/position-intelligence'),
        j('/api/v15/causal-trade-review')
      ]);
      const best=trace.best_sample||{};
      const d=best.decision||{};
      const r=best.market_reasoning||{};
      const b=r.market_belief||{};
      const hyps=Array.isArray(r.hypotheses)?r.hypotheses:[];
      if(content())content().innerHTML=`
        <section class="card"><div class="eyebrow">BTC AUTONOMOUS REASONING</div><h2>${esc(d.action||'WAIT')} · ${esc(best.pipeline_stop_reason||'—')}</h2>
        <div class="grid"><div><span>MARKET BELIEF</span><b>${esc(b.trend_direction||'UNKNOWN')} · ${esc(b.regime||'UNKNOWN')}</b></div><div><span>PORTFOLIO UTILITY</span><b>${n(d.portfolio_adjusted_utility,4)}</b></div><div><span>EXPECTED VALUE</span><b>${n(d.expected_value_r,3)}R</b></div><div><span>LEGACY SCORE</span><b>${best.legacy_score??'—'} OBSERVATION</b></div></div></section>
        <section class="card"><div class="eyebrow">COMPETING HYPOTHESES</div>${hyps.slice(0,4).map(h=>`<p><b>${esc(h.name)}</b> · ${n((Number(h.probability)||0)*100,1)}%<br><small>${esc((h.evidence_for||[])[0]||'No additional evidence')}</small></p>`).join('')||'<p>No verified hypotheses available.</p>'}</section>
        <section class="card"><div class="eyebrow">POSITION INTELLIGENCE</div><p>Open positions: <b>${pos.open_positions??0}</b>. Automatic position actions may only reduce risk; ADD must re-enter the full V15 allocator.</p></section>
        <section class="card"><div class="eyebrow">CAUSAL TRADE REVIEW</div><p>Closed paper reviews: <b>${review.count??0}</b>. Decision quality is evaluated separately from P&amp;L outcome.</p></section>
        <section class="card"><div class="eyebrow">SAFETY</div><p><b>LIVE BROKER EXECUTION LOCKED</b> · V14.1 verified risk geometry preserved · 29 permanent specialists preserved.</p></section>`;
    }catch(e){if(content())content().innerHTML=`<div class="loading">V15 reasoning unavailable: ${esc(e.message||e)}</div>`}
  }

  function boot(){nav()}
  if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",boot);else boot();
})();
