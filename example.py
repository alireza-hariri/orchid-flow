import asyncio
from orchid_flow.callbacks import Callback, CallbackEvent
from orchid_flow.context import ConversationState, NodeContext
from orchid_flow.node import Node
from orchid_flow.workflow import Workflow
from pydantic import BaseModel
from typing import Optional
from orchid_flow.types import UIOutput, UserInput, AgentResp, AgentRequest


# Define the global state for the conversation
class SupportState(ConversationState):
    intent: Optional[str] = None
    attempt_count: int = 0
    customer_id: Optional[str] = None


# Define configuration for a specific node
class RefundConfig(BaseModel):
    max_refund_amount: float = 50.0
    require_reason: bool = True


async def classify_intent(ctx: NodeContext) -> AgentResp:
    """
    Analyzes user input to determine intent.
    Demonstrates a simple linear progression.
    """
    # Access state
    state = ctx.state

    # Logic to determine intent (mocked for example)
    user_text = ctx.user_input.text or ""
    if "refund" in user_text.lower():
        state.intent = "refund"
    elif "human" in user_text.lower():
        state.intent = "human_agent"
    else:
        state.intent = "general"

    # Return None to silently proceed to the next node (router)
    return None


def handle_refund(ctx: NodeContext, config: RefundConfig) -> AgentResp:
    """
    Handles refund requests. Uses injected RefundConfig.
    """
    ctx.add_log("info", "some log")

    return AgentResp(
        ui_output=UIOutput(
            text=f"Processing refund (Limit: ${config.max_refund_amount}). Please confirm.",
            answer_type="select",
            select_options=["Yes, Refund", "Cancel"],
        )
    )


async def transfer_to_human(ctx: NodeContext) -> AgentResp:

    return AgentResp(ui_output=UIOutput(text="transfer is done"))


## router function


def intent_router(ctx: NodeContext) -> str:
    """
    Routes based on the intent stored in state.
    """
    return "refund_node"


# Define callbacks for logging
async def log_start(ctx: NodeContext, e: CallbackEvent):
    1 + ""
    print(f"Node {ctx.node_name} started.")


async def log_end(ctx: NodeContext, e: CallbackEvent):
    print(f"Node {ctx.node_name} ended. {e.data['elapsed_ms']:.2f}")


async def log_err(ctx: NodeContext, e: CallbackEvent):
    print(f"Node {ctx.node_name} error.")


async def on_set_state(ctx: NodeContext, e: CallbackEvent):
    print("set state", e.data, f"in node {ctx.node_name}")


# The Workflow Definition
support_workflow = Workflow(
    name="customer_support",
    initial_state=SupportState(),
    entry_node="entry_point",
    callbacks=[
        Callback(on="node_start", fn=log_start),
        Callback(on="node_end", fn=log_end),
        Callback(on="node_err", fn=log_err),
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
            output_node="transfer_node",
            run_in_worker=True,
        ),
        Node(
            name="transfer_node",
            func=transfer_to_human,
            output_node="transfer_node",  # End of flow
        ),
    ],
)


async def run():
    out1 = await support_workflow.run(
        AgentRequest(
            conversation_id="alaki",
            user_input=UserInput(text="سلام"),
        )
    )
    out2 = await support_workflow.run(
        AgentRequest(
            conversation_id="alaki",
            user_input=UserInput(text="خوبی"),
        )
    )
    return out1, out2


out1, out2 = asyncio.run(run())
print(out1.ui_output.text)
print(out2.ui_output.text)
