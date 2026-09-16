# JARVIS V17 - Install and Autonomous Options Runtime

## What V17 changes

V17 converges the existing V16 professional terminal into one autonomous-options PAPER runtime. It does not create a second Paper Desk or a second scanner.

The normal autonomous option path is:

`verified live provider data -> completed bars -> multi-timeframe scanner -> strategy decision -> option intelligence -> exact contract selection -> fresh quote -> deterministic risk/capital sizing -> Paper Desk -> position management -> journal/learning`

For a qualified autonomous plan, the user does **not** need to click a strike, enter lots, enter stop/target, or click BUY. The option contract and risk geometry must already be verified by JARVIS before Paper Desk admission.

## Safety and execution scope

V17 remains PAPER-only. There is no live broker-order method in the V17 autonomy layer. Live execution is locked.

Verified automatic option execution currently covers:

- NIFTY options via the FYERS NSE FO symbol master
- BANKNIFTY options via the FYERS NSE FO symbol master
- SENSEX options via the FYERS BSE FO symbol master

The broader market universe can still be scanned/researched where provider data exists. MCX option execution and crypto option execution remain fail-closed until an exact verified option-contract provider/resolver exists in the repository. V17 will not invent strikes, expiries, lot sizes, quotes or fills.

There is no forced daily trade count. JARVIS can scan many symbols and timeframes continuously, but only qualified setups may create paper exposure.

## Install on the current Windows machine

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

## Start V17

Either double-click:

`JARVIS_V17.bat`

or run:

```powershell
cd C:\Jarvis
.\.venv\Scripts\Activate.ps1
python .\start_jarvis_professional_terminal_v17.py
```

The terminal remains on the canonical professional-terminal port (normally 8787).

## Daily autonomous workflow

1. Start V17.
2. Open the INTRADAY or SWING workspace.
3. Start that paper session once.
4. Leave autonomous scanning running.
5. JARVIS reads provider market data and completed candles, not chart screenshots.
6. When a supported underlying produces a qualified setup, JARVIS can choose the verified CE/PE contract automatically and route it through the canonical Paper Desk.
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

Those constraints keep the autonomous loop testable while we validate data quality, option selection, reconciliation, resource stability and paper performance.
