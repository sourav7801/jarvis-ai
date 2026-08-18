# Canonical Migration Inventory

## Active runtime

| Concern | Canonical location |
|---|---|
| Console orchestration | `main.py` |
| Configuration | `config.py` and process environment |
| Durable orchestration | `omni/contracts.py`, `omni/orchestrator.py` |
| Agent contracts | `omni/agent_registry.py`, `omni/dispatch.py` |
| Worker isolation | `omni/isolated_runner.py`, `omni/isolated_worker.py` |
| Safety and approvals | `tools/safety.py`, `tools/capabilities.py`, `omni/approval.py` |
| Audit and episodic state | `omni/audit.py` |
| Hybrid memory | `omni/hybrid_memory.py` |
| Model routing | `omni/model_router.py`, `omni/model_provider.py` |
| Governed research retrieval | `omni/web_research.py` |
| Trading research | `trading/research/` |
| Workstation service | `workstation/app.py` |
| Workstation frontend | `workstation/jarvis_trading_workstation_v7/static/` |
| Operational checks | `scripts/doctor.py`, `scripts/static_check.py` |

## Compatibility components

The specialized modules immediately under `agents/` remain compatibility
implementations behind the canonical agent registry. They should be migrated
incrementally, one tested contract at a time.

## Historical components

Root files containing `backup`, `before`, `old`, or `stable`, workstation V1–V5,
and embedded version packages are preserved historical references. They are not
canonical entry points and should not receive new features.

No historical files were deleted because provenance and rollback policy have
not yet been agreed with the owner.

