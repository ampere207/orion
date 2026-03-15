import logging
import uuid

from fastapi import APIRouter, HTTPException, Request

from api.schemas.task_schemas import TaskRequest, TaskResponse
from core.dependencies import AppContainer

router = APIRouter(prefix="", tags=["task"])
logger = logging.getLogger(__name__)


@router.post("/task", response_model=TaskResponse)
async def create_task(payload: TaskRequest, request: Request) -> TaskResponse:
    container: AppContainer = request.app.state.container

    workflow_id = str(uuid.uuid4())
    container.state_tracker.create(workflow_id)

    try:
        plan = await container.planner_agent.create_plan(payload.task)
        graph = container.graph_builder.build(plan)
        execution = await container.executor.execute(
            workflow_id=workflow_id,
            user_task=payload.task,
            graph=graph,
            initial_context={"original_task": payload.task},
        )
        return TaskResponse(**execution)
    except Exception as exc:
        logger.exception("Workflow execution failed for workflow_id=%s", workflow_id)
        raise HTTPException(
            status_code=500,
            detail="Workflow execution failed. Please retry; if the issue persists, check provider quota and logs.",
        ) from exc
