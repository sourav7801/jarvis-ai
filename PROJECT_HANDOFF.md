# JARVIS Project Handoff

Last verified: 2026-08-25 (Asia/Kolkata)
Workspace: C:\Jarvis
Branch: jarvis-dev/20260820-011315-JARVIS-Quant-Trading-Intelligence-V5-Nautilus-Core
Base commit: 5bd7b64
Working tree: intentionally modified and not committed

## Executive state

JARVIS is a local-first AI operating system plus a governed quant-research and
paper-trading platform. The repository now has a verified V5 checkpoint:

- Master JARVIS voice/dashboard on port 8797.
- Quant Signal Terminal on port 8787.
- Read-only FYERS bridge on port 8790.
- Isolated Nautilus research core on port 8792.
- Native Windows voice bridge on port 8798.
- Deterministic routing, specialist agents, Mission Control, Company OS, Web
  Intelligence, memory, audit, approval gates, charting and paper trading.
- A command such as “analyze bitcoin 5 minute chart and tell me buy sell or
  wait” opens a one-chart signal terminal with EMA20, EMA50, VWAP, Bollinger
  Bands, RSI14 and an explainable BUY/SELL/WAIT paper signal.
- Direct paper-trade commands still pass score, risk/reward, price-drift,
  exposure and duplicate-position gates.
- Live broker execution remains locked.

The complete regression checkpoint is 1042 tests passed on 2026-08-25.

## Trading autonomy hardening checkpoint — 2026-08-25

The old one-click workflow only made a NIFTY 50 discovery scan visible while
the already-running paper engine silently rejected candidates. That mismatch
has been replaced by a governed multi-market workflow:

- `workstation/scanner_universe_registry.py` normalizes NIFTY 50, BANKNIFTY
  constituents, SENSEX 30, Indian indices, MCX majors, five public crypto
  markets, configured Indian equities and a research-only global-major list.
- `workstation/multi_market_scanner.py` provides a bounded completed-bar
  discovery radar, per-universe progress and explicit automatic-paper
  eligibility. Unofficial/delayed global equities remain research-only.
- Runtime Bank Nifty constituents retain their explicit FYERS exchange symbols,
  so valid members outside the NIFTY50/SENSEX alias lists scan without guessing
  or being dropped.
- The morning workflow starts the selected trading profile, queues an immediate
  governed paper scan, runs the multi-market discovery scanner and starts the
  bounded decision reviewer.
- Explicit `1m only`, `5m only` and `15m only` commands now fetch exactly that
  timeframe. They require a confirmed aligned breakout/breakdown; the default
  intraday mode still requires 5m/15m/1h consensus.
- Forming candles are excluded. Open attempts are revalidated against a fresh
  live mark and rejected for excessive drift, degraded R:R, stale data, closed
  sessions, unavailable FX valuation or portfolio risk.
- Crypto paper positions are valued in INR using the read-only FYERS USDINR
  contract when available, with a keyless public central-bank reference-rate
  fallback. If neither source is available, entry still fails closed.
- Synthetic re-entry keys include the signal-bar timestamp instead of only the
  calendar day, so a later valid bar can trade again without duplicating the
  same signal.
- `workstation/bounded_decision_review.py` reviews closed SQLite paper trades by
  strategy/timeframe cohort. It can only preserve or reduce risk, tighten
  score/R:R gates, or temporarily quarantine weak cohorts. It cannot increase
  risk, place orders or modify code.
- The dashboard exposes profile controls, NIFTY 50 / BANKNIFTY / SENSEX 30 /
  MCX / crypto / global-research universe controls, paper cycles/fills,
  rejection histograms and reviewer status.

This is completed-bar paper automation, not millisecond/HFT execution. It runs
only while the local JARVIS services and laptop remain running. Indian markets
are session/holiday gated; crypto research can run continuously. Real broker
and exchange-account execution remains locked.

### Paper exploration and live verification

