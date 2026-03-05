# Orchid flow

A lightweight, async-first workflow orchestration (minimal lang-graph alternative) library for LLM applications.  orchid_flow simplifies building multi-step agent workflows with type-safe state management, flexible routing, and built-in observability.

## Features

- **Async-First**: Built on `asyncio` for high-performance concurrent execution
- **Type-Safe**: Leverages Pydantic for configuration and state validation
- **Flexible Routing**: Static transitions, conditional routing, and parallel execution
- **Worker Support**: Offload CPU-bound nodes to background processes
- **Pluggable Storage**: In-memory, Redis, or custom context stores
- **FastAPI Integration**: Quick REST API generation for workflows
- **Observability**: Built-in callback system for logging and monitoring

## Installation

```bash
pip install orchid_flow
```

## Quick Start

```python
import asyncio
from pydantic import BaseModel
from typing import Optional

from  orchid_flow import Workflow, Node, NodeContext, AgentRequest, AgentResp, UIOutput, UserInput


class CounterState(BaseModel):
    count: int = 0


async def increment(ctx: NodeContext) -> AgentResp:
    state = ctx.state
    state.count += 1

    return AgentResp(
        ui_output=UIOutput(text=f"Count: {state.count}")
    )


workflow = Workflow(
    name="counter",
    initial_state=CounterState(),
    entry_node="start",
    nodes=[
        Node(name="start", func=increment, output_node=None)
    ]
)


async def main():
    result = await workflow.run(
        AgentRequest(
            conversation_id="session-123",
            user_input=UserInput(text="increment")
        )
    )
    print(result.ui_output.text)  # Count: 1


asyncio.run(main())
```

## Core Concepts

### Nodes

Nodes are async functions that receive a `NodeContext`. Return `AgentResp` to respond to the user, or `None` to proceed silently to the next node.

```python
async def my_node(ctx: NodeContext) -> AgentResp | None:
    user_text = ctx.user_input.text
    user_text = ctx.user_input.text

    if user_text:
        return AgentResp(ui_output=UIOutput(text=f"You said: {user_text}"))
    return None
```

- Each node can get a config with pydantic type
- Nodes can also be sync functions that run in a separate worker process 

```python
from pydantic import BaseModel


class MyConfig(BaseModel):
    max_retries: int = 3
    timeout: float = 30.0


def sync_node(ctx: NodeContext, config: MyConfig) -> AgentResp | None:
    ctx.add_log("info", f"Max retries: {config.max_retries}")
    ...
```

### Routing

The `output_node` parameter supports multiple routing strategies:

| Type | Behavior |
|------|----------|
| `str` | Direct transition to named node |
| `list[str]` | Parallel execution of multiple nodes |
| `Callable` | Dynamic routing based on context |

```python
def router(ctx: NodeContext) -> str:
    if ctx.state.intent == "refund":
        return ["refund_node","send_email"]
    return "general_node"

# all following nodes are valid:
Node(name="classify", func=classify, output_node="process")
Node(name="classify", func=classify, output_node=["send_email", "update_db"])
Node(name="classify", func=classify, output_node=router)
```

### State

Define conversation state with Pydantic models. State persists across turns within a conversation.

```python
from  orchid_flow.context import ConversationState


class SupportState(ConversationState):
    intent: Optional[str] = None
    attempt_count: int = 0
    customer_id: Optional[str] = None


support_workflow = Workflow(
    name="support",
    initial_state=SupportState(),
    ...
)


async def handle_request(ctx: NodeContext) -> AgentResp:
    state = ctx.state
    state.attempt_count += 1
    ...
```

### Callbacks

Observe workflow lifecycle with callbacks for logging, metrics, or side effects:

```python
from  orchid_flow import Callback, CallbackEvent


async def log_start(ctx: NodeContext, e: CallbackEvent):
    print(f"[START] {ctx.node_name}")

async def log_end(ctx: NodeContext, e: CallbackEvent):
    elapsed = e.data["elapsed_ms"]
    print(f"[END] {ctx.node_name} - {elapsed:.2f}ms")

async def log_error(ctx: NodeContext, e: CallbackEvent):
    print(f"[ERROR] {ctx.node_name}: {e.error}")

async def on_state_change(ctx: NodeContext, e: CallbackEvent):
    print(f"[STATE_CHANGE] {ctx.node_name}: {e.data}")

workflow = Workflow(
    ...,
    callbacks=[
        Callback(on="node_start", fn=log_start),
        Callback(on="node_end", fn=log_end),
        Callback(on="node_err", fn=log_error),
        Callback(on="set_state", fn=on_state_change),
    ]
)
```

## Complete Example: Customer Support Bot

