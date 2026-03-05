import asyncio
from typing import Callable, Any, Optional, Union, get_type_hints, get_args, get_origin
from inspect import Parameter, signature
from pydantic import BaseModel

from .context import NodeContext
from .types import AgentResp


RouterFunc = Callable[[NodeContext], Union[str, list[str]]]


class Node:
    """
    Represents a node in the workflow graph.

    A node can be either a function node (executes logic) or a router node
    (determines which node to execute next).
    """

    def __init__(
        self,
        name: str,
        func: Callable,
        config: Optional[BaseModel] = None,
        output_node: Optional[Union[str, list[str], RouterFunc]] = None,
        run_in_worker: bool = False,
    ):
        """
        Initialize a Node.

        Args:
            name: Unique identifier for the node
            func: The node function (for function nodes)
            config: Optional Pydantic config model to inject into the function
            output_node: Next node(s) to execute, can be string, list, or router callable (for router nodes)
            run_in_worker: If True, execute this node in a background worker thread
        """
        self.name = name
        self.func = func
        self.config = config
        self.output_node = output_node
        self.run_in_worker = run_in_worker

        params = fn_params(func)
        assert len(params) <= 2
        if len(params) == 2:
            assert params[0].annotation is NodeContext, (
                "First arg of a node_fn should have `NodeContext` type hint"
            )
            assert params[1].annotation is type(config), (
                "Second argument of a node fn should have same type as config"
            )

    def is_function(self) -> bool:
        """Check if this node is a function node."""
        return self.func is not None


def fn_params(func: Callable):
    sig = signature(func)
    params: list[Parameter] = list(sig.parameters.values())
    return params
