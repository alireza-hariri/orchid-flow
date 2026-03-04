from typing import Any, Dict
from .base import ContextStore


class InMemoryContextStore(ContextStore):
    """
    Simple in-memory implementation of ContextStore.
    Uses a dictionary to store conversation contexts.
    Note: Data is lost when the process restarts.
    """

    def __init__(self):
        self._storage: Dict[str, Any] = {}

    async def get(self, conversation_id: str) -> Any:
        """
        Retrieve context for a given conversation ID.

        Args:
            conversation_id: Unique identifier for the conversation

        Returns:
            The stored context object, or None if not found
        """
        return self._storage.get(conversation_id)

    async def set(self, conversation_id: str, ctx: Any) -> None:
        """
        Store context for a given conversation ID.

        Args:
            conversation_id: Unique identifier for the conversation
            ctx: The context object to store
        """
        self._storage[conversation_id] = ctx
