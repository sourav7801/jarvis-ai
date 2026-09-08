# JARVIS V14 — Autonomous Execution Intelligence

V14 builds on V13 contextual market intelligence and fixes the remaining behavioral problem where JARVIS could still behave as if confidence or an internal hurdle were binary permission gates. V14 keeps the contextual probability/EV work, closed-paper outcome memory, completed-bar correlation and fractional constraint-aware sizing, but changes final paper entry authority to a continuous economic rule.

## Decision authority

`VERIFIED DATA -> V13 CONTEXTUAL EVIDENCE -> EXPECTED VALUE -> CONTINUOUS RISK -> VERIFIED FRACTIONAL SIZE -> PAPER DESK`

Hard data/accounting/safety blockers still veto. Otherwise, **positive contextual expected value is executable**. Confidence, uncertainty, legacy score, alignment and static R:R do not independently veto a positive-EV paper opportunity. They change probability, expected value or final paper size.

- `expected_value_r > 0` with no hard blocker: executable paper opportunity.
- higher uncertainty: smaller paper risk.
- stronger positive EV + stronger confidence: larger but bounded paper risk.
- zero/negative contextual EV: wait.
- stale/unverified data, invalid risk levels, unavailable accounting/valuation, session constraints and final Paper Desk limits: hard boundaries.

`PRIMARY` and `PROBE` remain descriptive intensity labels only. Their label boundary is not execution authority.

## No ambiguous WATCHING terminal state

V14 adds a durable opportunity lifecycle with explicit states:

- `WAIT_NEGATIVE_OR_ZERO_EV`
- `BLOCKED_SAFETY_OR_DATA`
- `RECHECK_PENDING`
- `ACTIONABLE`
- `POSITION_OPENED`

The UI surfaces the exact reason rather than collapsing all non-open cases into `WATCHING`.

## Execution sizing

V14 requires the V13 constraint-aware fractional sizing bridge. Automatic crypto quantity is computed as a real fractional number, quantized to the verified provider step, and then capped by every existing Paper Desk risk/exposure constraint. Risk limits are not relaxed.

## Runtime

- Master `127.0.0.1:8797`: protected V8 Unified Intelligence with `/api/v14/paper-authority`.
- Quant `127.0.0.1:8787`: V14 continuous positive-EV authority with `/api/v14/execution-authority` and `/api/v14/opportunity-lifecycle`.
- Completion `127.0.0.1:8799`: V14 autonomous execution observability and lifecycle.
- Nautilus: preserved research/backtest core.

## Safety invariants

- permanent specialists remain exactly 29, including legacy `critic`
- V14 components are system planes, not new permanent agents
- `paper_only=True`
- `live_execution=False`
- `automatic_broker_order=False`
- automatic production strategy rewrite disabled
- external consequential actions approval-gated
- no live broker-order API added
- no fabricated market/history/correlation data
- Paper Desk remains final portfolio/risk authority
