const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('workstation/jarvis_os_v3_assets/v16_main_trading_runtime.js', 'utf8').replace(/v16InstallMainTradingRuntime\(\);\s*$/, '');
let reads = 0;
const ctx = vm.createContext({Map, Date, Promise, setTimeout, clearTimeout, console,
  selectedTimeframe:'5m', chartSlots:[], setChartCount(){}, renderChartSlots(){}, loadChart(){},
  fetch:async()=>{ reads++; await new Promise(r=>setTimeout(r,20)); return {ok:true,json:async()=>({success:true,candles:[{time:1,open:1,high:2,low:1,close:2}]})}; }
});
vm.runInContext(source,ctx);
(async()=>{
  await vm.runInContext("Promise.all(Array.from({length:8},()=>v16FetchChart('BTC','5m')))",ctx);
  assert.equal(reads,1,'eight identical slots must share one in-flight request');
  await vm.runInContext("v16FetchChart('BTC','5m')",ctx);
  assert.equal(reads,1,'cached history should not reload');
  for(let n=1;n<=8;n++) assert.equal(vm.runInContext(`v16NormalizeChartCount(${n})`,ctx),n);
  console.log('PASS chart request coalescing, cached reuse, exact 1-8 normalization');
})().catch(e=>{console.error(e);process.exitCode=1;});
