# JARVIS V14.1 — Risk-Geometry Convergence

V14.1 closes the execution gap observed after V14: a legacy Quant consensus could correctly expose a directional candidate while suppressing entry/stop/target because historical qualification gates did not pass. V14 then treated the missing geometry as `INVALID_RISK_LEVELS`, so a positive contextual-EV opportunity could never reach sizing or Paper Desk.

## Authority separation

V14.1 does **not** weaken `INVALID_RISK_LEVELS` and does not revive static score authority.

The pipeline is now:

1. verified completed-bar market evidence,
2. directional candidate from the existing Quant consensus,
3. V14.1 verified risk geometry,
4. V13 contextual evidence and closed-paper memory,
5. V14 positive contextual expected value,
6. uncertainty-scaled paper risk,
7. verified instrument-step fractional sizing,
8. Paper Desk final risk authority.

Legacy score, alignment and static R:R remain observable evidence. They do not decide whether geometry is allowed to exist.

## Geometry inputs

Risk geometry is derived only when the existing scan has a LONG/SHORT candidate and fresh completed-bar evidence with a positive close and ATR. It uses:

- completed-bar close as the decision reference,
- ATR14 for bounded volatility distance,
- verified support/resistance when available,
- a bounded structural stop,
- verified support/resistance target when it provides meaningful reward,
- otherwise a deterministic 2R volatility extension.

The resulting object records provider, timeframe, data quality, completed-bar count and the exact construction method. It explicitly records `synthetic_market_data=false` and `data_fabricated=false`.

## Fail-closed behavior

`INVALID_RISK_LEVELS` is removed only after directional validation succeeds:

- LONG: stop < entry < target
- SHORT: target < entry < stop

If data is stale, direction is absent, ATR/close is unavailable, or geometry fails validation, JARVIS leaves the hard blocker intact.

## BTC runtime trace

Quant exposes:

- `/api/v14.1/risk-geometry`
- `/api/v14.1/execution-trace`
- `/api/v14.1/status`

The trace reports every profile even when none is actionable and separates `data_sample_pass` from `execution_pipeline_ready`, eliminating the misleading V14 case where five BTC profiles could return data while the release output printed blank EV/action fields.

## Safety invariants

- paper only
- live execution false
- automatic broker order false
- automatic production strategy rewrite false
- 29 permanent specialists remain unchanged
- legacy `critic` remains one of the 29
- external consequential actions remain approval-gated
- protected V8 Master identity remains unchanged