`paper_exploration` is a separate synthetic-learning profile, not a weakening
of the normal intraday or any future live-trading gate. It consumes exactly one
completed 5m timeframe, accepts bounded range-regime setups at a 62 score and
1.5 R:R floor, and sizes new positions at 0.25x the normal paper risk. The Quant
UI exposes it as **PAPER LEARN - 0.25x RISK**.

The 2026-08-25 live verification scanned 71 deduplicated instruments across
NIFTY50, BANKNIFTY, SENSEX30, Indian indices, MCX majors and crypto. All 50
NIFTY rows, all 14 current BANKNIFTY rows, all 30 SENSEX rows, four MCX majors
and five crypto markets returned data. Eleven governed watch candidates were
found and a bounded shortlist was enrolled. The autonomous paper desk opened
NATURALGAS long and CRUDEOIL short; other candidates were rejected where their
fresh mark degraded R:R or another risk gate failed. Indian cash entries were
correctly rejected because the cash session was closed.

### Company Autopilot checkpoint

One company idea now creates a durable local operating package containing
market-research evidence, brand and website copy, a four-page HTML/CSS website
prototype, Instagram/short-form drafts, YouTube concepts/scripts and an
executive autopilot report. A bounded background worker gathers citable public
research and updates the plan. Connector state is visible in Company OS.

Local research, drafting and file generation can proceed automatically.
Publishing posts, creating external accounts, deploying a site, sending
messages or spending money require an explicit approval plus an authenticated
provider connector; JARVIS must never report those actions as completed when a
connector is absent.

## Non-negotiable safety boundary

- LIVE_TRADING_ENABLED is False in config.py.
- FYERS is read-only; no order endpoint is exposed.
- Crypto integrations use public market data, not exchange-account trading.
- Signals are research/paper signals, not promises or win probabilities.
- Bare EXECUTE fails closed until a supported market is identified.
- External communications, spending, incorporation, credentials, deployment
  and live trading require explicit governed approval.

Do not weaken these invariants while extending the project.

## Runtime architecture

~~~
Voice / browser / typed command
        |
        v
Master JARVIS :8797
  deterministic router -> specialist agents -> governed tools
        |
        +---- market command ----> Quant Terminal :8787
                                   |-- FYERS bridge :8790 (read-only)
                                   |-- Binance public crypto data
                                   |-- indicators + regime + strategy votes
                                   |-- BUY / SELL / WAIT research signal
                                   |-- persistent Paper Desk
                                   +-- Nautilus core :8792
~~~

| Service | Port | Entrypoint | Purpose |
|---|---:|---|---|
| Master JARVIS | 8797 | start_jarvis_v3.py | Voice-first orchestrator and main tabs |
| Quant Signal Terminal | 8787 | start_jarvis_quant_terminal.py | Live charts, indicators, signals and paper actions |
| FYERS data bridge | 8790 | workstation.fyers_live_bridge_service | Read-only Indian market data |
| Nautilus Quant Core | 8792 | start_jarvis_nautilus_core.py | Isolated research/backtest kernel |
| Native voice | 8798 | start_jarvis_native_voice.ps1 | Windows speech-recognition bridge |

## Important folders

| Path | Responsibility |
|---|---|
| agents/ | Bounded specialist and broker-data agents |
| omni/ | Orchestration, memory, approvals, operator, web and Company OS |
| omni/trading_intelligence/ | Features, regimes, strategies, validation, derivatives and evolution |
| workstation/ | Master/Quant HTTP services, FYERS bridge, Paper Desk and UI |
| workstation/quant_terminal_v2_static/ | Professional chart terminal frontend |
| research/nautilus_kernel/ | Isolated Nautilus worker processes |
| tests/ | Complete deterministic regression suite |
| data/state/ | Master state, audit, memory and missions |
| data/trading/ | Persistent paper portfolio |
| docs/ | Architecture, alignment and readiness records |

## Current Python environments

