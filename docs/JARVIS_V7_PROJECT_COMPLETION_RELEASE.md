# JARVIS V7 — Project Completion Core

## Purpose

V7 turns the successful V6.3 advanced baseline into a project-completion release program.  The goal is not to add another isolated trading screen.  The goal is to close the largest remaining repository-controlled gaps, make the remaining blockers explicit, and give the operator one place to see whether JARVIS is actually complete, healthy and governed.

## V6.3 rollback floor

V7 is based on the locally verified V6.3 checkpoint:

`ade91b7526252bc29f3b2c4956919dcdc0ebef5c`

V6.3 passed 85 targeted tests, 1258 full repository tests and all required Master/Quant HTTP surfaces.  V7 must remain a descendant of that exact checkpoint.

## V7 completion surfaces

- Project Completion Auditor (`omni/project_completion.py`)
- Project Completion Center (`http://127.0.0.1:8799`)
- Repository AST Code Intelligence
- Model Router Telemetry
- Resumable local Mission Queue
- Robust OOS/bootstrap/cost Strategy Validation
- Durable paper/research Champion-Challenger Registry
- Rolling Correlation Risk Intelligence
- Canonical market-event publisher adapters
- V7 runtime ownership/supervision
- Updated machine-readable gap map
- Updated blueprint status

## Completion semantics

`PRESENT` means the repository contains the audited capability and its required evidence files.

`PARTIAL` means a repository-controlled capability exists but an important local implementation or machine capability is incomplete.

`MISSING` or `BROKEN` are repository defects.

`BLOCKED_EXTERNAL` means the capability cannot truthfully be completed by repository code alone.  Examples include licensed exchange-grade L2/L3 data, production infrastructure, hardware authorization and reviewed live broker execution.

External blockers are never silently counted as completed repository code.

## V7 safety boundary

V7 must preserve:

- paper/research trading only
- live execution false
- automatic broker order false
- automatic production strategy rewrite false
- external actions approval-gated
- approval state changes do not automatically execute the approved action
- robust validation can create paper challengers only
- the Champion/Challenger Registry can nominate paper champions only
- correlation intelligence is read-only until separately validated for risk-limit integration
- Code Intelligence parses source without importing arbitrary target modules

## Local release gate

Use `install-jarvis-v7-project-completion.ps1`.

The installer creates a timestamped rollback branch and refuses a dirty working tree.  It verifies descent from V6.3, compiles touched Python, checks JavaScript syntax, runs V7 plus V6.3 targeted regressions, runs the full repository regression, imports the main runtime, checks the V7 safety contract, validates Git cleanliness, starts JARVIS and verifies Master, Quant and Completion Center endpoints.

Any failure restores the exact previous branch/HEAD and keeps the backup branch.

## What V7 still does not claim

V7 does not claim:

- exchange co-location
- institutional FIX connectivity
- HFT execution
- licensed Level-2/Level-3 data where none is connected
- proprietary news/research subscriptions
- biometric owner authorization without trusted hardware/OS integration
- independent production security certification
- real broker execution

Those require separate infrastructure, credentials, licensing, controls and review.

## Definition of successful V7 installation

A successful local run ends with:

`JARVIS V7 PROJECT COMPLETION CORE: SUCCESS`

and HTTP 200 for:

- Master JARVIS `8797/`
- Quant health `8787/api/health`
- Quant intelligence page/runtime
- Project Completion Center `8799/`
- Project Completion health `8799/api/health`
- Project Completion audit `8799/api/completion`

Only after that local result should the V7 branch be described as verified.
