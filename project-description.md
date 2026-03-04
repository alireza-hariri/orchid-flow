# Orcha: Workflow Orchestration for LLM Applications

`orcha` is a lightweight, async-first workflow orchestration library designed specifically for LLM applications. It allows you to define complex conversation flows, state management, and multi-agent interactions using a declarative Python interface.

## Features

- **Async-First**: Built on `asyncio` for high-performance concurrent execution.
- **Type-Safe**: Leverages Pydantic for configuration and state validation.
- **Flexible Routing**: Supports static transitions, conditional routing, and parallel execution.
- **Worker Support**: Offload heavy nodes to background workers via `ProcessPoolExecutor`.
- **Pluggable Context Storage**: Swap between in-memory, Redis, or custom stores.

## Installation

```bash
pip install orcha
```

## Quick Example

Here is a complete example of a customer support bot that classifies user intent and routes to specific handlers.

### 1. Define State and Configuration

First, define the shape of your workflow state and node-specific configurations using Pydantic.

```python
from pydantic import BaseModel
from typing import Optional

class SupportState(BaseModel):
    intent: Optional[str] = None
    attempt_count: int = 0
    customer_id: Optional[str] = None

class RefundConfig(BaseModel):
    max_refund_amount: float = 50.0
    require_reason: bool = True
```

### 2. Define Nodes

Node functions receive `ctx: NodeContext` as the first argument, and optionally a config as the second. They can be async or sync.

```python
from orcha.context import NodeContext
from orcha.types import AgentResp, UIOutput

async def classify_intent(ctx: NodeContext) -> AgentResp:
    state = ctx.getState(SupportState)
    
    user_text = ctx.user_input.text or ""
    if "refund" in user_text.lower():
        state.intent = "refund"
    elif "human" in user_text.lower():
        state.intent = "human_agent"
    else:
        state.intent = "general"
    
    ctx.setState("intent", state.intent)
    return None  # Proceed silently to next node


def handle_refund(ctx: NodeContext, config: RefundConfig) -> AgentResp:
    state = ctx.getState(SupportState)
    state.attempt_count += 1
    ctx.setState("attempt_count", state.attempt_count)

    if state.attempt_count > 3:
        return AgentResp(ui_output=UIOutput(text="I'm having trouble processing this."))

    return AgentResp(
        ui_output=UIOutput(
            text=f"Processing refund (Limit: ${config.max_refund_amount}). Please confirm.",
            answer_type="select",
            select_options=["Yes, Refund", "Cancel"]
        )
    )
```

### 3. Define Routers

Routers determine which node to execute next based on the current context.

```python
def intent_router(ctx: NodeContext) -> str:
    state = ctx.getState(SupportState)
    
    if state.intent == "refund":
        return "refund_node"
    elif state.intent == "human_agent":
        return "transfer_node"
    return "general_chat_node"
```

### 4. Compose the Workflow

Connect your nodes and routers into a `Workflow` object.

```python
from orcha.workflow import Workflow
from orcha.node import Node
from orcha.callbacks import Callback

async def log_start(ctx, event):
    print(f"Node {ctx.node_name} started.")

async def log_end(ctx, event):
    print(f"Node {ctx.node_name} ended. {event.data['elapsed_ms']:.2f}ms")

support_workflow = Workflow(
    name="customer_support",
    state_model=SupportState,
    init_state=SupportState(),
    entry_node="entry_point",
    callbacks=[
        Callback(on="node_start", fn=log_start),
        Callback(on="node_end", fn=log_end),
    ],
    nodes=[
        Node(
            name="entry_point",
            func=classify_intent,
            output_node=intent_router,  # Router function
        ),
        Node(
            name="refund_node",
            func=handle_refund,
            config=RefundConfig(max_refund_amount=100.0),
            output_node="transfer_node",
            run_in_worker=True
        ),
        Node(
            name="transfer_node",
            func=transfer_to_human,
            output_node=None  # End of flow
        ),
    ]
)
```

### 5. Run the Workflow