The old .venv, .venv-fyers and .venv-nautilus executables point to an
inaccessible Microsoft Store Python 3.13 installation.

Verified environments:

- .venv-new: canonical Python 3.12.13 app/test environment.
- .venv-nautilus-new: isolated Python 3.12 Nautilus Trader 1.231.0.

omni/runtime_paths.py proves that an interpreter can import the required SDK
before selecting it. FYERS falls back to .venv-new and Nautilus uses
.venv-nautilus-new.

Rebuild commands:

~~~powershell
Set-Location C:\Jarvis
py -3.12 -m venv .venv-new
.\.venv-new\Scripts\python.exe -m pip install -r requirements.txt
.\.venv-new\Scripts\python.exe -m playwright install chromium
.\.venv-new\Scripts\python.exe -m venv .venv-nautilus-new
.\.venv-nautilus-new\Scripts\python.exe -m pip install -r requirements-nautilus.txt
~~~

Do not install nautilus_trader into the main environment; isolation is tested.
requests 2.31.0 is pinned for FYERS. google-api-core 2.25.1 is pinned to
coexist with it.

## Launch and stop

Complete system:

~~~powershell
Set-Location C:\Jarvis; .\Launch-JARVIS.cmd
~~~

This now invokes JARVIS.bat, starts all local services and opens Master JARVIS
at http://127.0.0.1:8797.

Quant terminal only:

~~~powershell
Set-Location C:\Jarvis
.\.venv-new\Scripts\python.exe .\start_jarvis_quant_terminal.py
~~~

Open http://127.0.0.1:8787. Press Ctrl+C in the owning terminal to stop it.
Do not run multiple copies on the same ports.

## FYERS setup

FYERS needs a valid daily session. Secrets must stay local and must never be
pasted into chat or committed.

~~~powershell
Set-Location C:\Jarvis
$env:JARVIS_MARKET_DATA_PROVIDER = "AUTO"
.\.venv-new\Scripts\python.exe -m agents.fyers_auth_manager login
~~~

If the session is expired or an active MCX contract cannot be resolved, Indian
market analysis fails closed to WAIT. Crypto charts can continue from public
data when that provider is reachable.

## Quant command and signal flow

1. workstation/quant_terminal_bridge.py recognizes market, timeframe and
   intent, including conservative recovery such as “bitcoi n”.
2. workstation/quant_signal_terminal.py emits a chart directive and maps
   LONG/SHORT/WAIT to BUY/SELL/WAIT.
3. workstation/quant_firm_runtime.py loads verified candles and calls the
   regime-aware ensemble in omni/trading_intelligence/quant_firm_engine.py.
4. The frontend opens one selected chart, activates the timeframe, renders
   indicators, shows evidence and draws entry/stop/target reference lines.
5. The decision refreshes every 30 seconds; existing live price updates remain.
6. Direct paper entry passes through paper_trade_action_router.py and the
   persistent portfolio risk engine.
7. Autonomous entries use the same fresh-price validation, currency valuation,
   bounded adaptive policy and persistent risk desk.
7. No broker order is sent.

Example commands:

~~~text
analyze bitcoin 5 minute chart and tell me buy sell or wait
analyze bank nifty 15 minute chart
show crude oil chart with indicators and signal
take a paper trade in bitcoin
open paper trading
show my paper portfolio positions P and L and risk exposure
~~~

## Quant Terminal API

| Method | Endpoint | Purpose |
|---|---|---|
| GET | /api/health | Version and execution-lock posture |
| GET | /api/provider | FYERS/session state |
| GET | /api/candles | Verified OHLCV candles |
| GET | /api/live | Read-only live snapshot |
| GET | /api/scan | 5m/15m/1h evidence and alignment |
| GET | /api/decision | Regime-aware decision for one timeframe |
| GET | /api/paper/portfolio | Persistent synthetic portfolio |
| GET | /api/paper/autonomy | Paper scanner state |
| POST | /api/agent | Deterministic Quant command router |
| POST | /api/paper/command | Paper Desk commands |
| POST | /api/paper/autonomy/start | Arm paper scanning |
| POST | /api/paper/autonomy/stop | Pause paper scanning |
| POST | /api/fyers/login | Open local FYERS authentication |
| POST | /api/market/restart | Restart read-only data bridge |

