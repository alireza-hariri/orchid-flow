from typing import List
from fastapi import FastAPI

from ..types import AgentRequest, AgentResp
from ..workflow import Workflow


def make_fastapi_app(workflows: List[Workflow], title: str = "Agents API") -> FastAPI:
    """
    Create a FastAPI application with workflow endpoints.

    Args:
        workflows: List of Workflow instances to register
        title: Title for the FastAPI app

    Returns:
        Configured FastAPI application
    """
    app = FastAPI(title=title)
    workflow_index: dict[str, Workflow] = {w.name: w for w in workflows}

    @app.post("/agent_conversation/{workflow}")
    async def agent_conversation(workflow: str, request: AgentRequest) -> AgentResp:
        """
        Process a conversation turn for a workflow.

        Args:
            workflow: Name of the workflow from the URL path
            request: AgentRequest containing conversation_id and user_input

        Returns:
            AgentResp from the workflow execution
        """
        workflow = workflow_index.get(workflow)

        return await workflow.run(request)

    return app