```python
from orcha.types import AgentRequest, UserInput

result = await support_workflow.run(
    AgentRequest(
        conversation_id="user-123",
        user_input=UserInput(text="I want a refund")
    )
)
print(result.ui_output.text)
```

---

## Core Concepts

### Node Functions

Node functions receive `ctx: NodeContext` and optionally a config. They can be async or sync.

```python
async def my_node(ctx: NodeContext) -> AgentResp | None:
    ...

def my_sync_node(ctx: NodeContext, config: MyConfig) -> AgentResp | None:
    ...
```

- **`ctx`**: The `NodeContext` provides access to conversation history, user input, and state management.
- **`config`**: (Optional) A Pydantic model instance injected at runtime.
- **Return**: Returns an `AgentResp` to send a message to the user, or `None` to proceed to next node/nodes.

### Node Output & Routing

The `output_node` parameter can be:

1. **A String**: `"next_node_name"` (Direct transition).
2. **A List**: `["node_a", "node_b"]` (Parallel execution).
3. **A Router Function**: A callable that returns the name(s) of the next node(s).

### State Management

State is defined globally per workflow but accessed locally.

```python
state = ctx.getState(MyStateModel)
state.counter += 1
ctx.setState("counter", state.counter)
```

### Callbacks

Hooks to observe workflow lifecycle events.

Events:
- `node_start`: Fired before a node executes.
- `node_end`: Fired after a node executes successfully.
- `node_err`: Fired if a node raises an exception.
- `set_state`: Fired when state is updated.

```python
Callback(on="node_end", fn=my_handler)
```

The callback receives `(ctx: NodeContext, event: CallbackEvent)`:
- `event.data["elapsed_ms"]` - Execution time in milliseconds
- `event.data["node_result"]` - The node's return value (on `node_end`)

---

## API Reference

### `NodeContext`

| Method/Property | Type | Description |
| :--- | :--- | :--- |
| `conversation_id` | `str` | Unique ID for the session. |
| `user_input` | `UserInput` | The input from the user for this turn. |
| `conversation_history`| `list[Turn]` | History of the conversation. |
| `node_name` | `str` | Name of the current node. |
| `node_counter` | `dict[str, int]` | Execution count per node. |
| `getState(model_cls)` | `BaseModel` | Retrieves the current state object. |
| `setState(key, val)`| `None` | Updates the state. |
| `add_log(level, msg)`| `None` | Adds a log entry. |

### `Node`

| Argument | Type | Description |
| :--- | :--- | :--- |
| `name` | `str` | Unique identifier for the node. |
| `func` | `Callable` | The node function (async or sync). |
| `config` | `BaseModel` | Configuration object for the node. |
| `output_node` | `str \| list \| Callable` | Next step definition. |
| `run_in_worker` | `bool` | If True, runs in a background worker process. |

### `Workflow`

| Argument | Type | Description |
| :--- | :--- | :--- |
| `name` | `str` | Unique workflow identifier. |
| `state_model` | `Type[BaseModel]` | Pydantic model class for state. |
| `init_state` | `BaseModel` | Initial state instance. |
| `entry_node` | `str` | Name of the first node to execute. |
| `nodes` | `list[Node]` | List of Node instances. |
| `callbacks` | `list[Callback]` | Optional list of Callback handlers. |
| `n_worker` | `int` | Number of worker processes. |
| `node_timeout` | `float` | Optional timeout per node (seconds). |
| `context_store` | `ContextStore` | Store for persisting context. |

### `Workflow.run()`

```python
async def run(request: AgentRequest) -> AgentResp
```

Execute the workflow for a single turn. Returns the `AgentResp` from the terminating node.

### `ContextStore`

Abstract base class for persisting conversation context.

```python
class ContextStore(ABC):
    async def get(self, conversation_id: str) -> Any: ...
    async def set(self, conversation_id: str, ctx: Any) -> None: ...
```

Built-in implementations:
- `InMemoryContextStore`: Simple in-memory storage (default).
