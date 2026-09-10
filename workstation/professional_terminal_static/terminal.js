/* One awaited refresh loop. Trading levels always come from the paper ledger. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const esc = value => String(value ?? '—').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const human = value => String(value ?? '').replace(/_/g, ' ').toLowerCase().replace(/^./, s => s.toUpperCase());
  const num = value => Number.isFinite(Number(value)) ? Number(value).toLocaleString('en-IN', {maximumFractionDigits:2}) : '—';
  const money = value => '₹' + num(value);
  const pct = value => num(Number(value) * 100) + '%';
  const when = value => value ? new Date(value).toLocaleString('en-IN', {timeZone:'Asia/Kolkata', hour12:false}) + ' IST' : '—';
  const saved = key => { try { return localStorage.getItem('jarvis.terminal.' + key); } catch { return null; } };
  const save = (key,value) => { try { localStorage.setItem('jarvis.terminal.' + key,value); } catch { /* Preferences are optional. */ } };
  let workspace = ['INTRADAY','SWING','INVESTMENT'].includes(saved('workspace')) ? saved('workspace') : 'INTRADAY';
  let symbol = saved(workspace + '.symbol') || 'NIFTY', timeframe = saved(workspace + '.timeframe') || (workspace === 'INTRADAY' ? '5m' : '1d');
  let state, token, view = 'terminal', blotter = 'positions', moduleName, selected, epoch = 0, bars = [], chartKey = '', lastChart = 0;
  let chart, series, markers, overlay, priceLines = [], firstFit = true, settingsDirty = true, toastTimer;
  const phases = {PAUSED:'Session paused',STARTING:'Starting session',SCANNING:'Scanning markets',WAITING_FOR_TRIGGER:'Waiting for a trigger',MANAGING_POSITION:'Managing positions',DATA_PROBLEM:'Market data problem',PROBLEM:'Session needs attention'};

  async function get(path, args={}) {
    const response = await fetch(path + '?' + new URLSearchParams(args), {signal:AbortSignal.timeout(6000),cache:'no-store'});
    const data = await response.json();
    if (!response.ok || data.success === false) throw Error(data.message || data.reason || 'Request failed');
    return data;
  }
  async function post(path, body) {
    const response = await fetch('/api/terminal/' + path, {method:'POST', headers:{'Content-Type':'application/json','X-Jarvis-Token':token || ''},body:JSON.stringify({workspace,...body}),signal:AbortSignal.timeout(6000)});
    const data = await response.json();
    if (!response.ok || data.success === false) throw Error(data.message || data.reason || 'Action failed');
    return data;
  }
  function toast(message) {
    $('toast').textContent = message; $('toast').classList.remove('hidden');
    clearTimeout(toastTimer); toastTimer = setTimeout(() => $('toast').classList.add('hidden'), 7000);
  }
  function table(headers, rows) {
    if (!rows.length) return '<p class="empty">No records in this workspace.</p>';
    return '<table><thead><tr>' + headers.map(h => '<th>' + esc(h) + '</th>').join('') + '</tr></thead><tbody>' + rows.map(r => '<tr>' + r.map(c => '<td>' + c + '</td>').join('') + '</tr>').join('') + '</tbody></table>';
  }
  const value = (label, data) => '<div><span class="muted">' + esc(label) + '</span><strong>' + esc(data) + '</strong></div>';
  const selectButton = (label,type,id) => '<button class="textbutton" data-select="' + type + '" data-id="' + esc(id) + '">' + esc(label) + '</button>';
  function chooseSymbol(next) {
    symbol = next; save(workspace + '.symbol',symbol); epoch++; resetChart();
    selected = null; render();
  }
  function setWorkspace(next) {
    workspace = next; save('workspace',workspace); symbol = saved(workspace + '.symbol') || 'NIFTY';
    timeframe = saved(workspace + '.timeframe') || (workspace === 'INTRADAY' ? '5m' : '1d');
    state = null; selected = null; settingsDirty = true; epoch++; resetChart();
    $('sessionButton').disabled = true; $('sessionState').textContent = 'Loading workspace';
    ['equity','available','committed','openRisk','dailyPnl','dailyLimit'].forEach(id => $(id).textContent = '—');
    ['blotter','journal','notes','setups','tradeReasoning','capitalSummary','performance','watchlist'].forEach(id => $(id).replaceChildren());
    $('moduleResult').textContent = 'Select an analysis tool.'; moduleName = null;
    document.querySelectorAll('[data-workspace]').forEach(b => b.classList.toggle('active', b.dataset.workspace === workspace));
    $('workspaceLabel').textContent = workspace + ' WORKSPACE';
    $('researchTab').textContent = workspace === 'INVESTMENT' ? 'Research & thesis' : 'Setups & alerts';
    $('researchTitle').textContent = $('researchTab').textContent;
    $('noteKind').value = workspace === 'INVESTMENT' ? 'thesis' : 'alert'; toggleNoteKind();
  }
  function render() {
    $('chartSymbol').textContent = symbol; $('analysisSymbol').textContent = symbol; $('timeframe').value = timeframe;
    if (!state) return;
    const a = state.account;
    $('sessionState').textContent = phases[state.state] || human(state.state);
    $('sessionReason').textContent = state.status_reason;
    $('sessionButton').disabled = false;
    $('sessionButton').textContent = state.entry_session === 'RUNNING' || state.state === 'STARTING' ? 'Pause new entries' : 'Start paper session';
    $('sessionButton').classList.toggle('pause',state.entry_session === 'RUNNING');
    for (const [id,key] of Object.entries({equity:'equity',available:'available_capital',committed:'committed_capital',openRisk:'open_risk',dailyPnl:'daily_pnl',dailyLimit:'daily_loss_limit'})) $(id).textContent = money(a[key]);
    $('dailyPnl').className = a.daily_pnl < 0 ? 'negative' : 'positive';
    $('watchCount').textContent = a.settings.symbols.length;
    const instruments = [...new Set([...a.settings.symbols,...a.positions.map(p => p.symbol)])];
    $('watchlist').innerHTML = instruments.map(s => {
      const p = a.positions.find(p => p.symbol === s), quote = state.marks[s];
      return '<button class="watchitem ' + (s === symbol ? 'active' : '') + '" data-symbol="' + esc(s) + '"><strong>' + esc(s) + '</strong><span>' + (p ? 'PAPER · ' + esc(p.side) : quote?.eligible_for_entry ? num(quote.mark) : 'Scan instrument') + '</span></button>';
    }).join('');
    $('scanCycles').textContent = state.scan.cycles + ' scan cycles';
    renderSetups(); renderBlotter(); renderJournal(); renderNotes(); renderCapital(); updateOverlay();
    $('lastUpdate').textContent = 'Ledger updated ' + when(state.generated_at);
    if ($('diagnostics').open) renderDiagnostics();
  }
  function renderSetups() {
    const rows = state.scan.rows.filter(r => Number(r.entry) > 0 && Number(r.stop) > 0 && Number(r.target) > 0);
    $('setupCount').textContent = rows.length;
    $('setups').innerHTML = rows.length ? rows.map(r => '<button class="setupitem" data-select="setup" data-id="' + esc(state.scan.rows.indexOf(r)) + '"><strong>' + esc(r.symbol) + ' · ' + esc(r.side || r.signal || r.action || '') + '</strong><span>' + esc(r.strategy || r.profile || '') + '</span></button>').join('') : '<p class="muted">No eligible setup yet. Scan decisions below explain what is missing.</p>';
  }
  function renderBlotter() {
    let headers, rows;
    if (blotter === 'positions') {
      headers = [workspace === 'INVESTMENT' ? 'Holding' : 'Instrument','Side / size','Entry','Last mark','Stop / target','P&L','Capital / risk'];
      rows = state.account.positions.map(p => [selectButton(p.symbol,'position',p.id),esc(p.side) + ' · ' + num(p.quantity),num(p.entry),num(p.mark) + (!state.marks[p.symbol]?.eligible_for_exit ? '<small class="negative">Mark unverified / frozen</small>' : ''),num(p.stop) + ' / ' + num(p.target),'<span class="' + (p.unrealized_pnl < 0 ? 'negative' : 'positive') + '">' + money(p.unrealized_pnl) + '</span>',money(p.capital_allocated) + ' / ' + money(p.capital_at_risk)]);
    } else if (blotter === 'orders') {
      headers = ['Time (IST)','Instrument','Action','Status','Reason','Paper position'];
      rows = state.orders.map(o => [esc(when(o.created_at)),esc(o.payload.symbol),esc(human(o.kind || 'ENTRY')) + ' · ' + esc(o.payload.side),esc(o.status),esc(human(o.reason)),o.position_id ? selectButton('#' + o.position_id,'position',o.position_id) : '—']);
    } else {
      headers = ['Instrument','Strategy / lane','Decision','Reason'];
      rows = state.scan.rows.map((r,i) => [selectButton(r.symbol,'setup',i),esc(r.strategy || r.profile),esc(r.action || r.side || r.signal || 'WAIT'),esc(human(r.reason || r.message || r.blocker || (r.blockers || []).join(', ') || 'See strategy evidence'))]);
      const rejects = Object.entries(state.scan.rejections).map(([reason,count]) => '<span class="chip">' + esc(human(reason)) + ' · ' + num(count) + '</span>').join('');
      $('blotter').innerHTML = '<div class="pad">' + rejects + '</div>' + table(headers,rows); return;
    }
    $('blotter').innerHTML = table(headers,rows);
  }
  function renderJournal() {
    $('performance').innerHTML = '<div class="detailgrid">' + value('Realized P&L',money(state.performance.realized_pnl)) + value('Unrealized P&L',money(state.performance.unrealized_pnl)) + value('Closed trades displayed',num(state.performance.displayed_closed_trades)) + value('Winning trades displayed',num(state.performance.wins)) + '</div>';
    $('journal').innerHTML = table(['Closed (IST)','Instrument','Strategy','Entry → exit','Quantity','Net P&L','Exit reason'],state.history.map(p => [esc(when(p.closed_at)),selectButton(p.symbol,'history',p.id),esc(p.strategy),num(p.entry) + ' → ' + num(p.exit_price),num(p.initial_quantity || p.metadata.initial_quantity || p.quantity),money(p.realized_pnl),esc(human(p.close_reason || p.exit_reason || p.metadata.exit_reason))]));
  }
  function renderNotes() {
    $('notes').innerHTML = state.notes.length ? state.notes.map(n => '<article class="notecard"><h3>' + esc(n.symbol) + ' <small>' + esc(human(n.kind)) + '</small></h3><p>' + esc(n.body.text || '') + '</p>' + (n.kind === 'alert' ? '<p>' + esc(human(n.body.condition)) + ' ' + num(n.body.level) + ' · ' + (n.body.triggered_at ? 'Triggered ' + esc(when(n.body.triggered_at)) : 'Waiting for a valid live quote') + '</p>' : '') + '<small class="muted">' + esc(when(n.updated_at)) + '</small></article>').join('') : '<p class="muted">Save a thesis or price alert for this workspace.</p>';
  }
  function renderCapital() {
    $('capitalSummary').innerHTML = table(['Workspace','Allocation','Equity','Committed','Available','At risk'],Object.values(state.accounts).map(a => [esc(human(a.workspace)),pct(a.allocation),money(a.equity),money(a.committed_capital),money(a.available_capital),money(a.open_risk)]));
    if (!settingsDirty) return;
    const cfg = state.account.settings;
    for (const name of ['INTRADAY','SWING','INVESTMENT']) $('alloc' + human(name)).value = num(state.accounts[name].allocation * 100).replace(/,/g,'');
    for (const [id,key] of Object.entries({riskPerTrade:'risk_per_trade',totalRisk:'open_risk',dailyLoss:'daily_loss',concentration:'concentration'})) $(id).value = cfg[key] * 100;
    $('maxPositions').value = cfg.max_positions; $('symbols').value = cfg.symbols.join(', ');
    $('costForm').innerHTML = Object.entries(cfg.costs).map(([key,v]) => '<label>' + esc(human(key)) + '<input type="number" name="' + esc(key) + '" value="' + esc(v) + '" min="0" max="1000" step="any" required></label>').join('') + '<button class="primary" type="submit">Save cost assumptions</button>';
    settingsDirty = false;
  }
  function renderDiagnostics() {
    $('diagnosticSummary').textContent = state.monitor.error || 'Position monitoring runs independently of entry sessions. A frozen mark does not simulate an exit.';
    $('diagnosticData').textContent = JSON.stringify({reconciliation:state.reconciliation,data_bridge:state.data_bridge,monitor:state.monitor,cache:state.cache,scan:state.scan.rejections,marks:state.marks,paper_only:state.paper_only,live_execution:state.live_execution},null,2);
  }
  function selectedTrade() {
    if (selected?.type === 'history') { const p=state.history.find(p => p.id === selected.id); return p ? {...p,executed:true,closed:true} : null; }
    if (selected?.type === 'setup') { const p=state.scan.rows.find(p => setupKey(p) === selected.key); return p ? {...p,executed:false} : null; }
    const open = state.account.positions.find(p => selected?.type === 'position' ? p.id === selected.id : p.symbol === symbol);
    if (open) return {...open,executed:true};
    if (selected?.type === 'position') { const p=state.history.find(p => p.id === selected.id); return p ? {...p,executed:true,closed:true} : null; }
    const setup = state.scan.rows.find(p => p.symbol === symbol && Number(p.entry) > 0);
    return setup ? {...setup,executed:false} : null;
  }
  function setupKey(p) { return JSON.stringify([p?.symbol,p?.profile,p?.strategy,p?.entry,p?.stop,p?.target]); }
  function updateOverlay() {
    if (!state) return;
    const p = selectedTrade();
    if (!p || p.symbol !== symbol || ![p.entry,p.stop,p.target].every(v => Number.isFinite(Number(v)) && Number(v) > 0)) {
      $('proposalBadge').textContent = 'NO SETUP'; $('tradeReasoning').innerHTML = '<p class="muted">No trade geometry for this instrument. Select a setup or position.</p>';
      overlay?.set(null); clearLines(); return;
    }
    const sizing = p.metadata?.workspace_sizing || p.workspace_sizing;
    const rr = Math.abs((p.target-p.entry)/(p.entry-p.stop));
    $('proposalBadge').textContent = p.closed ? 'CLOSED PAPER' : p.executed ? 'EXECUTED PAPER' : 'PROPOSED';
    $('tradeReasoning').innerHTML = '<h3>' + esc(p.side || p.action || 'Setup') + ' · ' + esc(p.symbol) + '</h3><p class="muted">' + esc(p.strategy || p.profile || '') + '</p><div class="detailgrid">' + value('Entry',num(p.entry)) + value('Stop',num(p.stop)) + value('Target',num(p.target)) + value('Reward / risk',num(rr) + ' R') + value('Quantity',p.quantity ? num(p.quantity) : 'Sized at admission') + value('Contract units',sizing ? num(sizing.contract_multiplier) : '—') + '</div>' + (sizing ? '<p><strong>' + esc(sizing.limiting_constraint) + '</strong> sets this size.</p><div class="detailgrid">' + value('Allocated',money(sizing.capital_allocated)) + value('At risk incl. costs',money(sizing.capital_at_risk)) + value('Evidence risk weight',pct(sizing.risk_weight)) + value('Risk budget',money(sizing.risk_budget)) + '</div><p class="muted">Evidence weight is uncalibrated. It is capped at 25% of the risk budget.</p>' : '<p class="muted">Proposed levels are estimates. Fresh data, verified specifications and available workspace capital are checked at admission.</p>') + '<details><summary>Decision evidence</summary><pre>' + esc(JSON.stringify(p.metadata?.adaptive_decision || p.metadata?.reasoning || p.metadata || p.evidence || p,null,2)) + '</pre></details>';
    if (overlay) { overlay.set(p); drawLines(p); drawMarkers(); }
  }
  function initChart() {
    if (!window.LightweightCharts) { $('chartEmpty').textContent = 'Chart library unavailable'; return; }
    chart = LightweightCharts.createChart($('chart'),{autoSize:true,layout:{background:{color:'#111b26'},textColor:'#9eafc2'},grid:{vertLines:{color:'#1c2938'},horzLines:{color:'#1c2938'}},rightPriceScale:{borderColor:'#2b3b4d'},timeScale:{rightOffset:12,timeVisible:true,secondsVisible:false,borderColor:'#2b3b4d'},localization:{locale:'en-IN',timeFormatter:t => new Date(Number(t)*1000).toLocaleString('en-IN',{timeZone:'Asia/Kolkata',hour12:false})}});
    series = chart.addSeries(LightweightCharts.CandlestickSeries,{upColor:'#3eb99a',downColor:'#e8727f',wickUpColor:'#3eb99a',wickDownColor:'#e8727f',borderVisible:false});
    markers = LightweightCharts.createSeriesMarkers(series,[]);
    overlay = new RiskOverlay(); series.attachPrimitive(overlay);
  }
  class RiskOverlay {
    attached({chart,series,requestUpdate}) { this.chart=chart; this.series=series; this.requestUpdate=requestUpdate; }
    detached() { this.requestUpdate=null; }
    set(trade) { this.trade=trade; this.requestUpdate?.(); }
    autoscaleInfo() {
      if (!this.trade) return null;
      const prices=[this.trade.entry,this.trade.stop,this.trade.target].map(Number);
      return {priceRange:{minValue:Math.min(...prices),maxValue:Math.max(...prices)}};
    }
    paneViews() { return [{zOrder:()=>'bottom',renderer:()=>({draw:target=>this.draw(target)})}]; }
    draw(target) {
      const p=this.trade; if (!p) return;
      target.useMediaCoordinateSpace(({context:ctx,mediaSize:size}) => {
        const entry=this.series.priceToCoordinate(Number(p.entry)), stop=this.series.priceToCoordinate(Number(p.stop)), profit=this.series.priceToCoordinate(Number(p.target));
        if ([entry,stop,profit].some(v=>v===null)) return;
        const opened = p.opened_at ? Math.floor(Date.parse(p.opened_at)/1000) : null;
        const start = opened && bars.length ? this.chart.timeScale().timeToCoordinate(nearestBar(opened)) : null;
        const x = start === null ? size.width * .60 : Math.max(0,start);
        ctx.fillStyle = p.executed ? 'rgba(230,93,111,.24)' : 'rgba(230,93,111,.12)';
        ctx.fillRect(x,Math.min(entry,stop),size.width-x,Math.abs(entry-stop));
        ctx.fillStyle = p.executed ? 'rgba(48,186,145,.24)' : 'rgba(48,186,145,.12)';
        ctx.fillRect(x,Math.min(entry,profit),size.width-x,Math.abs(entry-profit));
      });
    }
  }
  function clearLines() { if (series) priceLines.forEach(l=>series.removePriceLine(l)); priceLines=[]; }
  function drawLines(p) {
    clearLines();
    for (const [key,label,color] of [['entry','Entry','#b9c9dd'],['stop','Stop','#e8727f'],['target','Target','#3eb99a']]) priceLines.push(series.createPriceLine({price:Number(p[key]),color,lineWidth:1,lineStyle:p.executed ? LightweightCharts.LineStyle.Solid : LightweightCharts.LineStyle.Dashed,axisLabelVisible:true,title:label}));
  }
  function nearestBar(t) { let best=bars[0]?.time; for (const b of bars) { if (b.time > t) break; best=b.time; } return best; }
  function drawMarkers() {
    if (!markers || !bars.length) return;
    const trades=[...state.account.positions,...state.history].filter(p=>p.symbol === symbol), result=[];
    for (const p of trades) {
      for (const [time,exit] of [[p.opened_at,false],[p.closed_at,true]]) {
        if (!time) continue; const t=Date.parse(time)/1000;
        if (t < bars[0].time || t > bars.at(-1).time + seconds()) continue;
        const long=p.side==='LONG';
        result.push({time:nearestBar(t),position:(exit ? !long : long) ? 'belowBar':'aboveBar',color:exit ? '#c7a8ea' : '#58c8b0',shape:exit ? 'circle':long ? 'arrowUp':'arrowDown',text:(exit ? 'Exit #':'Paper #') + p.id});
      }
    }
    markers.setMarkers(result.sort((a,b)=>a.time-b.time));
  }
  function resetChart() {
    bars=[]; chartKey=''; lastChart=0; firstFit=true; series?.setData([]); markers?.setMarkers([]); overlay?.set(null); clearLines();
    $('chartEmpty').classList.remove('hidden'); $('chartEmpty').textContent='Loading provider candles…'; $('dataStatus').textContent='Awaiting verified quote';
  }
  function seconds() { return {'1m':60,'5m':300,'15m':900,'1h':3600,'4h':14400,'1d':86400}[timeframe] || 300; }
  function applyQuote(quote) {
    const valid = quote.eligible_for_entry === true;
    $('dataStatus').textContent = valid ? (quote.source || 'Provider') + ' · live · ' + num(quote.age_seconds) + 's' : human(quote.reason || 'Quote unavailable') + ' · entries blocked';
    $('dataStatus').className = valid ? 'positive' : 'negative';
    if (!valid || !bars.length || !series) return;
    const raw=quote.exchange_timestamp, numeric=Number(raw), span=seconds();
    const t=Number.isFinite(numeric) ? numeric / (numeric > 1e12 ? 1000 : 1) : Date.parse(raw)/1000;
    if (span >= 86400) return; // Daily candle boundaries are provider-owned.
    // Anchor Indian intraday candles at 09:15 IST; never synthesize missing bars.
    const crypto=String(quote.source).startsWith('BINANCE'), anchor=crypto ? 0 : 13500;
    const bucket=Math.floor((t-anchor)/span)*span+anchor, last=bars.at(-1), price=Number(quote.mark);
    if (!Number.isFinite(bucket) || bucket < last.time || !Number.isFinite(price)) return;
    if (bucket === last.time) { Object.assign(last,{high:Math.max(last.high,price),low:Math.min(last.low,price),close:price}); series.update(last); }
    // New bars come from provider history so open/volume are not invented from
    // a partial stream subscription. A quote remains visible beside the chart.
  }
  async function refreshMarket(expected) {
    if (view !== 'terminal') return;
    const key=workspace+symbol+timeframe;
    if (Date.now()-lastChart > 10000 || chartKey!==key) {
      try {
        const data=await get('/api/terminal/chart',{symbol,timeframe});
        if (expected!==epoch) return;
        if (!data.pending) {
          const p=data.result;
          if (!p?.success || !p.candles?.length) throw Error(p?.message || 'Provider candles unavailable');
          bars=p.candles.map(b=>({time:Number(b.time),open:Number(b.open),high:Number(b.high),low:Number(b.low),close:Number(b.close)}));
          series?.setData(bars); chartKey=key; lastChart=Date.now();
          $('chartEmpty').classList.add('hidden');
          if (firstFit) { chart?.timeScale().fitContent(); firstFit=false; }
          if (p.quote) applyQuote(p.quote); updateOverlay(); drawMarkers();
        }
      } catch(error) { if(expected!==epoch)return; $('chartEmpty').textContent=error.message; $('chartEmpty').classList.remove('hidden'); lastChart=Date.now(); chartKey=key; }
    }
    try { const q=await get('/api/terminal/quote',{symbol}); if(expected===epoch && !q.pending) applyQuote(q.result); }
    catch(error) { if(expected===epoch) { $('dataStatus').textContent=error.message; $('dataStatus').className='negative'; } }
  }
  function rich(data,depth=0) {
    if (data === null || data === undefined) return '<span class="muted">Unavailable</span>';
    if (typeof data !== 'object') return esc(typeof data === 'number' ? num(data) : data);
    if (depth > 3) return '<details><summary>Full evidence</summary><pre>' + esc(JSON.stringify(data,null,2)) + '</pre></details>';
    if (Array.isArray(data)) {
      if (!data.length) return '<p class="muted">No records available.</p>';
      if (data.every(v=>v && typeof v==='object' && !Array.isArray(v))) {
        const keys=[...new Set(data.flatMap(Object.keys))].slice(0,18);
        return '<div class="tablewrap">' + table(keys.map(human),data.slice(0,100).map(row=>keys.map(k=>rich(row[k],depth+1)))) + '</div>';
      }
      return '<ul>' + data.map(v=>'<li>'+rich(v,depth+1)+'</li>').join('')+'</ul>';
    }
    return '<div class="evidencecards">' + Object.entries(data).filter(([k])=>!['metadata_json','generated_at'].includes(k)).map(([k,v])=>'<section><h3>' + esc(human(k)) + '</h3>' + rich(v,depth+1) + '</section>').join('') + '</div>';
  }
  async function refreshModule(expected) {
    if (view!=='analysis' || !moduleName) return;
    const requested=moduleName;
    try {
      const data=await get('/api/terminal/module',{workspace,symbol,module:requested});
      if(expected!==epoch || requested!==moduleName)return;
      if (data.pending) { $('moduleResult').textContent='Analyzing '+symbol+'… Trading and position monitoring continue.'; return; }
      $('moduleResult').innerHTML=rich(data.result); moduleName=null;
    } catch(error) { if(expected===epoch) { $('moduleResult').textContent=error.message; moduleName=null; } }
  }
  async function poll() {
    let delay=1500; const expected=epoch;
    try {
      const data=await get('/api/terminal/state',{workspace});
      if(expected===epoch) { state=data; token=data.csrf_token; render(); await refreshMarket(expected); await refreshModule(expected); }
    } catch(error) {
      if(expected===epoch) { $('sessionState').textContent='Connection interrupted'; $('sessionReason').textContent=error.message+' · reconnecting'; $('sessionButton').disabled=true; $('lastUpdate').textContent='Displayed values are from the last successful response'; }
      delay=4000;
    }
    setTimeout(poll,document.hidden ? Math.max(delay,6000) : delay);
  }
  document.addEventListener('click',event=>{
    const b=event.target.closest('button'); if(!b)return;
    if(b.dataset.workspace) setWorkspace(b.dataset.workspace);
    if(b.dataset.symbol) chooseSymbol(b.dataset.symbol);
    if(b.dataset.view) { view=b.dataset.view; document.querySelectorAll('.view').forEach(v=>v.classList.toggle('hidden',v.id!==view+'View')); document.querySelectorAll('[data-view]').forEach(v=>v.classList.toggle('active',v===b)); if(view==='terminal') chart?.resize($('chart').clientWidth,$('chart').clientHeight); }
    if(b.dataset.blotter) { blotter=b.dataset.blotter; document.querySelectorAll('[data-blotter]').forEach(v=>v.classList.toggle('active',v===b)); if(state)renderBlotter(); }
    if(b.dataset.select && state) {
      selected={type:b.dataset.select,id:Number(b.dataset.id)};
      if(selected.type==='setup') selected.key=setupKey(state.scan.rows[selected.id]);
      const p=selectedTrade();
      if(p?.symbol && symbol!==p.symbol) { symbol=p.symbol; save(workspace+'.symbol',symbol); epoch++; resetChart(); }
      document.querySelector('[data-view="terminal"]').click(); render();
    }
    if(b.dataset.module) { moduleName=b.dataset.module; document.querySelectorAll('[data-module]').forEach(v=>v.classList.toggle('active',v===b)); $('moduleResult').textContent='Loading analysis…'; }
  });
  $('sessionButton').onclick=async()=>{ if(!state)return; const b=$('sessionButton'); b.disabled=true; try { const r=await post('session',{action:state.entry_session==='RUNNING' || state.state==='STARTING' ? 'pause':'start'}); toast(r.state==='PAUSED' ? 'Entries paused. Existing positions remain monitored.' : 'Starting workspace session.'); } catch(e){toast(e.message);} finally {b.disabled=false;} };
  $('timeframe').onchange=()=>{timeframe=$('timeframe').value;save(workspace+'.timeframe',timeframe);epoch++;resetChart();};
  $('diagnosticsButton').onclick=()=>{if(state)renderDiagnostics();$('diagnostics').showModal();}; $('closeDiagnostics').onclick=()=>$('diagnostics').close();
  function toggleNoteKind() { const alert=$('noteKind').value==='alert'; $('alertConditionLabel').classList.toggle('hidden',!alert);$('alertLevelLabel').classList.toggle('hidden',!alert);$('alertLevel').required=alert; }
  $('noteKind').onchange=toggleNoteKind;
  $('noteForm').onsubmit=async e=>{e.preventDefault();try{await post('note',{kind:$('noteKind').value,symbol:$('noteSymbol').value,body:{text:$('noteText').value,condition:$('alertCondition').value,level:Number($('alertLevel').value)}});toast('Workspace record saved.');$('noteText').value='';}catch(error){toast(error.message);}};
  $('riskForm').onsubmit=async e=>{e.preventDefault();try{const allocations={INTRADAY:Number($('allocIntraday').value)/100,SWING:Number($('allocSwing').value)/100,INVESTMENT:Number($('allocInvestment').value)/100};const changed=Object.keys(allocations).some(k=>Math.abs(allocations[k]-state.accounts[k].allocation)>1e-9);await post('settings',{...(changed?{allocations}:{}),settings:{risk_per_trade:Number($('riskPerTrade').value)/100,open_risk:Number($('totalRisk').value)/100,daily_loss:Number($('dailyLoss').value)/100,concentration:Number($('concentration').value)/100,max_positions:Number($('maxPositions').value),symbols:$('symbols').value.split(',').map(s=>s.trim()).filter(Boolean)}});settingsDirty=true;toast('Capital and risk settings saved.');}catch(error){toast(error.message);}};
  $('costForm').onsubmit=async e=>{e.preventDefault();try{await post('settings',{settings:{costs:Object.fromEntries([...new FormData(e.target)].map(([k,v])=>[k,Number(v)]))}});settingsDirty=true;toast('Paper cost assumptions saved.');}catch(error){toast(error.message);}};
  const modules={'option-chain':'Option chain','oi-iv':'OI & IV','liquidity':'Liquidity','order-flow':'Order flow','structure':'Structure','fvg':'Fair value gaps','patterns':'Patterns','heatmaps':'Heatmaps','adaptive-brain':'Strategy reasoning','portfolio-risk':'Portfolio risk','strategy-lab':'Strategy lab','learning':'Learning','self-improvement':'Research improvements'};
  $('moduleTabs').innerHTML=Object.entries(modules).map(([key,label])=>'<button data-module="'+key+'">'+label+'</button>').join('');
  initChart(); setWorkspace(workspace); poll();
})();
