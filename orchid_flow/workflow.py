import asyncio
from asyncio import Task
from concurrent.futures import ProcessPoolExecutor
import time
from typing import Optional, List, Dict, Any, Type, Union, Callable
from pydantic import BaseModel

from .types import AgentRequest, AgentResp, Turn
from .context import NodeContext
from .node import Node, fn_params
from .callbacks import Callback, CallbackEvent
from .stores.base import ContextStore
from .stores.memory import InMemoryContextStore


async def run_node_fn(fn, ctx, config):
    params = fn_params(fn)
    if len(params) == 1:
        assert config is None, "This node should not have a config"
        return await fn(ctx)
    elif len(params) == 2:
        return await fn(ctx, config)


def run_node_fn_sync(fn, ctx, config):
    worker_ctx = NodeContext.model_validate(ctx)
    params = fn_params(fn)
    if len(params) == 1:
        assert config is None, "This node should not have a config"
        result = fn(worker_ctx)
        return result, worker_ctx
    elif len(params) == 2:
        result = fn(worker_ctx, config)
        return result, worker_ctx


# def _on_field_change(ctx, name, value, old_value):
#     print("state {name} changed! ")


class Workflow:
    """
    Workflow orchestration engine for async LLM applications.

    Manages node execution, state persistence, and callback firing.
    """

    def __init__(
        self,
        name: str,
        initial_state: BaseModel,
        nodes: List[Node],
        entry_node: str,
        callbacks: Optional[List[Callback]] = None,
        n_worker: int = 4,
        node_timeout: Optional[float] = 20,
        context_store: Optional[ContextStore] = None,
    ):
        """
        Initialize a Workflow.

        Args:
            name: Unique workflow identifier
            initial_state: Initial state instance
            nodes: List of Node instances in the workflow
            callbacks: Optional list of Callback handlers
            n_worker: Number of worker processes for CPU-bound tasks
            node_timeout: Optional timeout for individual node execution (seconds)
            context_store: Store for persisting conversation context
        """
        assert nodes

        self.name = name
        self.initial_state = initial_state
        self.nodes = nodes
        self.entry_node = entry_node
        self.callbacks = callbacks or []
        self.n_worker = n_worker
        self.node_timeout = node_timeout
        self.context_store = context_store or InMemoryContextStore()

        self._node_index: Dict[str, Node] = {n.name: n for n in nodes}
        self._worker_pool: Optional[ProcessPoolExecutor] = None

    def _get_or_create_worker_pool(self) -> ProcessPoolExecutor:
        """Get or create the worker process pool."""

        # raise Exception("Worker implemetation needs more time for polishing. avoid it for now")
        if self._worker_pool is None:
            self._worker_pool = ProcessPoolExecutor(max_workers=self.n_worker)
        return self._worker_pool

    def _on_field_change(self, ctx, name, old_value, value):
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        loop.create_task(
            self._fire_callbacks(
                "set_state",
                ctx,
                data={
                    "field_name": name,
                    "old_value": old_value,
                    "value": value,
                },
            )
        )

    async def _fire_callbacks(
        self,
        event_name: str,
        ctx: NodeContext,
        node_name: str | None = None,
        error: Optional[Exception] = None,
        data: Any = None,
    ) -> None:
        """
        Fire all registered callbacks for a given event.

        Args:
            event_name: Name of the event (e.g., 'node_start', 'node_end', 'node_err')
            ctx: Current node context
            node_name: Name of the node that triggered the event
            error: Optional exception if the event is an error
            data: Optional additional data
        """
        if node_name is None:
            node_name = ctx.node_name
        event = CallbackEvent(
            event_name=event_name, node_name=node_name, error=error, data=data
        )
        ctx.add_log("info", f"Event '{event_name}' at '{node_name}'")
        for callback in self.callbacks:
            if callback.on == event_name:
                try:
                    await callback.fire(ctx, event)
                except Exception:
                    ctx.add_log(
                        "error",
                        f"Exception while executing callback '{callback.fn.__name__}' on {event_name} Event",
                    )

    async def _execute_node(self, node: Node, ctx: NodeContext) -> Optional[AgentResp]:
        """
        Execute a single node with worker offloading if needed.

        Args:
            node: The Node to execute
            ctx: Current node context

        Returns:
            AgentResp from the node, or None
        """
        t0 = time.time()
        ctx.node_name = node.name
        await self._fire_callbacks("node_start", ctx, node.name)
        try:
            if node.run_in_worker:
                loop = asyncio.get_event_loop()
                pool = self._get_or_create_worker_pool()
                ctx_before = ctx.model_dump()
                result, new_ctx = await loop.run_in_executor(
                    pool, run_node_fn_sync, node.func, ctx_before, node.config
                )

                # update the ctx.state of main process based on new_ctx
                for k, v in new_ctx.state.model_dump().items():
                    setattr(ctx.state, k, v)
                n_log = len(ctx_before["logs"])
                # update the ctx.logs of main process based on new_ctx
                for log in new_ctx.logs[n_log:]:
                    ctx.logs.append(log)
            else:
                result = await run_node_fn(node.func, ctx, node.config)

            await self._fire_callbacks(
                "node_end",
                ctx,
                node.name,
                data={
                    "node_result": result,
                    "elapsed_ms": 1000 * (time.time() - t0),
                },
            )

            return result

        except Exception as e:
            await self._fire_callbacks("node_err", ctx, node.name, error=e)
            raise

    async def _get_next_nodes(self, node: Node, ctx: NodeContext) -> List[Node]:
        """
        Determine the next node(s) to execute based on node configuration and result.

        Args:
            node: The current node
            ctx: Current node context

        Returns:
            List of next Node(s) to execute
        """

        output_node = node.output_node
        if output_node is None:
            return []

        if isinstance(output_node, str):
            next_node = self._node_index[output_node]
            return [next_node]

        if isinstance(output_node, list):
            next_nodes = []
            for name in output_node:
                next_nodes.append(self._node_index[name])
            return next_nodes

        if callable(output_node):
            if asyncio.iscoroutinefunction(output_node):
                next_names = await output_node(ctx)
            else:
                next_names = output_node(ctx)
            if isinstance(next_names, str):
                next_node = self._node_index[next_names]
                return [next_node]
            elif isinstance(next_names, list):
                next_nodes = []
                for name in next_names:
                    next_nodes.append(self._node_index[name])
                return next_nodes
            else:
                raise Exception("bad return type in router function")

    async def _build_context(
        self, request: AgentRequest
    ) -> tuple[NodeContext, list[Node]]:
        """
        Build or retrieve NodeContext from the store.

        Args:
            request: Incoming AgentRequest

        Returns:
            A tuple of (NodeContext instance, list of start nodes) ready for execution
        """
        stored = await self.context_store.get(request.conversation_id)

        if stored is not None:
            last_node = stored["last_node"]
            if isinstance(stored, dict):
                ctx = NodeContext(**stored)
            else:
                ctx = stored
            ctx.user_input = request.user_input
            ctx.other_data = request.other_data
            start_nodes = await self._get_next_nodes(self._node_index[last_node], ctx)
        else:
            start_nodes = [self._node_index[self.entry_node]]

            ctx = NodeContext(
                conversation_id=request.conversation_id,
                node_name="",
                node_counter={},
                conversation_history=[],
                other_data=request.other_data,
                user_input=request.user_input,
                logs=[],
            )
            ctx.state = self.initial_state

        ctx.state._parent_ctx = ctx
        ctx.state._on_field_change = self._on_field_change
        return ctx, start_nodes

    async def _save_context(self, ctx: NodeContext, last_node: str) -> None:
        """
        Persist the context to the store.

        Args:
            ctx: NodeContext to persist
            last_node: Name of the last executed node
        """
        data = ctx.model_dump()
        data["last_node"] = last_node
        await self.context_store.set(ctx.conversation_id, data)

    async def run(self, request: AgentRequest) -> AgentResp:
        """
        run the workflow to reach a turn.

        Args:
            request: The AgentRequest containing conversation_id and user_input

        Returns:
            AgentResp from the last executed node
        """
        ctx, start_nodes = await self._build_context(request)

        ctx.conversation_history.append(Turn(role="user", obj=request.user_input))
        tasks: set[Task[AgentResp | None]] = set()
        node_map: dict[Task, Node] = {}

        def add_node_task(node):
            ctx.node_counter[node.name] = ctx.node_counter.get(node.name, 0) + 1
            task = asyncio.create_task(self._execute_node(node, ctx))
            node_map[task] = node
            tasks.add(task)

        for n in start_nodes:
            add_node_task(n)
        result = None
        result_node = None
        while tasks:
            done, tasks = await asyncio.wait(
                tasks, timeout=self.node_timeout, return_when=asyncio.FIRST_COMPLETED
            )
            if len(done) == 0:
                raise TimeoutError(f"Node timed out after {self.node_timeout}s")
            for task in done:
                node = node_map[task]
                res = task.result()
                if res:
                    assert result is None, (
                        "Only one of concurent nodes should have a result"
                    )
                    result = res
                    result_node = node
                else:
                    # run the output nodes
                    next_nodes = await self._get_next_nodes(node, ctx)
                    for node in next_nodes:
                        add_node_task(node)

        assert result is not None
        assert result_node is not None
        ctx.conversation_history.append(Turn(role="bot", obj=result.ui_output))

        await self._save_context(ctx, result_node.name)

        return result

    def shutdown(self) -> None:
        """Shutdown the worker pool if it exists."""
        if self._worker_pool is not None:
            self._worker_pool.shutdown(wait=True)
            self._worker_pool = None
