# Professional paper terminal — implementation checkpoint

This branch upgrades the existing V15.1 trading implementation. It is **paper only**. It does not implement the unrelated V16 desktop/Office/browser roadmap in the attached specification.

## Run on the existing Windows installation

1. Stop older JARVIS processes before switching branches. Preserve `data/trading`, `data/state`, and your local FYERS token/configuration. Do not delete the paper databases.
2. Check out `jarvis-dev/20260909-professional-paper-terminal` in your JARVIS repository.
3. Use the existing primary `.venv` or `.venv-new`. If dependencies are missing, run:

   ```powershell
   .\.venv\Scripts\python.exe -m pip install -r requirements-terminal.txt
   ```

4. Double-click `JARVIS.bat`, or run:

   ```powershell
   .\.venv\Scripts\python.exe start_jarvis_quant_terminal.py
   ```

5. Open `http://127.0.0.1:8787`. Select Intraday, Swing, or Investment, check the workspace capital, and select **Start paper session**. Start and pause apply to new entries; existing positions remain monitored.

For a new environment, run `py -3.12 -m venv .venv` before installing the terminal requirements. The optional full workstation is preserved as `JARVIS_WORKSTATION.bat`; its voice, desktop and Nautilus dependencies remain separate.

FYERS market data requires your own entitled account and valid local token. Keep the existing isolated `.venv-fyers` if present. Otherwise create it with `py -3.12 -m venv .venv-fyers`, install `fyers-apiv3 requests tzdata` in it, configure `FYERS_APP_ID`, `FYERS_SECRET_ID`, and `FYERS_REDIRECT_URI` through the existing local configuration, then run `.\.venv-fyers\Scripts\python.exe -m agents.fyers_auth_manager login`. Never put credentials in Git. This is a local broker login step, not an order authorization.

Linux development: `python -m pip install -r requirements-terminal.txt`, then `JARVIS_NO_BROWSER=1 python start_jarvis_quant_terminal.py`. Production Windows startup and actual broker entitlements require local verification.

## Completed at this checkpoint

- Chart-centered interface with isolated workspace positions, entry/exit orders, journal, performance, alerts, thesis notes and capital controls.
- Existing option chains, liquidity, strategy lab, reasoning and learning modules remain accessible on demand; original advanced screens remain under `/legacy`.
- SQLite transactions serialize admission, capital checks, paper fills, partials and exits across desk instances and processes. Order keys remain idempotent after restart.
- Cost-aware variable sizing distinguishes committed capital from risk. Limits include per-trade risk, total open risk, daily losses, concentration and simultaneous positions. Heuristic evidence is not a calibrated win probability; its risk weight is capped at 25%.
- Exchange and receive timestamps, session status, provider/instrument matching, bid/ask and candle geometry are checked. Invalid quotes block new entries; outages freeze paper marks until valid quotes return. No imaginary stop fill is booked during an outage.
- One position monitor continues across all workspaces when entry scans pause. Shared caches and bounded analysis/HTTP workers reduce duplicate work. Restart restores positions and preferences with entry sessions paused.
- Reconciliation checks order/position/event links and prevents a second default legacy paper book from spending terminal capital. Existing legacy exposure must be resolved using its original records; new defined-risk spread commitments still need shared-ledger integration. Research and existing exit paths remain available.

## Work still in progress

- The newly requested 1–8 chart layouts and expanded Indian/commodity/crypto futures and options selection are being implemented after this checkpoint.
- Final load, visual and full regression comparison, provider research matrix and final validation report are pending.
- Live FYERS end-to-end execution is not verified here: credentials, entitlement and a live Indian session are unavailable. The browser QA uses explicitly marked temporary simulation fixtures.

## Evidence behind the fixes

The old page loads 15 JavaScript layers containing 16 interval loops. The original launcher brings up several workstation services, and Quant's V12 startup armed all three mandates. Two independently locked paper desks could pass the same position limit before either inserted its trade. Saved position marks reverted to entry on subsequent snapshots without a mark loader. Scale-out rung bookkeeping and the actual reduction used separate commits. NaN workspace allocations bypassed the sum check. The only portfolio mark worker belonged to Intraday, so pausing it removed Swing/Investment monitoring. Missing live quotes could fall back to historical decision entries. These are reproducible implementation defects; production crash logs were not supplied.

The new default launcher reserves its exclusive HTTP port before workers start, keeps sessions paused until requested, and retains the full workstation as a separate launcher. FYERS bridge startup is single flight with a retry cooldown; its local log is `data/logs/fyers_bridge.log`.

## Data and state

The canonical database is `data/trading/paper_desk.sqlite3` (SQLite WAL). `JARVIS_PAPER_DB` can select an isolated development database. The terminal adds workspace/order/daily-equity/note tables without deleting the existing paper journal. Unknown historical portfolio buckets are charged to Intraday. Back up SQLite only after stopping writers, or use SQLite's online backup API; copying just the main file while WAL writers are running is insufficient.

Default allocations are 50% Intraday, 30% Swing and 20% Investment. Allocation changes require all entry sessions paused and all paper positions flat. Costs are configurable conservative paper assumptions, not a broker tariff. The terminal uses a conservative Indian entry cutoff of 15:10 IST and excludes closing-auction prices after 15:15 IST; it does not model auction fills.

Run focused checks with `python -m unittest tests.test_professional_terminal tests.test_paper_mark_freshness -v`. Optional browser QA: `npm ci`, then `npm run dev`; this uses temporary simulated fixtures and never connects to a broker.
