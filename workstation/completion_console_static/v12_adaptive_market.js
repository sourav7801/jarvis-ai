(()=>{
  "use strict";
  const $=id=>document.getElementById(id);
  const esc=v=>String(v??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const pct=v=>Number.isFinite(Number(v))?(Number(v)*100).toFixed(1)+"%":"—";
  const num=(v,d=2)=>Number.isFinite(Number(v))?Number(v).toFixed(d):"—";

  function style(){
    if($("v12AdaptiveStyle"))return;
    const s=document.createElement("style");s.id="v12AdaptiveStyle";s.textContent=`
      .v12-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin:10px 0 14px}
      .v12-card{border:1px solid #1b4352;background:#07151d;border-radius:10px;padding:12px;min-width:0}.v12-card span{display:block;font-size:9px;color:#7ca5b4;letter-spacing:.08em}.v12-card b{display:block;margin-top:5px;color:#e6fbff;font-size:17px;overflow-wrap:anywhere}
      .v12-toolbar{display:flex;gap:8px;flex-wrap:wrap;margin:10px 0}.v12-toolbar input{flex:1;min-width:180px;background:#06131a;border:1px solid #214b5d;color:#e6fbff;border-radius:7px;padding:9px}
      .v12-list{display:grid;gap:8px}.v12-row{border:1px solid #173d4b;background:#061219;border-radius:9px;padding:10px;overflow-wrap:anywhere}.v12-row h3{margin:0 0 7px;font-size:12px}.v12-badge{display:inline-block;border:1px solid #29596b;border-radius:999px;padding:3px 7px;margin:0 5px 5px 0;font-size:9px}.v12-ok{color:#75efae}.v12-probe{color:#ffd27a}.v12-wait{color:#ff8d96}.v12-note{font-size:10px;color:#86a9b6;line-height:1.5}.v12-row pre{white-space:pre-wrap;overflow-wrap:anywhere;max-height:220px;overflow:auto;background:#040c11;border:1px solid #13313d;border-radius:7px;padding:8px;color:#9dc2cf;font-size:9px}
      @media(max-width:1000px){.v12-grid{grid-template-columns:1fr 1fr}}@media(max-width:680px){.v12-grid{grid-template-columns:1fr}}
    `;document.head.appendChild(s);
  }
  async function api(url){const r=await fetch(url);let p={};try{p=await r.json()}catch{}if(!r.ok||p.success===false)throw new Error(p.message||p.error||`HTTP ${r.status}`);return p}
  function cards(rows){return `<div class="v12-grid">${rows.map(([a,b,k=""])=>`<article class="v12-card"><span>${esc(a)}</span><b class="${k}">${esc(b)}</b></article>`).join("")}</div>`}
  function actionClass(a){return a==="PRIMARY"?"v12-ok":a==="PROBE"?"v12-probe":"v12-wait"}

  async function render(){
    document.querySelectorAll(".nav button").forEach(b=>b.classList.remove("active"));$("adaptiveMarketNav")?.classList.add("active");
    $("sectionKicker").textContent="V12 ADAPTIVE MARKET INTELLIGENCE";$("sectionTitle").textContent="ADAPTIVE MARKET";$("sectionMessage").textContent="Continuous expected value, uncertainty and learned outcome priors. Static 67/68/70 Quant scores remain visible but are not execution authority.";
    $("content").innerHTML='<div class="loading">Loading adaptive policy…</div>';
    try{
      const p=await api("/api/adaptive-policy");
      $("content").innerHTML=cards([
        ["DECISION MODEL",p.decision_model||"—"],
        ["STATIC SCORE GATE",p.legacy_score_threshold_is_execution_authority?"AUTHORITY":"NOT AUTHORITY",p.legacy_score_threshold_is_execution_authority?"v12-wait":"v12-ok"],
        ["LOW-RISK PROBES",p.supports_low_risk_probe?"ENABLED":"OFF",p.supports_low_risk_probe?"v12-ok":""],
        ["LIVE EXECUTION",p.live_execution?"ENABLED":"LOCKED","v12-wait"]
      ])+`<section class="section"><div class="section-head"><h2>Live multi-profile sample</h2><small>Reads the authoritative Quant process on 8787. No fabricated candles and no broker order API.</small></div><div class="v12-toolbar"><input id="v12Symbol" value="BTC" placeholder="BTC / NIFTY / BANKNIFTY"><button id="v12Sample">SAMPLE LIVE MARKET</button></div><div class="v12-note">A PRIMARY or PROBE decision can exist even when legacy score is below 67/68/70. Hard data, stale-feed, session, accounting and portfolio-risk failures remain blockers.</div><div id="v12SampleResult" class="empty">Click SAMPLE LIVE MARKET to evaluate 5m, 10m, 15m, adaptive intraday and swing evidence.</div></section><section class="section"><div class="section-head"><h2>Hard blockers</h2></div><pre>${esc(JSON.stringify(p.hard_blockers||[],null,2))}</pre></section>`;
      $("v12Sample")?.addEventListener("click",sample);
    }catch(e){$("content").innerHTML=`<div class="error">${esc(e.message)}</div>`}
  }

  async function sample(){
    const symbol=($("v12Symbol")?.value||"BTC").trim().toUpperCase();const host=$("v12SampleResult");host.className="loading";host.textContent=`Sampling ${symbol} from Quant…`;
    try{
      const p=await api(`/api/adaptive-market/sample?symbol=${encodeURIComponent(symbol)}`);const rows=p.samples||[],best=p.best_adaptive_sample||null,ctrl=p.portfolio_controller||{};
      host.className="";host.innerHTML=cards([
        ["SYMBOL",p.symbol||symbol],
        ["ACTIONABLE PROFILES",String(p.actionable_count||0),p.actionable_count?"v12-ok":"v12-wait"],
        ["ACTIVE MANDATES",(ctrl.active_mandates||[]).join(" · ")||"NONE"],
        ["BEST ACTION",best?.adaptive?.action||"WAIT",actionClass(best?.adaptive?.action||"WAIT")]
      ])+`<div class="v12-list">${rows.map(r=>{const a=r.adaptive||{},action=a.action||"ERROR";return `<article class="v12-row"><h3>${esc(r.profile||"—")} · <span class="${actionClass(action)}">${esc(action)}</span></h3><span class="v12-badge">side ${esc(a.side||r.candidate_side||"WAIT")}</span><span class="v12-badge">legacy score ${esc(r.legacy_score??"—")}</span><span class="v12-badge">EV ${esc(num(a.expected_value_r,3))}R</span><span class="v12-badge">confidence ${esc(pct(a.confidence))}</span><span class="v12-badge">risk ×${esc(num(a.risk_multiplier,2))}</span><div class="v12-note">Legacy qualified: ${esc(Boolean(r.legacy_qualified))} · alignment ${esc(r.alignment??"—")} · R:R ${esc(r.risk_reward??"—")} · regime ${esc(r.regime||"—")}</div><pre>${esc(JSON.stringify({hard_blockers:a.hard_blockers||[],soft_evidence:a.soft_evidence||[],reasons:a.reasons||[]},null,2))}</pre></article>`}).join("")}</div>`;
    }catch(e){host.className="error";host.textContent=e.message}
  }

  style();$("adaptiveMarketNav")?.addEventListener("click",render);
  document.querySelectorAll("[data-section],#executionMeshNav,#autonomyNav,#tradingDecisionNav,#derived10mNav,#worldNav,#criticNav,#engineeringGovNav,#systemDiagNav,#tradingGovNav").forEach(b=>b.addEventListener("click",()=>$("adaptiveMarketNav")?.classList.remove("active")));
})();
