(()=>{
  "use strict";
  const $=id=>document.getElementById(id);
  const esc=v=>String(v??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const n=(v,d=3)=>Number.isFinite(Number(v))?Number(v).toFixed(d):"—";

  function style(){
    if($("v14ExecutionStyle"))return;
    const s=document.createElement("style");
    s.id="v14ExecutionStyle";
    s.textContent=`
      #v14ExecutionStrip{display:grid;grid-template-columns:repeat(auto-fit,minmax(128px,1fr));gap:5px;margin:7px 0}
      #v14ExecutionStrip div{border:1px solid #1d4b5f;background:#071821;border-radius:5px;padding:6px;font-size:8px}
      #v14ExecutionStrip span{display:block;color:#7da5b5}
      #v14ExecutionStrip b{display:block;color:#e0f7ff;margin-top:2px;overflow-wrap:anywhere}
      .v14-on{color:#7df4ae!important}.v14-warn{color:#ffd47d!important}.v14-off{color:#ff9f9f!important}
    `;
    document.head.appendChild(s);
  }

  async function j(url){const r=await fetch(url,{cache:'no-store'});if(!r.ok)throw new Error(String(r.status));return await r.json()}
  async function read(){
    try{
      const [authority,lifecycle,controller]=await Promise.all([
        j('/api/v14/execution-authority'),
        j('/api/v14/opportunity-lifecycle'),
        j('/api/paper/portfolio-controller')
      ]);
      apply(authority,lifecycle,controller);
    }catch{}
  }

  function openedCount(p){
    let total=0;
    Object.values(p?.mandates||{}).forEach(m=>{
      total+=Number(m?.positions_opened||0);
      Object.values(m?.lanes||{}).forEach(l=>total+=Number(l?.positions_opened||0));
    });
    return total;
  }

  function apply(authority,lifecycle,controller){
    style();
    const desk=$("paperDeskV4");
    if(!desk)return;
    const eyebrow=desk.querySelector(':scope > .eyebrow');
    if(eyebrow)eyebrow.textContent='JARVIS PAPER PORTFOLIO · V14 AUTONOMOUS EXECUTION INTELLIGENCE';
    const head=desk.querySelector('.decision-head span');
    if(head)head.textContent='POSITIVE CONTEXTUAL EV = EXECUTABLE · UNCERTAINTY SCALES SIZE · HARD SAFETY STILL VETOES';
    let strip=$("v14ExecutionStrip");
    if(!strip){strip=document.createElement('div');strip.id='v14ExecutionStrip';const target=desk.querySelector('.decision-wrap');if(target)target.prepend(strip)}

    const states=lifecycle?.state_counts||{};
    const actionable=Number(states.ACTIONABLE||0)+Number(states.RECHECK_PENDING||0);
    const blocked=Number(states.BLOCKED_SAFETY_OR_DATA||0);
    const negative=Number(states.WAIT_NEGATIVE_OR_ZERO_EV||0);
    const opened=openedCount(controller);
    const hard=(lifecycle?.top_hard_blockers||[])[0]||{};
    const execution=(lifecycle?.top_execution_rejections||[])[0]||{};
    const runtime=authority?.runtime||{};
    const policy=authority?.policy||{};
    const sizing=authority?.sizing||{};
    const mode=opened>0?'MANAGING POSITIONS':actionable>0?'EXECUTION SEEKING':'SCANNING FOR POSITIVE EV';
    const modeClass=opened>0||actionable>0?'v14-on':'v14-warn';

    strip.innerHTML=`
      <div><span>V14 MODE</span><b class="${modeClass}">${esc(mode)}</b></div>
      <div><span>AUTHORITY</span><b class="v14-on">POSITIVE CONTEXTUAL EV</b></div>
      <div><span>ACTIONABLE / RECHECK</span><b class="${actionable?'v14-on':''}">${actionable}</b></div>
      <div><span>NON-POSITIVE EV</span><b>${negative}</b></div>
      <div><span>HARD BLOCKED</span><b class="${blocked?'v14-warn':'v14-on'}">${blocked}</b></div>
      <div><span>TOP DATA/SAFETY BLOCKER</span><b class="${hard.reason?'v14-warn':'v14-on'}">${esc(hard.reason||'NONE')} ${hard.count?('· '+hard.count):''}</b></div>
      <div><span>TOP EXECUTION REJECTION</span><b class="${execution.reason?'v14-warn':'v14-on'}">${esc(execution.reason||'NONE')} ${execution.count?('· '+execution.count):''}</b></div>
      <div><span>POSITIONS OPENED</span><b class="${opened?'v14-on':''}">${opened}</b></div>
      <div><span>CONFIDENCE GATE</span><b class="v14-on">NONE · SIZE ONLY</b></div>
      <div><span>MIN EV</span><b>${n(policy.positive_ev_boundary_r,3)}R ECONOMIC</b></div>
      <div><span>FRACTIONAL SIZING</span><b class="${sizing.installed?'v14-on':'v14-off'}">${sizing.installed?'ACTIVE':'NOT READY'}</b></div>
      <div><span>WATCHING TERMINAL STATE</span><b class="v14-on">DISABLED</b></div>
      <div><span>LIVE BROKER</span><b class="v14-on">LOCKED</b></div>
    `;

    window.JARVIS_V14_EXECUTION_STATE={authority,lifecycle,controller,runtime};
  }

  function boot(){read();setInterval(read,2500)}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot);else boot();
})();
