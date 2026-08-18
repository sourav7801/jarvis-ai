# Jarvis Core — Phase 1

This package converts Jarvis from a one-shot JSON command dispatcher into a
real agent loop:

**Understand → choose tool → execute Python → observe real result → continue → answer**

## Why this fixes your old `current_time` bug

Old model output:

```json
{"action":"current_time","response":"2024-02-20 14:30:00"}
```

The old runtime treated the payload incorrectly and the model was also allowed
to invent a result.

The Phase-1 parser now:

1. Accepts both `action` and `tool` for compatibility.
2. Normalizes them into a real `ToolCall`.
3. Ignores any fake `response` attached to a tool request.
4. Executes the actual registered Python function.
5. Sends the real result back to the model as `TOOL OBSERVATION`.
6. Allows the model to either call another tool or return a final answer.

## Target folder structure

Copy these folders/files into `C:\Jarvis`:

```text
C:\Jarvis
├── core\
│   ├── executor.py
│   ├── model.py
│   ├── orchestrator.py
│   ├── parser.py
│   ├── prompts.py
│   └── types.py
├── tools\
│   ├── registry.py
│   └── computer_phase1.py
├── tests\
│   ├── test_parser.py
│   └── test_registry_executor.py
├── bootstrap.py
└── example_main.py
```

## First test

From your existing virtual environment:

```powershell
cd C:\Jarvis
python -m unittest discover -s tests -v
```

Expected result: all tests pass.

## Verify registry

```powershell
python -c "import bootstrap; from tools.registry import list_tools; print(list(list_tools().keys()))"
```

Expected:

```text
['current_time', 'system_info', 'list_files', 'open_website', 'open_notepad', 'open_calculator']
```

## Verify real current-time execution

```powershell
python -c "import bootstrap; from core.executor import ToolExecutor; from core.types import ToolCall; print(ToolExecutor().execute(ToolCall('current_time', {})).to_dict())"
```

The time must come from Python on your Windows machine — never from the LLM.

## Connect your existing tools

You already have functions in `tools\computer.py`.

You have two clean options:

### Option A — decorate the existing functions

```python
from tools.registry import tool

@tool(description="Get the current local date and time.", risk="read_only")
def current_time():
    ...
```

Do this for each existing function.

### Option B — register them without editing their source

```python
from tools.registry import register_tool
from tools.computer import current_time, open_notepad

register_tool(
    current_time,
    description="Get the current local date and time.",
    risk="read_only",
)

register_tool(
    open_notepad,
    description="Open Notepad.",
    risk="low",
)
```

## Connect your current model

In `example_main.py`, replace:

```python
your_existing_ai_function(messages)
```

with your current Ollama/OpenAI model function.

The model receives normal chat messages and must return one of:

```json
{"tool":"current_time","arguments":{}}
```

or:

```json
{"final":"It is 2:55 AM."}
```

The orchestrator automatically loops after a tool result.

## Phase 2

After this core is stable, add:

- model router (Ollama + cloud/coding providers)
- SQLite memory
- task planner
- permission levels
- execution logs
- browser/research tools
- computer vision/control

Do not add autonomous trading or destructive computer actions until the
permission and risk layer exists.