## State, database and credentials

- Audit: data/state/omni_jarvis.sqlite3
- Hybrid memory: data/state/memory.sqlite3
- Missions: data/state/mission_control.json and data/state/missions/
- Web research: data/state/web_intelligence.json
- Paper portfolio: data/trading/paper_desk.sqlite3
- Derivatives history: SQLite store under data/
- Google OAuth: Windows DPAPI when available; otherwise encrypted Fernet vault
  plus a separate private key file. Plaintext tokens are never written.

Never commit data/credentials, access tokens, App Secrets, browser profiles,
generated state or paper databases.

## Work completed in this checkpoint

- Made `Launch-JARVIS.cmd` idempotent when Master JARVIS is already healthy:
  it verifies dashboard identity, opens the existing instance, and exits with
  code 0. An unknown service occupying port 8797 still fails closed.
- Fixed the Quant Terminal's blank `LOADING` panels at all three actual failure
  points: the missing slot status reference, a self-triggering expired-session
  MutationObserver loop, and an HTML-parser dependency on a remote chart CDN.
- Bundled and locally serves pinned TradingView Lightweight Charts 5.2.0, so
  charts do not require unpkg/jsDelivr at runtime.
- Throttled high-frequency Binance WebSocket rendering to two updates per
  second so live BTC traffic cannot starve the browser main thread.
- Added a direct Quant self-diagnostic and repair route. JARVIS now probes
  health, candles and provider state, safely restarts the read-only FYERS
  bridge when needed, and opens a cache-busted terminal with a concrete report.
- Added governed local image/video intelligence for Downloads, Desktop and the
  project root. Video analysis samples bounded timestamped frames, treats media
  as untrusted, and uses local `qwen3-vl:4b-instruct`; OpenCV is now a declared
  dependency. The agent never follows instructions embedded in media.
- Fixed short acknowledgement route contamination (`Now can.`), current/trending
  web routing, ordinal song follow-ups, and original voice-song behavior.
- Source-integrated the validated V5.4 deterministic paper action router.
- Corrected Paper Desk precedence so navigation/status cannot create a fill.
- Added signal-terminal routing and automatic deep-linked chart opening.
- Added EMA20/50, VWAP, Bollinger Bands and an RSI pane.
- Added BUY/SELL/WAIT badge, ensemble evidence, regime, score and level lines.
- Added /api/decision and 30-second decision refresh.
- Replaced the user-facing and autonomous entry decision with one governed
  `MTF_CONSENSUS_V2` contract. The 5m, 15m and 1h strategy decisions, higher-
  timeframe trend, regime, score, risk/reward, verified levels and market
  session must pass together; any directional conflict fails closed to WAIT.
- The chart badge, Quant Scanner, Paper Setup and autonomous Paper Desk now
  consume that same consensus payload. Isolated `/api/decision` remains a raw
  diagnostic endpoint and can no longer place or advertise an actionable fill.
- Automatic paper scanning now starts with the Quant service by default,
  requires score >= 68 and risk/reward >= 1.8, blocks closed exchange sessions,
  avoids duplicate symbol exposure and never exposes broker-order APIs. Set
  `JARVIS_AUTO_PAPER_START=0` to opt out.
- Fixed missing HTTP routes for both terminal hotfix scripts.
- Fixed stale-scan cancellation and indicator/signal consistency.
- Fixed voice compile-test file locking with a unique temporary output.
- Repaired the launcher and isolated Nautilus runtime.
- Added verified interpreter selection for FYERS and Nautilus.
- Added missing browser, semantic UI, Google and image dependencies.
- Added encrypted OAuth-vault fallback when DPAPI is unavailable.

