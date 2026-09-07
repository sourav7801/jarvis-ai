# JARVIS V12 — Adaptive Market Intelligence

Base: verified V11 cognitive-execution checkpoint `3fa42cdca66423d4a7284c9e4c81eb571aac9029`.

V12 changes paper-trading execution authority from fixed Quant thresholds to a continuous evidence policy. Legacy score, alignment and profile R:R thresholds remain visible for diagnostics and backward compatibility, but values such as 67/68/70 do not independently decide whether JARVIS may open a paper position.

## Decision model

`VERIFIED DATA -> MULTI-TIMEFRAME EVIDENCE -> STRUCTURE/PATTERN/REGIME -> STRATEGY AGREEMENT -> PAPER OUTCOME PRIORS -> PROBABILITY + UNCERTAINTY -> EXPECTED VALUE (R) -> PORTFOLIO/ACCOUNTING SAFETY -> PRIMARY / PROBE / WAIT`

- **PRIMARY**: positive expected value with sufficient evidence confidence. Risk is confidence/edge scaled and capped below the profile's full nominal risk.
- **PROBE**: positive expected value with lower confidence. V12 permits a small paper-only learning position; probe count is bounded per scan.
- **WAIT**: negative/insufficient adaptive edge or a true hard blocker.

A low legacy score can therefore be PRIMARY/PROBE when the combined evidence is favorable. A high legacy score can still be WAIT when data is stale, levels are invalid, the feed is research-only, the session is closed where applicable, accounting/valuation is unavailable, current price has invalidated the setup, or the persistent portfolio risk layer rejects exposure.

## Runtime ownership

V12 keeps the protected V8 Master surface on 8797, the Quant owner on 8787, Nautilus on 8792 and Completion on 8799. The V12 supervisor will not silently adopt an older Quant process merely because it reports `JARVIS_QUANT_TERMINAL`; the controller must expose `ADAPTIVE_EXPECTED_VALUE_NOT_STATIC_SCORE`. Unknown processes are never terminated.

The Master uses `start_jarvis_master_v12.py` so direct paper-trade commands receive the same V12 adaptive authority while the protected Master UI/HTTP identity remains V8-compatible.

## Trading horizons

- INTRADAY 50%: adaptive MTF plus independent completed 5m, derived-completed 10m and 15m lanes.
- SWING 30%: adaptive 1h/4h/1d evaluation.
- INVESTMENT 20%: adaptive daily evaluation, LONG only.

The 10m lane is still constructed only from two contiguous completed 5m provider candles. Missing/forming bars are never synthesized.

## Learning

V12 consumes bounded paper outcome priors from the existing TradeLearningEngine by strategy family, strategy, regime and symbol. Learning changes probability estimates only after evidence accumulates; it does not rewrite production strategy code or enable live execution.

## Live market sampler

Completion exposes a read-only multi-profile sampler for BTC and other supported symbols. It reads the authoritative Quant process and reports legacy score/qualification alongside V12 action, expected value, confidence, risk multiplier, hard blockers and soft contradictory evidence.

## Safety invariants

- permanent specialists: 29; legacy `critic` preserved
- system planes do not become agent 30
- `paper_only=True`
- `live_execution=False`
- `automatic_broker_order=False`
- automatic production strategy rewrite disabled
- external consequential actions approval-gated
- no broker order API added
- no fabricated candles or dealer/L2 claims

V12 is a release candidate until the Windows installer completes targeted regression, full repository regression, protected-core checks and live runtime validation.
