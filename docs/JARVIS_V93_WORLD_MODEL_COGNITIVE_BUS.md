# JARVIS V9.3 — World Model + Cognitive Event Bus

Base checkpoint: `5bfaadbbcbd4bd61d21c172664b14a7331d24677` (V9 Release 2, user-reported successful local gate).

## Purpose

V9.3 connects the persistent mission runtime to a bounded cognitive state layer. JARVIS can now maintain provenance-aware observations about its own runtime, missions, paper portfolio and verified market-event state, while a typed internal event bus carries meaningful state changes without granting execution authority.

## World Model

`omni/world_model.py` implements a bounded persistent state graph.

Every observation carries:

- node identity and kind;
- state snapshot;
- source;
- observation timestamp;
- freshness age and stale threshold;
- explicit `FRESH` / `STALE` state;
- confidence;
- provenance.

The graph is a context/reasoning surface only. It does not execute tools or external actions.

## Cognitive Event Bus

`omni/cognitive_event_bus.py` implements a bounded typed persistent bus with subscriber isolation.

Supported event families include markets/providers, services, missions/tasks, approvals, engineering/tests, model routing, memory and world-state updates.

The bus:

- caps retained events;
- isolates subscriber failures;
- redacts credential-like fields before persistence;
- keeps external actions approval-gated;
- contains no broker-order surface.

## Verified market bridge

`omni/cognitive_bridges.py` connects the existing validated `MarketEventBus` to the cognitive bus.

It intentionally does **not** mirror every tick. It forwards only meaningful state events such as:

- verified completed bars;
- stale market data;
- provider READY / DEGRADED / DOWN.

Unverified ordinary ticks are not promoted into cognitive facts.

## Executive context integration

`omni/context_fabric.py` now exposes bounded World Model and Cognitive Event Bus snapshots to Executive reasoning while preserving the historical V8 context-fabric version contract for compatibility.

## Completion Center

The V9.3 Completion Center extension exposes:

- `/api/world`
- `/api/world?refresh=1`
- `POST /api/world/refresh`
- `/api/cognitive-events`
- `/api/cognitive-bridge`
- `/v93_world.js`

The operator UI adds a dedicated **WORLD MODEL** surface showing node freshness, confidence, source, state and recent typed events.

## Safety

V9.3 preserves:

- `paper_only=True`
- `live_execution=False`
- `automatic_broker_order=False`
- automatic production rewrite disabled
- consequential external actions `APPROVAL_GATED`
- 29 permanent specialist agents

## Verification

Run `install-jarvis-v9-release3.ps1` on Windows.

The release is **not considered verified** until Python compile, JavaScript syntax, V9.3 targeted tests, prior-generation compatibility tests, the full repository regression, Protected Core, runtime HTTP checks and V9.3 identity/safety assertions all pass locally.