```python
import asyncio
from pydantic import BaseModel
from typing import Optional

from  orchid_flow import (
    Workflow, Node, NodeContext, Callback, CallbackEvent,
    AgentRequest, AgentResp, UIOutput, UserInput
)
from  orchid_flow.context import ConversationState


class SupportState(ConversationState):
    intent: Optional[str] = None
    attempt_count: int = 0
    customer_id: Optional[str] = None


class RefundConfig(BaseModel):
    max_refund_amount: float = 50.0
    require_reason: bool = True


async def classify_intent(ctx: NodeContext) -> AgentResp:
    state = ctx.state
    user_text = ctx.user_input.text or ""

    if "refund" in user_text.lower():
        state.intent = "refund"
    elif "human" in user_text.lower():
        state.intent = "human_agent"
    else:
        state.intent = "general"

    return None


def intent_router(ctx: NodeContext) -> str:
    state = ctx.state
    if state.intent == "refund":
        return "refund_node"
    elif state.intent == "human_agent":
        return "transfer_node"
    return "general_node"


def handle_refund(ctx: NodeContext, config: RefundConfig) -> AgentResp:
    ctx.add_log("info", "Processing refund request")

    return AgentResp(
        ui_output=UIOutput(
            text=f"Processing refund (Limit: ${config.max_refund_amount}). Confirm?",
            answer_type="select",
            select_options=["Yes, Refund", "Cancel"],
        )
    )


async def transfer_to_human(ctx: NodeContext) -> AgentResp:
    return AgentResp(
        ui_output=UIOutput(text="Transferring to human agent...")
    )


async def handle_general(ctx: NodeContext) -> AgentResp:
    return AgentResp(
        ui_output=UIOutput(text="How can I help you today?")
    )


async def on_set_state(ctx: NodeContext, e: CallbackEvent):
    print(f"State updated: {e.data}")


support_workflow = Workflow(
    name="customer_support",
    initial_state=SupportState(),
    entry_node="entry_point",
    callbacks=[
        Callback(on="set_state", fn=on_set_state),
    ],
    nodes=[
        Node(
            name="entry_point",
            func=classify_intent,
            output_node=intent_router,
            run_in_worker=False,
        ),
        Node(
            name="refund_node",
            func=handle_refund,
            config=RefundConfig(max_refund_amount=100.0),
            output_node=None,
            run_in_worker=True,
        ),
        Node(
            name="transfer_node",
            func=transfer_to_human,
            output_node=None,
        ),
        Node(
            name="general_node",
            func=handle_general,
            output_node=None,
        ),
    ],
)


app: FastAPI = make_fastapi_app(
    workflows=[support_workflow],
)

```


### Workflow

| Parameter | Type | Description |
|-----------|------|-------------|
| `name` | `str` | Workflow identifier |
| `initial_state` | `BaseModel` | Initial state instance |
| `entry_node` | `str` | Starting node name |
| `nodes` | `list[Node]` | Node definitions |
| `callbacks` | `list[Callback]` | Event handlers (optional) |
| `n_worker` | `int` | Worker processes (default: 4) |
| `node_timeout` | `float` | Node timeout in seconds (optional) |
| `context_store` | `ContextStore` | Context persistence (optional) |

### Node

| Parameter | Type | Description |
|-----------|------|-------------|
| `name` | `str` | Node identifier |
| `func` | `Callable` | Node function (async or sync) |
| `config` | `BaseModel` | Config injected as second argument |
| `output_node` | `str \| list \| Callable` | Next node(s) or router |
| `run_in_worker` | `bool` | Run in background process |

### NodeContext

| Property/Method | Description |
|-----------------|-------------|
| `conversation_id` | Unique conversation identifier |
| `node_name` | Current node name |
| `node_counter` | Execution counter |
| `conversation_history` | List of conversation turns |
| `user_input` | Current user input |
| `state` | Conversation state (typed) |
| `logs` | List of log entries |
| `add_log(level, message)` | Add a log entry |

### Types

| Type | Description |
|------|-------------|
| `AgentRequest` | Incoming request with `conversation_id` and `user_input` |
| `AgentResp` | Response with `ui_output` |
| `UserInput` | User input with `text`, `select`, `number`, `date` |
| `UIOutput` | UI output with `text`, `answer_type`, `select_options` |
| `Turn` | Conversation turn (user/bot) |
| `Log` | Log entry with `level` and `message` |

### Callback Events

| Event | Description |
|-------|-------------|
| `node_start` | Fired when a node begins execution |
| `node_end` | Fired when a node completes successfully |
| `node_err` | Fired when a node raises an exception |
| `set_state` | Fired when state is modified |

## License

MIT