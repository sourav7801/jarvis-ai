(()=>{
  "use strict";
  const content=()=>document.getElementById('content');
  const title=()=>document.getElementById('sectionTitle');
  const msg=()=>document.getElementById('sectionMessage');
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const n=(v,d=3)=>Number.isFinite(Number(v))?Number(v).toFixed(d):'—';

  async function j(url){const r=await fetch(url,{cache:'no-store'});const p=await r.json();if(!r.ok)throw new Error(p?.message||String(r.status));return p}
  function cards(rows){return `<div class="grid">${rows.map(([k,v,c])=>`<div class="card"><div class="eyebrow">${esc(k)}</div><b class="${c||''}">${esc(v)}</b></div>`).join('')}</div>`}
  function table(rows){if(!rows.length)return '<div class="loading">No lifecycle observations yet.</div>';return `<div class="table-wrap"><table><thead><tr><th>SYMBOL</th><th>BUCKET</th><th>LANE</th><th>STATE</th><th>REASON</th><th>EV</th><th>CONF</th><th>RISK</th><th>SCORE OBS</th></tr></thead><tbody>${rows.map(r=>`<tr><td>${esc(r.symbol)}</td><td>${esc(r.bucket)}</td><td>${esc(r.lane)}</td><td>${esc(r.state)}</td><td>${esc(r.reason)}</td><td>${n(r.expected_value_r)}R</td><td>${Number.isFinite(Number(r.confidence))?(Number(r.confidence)*100).toFixed(0)+'%':'—'}</td><td>${n(r.risk_multiplier,3)}x</td><td>${esc(r.legacy_score??'—')}</td></tr>`).join('')}</tbody></table></div>`}

  async function render(){
    try{
      const [a,l]=await Promise.all([j('/api/v14/execution-authority'),j('/api/v14/opportunity-lifecycle')]);
      title().textContent='AUTONOMOUS EXECUTION';
      msg().textContent='Positive contextual expected value can execute at continuously scaled paper risk. Confidence, score, alignment and static R:R are evidence—not arbitrary binary execution gates.';
      const p=a.policy||{}, r=a.runtime||{}, s=a.sizing||{}, counts=l.state_counts||{};
      const blockers=(l.top_hard_blockers||[]).map(x=>`${x.reason} (${x.count})`).join(', ')||'NONE';
      content().innerHTML=cards([
        ['AUTHORITY',p.decision_authority||'POSITIVE CONTEXTUAL EV','ok'],
        ['POSITIVE EV BOUNDARY',`${n(p.positive_ev_boundary_r,3)}R`,'ok'],
        ['CONFIDENCE EXECUTION GATE',p.arbitrary_confidence_execution_gate===false?'NONE':'UNKNOWN',p.arbitrary_confidence_execution_gate===false?'ok':'warn'],
        ['FRACTIONAL SIZING',s.installed?'ACTIVE':'NOT READY',s.installed?'ok':'warn'],
        ['WATCHING TERMINAL STATE',r.watching_is_terminal_state===false?'DISABLED':'UNKNOWN',r.watching_is_terminal_state===false?'ok':'warn'],
        ['ACTIONABLE',Number(counts.ACTIONABLE||0)+Number(counts.RECHECK_PENDING||0),'ok'],
        ['NON-POSITIVE EV',counts.WAIT_NEGATIVE_OR_ZERO_EV||0,''],
        ['HARD BLOCKED',counts.BLOCKED_SAFETY_OR_DATA||0,Number(counts.BLOCKED_SAFETY_OR_DATA||0)?'warn':'ok'],
        ['POSITIONS OPENED',counts.POSITION_OPENED||0,'ok'],
        ['TOP HARD BLOCKERS',blockers,blockers==='NONE'?'ok':'warn'],
        ['LIVE EXECUTION','LOCKED','ok'],
        ['PERMANENT AGENTS','29','ok']
      ])+`<h2>OPPORTUNITY LIFECYCLE</h2>${table(l.active||[])}`;
    }catch(e){content().innerHTML=`<div class="loading">V14 execution surface unavailable: ${esc(e.message)}</div>`}
  }

  function boot(){
    const nav=document.getElementById('autonomousExecutionNav');
    if(nav)nav.addEventListener('click',()=>{document.querySelectorAll('.nav button').forEach(b=>b.classList.remove('active'));nav.classList.add('active');render()});
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot);else boot();
})();
