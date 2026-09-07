(()=>{
  "use strict";
  const $=id=>document.getElementById(id);
  const esc=v=>String(v??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const num=(v,d=3)=>Number.isFinite(Number(v))?Number(v).toFixed(d):"—";
  const pct=v=>Number.isFinite(Number(v))?(Number(v)*100).toFixed(1)+"%":"—";
  const json=async url=>{const r=await fetch(url,{cache:"no-store"});const p=await r.json();if(!r.ok)throw new Error(p.message||`HTTP ${r.status}`);return p};

  function installStyle(){
    if($("v13IntelligenceStyle"))return;
    const style=document.createElement("style");style.id="v13IntelligenceStyle";style.textContent=`
      .v13-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:10px}.v13-card{border:1px solid #173b4a;background:#06141c;border-radius:8px;padding:12px;min-width:0}.v13-card .eyebrow{margin-bottom:5px}.v13-card b{color:#d8f3ff}.v13-card p,.v13-card small{color:#82a8b5;overflow-wrap:anywhere}.v13-metric{display:flex;justify-content:space-between;gap:8px;padding:4px 0;border-bottom:1px solid #102c37;font-size:11px}.v13-metric:last-child{border:0}.v13-good{color:#78f2aa}.v13-warn{color:#ffd27a}.v13-bad{color:#ff8999}.v13-table{width:100%;border-collapse:collapse;font-size:10px}.v13-table td,.v13-table th{padding:6px;border-bottom:1px solid #14313d;text-align:left;vertical-align:top}.v13-pill{border:1px solid #245267;border-radius:999px;padding:2px 6px;font-size:9px;white-space:nowrap}
    `;document.head.appendChild(style);
  }

  function setHero(title,message){if($("sectionKicker"))$("sectionKicker").textContent="V13 ADAPTIVE INTELLIGENCE OS";if($("sectionTitle"))$("sectionTitle").textContent=title;if($("sectionMessage"))$("sectionMessage").textContent=message}
  function content(html){const host=$("content");if(host)host.innerHTML=html}
  function errorView(error){content(`<div class="v13-card"><b>V13 surface unavailable</b><p>${esc(error.message||error)}</p></div>`)}

  async function intelligence(){
    setHero("CONTEXTUAL INTELLIGENCE","V12 market evidence refined by closed-paper context, uncertainty and portfolio correlation.");content('<div class="loading">Loading V13 contextual decision state…</div>');
    try{const [decision,memory,corr]=await Promise.all([json('/api/contextual-decision'),json('/api/contextual-memory'),json('/api/portfolio-correlation')]);content(`<div class="v13-grid">
      <div class="v13-card"><div class="eyebrow">DECISION AUTHORITY</div><b>${esc(decision.decision_authority)}</b><div class="v13-metric"><span>closed-paper R samples</span><strong>${esc(decision.contextual_outcome_memory?.usable_r_count??0)}</strong></div><div class="v13-metric"><span>context cohorts</span><strong>${esc(decision.contextual_outcome_memory?.cohort_count??0)}</strong></div><div class="v13-metric"><span>static 67/68/70 authority</span><strong class="v13-good">OFF</strong></div><div class="v13-metric"><span>dynamic uncertainty hurdle</span><strong class="v13-good">ON</strong></div></div>
      <div class="v13-card"><div class="eyebrow">OUTCOME MEMORY</div><b>${esc(memory.source)}</b><div class="v13-metric"><span>closed trades</span><strong>${esc(memory.closed_trade_count??0)}</strong></div><div class="v13-metric"><span>usable realized-R</span><strong>${esc(memory.usable_r_count??0)}</strong></div><div class="v13-metric"><span>synthetic history</span><strong class="v13-good">NO</strong></div></div>
      <div class="v13-card"><div class="eyebrow">PORTFOLIO CORRELATION</div><b>${esc(corr.service)}</b><div class="v13-metric"><span>open positions</span><strong>${esc(corr.open_positions??0)}</strong></div><div class="v13-metric"><span>minimum aligned bars</span><strong>${esc(corr.minimum_observations??30)}</strong></div><div class="v13-metric"><span>risk can increase</span><strong class="v13-good">NO</strong></div><div class="v13-metric"><span>missing data behavior</span><strong>UNKNOWN</strong></div></div>
    </div>`)}catch(e){errorView(e)}
  }

  async function forensics(){
    setHero("DECISION FORENSICS","Why JARVIS chose PRIMARY, PROBE or WAIT, including context and correlation changes.");content('<div class="loading">Loading bounded decision evidence…</div>');
    try{const p=await json('/api/decision-forensics');const rows=(p.records||[]).slice().reverse().slice(0,40);content(`<div class="v13-card"><div class="eyebrow">RECENT DECISIONS · ${esc(p.record_count||0)} BOUNDED RECORDS</div>${rows.length?`<table class="v13-table"><thead><tr><th>MARKET</th><th>ACTION</th><th>EV</th><th>CONF</th><th>CONTEXT</th><th>CORRELATION</th><th>EVIDENCE</th></tr></thead><tbody>${rows.map(r=>`<tr><td><b>${esc(r.symbol)}</b><br>${esc(r.profile||r.timeframe||'')}</td><td><span class="v13-pill">${esc(r.final_action)}</span><br><small>base ${esc(r.base_v12_action||'—')}</small></td><td>${num(r.final_ev_r)}R<br><small>base ${num(r.base_v12_ev_r)}R</small></td><td>${pct(r.final_confidence)}</td><td>${num(r.context_edge_r)}R<br>${pct(r.context_win_rate)}</td><td>${esc(r.correlation_state||'—')}<br><small>${num(r.correlation_multiplier,2)}x</small></td><td><small>${esc((r.hard_blockers||[]).join(', ')||'no hard blocker')}<br>${esc((r.soft_evidence||[]).slice(0,3).join(', '))}</small></td></tr>`).join('')}</tbody></table>`:'<p>No V13 scan forensics have been recorded yet.</p>'}</div>`)}catch(e){errorView(e)}
  }

  async function options(){
    setHero("OPTIONS VOLATILITY","Verified derivatives history only. No OI-to-dealer-gamma fabrication.");content(`<div class="v13-card"><div class="eyebrow">SYMBOL</div><input id="v13OptionSymbol" class="search" value="NIFTY" placeholder="NIFTY"><button id="v13OptionLoad">LOAD VERIFIED HISTORY</button><div id="v13OptionResult" style="margin-top:10px">Select a symbol.</div></div>`);const load=async()=>{const symbol=($("v13OptionSymbol")?.value||"NIFTY").trim();const host=$("v13OptionResult");if(host)host.textContent="Loading…";try{const p=await json('/api/options-volatility?symbol='+encodeURIComponent(symbol));if(host)host.innerHTML=`<div class="v13-grid"><div><b>${esc(p.symbol)}</b><div class="v13-metric"><span>history snapshots</span><strong>${esc(p.snapshot_count??0)}</strong></div><div class="v13-metric"><span>IV rank</span><strong>${num(p.iv_rank,1)}</strong></div><div class="v13-metric"><span>IV percentile</span><strong>${num(p.iv_percentile,1)}</strong></div><div class="v13-metric"><span>PCR OI</span><strong>${num(p.pcr_oi,2)}</strong></div></div><div><div class="v13-metric"><span>call OI Δ</span><strong>${esc(p.oi_change?.call??'—')}</strong></div><div class="v13-metric"><span>put OI Δ</span><strong>${esc(p.oi_change?.put??'—')}</strong></div><div class="v13-metric"><span>dealer positioning</span><strong class="v13-warn">${esc(p.dealer_positioning?.reason||'UNAVAILABLE')}</strong></div><small>OI is not treated as verified dealer inventory.</small></div></div>`}catch(e){if(host)host.textContent=e.message}};$("v13OptionLoad")?.addEventListener('click',load);load();
  }

  async function governance(){
    setHero("STRATEGY GOVERNANCE","Research candidates progress through robust validation and paper shadow; CHAMPION requires operator approval.");content('<div class="loading">Loading governed strategy lifecycle…</div>');try{const p=await json('/api/strategy-governance-v13');const counts=p.counts||{};content(`<div class="v13-grid">${(p.stages||[]).map(s=>`<div class="v13-card"><div class="eyebrow">${esc(s)}</div><b>${esc(counts[s]||0)}</b></div>`).join('')}</div><div class="v13-card" style="margin-top:10px"><b>GOVERNANCE</b><div class="v13-metric"><span>automatic promotion</span><strong class="v13-good">OFF</strong></div><div class="v13-metric"><span>production rewrite</span><strong class="v13-good">OFF</strong></div><div class="v13-metric"><span>champion scope</span><strong>PAPER RESEARCH ONLY</strong></div><div class="v13-metric"><span>operator approval</span><strong>REQUIRED</strong></div></div>`)}catch(e){errorView(e)}
  }

  function bind(id,fn){$(id)?.addEventListener('click',event=>{event.preventDefault();document.querySelectorAll('.nav button').forEach(b=>b.classList.remove('active'));event.currentTarget.classList.add('active');fn()})}
  function boot(){installStyle();bind('contextualIntelligenceNav',intelligence);bind('decisionForensicsNav',forensics);bind('optionsVolatilityNav',options);bind('strategyPipelineNav',governance)}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot);else boot();
})();
