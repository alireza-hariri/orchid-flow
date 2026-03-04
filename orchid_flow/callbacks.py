from pydantic import BaseModel, ConfigDict
from typing import Callable, Literal, Optional, Any, TypeAlias, Union
import asyncio

from .context import NodeContext


class CallbackEvent(BaseModel):
    """
    Event object passed to callback functions.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    event_name: str
    node_name: str
    error: Optional[Exception] = None
    data: Optional[Any] = None


EventStr: TypeAlias = Literal["node_start", "node_end", "node_err", "set_state"]


class Callback:
    """
    Represents a callback handler for workflow events.

    Callbacks are fired at specific points during workflow execution
    to allow observation and side effects.
    """

    def __init__(self, on: EventStr, fn: Callable):
        """
        Initialize a Callback.

        Args:
            on: Event name to listen for (e.g., 'node_start', 'node_end', 'node_err', 'set_state')
            fn: Async callback function that takes (ctx: NodeContext, event: CallbackEvent)
        """
        self.on = on
        self.fn = fn

    async def fire(self, ctx: NodeContext, event: CallbackEvent) -> None:
        """
        Fire the callback with the given context and event.

        Args:
            ctx: The current node context
            event: The callback event object
        """
        if asyncio.iscoroutinefunction(self.fn):
            await self.fn(ctx, event)
        else:
            self.fn(ctx, event)
