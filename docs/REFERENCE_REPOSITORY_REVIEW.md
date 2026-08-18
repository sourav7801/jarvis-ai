# External Repository Review

Date: 2026-08-17

This review treats every downloaded archive and public repository as untrusted
reference material. No installer, shell script, PowerShell script, binary,
package lifecycle hook, model pickle, or project code from the reviewed
repositories was executed. No third-party source code or visual trade dress was
copied into JARVIS.

## Scope

| Reference | Observed size | License posture | Decision |
|---|---:|---|---|
| OpenClaw archive | 32,507 files; about 408 MB unpacked | MIT, with many bundled extensions and dependencies | Learn from gateway, manifest, session-isolation, diagnostics, and approval patterns; do not import the platform |
| AI-trader archive | 160 files; about 6.2 MB unpacked | MIT | Learn from evidence-oriented trading dashboards and model-monitoring vocabulary; do not import execution or serialized models |
| FinceptTerminal archive | 3,598 files; about 59 MB unpacked | Attached terms include AGPL language plus additional commercial-use and trade-dress restrictions | Do not copy code, layouts, terminology, or visual identity; use only general engineering concepts |
| LangGraph | Current public GitHub project | MIT | Keep JARVIS's dependency-light durable orchestrator; adopt explicit state, human gates, and observability principles |
| OpenHands Agent Canvas | Current public GitHub project | MIT | Learn from the multi-agent control-center concept; do not embed a second Node/Docker agent runtime with broad filesystem authority |
| Browser Use | Current public GitHub project | MIT | Keep as a future opt-in browser adapter with domain allowlists and approvals; do not silently add browser control |
| Dify / Flowise | Current public GitHub projects | Project-specific open-source terms | Do not add a second workflow/frontend stack; JARVIS already owns its orchestration and dashboard surfaces |

Primary upstream references:

- <https://github.com/openclaw/openclaw>
- <https://github.com/aaryansinha16/AI-trader>
- <https://github.com/Fincept-Corporation/FinceptTerminal>
- <https://github.com/langchain-ai/langgraph>
- <https://github.com/OpenHands/OpenHands>
- <https://github.com/browser-use/browser-use>
- <https://github.com/langgenius/dify>
- <https://github.com/FlowiseAI/Flowise>

## JARVIS baseline review

The canonical inventory contained 281 non-environment/non-state files,
including 241 Python files and 17 test modules before this change. The review
covered the runtime, agent registry, durable orchestrator, approvals, audit
database, model router, memory, sandbox, Company OS, Mission Control, web
research, market runtime, trading research, workstation API, UI, launch scripts,
configuration, tests, and project documentation.

Strong foundations already present:

- typed agent capabilities with bounded inputs and outputs;
- optional isolated workers with signed requests and time limits;
- durable plans, task states, audit events, and single-use scoped approvals;
- fail-closed tool schemas, capability declarations, and postconditions;
- loopback-first authenticated workstation API;
- private-network blocking and bounded public-web retrieval;
- read-only FYERS data with live broker execution disabled;
- separate contextual workspaces and conversations;
- independent mission critic and visible approval locks.

Material gaps or operating risks that remain visible:

- the initialized Git repository currently reports the working project files as
  untracked, so a deliberate first commit and remote/backup policy are required;
- optional dependencies are broadly specified rather than fully locked with a
  reproducible hash-verified environment;
- historical workstation and trading-core copies increase maintenance noise;
- the coding agent is advisory, not a fully isolated autonomous engineering
  runtime;
- there is no distributed/background queue for work that must outlive the local
  process;
- interactive browser control, cloud connectors, premium data, production
  monitoring, and hardware-backed authorization remain external integrations;
- live broker execution and reconciliation remain intentionally absent.

## Adopted changes

The review identified observability as the highest-value, lowest-risk upgrade.
JARVIS now includes a native System Core control plane that:

1. statically parses every registered agent module and confirms the configured
   entrypoint without importing or executing the agent;
2. displays authority, capabilities, isolation, readiness, and diagnostics;
3. displays every registered tool's capability set, risk class, and policy;
4. shows runtime trust boundaries, FYERS connection posture, approval locks,
   and live-execution state;
5. exposes a secret-free audit timeline that omits arguments, results, event
   payloads, and credentials;
6. summarizes durable mission status and critic/approval state;
7. provides a separate System Control chat and authenticated
   `/api/control-plane` endpoint.

This captures useful control-center, manifest, diagnostics, and trace ideas
without importing third-party runtimes, dependencies, execution authority, or
protected visual identity.

## Explicitly rejected changes

- No downloaded ZIP was extracted into or vendored inside JARVIS.
- No live/paper execution code, broker order router, performance claim, or
  serialized `.pkl`/`.joblib` model was imported from AI-trader.
- No Fincept source, screen layout, palette, command syntax, or widget
  vocabulary was copied.
- No OpenClaw installer, Node workspace, channel gateway, plugin bundle, or
  device runtime was installed.
- No browser-control package was installed or granted access to the user's
  signed-in browser.
- No framework was added merely to increase the agent count.

The guiding rule is capability depth with evidence, not superficial agent or
dependency count.
