(()=>{
  "use strict";
  const $=id=>document.getElementById(id);
  const esc=v=>String(v??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const n=(v,d=2)=>Number.isFinite(Number(v))?Number(v).toFixed(d):"—";
  const supported=new Set(["NIFTY","BANKNIFTY","SENSEX"]);

  function selectedSymbol(){
    const value=String($("scanSymbol")?.textContent||"NIFTY").trim().toUpperCase();
    return supported.has(value)?value:"NIFTY";
  }
  function style(){
    if($("v151OptionsStyle"))return;
    const s=document.createElement("style");
    s.id="v151OptionsStyle";
    s.textContent=`#v151OptionsCard{border:1px solid #5d4b79;background:#110c1a;border-radius:8px;padding:8px;margin-top:7px;font-size:9px}#v151OptionsGrid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:5px;margin-top:6px}#v151OptionsGrid div{border:1px solid #3a2f4d;background:#0e0a15;border-radius:5px;padding:5px}#v151OptionsGrid span{display:block;color:#a58dbd;font-size:8px}#v151OptionsGrid b{display:block;color:#f4eaff;margin-top:2px;overflow-wrap:anywhere}.v151-ok{color:#7cf0aa!important}.v151-warn{color:#ffd27a!important}.v151-bad{color:#ff9c9c!important}`;
    document.head.appendChild(s);
  }
  async function getPlan(){
    const symbol=encodeURIComponent(selectedSymbol());
    const r=await fetch(`/api/v15.1/options/plan?symbol=${symbol}&provider=fyers`,{cache:"no-store"});
    if(!r.ok)throw new Error(String(r.status));
    return await r.json();
  }
  function render(plan){
    style();
    let card=$("v151OptionsCard");
    if(!card){
      card=document.createElement("section");
      card.id="v151OptionsCard";
      card.className="intel-card";
      const panel=document.querySelector(".intel-panel");
      if(panel)panel.insertBefore(card,panel.children[1]||null);
    }
    if(!card)return;
    const selected=plan?.selected||{};
    const risk=selected?.risk_plan||{};
    const q=selected?.quote||{};
    const econ=selected?.economics||{};
    const executable=plan?.executable===true;
    const action=String(plan?.action||"NO_OPTION_TRADE");
    const reason=String(plan?.reason||"NO_OPTION_TRACE");
    card.innerHTML=`<div class="eyebrow">V15.1 OPTIONS EXECUTION · ${esc(plan?.underlying||selectedSymbol())}</div>
      <b class="${executable?"v151-ok":"v151-warn"}">${esc(action)} · ${esc(reason)}</b>
      <div id="v151OptionsGrid">
        <div><span>CONTRACT</span><b>${esc(selected?.symbol||"—")}</b></div>
        <div><span>EXPIRY / STRIKE</span><b>${esc(selected?.expiry||"—")} · ${n(selected?.strike,0)}</b></div>
        <div><span>PREMIUM ENTRY / STOP / TARGET</span><b>${n(risk?.entry)} / ${n(risk?.stop)} / ${n(risk?.target)}</b></div>
        <div><span>OPTION EV / UTILITY</span><b>${n(selected?.option_expected_value_r,3)}R / ${n(selected?.option_utility,4)}</b></div>
        <div><span>DELTA / THETA / IV</span><b>${q?.delta??"UNAVAILABLE"} / ${q?.theta??"UNAVAILABLE"} / ${q?.implied_volatility??"UNAVAILABLE"}</b></div>
        <div><span>SPREAD</span><b>${econ?.spread_pct==null?"UNAVAILABLE":n(Number(econ.spread_pct)*100,2)+"%"}</b></div>
        <div><span>OPTION MODE</span><b>LONG PREMIUM · PAPER ONLY</b></div>
        <div><span>LIVE BROKER</span><b class="v151-ok">LOCKED</b></div>
      </div>`;
    window.JARVIS_V151_OPTIONS_PLAN=plan;
  }
  async function read(){try{render(await getPlan())}catch(e){render({underlying:selectedSymbol(),action:"NO_OPTION_TRADE",reason:`OPTIONS_TRACE_UNAVAILABLE:${e.message||e}`,executable:false})}}
  function boot(){read();setInterval(read,6000)}
  if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",boot);else boot();
})();
