from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, model_validator
from typing import Any, Callable, Optional, TypeVar, Dict

from .types import UserInput, Turn, Log


class ConversationState(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    _on_field_change: Optional[Callable] = PrivateAttr(default=None)
    _initialized: bool = PrivateAttr(default=False)
    _parent_ctx: Optional["NodeContext"] = PrivateAttr(default=None)

    @model_validator(mode="after")
    def _post_init(self) -> "ConversationState":
        """Mark model as initialized after validation completes."""
        self._initialized = True
        return self

    def __setattr__(self, name: str, value: Any) -> None:
        # Get the old value if it exists
        old_value = self.__dict__.get(name, None)

        # Set the new value
        super().__setattr__(name, value)

        # Trigger callback only if:
        # 1. Model is fully initialized
        # 2. Attribute is a model field (not private)
        # 3. Callback is defined
        # 4. Value actually changed
        if (
            self._initialized
            and name in type(self).model_fields
            and self._on_field_change is not None
            and old_value != value
        ):
            # breakpoint()
            self._on_field_change(self._parent_ctx, name, old_value, value)


State = TypeVar("State", bound=ConversationState)


class NodeContext(BaseModel):
    """
    Context object passed to each node during workflow execution.
    Provides access to conversation state, history, and state management.
    """

    conversation_id: str
    node_name: str
    node_counter: Dict[str, int] = Field(default_factory=dict)
    conversation_history: list[Turn] = Field(default_factory=list)
    other_data: Dict[str, Any] = Field(default_factory=dict)
    user_input: UserInput
    logs: list[Log] = Field(default_factory=list)

    state: State | None = None

    def exec_count(self, node: str):
        return self.node_counter.get(node, 0)

    def add_log(self, level: str, message: str) -> None:
        """
        Add a log entry to the context.

        Args:
            level: Log level (e.g., 'info', 'error', 'debug')
            message: Log message
        """
        import time

        self.logs.append(Log(level=level, message=message, timestamp=time.time()))