## Verification evidence

~~~text
Full suite: 1014 tests passed in 51.182s
Targeted signal/paper/voice suite: 49 tests passed
Previously failing environment groups: 74 tests passed
JavaScript syntax checks: passed
Python compile checks: passed
pip check: no broken requirements
git diff --check: passed (line-ending warnings only)
~~~

Browser-level runtime verification after the repair:

~~~text
URL=http://127.0.0.1:8787/?symbol=BTC&timeframe=15m&analyze=1
chart statuses=CRYPTO TICK with live BTC price
canvases=11
LOADING labels=0
page errors=0
scan=TRENDING
signal=BUY research signal
provider=SESSION EXPIRED (Indian/MCX only)
live execution=false
~~~

Browser-level consensus verification on the live BTC terminal:

~~~text
5m strategy=SHORT 66.7
15m strategy=LONG 64.9
1h strategy=LONG 66.0
scanner=CONFLICT / WAIT
actionable signal=WAIT
paper setup=NO QUALIFIED SETUP
paper position opened=no
autonomous paper desk=RUNNING
live execution=false
~~~

Real local-media smoke test resolved `C:\Users\Soura\Downloads\Video-83486.mp4`,
read 3,394 frames of a 113.13-second 720x1280 video, sampled four timestamped
frames, and returned a local visual summary without executing media content.

Runtime smoke for the exact analysis command:

~~~text
action=open_signal_chart
symbol=BTC
timeframe=5m
layout=1
indicators=EMA20,EMA50,VWAP,BB20,RSI14
paper_only=true
live_execution=false
HTML=200
session_hotfix.js=200
scan_consistency_hotfix.js=200
~~~

The Quant Terminal was restarted on port 8787 after the browser repair. Runtime
service posture at handoff must be checked rather than inferred from old PIDs.

## Blueprint alignment

| Phase | State | Honest interpretation |
|---|---|---|
| V5 stabilization | Complete | Routing, precedence, voice compile and regression are green |
| V6 market state | Strong partial | Feature, regime, MTF, structure and indicator foundations exist |
| V7 strategy lab | Strong partial | Backtests, costs, sweeps, walk-forward, Monte Carlo and Nautilus exist; more OOS evidence is needed |
| V8 self-improvement | Partial | Journal, drift, evolution, validation and champion/challenger modules exist |
| V9 autonomous quant firm | Paper-only partial | Scanner, portfolio, paper execution and adaptation exist |
| V10 derivatives | Partial | Options, IV, expiry and defined-risk modules exist; deeper licensed history is needed |
| V11 Quant Scientist | Foundation only | Research/evolution primitives exist; autonomous science is not a completed claim |

The repository is aligned with the blueprint direction, but the multi-year
V6-V11 target is not honestly finished. The V5 user-facing and stability
checkpoint is complete and tested.

## V5.1 advanced equity, breakout and morning-paper checkpoint

This checkpoint extends the Quant Terminal without weakening the live-execution
lock:

- Indian cash equities now resolve from company names, NSE tickers and full
  FYERS symbols. `Reliance`, `RELIANCE` and `NSE:RELIANCE-EQ` resolve to the
  same official broker instrument.
- The official NSE NIFTY 50 constituent CSV is loaded at runtime with an exact
  50-stock fallback snapshot. The bounded scanner analyzes every constituent's
  daily candles for confirmed or approaching breakouts/breakdowns, relative
  volume, range structure, EMA trend, RSI, ATR and candle patterns.
- Global equities can be opened with common aliases or explicit exchange/ticker
  syntax such as `AAPL`, `NASDAQ:AAPL`, `NYSE:IBM` and `YF:7203.T`. Their
  public Yahoo chart feed is explicitly labelled unofficial/delayed and is not
  eligible for autonomous paper entries.
