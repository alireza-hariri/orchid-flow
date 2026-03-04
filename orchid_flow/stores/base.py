from abc import ABC, abstractmethod
from typing import Any


class ContextStore(ABC):
    """
    Abstract base class for storing conversation context.
    Implementations can use in-memory storage, Redis, databases, etc.
    """

    @abstractmethod
    async def get(self, conversation_id: str) -> Any:
        """
        Retrieve context for a given conversation ID.

        Args:
            conversation_id: Unique identifier for the conversation

        Returns:
            The stored context object, or None if not found
        """
        pass

    @abstractmethod
    async def set(self, conversation_id: str, ctx: Any) -> None:
        """
        Store context for a given conversation ID.

        Args:
            conversation_id: Unique identifier for the conversation
            ctx: The context object to store
        """
        pass
