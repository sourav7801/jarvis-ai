(()=>{
  "use strict";
  const content=()=>document.getElementById("content");
  const esc=v=>String(v??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const n=(v,d=3)=>Number.isFinite(Number(v))?Number(v).toFixed(d):"—";
  async function j(url){const r=await fetch(url,{cache:"no-store"});if(!r.ok)throw new Error(String(r.status));return await r.json()}
  function nav(){
    const aside=document.querySelector(".nav");
    if(!aside||document.getElementById("optionsExecutionV151Nav"))return;
    const b=document.createElement("button");
    b.id="optionsExecutionV151Nav";
    b.textContent="OPTIONS EXECUTION V15.1";
    const anchor=document.getElementById("marketReasoningV15Nav")||document.getElementById("autonomousExecutionNav");
    if(anchor&&anchor.nextSibling)aside.insertBefore(b,anchor.nextSibling);else aside.insertBefore(b,aside.firstChild);
    b.addEventListener("click",show);
  }
  async function show(){
    const title=document.getElementById("sectionTitle");
    const kicker=document.getElementById("sectionKicker");
    const msg=document.getElementById("sectionMessage");
    if(title)title.textContent="OPTIONS EXECUTION INTELLIGENCE";
    if(kicker)kicker.textContent="V15.1 VERIFIED CHAIN · CONTRACT ECONOMICS · PAPER LONG PREMIUM";
    if(msg)msg.textContent="Loading NIFTY option-expression intelligence over the V15 underlying market brain…";
    if(content())content().innerHTML='<div class="loading">Loading V15.1 options intelligence…</div>';
    try{
      const [plan,status]=await Promise.all([j('/api/v15.1/options/plan?symbol=NIFTY&provider=fyers'),j('/api/v15.1/options/status')]);
      const s=plan.selected||{}, q=s.quote||{}, r=s.risk_plan||{}, e=s.economics||{};
      if(content())content().innerHTML=`
        <section class="card"><div class="eyebrow">NIFTY OPTION EXPRESSION</div><h2>${esc(plan.action||'NO_OPTION_TRADE')} · ${esc(plan.reason||'—')}</h2>
        <div class="grid"><div><span>CONTRACT</span><b>${esc(s.symbol||'—')}</b></div><div><span>EXPIRY / STRIKE</span><b>${esc(s.expiry||'—')} · ${n(s.strike,0)}</b></div><div><span>OPTION EV</span><b>${n(s.option_expected_value_r)}R</b></div><div><span>OPTION UTILITY</span><b>${n(s.option_utility,4)}</b></div></div></section>
        <section class="card"><div class="eyebrow">PREMIUM RISK GEOMETRY</div><p>Entry <b>${n(r.entry)}</b> · Stop <b>${n(r.stop)}</b> · Target <b>${n(r.target)}</b> · R:R <b>${n(r.risk_reward,2)}</b></p><small>Premium stop/target are explicitly risk-plan estimates, not future market quotes.</small></section>
        <section class="card"><div class="eyebrow">VERIFIED CONTRACT EVIDENCE</div><p>Delta <b>${q.delta??'UNAVAILABLE'}</b> · Gamma <b>${q.gamma??'UNAVAILABLE'}</b> · Theta <b>${q.theta??'UNAVAILABLE'}</b> · Vega <b>${q.vega??'UNAVAILABLE'}</b> · IV <b>${q.implied_volatility??'UNAVAILABLE'}</b> · Spread <b>${e.spread_pct==null?'UNAVAILABLE':n(Number(e.spread_pct)*100,2)+'%'}</b></p></section>
        <section class="card"><div class="eyebrow">SAFETY</div><p><b>LONG PREMIUM PAPER ONLY</b> · Naked option selling disabled · Verified lot/tick required · Option chain provider remains read-only · Live broker execution locked.</p><p>Dealer positioning: <b>UNAVAILABLE WITHOUT VERIFIED DEALER INVENTORY</b>.</p></section>
        <section class="card"><div class="eyebrow">RUNTIME</div><p>Registered read-only chain providers: <b>${esc((status.chain_provider_registry?.providers||[]).join(', ')||'NONE')}</b></p></section>`;
    }catch(e){if(content())content().innerHTML=`<div class="loading">V15.1 options intelligence unavailable: ${esc(e.message||e)}</div>`}
  }
  function boot(){nav()}
  if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",boot);else boot();
})();
