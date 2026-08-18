
JARVIS TRADING WORKSTATION V7
=============================

Pages
-----
1. COMMAND CENTER — master JARVIS orchestration chat
2. CHART LAB — separate chart conversation
3. QUANT LAB — separate research conversation
4. PAPER DESK — startup-armed autonomous multi-asset paper portfolio
5. NEWS & IMPACT — separate contextual news conversation and spoken briefings

Chart layouts
-------------
1 / 2 / 3 / 4 / 6 / 8 charts at once.

Natural commands
-----------------
"Jarvis, open Nifty 50 last 2 months"
"Jarvis, open BankNifty 5 minute chart"
"Jarvis, compare Nifty and BankNifty"
"Jarvis, show 8 charts"
"Jarvis, find trades"
"Jarvis, show my paper portfolio"
"Jarvis, scan paper signals"
"Jarvis, arm paper trading"
"Jarvis, pause paper trading"
"Jarvis, paper buy 1 NIFTY"
"Jarvis, paper buy 0.01 BTC"
"Jarvis, paper sell 0.2 GOLD"
"Jarvis, show news impacting Nifty"
"Jarvis, tell me the top five crude oil headlines"
"Jarvis, read the first one"

Current status
--------------
The canonical workstation uses authenticated, read-only FYERS API v3 data for
live index quotes and historical OHLCV charts. The news page discovers current
source headlines through the keyless GDELT DOC 2.0 API, with Google News RSS as
a keyless fallback. Headline discovery is research context, not a trading signal
or a substitute for opening and verifying the linked report.

Chart Lab still avoids silently mapping friendly MCX names to invalid continuous
chart symbols. Paper Desk separately resolves current MCX front-month contracts
from FYERS's daily symbol master and rolls them without hard-coded expiries.

The paper execution layer now includes:
- durable synthetic positions, orders, closed trades, and P&L
- FYERS marking for NIFTY, BANKNIFTY, SENSEX, and four MCX mini contracts
- public Binance market-data-only marking for BTC, ETH, and SOL
- automatic startup arming, session-aware scans, and manual pause/scan controls
- 80%+ qualified-signal autopilot with 5% sizing, six-position cap, ATR exits,
  five-minute cadence/cooldown, and a 2% portfolio-loss halt

The remaining trading-research integrations are:
- options chain data
- optional premium/licensed news providers

Native FYERS charts
-------------------
Chart Lab renders broker historical candles locally on HTML canvas. It does not
load TradingView widgets, so NSE index charts do not depend on TradingView symbol
entitlements. The 1 / 2 / 3 / 4 / 6 / 8 layouts remain available.

Research safety
---------------
NO LIVE ORDER EXECUTION is implemented in this V7. Paper Desk never calls a
FYERS, Binance, or other order API. Trade candidates require current validated
market data and remain synthetic PAPER/RESEARCH positions.
