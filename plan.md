# Orcha Implementation Plan

## Overview

`orcha` is a lightweight, async-first workflow orchestration library for LLM applications. This plan outlines the implementation strategy.

## Project Structure

```
orcha/
├── __init__.py          # Public API exports
├── types.py             # Pydantic models
├── context.py           # NodeContext implementation
├── node.py              # Node class & @node_fn decorator
├── workflow.py          # Workflow class & execution engine
├── callbacks.py         # Callback system
├── stores/
│   ├── __init__.py
│   ├── base.py          # ContextStore abstract class
│   └── memory.py        # InMemoryContextStore
└── integrations/
    ├── __init__.py
    └── fastapi.py       # make_fastapi_app
```

## Phase Breakdown

### Phase 1: Core Types (`types.py`)

Implement base Pydantic models:

- `UserInput` - Input from user (text, select, number, date)
- `UIOutput` - Output to UI (text, answer_type, select_options)
- `AgentResp` - Agent response wrapper
- `AgentRequest` - Incoming request model
- `Turn` - Conversation turn (user/bot)
- `Log` - Log entry model

### Phase 2: Context Store (`stores/`)

- `ContextStore` - Abstract base class with `get()` and `set()` methods
- `InMemoryContextStore` - Simple dict-backed implementation

### Phase 3: Node Context (`context.py`)

Implement `NodeContext`:

- Properties: `conversation_id`, `node_name`, `node_counter`, `conversation_history`, `user_input`, `logs`
- Methods: `getState(model_cls)`, `setState(key, value)`
- Internal state store management

### Phase 4: Node System (`node.py`)

- `Node` class with:
  - `name`, `func`, `config`, `output_node`, `run_in_worker`
  - Support for routing: string, list of strings, or router callable
- `@node_fn` decorator:
  - Marks async function as workflow node
  - Inspects signature for config injection
  - Sets `_is_orcha_node` attribute

### Phase 5: Workflow Engine (`workflow.py`)

`Workflow` class:
- Constructor: `name`, `state_model`, `init_state`, `nodes`, `callbacks`, `n_worker`, `node_timeout` , `context_store`
- Node indexing by name
- Worker pool management

Execution engine:
- Graph traversal from entry point
- Handle router functions
- Parallel execution for list output_node
- Worker offloading via a prosess pool 
- Callback firing at each step

it have a .run method that gets a AgentRequest / fetch data from the store and build ctx / make task(s) and await (with FIRST_COMPLETED and timeout)

### Phase 6: Callbacks (`callbacks.py`)

- `CallbackEvent` model (event_name, node_name, error)
- `Callback` class (on, fn)
- Events: `node_start`, `node_end`, `node_err`, `set_state`

### Phase 7: FastAPI Integration (`integrations/fastapi.py`)

`make_fastapi_app()`:
- Accept `workflows` list`
- Register `/workflow/conversation_turn` endpoint
- Execute workflow
- Return response

### Phase 8: Public API (`__init__.py`)

Export:
- check the `example.py` imports and expose them to __init__



## Testing Strategy

1. Unit tests for each component
2. Integration test with example workflow (customer support bot)
3. Test parallel execution
4. Test worker offloading
5. Test callback firing

## Implementation Order

1. `types.py`
2. `stores/base.py`
3. `stores/memory.py`
4. `context.py`
5. `node.py`
6. `callbacks.py`
7. `workflow.py`
8. `integrations/fastapi.py`
9. `__init__.py`
10. Tests
