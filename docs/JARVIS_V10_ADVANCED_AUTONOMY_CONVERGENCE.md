# JARVIS V10 — Advanced Autonomy Convergence

V10 deliberately consolidates multiple remaining blueprint items into one larger governed release instead of shipping many small patches.

## What V10 converges

V10 includes the V9.3 World Model + Cognitive Event Bus work and adds:

- top-level governed Autonomy Orchestrator
- system-level Critic / Verifier (not agent #30)
- persistent bounded Evidence Ledger with sensitive-field redaction
- governed Engineering Workflow and durable review packets
- System Diagnostics and bounded reversible recovery actions
- advanced Executive Context integrating world state, critic, evidence, engineering, diagnostics and paper governance
- unified Paper Trading Learning + Champion/Challenger governance observability
- Completion Center advanced control surfaces for autonomy, critic/evidence, engineering, system diagnostics and trading governance

## Architecture

```text
USER
  |
AUTONOMY ORCHESTRATOR
  |
EXECUTIVE CONTROL PLANE
  |
CONTEXT FABRIC
  |-------------------------------|
  |               |               |
WORLD MODEL   COGNITIVE BUS   EVIDENCE LEDGER
  |               |               |
GOAL/TASK DAG  TYPED EVENTS   PROVENANCE
  |               |               |
MISSION WORKER ----+--------- SYSTEM CRITIC
  |                               |
29 SPECIALISTS                VERIFY / HOLD
  |                               |
  +------ GOVERNED TOOLS ----------+
             |
       APPROVAL BOUNDARY
```

## Governed autonomy

Autonomy Control can create a converged plan across Executive, Context, World Model and domain-specific governance. Mission queueing is explicit. Queueing a mission does **not** automatically start the worker and never grants authority for consequential external actions.

## Critic / Verifier

Verdicts:

- `VERIFIED`
- `PARTIAL`
- `CONTRADICTED`
- `INSUFFICIENT_EVIDENCE`
- `FAILED`

The Critic checks evidence completeness, provenance, freshness, contradictions, tool failures and safety policy. Only `VERIFIED` permits governed progression.

## Engineering governance

The workflow is:

```text
INSPECT
 -> PLAN
 -> CHILD BRANCH (explicit operator confirmation)
 -> GOVERNED EDITING BOUNDARY
 -> COMPILE
 -> TARGETED TESTS
 -> FULL REGRESSION when release-level
 -> DIFF CHECK
 -> CRITIC VERIFY
 -> REVIEW PACKET
 -> WAIT FOR OPERATOR
```

It does not automatically edit production code, merge, push, deploy, or rewrite strategy logic.

## System diagnostics

Diagnostics observe Master, Quant and Completion service health, disk pressure, runtime state and mission leases. Unknown processes are never killed. Only these reversible internal recoveries are executable by this module:

- recover expired mission leases
- refresh the World Model

Other actions remain proposals for operator review.

## Trading governance

The Trading Governance Center composes existing Paper Desk performance, bounded learning, mistake hypotheses, self-improvement research and Champion/Challenger records. It may propose research hypotheses but cannot promote live strategies or rewrite production strategy code.

## Safety contract

```text
permanent_agents                       = 29
paper_only                             = True
live_execution                         = False
automatic_broker_order                 = False
automatic_production_strategy_rewrite  = False
external_actions                       = APPROVAL_GATED
unknown_process_termination            = False
```

No broker place/modify/cancel order API is introduced. No synthetic L2/DOM/dealer inventory is fabricated.

## Release verification

V10 is not considered verified until the Windows installer passes:

1. clean-tree and exact-backup preflight
2. V9.2 ancestry check (so the user can install directly from the current rollback floor)
3. Python compilation
4. JavaScript syntax validation
5. V9.3 + V10 safety contracts
6. V10/V9.3/V9.2/V9.1/V8.1/V8 targeted compatibility tests
7. full repository unittest regression
8. 29-agent Protected Core checks
9. `git diff --check` and clean post-test tree
10. live Master/Quant/Completion HTTP verification including World Model, Cognitive Bus, Autonomy, Critic, Engineering, Diagnostics and Trading Governance endpoints
11. exact rollback on failure

The historical V9.3 PowerShell `$home`/`$HOME` runtime-check bug is avoided in the V10 installer by using a non-reserved variable name.