- `Jarvis, open Reliance daily chart and analyze the exact conditional entry,
  stop and target for a swing trade` selects the 1h/4h/1d swing profile. It
  returns WAIT unless directional alignment, score, regime, verified levels,
  risk/reward and market session all pass. Conditional levels are never called
  an executable setup when those gates fail.
- `Jarvis, scan all Nifty 50 companies for breakouts` starts a bounded
  three-worker official-universe scan. Up to eight research candidates can be
  enrolled in the governed 5m/15m/1h paper watchlist; the daily watch result
  alone cannot open a position.
- `Jarvis, start trading` and the `START JARVIS PAPER` button start the morning
  paper workflow: scan, verify, size, simulate and manage stop/target exits.
  It remains synthetic; no broker or crypto order is sent.
- FYERS NIFTY/BANKNIFTY option-chain research exposes expiry, spot, bid/ask,
  spread, OI/change OI, volume, IV, Greeks and PCR. Public Deribit BTC/ETH
  options are research-only. Stock-option automation, dynamic option streaming,
  naked shorts and live orders remain unavailable.
- FYERS equity symbols can be added to the read-only live bridge dynamically.
  Global public equities remain research-only.
- Tick updates may arrive in real time, but autonomous strategy decisions are
  deliberately made from completed bars. This is not an HFT or millisecond
  execution engine.

Verified runtime on 2026-08-25:

~~~text
FYERS bridge=CONNECTED
RELIANCE daily history=140 broker candles (NSE:RELIANCE-EQ)
RELIANCE read-only live quote=available
AAPL daily history=100 public unofficial candles; auto-entry blocked
NIFTY option chain=available with OI/IV/Greeks/PCR
NIFTY 50 scanner=50/50 complete, 8 research candidates, 0 errors
autonomous paper universe=18 symbols after bounded candidate enrollment
autonomous paper desk=RUNNING, positions opened=0, live execution=false
browser=charts rendered; morning, scanner and options cards rendered
~~~

Primary V5.1 modules:

- `workstation/equity_universe.py`
- `workstation/global_equity_data.py`
- `workstation/advanced_pattern_engine.py`
- `workstation/nifty50_breakout_scanner.py`
- `workstation/morning_trading_coordinator.py`
- `workstation/options_readiness.py`
- `workstation/quant_terminal_v2_static/advanced_terminal_runtime.js`
- `tests/test_quant_v51_advanced_equities.py`

## Remaining prioritized work

1. Collect versioned multi-regime datasets for every market with provenance.
2. Add chart-visible BOS/CHOCH, swing structure, supply/demand, FVG and
   liquidity-sweep overlays from one normalized MarketState object.
3. Add historical signal replay so every marker is auditable candle by candle.
4. Calibrate per-instrument/regime thresholds using walk-forward and OOS data.
5. Build champion/challenger dashboards with promotion and rollback gates.
6. Add reliable derivatives history for OI, IV, skew, Greeks and expiry.
7. Add portfolio reconciliation, alerts and daily/weekly paper review reports.
8. Obtain independent security/operational review before any live-execution
   design. Live execution is not authorized by this handoff.

## Exact stopping point

- Code changes are present in the working tree and are not committed.
- Full regression is green at 1014 tests.
- Backend, browser/canvas and real local-video smokes are green.
- Master JARVIS is running on port 8797 with the repaired command router.
- Quant Terminal is running on port 8787 with the repaired static bundle and
  `MTF_CONSENSUS_V2` automatic paper scanner running.
- No live broker order capability was added.
- FYERS reports `CONNECTED`; Indian-index/MCX history and read-only live data
  are available for the current session. Indian NSE cash equities can be
  subscribed dynamically. Public crypto data is also available.
- The official NIFTY 50 scanner completed 50/50 and enrolled eight bounded
  candidates; the paper universe contains 18 symbols and has opened no
  market-closed position.
- Next safe step: collect a multi-session paper record, calibrate each strategy
  out of sample, add replay/audit overlays, and complete portfolio/options
  reconciliation before considering any separately reviewed live adapter.
