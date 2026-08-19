# JARVIS Quant Trading Intelligence V4 — Paper Desk Milestone

This milestone consolidates paper-trading user experience instead of adding another isolated signal feature.

## User-visible command contract

The following commands route deterministically to Quant Trading Intelligence without being misread as market symbols:

- `open trading terminal`
- `open paper trading terminal`
- `open paper trading`
- `my paper trading position`
- `show my current paper trading portfolio, positions, P and L and risk exposure`
- `start autonomous paper trading`
- `stop autonomous paper trading`
- `autonomous paper trading status`

## Persistent synthetic paper account

`workstation.paper_trading_desk` stores simulated positions in SQLite under `data/trading/paper_desk.sqlite3` and exposes:

- open paper positions
- realized and unrealized P&L
- gross and net exposure
- risk-to-stop
- position limits
- risk limits
- persistent event history

## Autonomous paper runtime

`workstation.paper_autonomy_engine` separates two loops:

- frequent mark/risk loop for open synthetic positions
- slower multi-market strategy scan for new entries based on completed bars

This is deliberate. Recomputing full bar-based strategy research on every network tick adds load without creating new information.

The default research universe is NIFTY, BANKNIFTY, SENSEX, CRUDEOIL, GOLD, SILVER, NATURALGAS, BTC, ETH and SOL across 5m, 15m and 1h evidence.

## Trading safety boundary

This milestone is PAPER / RESEARCH only.

It does not import or expose broker order placement, modification or cancellation surfaces. `live_execution` is always false.

## Not claimed

This milestone does not claim exchange-colocated HFT latency or a universal highest-win-rate strategy. Retail API latency and bar-based strategies have different constraints from colocated market-making systems. The design instead emphasizes deterministic routing, verified data, portfolio risk, persistence and autonomous synthetic execution.
