# JARVIS V20 — Full Workspace Operating System

V20 is the browser presentation/runtime layer that replaces the old shared V17/V18 workspace surface.

## Workspaces

- **INTRADAY** — bounded multi-chart session workspace. Uses the existing V17 chart engine and 1–8 layouts.
- **SWING** — independent multi-session research workspace.
- **INVESTMENT** — dedicated portfolio, fundamentals, valuation, allocation and thesis workspace.
- **OPTIONS** — dedicated derivatives desk. It does not use the old single option chart/panel.

## Options desk

The V20 Options desk provides:

- NIFTY / BANKNIFTY / SENSEX
- expiry selection
- ±8 / ±12 / ±20 strike windows
- Price / Greeks / Straddle views
- spot / PCR / call wall / put wall / max pain
- CE/PE OI and change in OI
- IV / delta / gamma / theta when supplied by FYERS
- paper strategy lab
- isolated request cancellation on workspace exit
- dedicated backend option-data lane

The strategy lab is simulation/research only. It does not submit broker orders.

## Chart architecture

The existing V17 chart engine already creates every requested layout slot: 1, 2, 3, 4, 5, 6, 7 or 8.

History requests are bounded through the V17 candle lane, and workspace transitions cancel superseded work. V20 does not create a second chart engine.

If a provider is unavailable, V20 must show a data-state message rather than inventing candles.

## Data plane

V20 reads the existing provider/state endpoints and falls back to `/api/provider` when the V19 aggregate state is unavailable.

Runtime identity:

`GET /api/v20/identity`

Expected:

- version: 20.0
- service: JARVIS_V20_WORKSPACE_OS
- paper_only: true
- live_execution: false
- options_surface: V20_DEDICATED_OPTIONS_DESK
- chart_surface: V17_BOUNDED_MULTI_SLOT

## Startup

Use:

```powershell
cd C:\Jarvis
git fetch origin
git checkout jarvis-dev/20260916-JARVIS-V17-autonomous-options-runtime
git pull --ff-only origin jarvis-dev/20260916-JARVIS-V17-autonomous-options-runtime
.\JARVIS_V20.bat
```

The V20 launcher releases only the process listening on Quant port 8787 before the supervisor starts. It does not blanket-kill Python processes.

## Verification

Open: `http://127.0.0.1:8787`

Hard refresh: `Ctrl+Shift+R`

Then verify:

1. Header says **V20 WORKSPACE OS**.
2. Intraday does not show the shared V17 One-Touch banner.
3. Selecting layout 4 creates four chart slots; layout 8 creates eight slots.
4. Swing has a separate research context.
5. Investment opens the dedicated Investment Desk.
6. Options opens the V20 Options Desk, not the old single-chart/options panel.
7. Options contains the chain/Greeks/Straddle controls.
8. Switching away from Options cancels its outstanding request.
9. FYERS degradation does not blank unrelated workspace UI.
10. Live execution remains locked.

## Important pull rule

The V20 code is on `jarvis-dev/20260916-JARVIS-V17-autonomous-options-runtime`.

Do not run an old local copy of `JARVIS_V17.bat` and assume it contains the V20 browser assets. Pull the branch first and start `JARVIS_V20.bat`.