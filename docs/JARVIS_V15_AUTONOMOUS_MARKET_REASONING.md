# JARVIS V15 — Autonomous Market Reasoning

Verified base: V14.1 `c28f7e522063ad0aff02fb40ef157a722235bce0`.

## Purpose

V15 moves JARVIS from a single-opportunity execution policy toward an explainable market-reasoning and portfolio-allocation system while preserving the verified V14.1 paper execution pipeline.

Canonical flow:

```
VERIFIED MARKET DATA
  -> V14.1 VERIFIED RISK GEOMETRY
  -> V13 CLOSED-PAPER CONTEXT
  -> V14 POSITIVE CONTEXTUAL EV
  -> V15 MARKET BELIEF
  -> V15 COMPETING HYPOTHESES
  -> V15 PORTFOLIO-ADJUSTED UTILITY
  -> CONTINUOUS PAPER RISK
  -> FRACTIONAL CONSTRAINT-AWARE SIZE
  -> PAPER DESK FINAL RISK AUTHORITY
```

Legacy score, alignment and static R:R remain observations/evidence. They are not binary execution gates.

## Market belief model

`omni/trading_intelligence/market_reasoning_v15.py` produces explainable belief state from existing verified completed-bar evidence only:

- trend direction and strength
- range / breakout / reversal estimates
- volatility and liquidity state
- structure state
- regime and regime-transition estimate
- timeframe agreement/conflict
- signal freshness
- uncertainty
- data provenance

Probabilities are explicitly model estimates, not market facts.

`workstation/market_belief_store_v15.py` stores previous/current beliefs locally. Repeated polling over unchanged completed-bar provenance is de-duplicated so the UI cannot manufacture fake market-state history.

## Competing hypotheses

V15 carries multiple hypotheses instead of one opaque score, including bullish continuation, bearish continuation, range continuation and liquidity-sweep reversal. Each includes evidence for/against, probability estimate, invalidation condition, supporting/conflicting timeframes and uncertainty.

## Portfolio-aware authority

`autonomous_decision_engine_v15.py` wraps the verified V14 decision. It computes market quality and hypothesis alignment, then ranks executable opportunities by portfolio-adjusted utility. The allocator may reduce or skip weaker opportunities when better alternatives exist.

The allocator is one-way with respect to risk: **V15 can never increase the V14 risk multiplier.** Holding unused risk budget is valid.

`AdaptivePaperAutonomyEngine` continues to rank on the canonical `utility` field, which V15 rebinds to portfolio-adjusted utility.

## Position intelligence

`workstation/position_intelligence_v15.py` adds HOLD / REDUCE / TRAIL / PARTIAL_EXIT / EXIT style reasoning. Its automatic contract is risk-neutral or risk-reducing only. ADD can be marked eligible, but any add must re-enter the normal V15 opportunity/risk path; the position manager cannot increase exposure by itself.

## Causal trade review

`causal_trade_review_v15.py` explicitly separates decision quality from outcome. A losing trade with good verified process is not automatically punished, and a profitable trade with weak process is not automatically reinforced. Review includes entry EV, confidence, geometry quality, hard blockers, MAE/MFE and entry/exit timing heuristics.

## Execution forensics

`execution_forensics_v15.py` persists bounded paper-only events across:

DISCOVERY -> BELIEF_UPDATE -> HYPOTHESIS_BUILD -> DECISION -> PORTFOLIO_ALLOCATION -> LIVE_MARK_RECHECK -> SIZE_PLAN -> PAPER_DESK_ACCEPTED/REJECTED -> POSITION_OPENED/MANAGED/CLOSED -> POST_TRADE_REVIEW.

There is no ambiguous WATCHING terminal state.

## Supervisor hardening

V15 fixes the Windows launch race seen after V14.1 verification:

- OS-held single-supervisor lease
- `JARVIS.bat` fast-path opens the existing V15 dashboard instead of starting a duplicate supervisor
- runtime snapshots use unique PID-scoped temporary files and atomic `os.replace`
- the old shared `state.tmp` write pattern is not used by V15
- unknown processes are never terminated

## Runtime surfaces

Master remains protected V8 Unified Intelligence on `127.0.0.1:8797` with read-only `/api/v15/paper-authority`.

Quant on `127.0.0.1:8787` adds:

- `/api/v15/status`
- `/api/v15/reasoning-trace`
- `/api/v15/market-beliefs`
- `/api/v15/position-intelligence`
- `/api/v15/causal-trade-review`
- `/api/v15/execution-forensics`

Completion on `127.0.0.1:8799` proxies the same governed intelligence.

## Permanent safety contract

- paper only
- live execution false
- automatic broker order false
- no broker place/modify/cancel/submit API
- automatic production strategy rewrite false
- external consequential actions approval gated
- exactly 29 permanent specialists
- legacy `critic` remains one of the 29
- V15 planes are services, not new permanent agents
- investment remains LONG ONLY
- no fabricated candles, market data, dealer inventory, IV history or synthetic paper outcome history
- `INVALID_RISK_LEVELS` remains hard when verified geometry cannot be built
- Paper Desk remains final risk authority
