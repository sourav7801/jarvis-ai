(()=>{
  "use strict";
  const $=id=>document.getElementById(id);
  const esc=value=>String(value??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const num=(value,digits=1)=>Number.isFinite(Number(value))?Number(value).toLocaleString(undefined,{maximumFractionDigits:digits}):"—";
  let worldActive=false;

  function installStyle(){
    if($("v93WorldStyle"))return;
    const style=document.createElement("style");
    style.id="v93WorldStyle";
    style.textContent=`
      .world-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin-bottom:14px}
      .world-card{border:1px solid #1a3a4b;background:#07151e;border-radius:10px;padding:12px;min-width:0}
      .world-card span{display:block;color:#6f94a4;font-size:10px;letter-spacing:.08em}.world-card b{display:block;color:#e3f8ff;font-size:20px;margin-top:4px}
      .world-list{display:grid;gap:8px}.world-node{border:1px solid #173849;background:#07131b;border-radius:9px;padding:10px;min-width:0}
      .world-node-head{display:flex;align-items:center;justify-content:space-between;gap:10px}.world-node-head strong{color:#dff8ff;font-size:12px}.world-node-head span{font-size:9px;padding:3px 7px;border-radius:999px;border:1px solid #244b5e}
      .world-fresh{color:#72efac}.world-stale{color:#ffbe6b}.world-meta{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:7px;margin-top:8px;font-size:9px;color:#7fa1af}.world-meta b{display:block;color:#b9dbe8;font-size:10px;margin-top:2px;overflow-wrap:anywhere}
      .world-state{margin-top:8px;background:#050d13;border:1px solid #112b38;border-radius:7px;padding:8px;white-space:pre-wrap;overflow-wrap:anywhere;max-height:170px;overflow:auto;font-size:9px;color:#8eb3c2}
      .world-toolbar{display:flex;gap:7px;flex-wrap:wrap;margin:8px 0 12px}.world-toolbar button{min-height:30px}.world-event{display:grid;grid-template-columns:1fr 1fr 2fr;gap:8px;padding:7px 2px;border-top:1px solid #112b38;font-size:9px;color:#87aab8}.world-event strong{color:#dff8ff}.world-event span{overflow-wrap:anywhere}
      @media(max-width:1100px){.world-grid{grid-template-columns:1fr 1fr}.world-meta{grid-template-columns:1fr 1fr}.world-event{grid-template-columns:1fr}.world-event span:last-child{grid-column:1}}
      @media(max-width:700px){.world-grid{grid-template-columns:1fr}.world-meta{grid-template-columns:1fr}}
    `;
    document.head.appendChild(style);
  }

  async function api(url,options={}){
    const response=await fetch(url,options);let payload={};try{payload=await response.json()}catch{}
    if(!response.ok||payload.success===false)throw new Error(payload.message||payload.error||`HTTP ${response.status}`);
    return payload;
  }

  function stringify(value){try{return JSON.stringify(value??{},null,2)}catch{return String(value??"")}}

  function worldMarkup(world,events){
    const nodes=Array.isArray(world?.nodes)?world.nodes:[];
    const eventRows=Array.isArray(events?.events)?events.events.slice().reverse():[];
    const stale=Number(world?.stale_count||0);
    const nodeMarkup=nodes.length?nodes.map(node=>{
      const freshness=node.stale?"STALE":"FRESH";
      return `<article class="world-node">
        <div class="world-node-head"><strong>${esc(node.label||node.node_id)}</strong><span class="${node.stale?"world-stale":"world-fresh"}">${freshness}</span></div>
        <div class="world-meta">
          <div>KIND<b>${esc(node.kind||"STATE")}</b></div>
          <div>CONFIDENCE<b>${num(Number(node.confidence||0)*100,1)}%</b></div>
          <div>AGE<b>${node.freshness_seconds==null?"—":num(node.freshness_seconds,1)+"s"}</b></div>
          <div>SOURCE<b>${esc(node.source||"—")}</b></div>
        </div>
        <pre class="world-state">${esc(stringify(node.state))}</pre>
      </article>`;
    }).join(""):'<div class="empty">No world-state observations yet.</div>';

    const eventMarkup=eventRows.length?eventRows.slice(0,30).map(row=>`<div class="world-event"><strong>${esc(row.event_type||"EVENT")}</strong><span>${esc(row.subject||"—")}</span><span>${esc(row.source||"—")} · ${esc(row.timestamp||"—")}</span></div>`).join(""):'<div class="empty">No cognitive events retained yet.</div>';

    return `<div class="world-grid">
      <article class="world-card"><span>WORLD NODES</span><b>${num(world?.node_count||0,0)}</b></article>
      <article class="world-card"><span>RELATION EDGES</span><b>${num(world?.edge_count||0,0)}</b></article>
      <article class="world-card"><span>STALE OBSERVATIONS</span><b class="${stale?"world-stale":"world-fresh"}">${num(stale,0)}</b></article>
      <article class="world-card"><span>COGNITIVE EVENTS</span><b>${num(events?.retained||0,0)}</b></article>
    </div>
    <section class="section"><div class="section-head"><h2>World State Graph</h2><small>Every observation carries source, confidence, timestamp and freshness.</small></div>
      <div class="world-toolbar"><button id="refreshWorldNow">REFRESH WORLD STATE</button><button id="refreshEventsNow">REFRESH EVENTS</button></div>
      <div class="world-list">${nodeMarkup}</div>
    </section>
    <section class="section"><div class="section-head"><h2>Cognitive Event Bus</h2><small>Typed, bounded internal coordination. No execution authority.</small></div>${eventMarkup}</section>`;
  }

  async function renderWorld({refresh=true}={}){
    worldActive=true;installStyle();
    document.querySelectorAll("[data-section]").forEach(button=>button.classList.remove("active"));
    $("worldNav")?.classList.add("active");
    if($("sectionKicker"))$("sectionKicker").textContent="V9.3 COGNITIVE STATE FABRIC";
    if($("sectionTitle"))$("sectionTitle").textContent="WORLD MODEL";
    if($("sectionMessage"))$("sectionMessage").textContent="Bounded local state with explicit provenance, freshness, confidence and typed cognitive events.";
    if($("content"))$("content").innerHTML='<div class="loading">Refreshing bounded world state…</div>';
    try{
      const [worldPayload,events]=await Promise.all([
        api(`/api/world${refresh?"?refresh=1":""}`),
        api("/api/cognitive-events")
      ]);
      if(!worldActive)return;
      const world=worldPayload.world||{};
      $("serviceState").textContent=`JARVIS WORLD MODEL · ${worldPayload.version||"9.3"}`;
      $("updatedAt").textContent=new Date().toLocaleString();
      $("content").innerHTML=worldMarkup(world,events);
      $("refreshWorldNow")?.addEventListener("click",()=>renderWorld({refresh:true}));
      $("refreshEventsNow")?.addEventListener("click",()=>renderWorld({refresh:false}));
    }catch(error){
      if(worldActive&&$("content"))$("content").innerHTML=`<div class="error">${esc(error.message)}</div>`;
    }
  }

  function bind(){
    const worldNav=$("worldNav");if(!worldNav)return;
    worldNav.addEventListener("click",()=>renderWorld({refresh:true}));
    document.querySelectorAll("[data-section]").forEach(button=>button.addEventListener("click",()=>{
      worldActive=false;worldNav.classList.remove("active");
    }));
  }

  installStyle();bind();
})();