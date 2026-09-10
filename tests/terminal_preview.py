"""UI QA fixtures only; a temporary ledger and no external market connections."""
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
import math
import tempfile
import threading

from workstation.paper_trading_desk import PaperTradingDesk
from workstation import workspace_accounts as accounts
from workstation.professional_terminal import TerminalRuntime, TerminalHTTPServer, build_handler
from workstation.quant_terminal_v2 import Handler
from tests.test_professional_terminal import stub_engine, quote


def main():
    with tempfile.TemporaryDirectory() as folder:
        desk=PaperTradingDesk(Path(folder)/'fixture.sqlite3')
        accounts.initialize(desk)
        # Fixture generation uses the original isolated ledger method. The
        # professional HTTP handler still cannot bypass admission.
        for name,symbol,side,stop,target in [('INTRADAY','NIFTY','LONG',98,106),('SWING','NSE:RELIANCE-EQ','SHORT',102,94)]:
            desk._open_position(symbol=symbol,side=side,entry=100,stop=stop,target=target,quantity=10,portfolio_bucket=name,strategy='UI TEST FIXTURE',metadata={'workspace_sizing':{'capital_allocated':1000,'capital_at_risk':20,'risk_weight':.2,'risk_budget':100,'contract_multiplier':1,'limiting_constraint':'Fixture risk budget'}})
        controller=SimpleNamespace(engines={n:stub_engine() for n in accounts.WORKSPACES},allocations={},start_bucket=lambda *args,**kw:None)
        runtime=TerminalRuntime(desk,controller,mark_loader=lambda s:{**quote(s,100),'eligible_for_entry':False,'eligible_for_exit':False,'simulated':True,'reason':'SIMULATED_UI_TEST_FIXTURE'})
        original=runtime.snapshot
        def snapshot(name='INTRADAY'):
            result=original(name)
            result['status_reason']='UI TEST FIXTURE · Simulated data · Temporary paper ledger'
            result['scan']['rows']=[{'symbol':'BANKNIFTY','side':'SHORT','entry':100,'stop':102,'target':94,'strategy':'PROPOSED UI FIXTURE','action':'WAIT'}] if name=='INTRADAY' else []
            return result
        runtime.snapshot=snapshot
        def chart(symbol,timeframe):
            span={'1m':60,'5m':300,'15m':900,'1h':3600,'4h':14400,'1d':86400}.get(timeframe,300)
            end=int(datetime.now(timezone.utc).timestamp())//span*span
            candles=[]
            for i in range(80):
                op=100+math.sin(i/6)*1.7;cl=op+math.cos(i/3)*.5
                candles.append({'time':end-(79-i)*span,'open':op,'high':max(op,cl)+.6,'low':min(op,cl)-.6,'close':cl})
            return {'success':True,'pending':False,'result':{'success':True,'candles':candles,'quote':runtime.mark_loader(symbol),'simulated':True}}
        runtime.chart=chart
        runtime.module=lambda name,symbol,module:{'success':True,'pending':False,'result':{'status':'UI TEST FIXTURE','workspace':name,'symbol':symbol,'module':module,'no_live_data':True}}
        with TerminalHTTPServer(('127.0.0.1',8799),build_handler(Handler,runtime)) as server:
            print('Isolated UI fixtures ready; no provider or broker connection.',flush=True)
            try: server.serve_forever()
            finally: runtime.stop()


if __name__=='__main__': main()
