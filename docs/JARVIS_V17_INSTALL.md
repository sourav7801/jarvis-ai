# JARVIS V17 - Install and Autonomous Options Runtime

## What V17 changes

V17 converges the existing V16 professional terminal into one supervised autonomous-options PAPER workstation. It preserves one canonical scanner, one Paper Desk, one ledger and the existing V12-V16 reasoning/risk lineage.

The autonomous option path is:

`verified live provider data -> completed bars -> multi-timeframe scanner -> strategy decision -> option intelligence -> exact contract selection -> fresh quote -> deterministic risk/capital sizing -> Paper Desk -> position management -> journal/learning`

For a qualified autonomous plan, the user does **not** need to click a strike, enter lots, enter stop/target, or click BUY. The option contract and risk geometry must already be verified by JARVIS before Paper Desk admission.

## Safety and execution scope

V17 remains PAPER-only while the autonomous loop is stabilized. The V17 autonomy layer has no live broker-order method and live execution is locked.

Verified automatic option execution currently covers:

- NIFTY options via the FYERS NSE FO symbol master
- BANKNIFTY options via the FYERS NSE FO symbol master
- SENSEX options via the FYERS BSE FO symbol master

The broader market universe can still be scanned/researched where provider data exists. MCX option execution and crypto option execution remain fail-closed until an exact verified option-contract provider/resolver exists in the repository. V17 will not invent strikes, expiries, lot sizes, quotes or fills.

There is no forced daily trade count. JARVIS can scan many symbols and timeframes continuously, but only qualified setups may create paper exposure.

## Install on Windows

Open PowerShell:

```powershell
cd C:\Jarvis
git fetch origin
git switch jarvis-dev/20260916-JARVIS-V17-autonomous-options-runtime
git pull --ff-only origin jarvis-dev/20260916-JARVIS-V17-autonomous-options-runtime
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\install_v17.ps1
```

The installer reuses `.venv` if it already exists. Python 3.13 is preferred; the project supports Python >=3.11 and <3.14.

## Start the full V17 workstation

Either double-click:

`JARVIS_V17.bat`

or run:

```powershell
cd C:\Jarvis
.\.venv\Scripts\Activate.ps1
python -m scripts.jarvis_runtime_supervisor_v17
```

The supervisor owns the product as one runtime. The protected Master/workstation is normally on port 8797 and the professional trading service is internal on port 8787.

For trading-terminal-only debugging you may still run:

```powershell
python .\start_jarvis_professional_terminal_v17.py
```

## Daily autonomous workflow

1. Start V17.
2. Open the INTRADAY or SWING workspace.
3. Start that paper session once.
4. Leave autonomous scanning running.
5. JARVIS reads provider market data and completed candles, not chart screenshots.
6. When a supported underlying produces a qualified setup, JARVIS chooses the verified CE/PE contract automatically and routes it through the canonical Paper Desk.
7. The canonical risk engine sizes the paper position and the existing position manager/journal owns the lifecycle.

Manual option selection remains available for inspection/research, but it is not required for qualified autonomous plans.

## Provider throttling and stale data

V17 enables the shared/single-flight terminal market cache before starting the provider bridge. Chart, scanner, strategy and option consumers therefore reuse certified reads where possible instead of independently fanning out duplicate provider calls.

Provider rate limits, stale quotes, invalid timestamps, closed sessions, unverified contracts, reconciliation failures, duplicate underlying exposure, zero risk budget or invalid stop/target geometry block new entries.

## What V17 intentionally does not do yet

- No real-money automatic broker execution.
- No naked option selling.
- No fabricated MCX/crypto option contracts.
- No forced target number of daily trades.
- No bypass of stale-data, market-session, reconciliation or risk gates.

These constraints keep the autonomous loop testable while data quality, option selection, reconciliation, resource stability and paper performance are validated.
