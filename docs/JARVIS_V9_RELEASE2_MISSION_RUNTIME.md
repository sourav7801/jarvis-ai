# JARVIS V9 Release 2 — Goal Graph + Resumable Mission Runtime

Base checkpoint: `dfba843ca585f4f8c8878340548688715a9349e9` (V9 Release 1, user-confirmed successful local release gate).

## Purpose

V9 Release 2 converts the existing durable MissionQueue and one-shot Mission Control packet builder into a persistent, supervised local mission runtime. The release does not authorize consequential external actions and does not add any live broker execution surface.

## Persistent goal/task graph

`omni/goal_task_graph.py` stores bounded mission DAGs under `data/state/goal_task_graphs.json`.

Core local stages:

- `T00` — frame objective / bounded plan;
- `T10` — execute the supervised Mission Control packet;
- `T20` — verify critic evidence and safety;
- `A90` — consequential external actions, permanently held at `WAITING_APPROVAL` unless a separate approved execution system is deliberately invoked.

Graph state, evidence, artifacts, checkpoints, retry counts, failures and timestamps persist across process restarts.

## Mission queue extensions

`omni/mission_queue.py` now provides:

- durable priority queueing;
- lease acquisition and expired-lease recovery;
- heartbeat lease renewal;
- worker-owned checkpoints;
- pause/resume for non-active queued missions;
- bounded snapshots;
- a corrected priority-retention bound so high-priority head items are retained when the queue reaches its maximum size.

## Supervised mission worker

`omni/mission_worker.py` is intentionally single-flight (`bounded_concurrency = 1`). It:

1. leases the next queue item;
2. creates or reuses its persistent goal graph;
3. resumes from already verified checkpoints rather than automatically repeating completed stages;
4. renews the lease while local mission work is active;
5. invokes existing `MissionControl.create_mission()` for local specialist synthesis;
6. attaches the resulting mission packet/evidence to the graph;
7. verifies the existing Mission Control critic result;
8. completes the queue item only when the local packet passes verification;
9. leaves `A90` at `WAITING_APPROVAL`;
10. retries bounded failures up to the configured maximum.

A packet with `NEEDS_HUMAN_REVIEW` is blocked at the quality gate and is not treated as an automatically verified result.

## Completion / Mission Center

The loopback Completion Center exposes read/operator surfaces:

- `GET /api/missions`
- `GET /api/missions/graphs`
- `GET /api/missions/graph?id=<goal-id>`
- `POST /api/missions/enqueue`
- `POST /api/missions/start`
- `POST /api/missions/stop`
- `POST /api/missions/run-once`
- `POST /api/missions/pause`
- `POST /api/missions/resume`

The worker is **explicit-start** in this release. Merely launching JARVIS does not automatically consume queued missions.

The Mission UI shows queue state, worker state, persistent graph progress, and approval locks.

## Safety invariants

- `paper_only = True`
- `live_execution = False`
- `automatic_broker_order = False`
- `automatic_production_strategy_rewrite = False`
- `external_actions = APPROVAL_GATED`
- permanent specialist registry remains **29 agents**
- Executive Control Plane remains a system plane, not agent 30
- no live broker place/modify/cancel API was added
- no external consequential action is executed by the mission worker

## Release gate

Use `install-jarvis-v9-release2.ps1`.

The installer requires a clean tree, creates a rollback branch, verifies descent from V9 Release 1, compiles the new Python, checks Completion/Mission JavaScript, runs V9.2 targeted regression plus earlier compatibility suites, runs the full repository test suite by default, rechecks 29-agent/paper-only safety, launches JARVIS, and verifies the new mission runtime endpoints.

Do not treat V9 Release 2 as verified until that installer passes on the Windows workstation.
