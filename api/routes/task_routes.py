import logging
import uuid
import asyncio

from fastapi import APIRouter, HTTPException, Request

from api.schemas.task_schemas import TaskRequest, TaskResponse
from core.dependencies import AppContainer
from workflow.workflow_state import WorkflowState

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
        diagram_path = container.visualizer.render(workflow_id, graph)

        planned_steps = []
        for node_id in graph.nodes:
            node_data = graph.nodes[node_id]
            planned_steps.append(
                {
                    "node_id": node_id,
                    "agent": node_data.get("agent"),
                    "task": node_data.get("task"),
                    "tool": node_data.get("tool"),
                    "depends_on": list(graph.predecessors(node_id)),
                    "status": WorkflowState.PENDING.value,
                    "attempts": 0,
                }
            )

        container.state_tracker.update(
            workflow_id,
            WorkflowState.RUNNING,
            details={"diagram_path": diagram_path},
        )

        execution_task = asyncio.create_task(
            container.executor.execute(
                workflow_id=workflow_id,
                user_task=payload.task,
                graph=graph,
                initial_context={"original_task": payload.task},
            )
        )
        container.background_tasks[workflow_id] = execution_task
        execution_task.add_done_callback(lambda _task: container.background_tasks.pop(workflow_id, None))

        return TaskResponse(
            workflow_id=workflow_id,
            status=WorkflowState.RUNNING.value,
            steps=planned_steps,
        )
    except Exception as exc:
        logger.exception("Workflow execution failed for workflow_id=%s", workflow_id)
        raise HTTPException(
            status_code=500,
            detail="Workflow execution failed. Please retry; if the issue persists, check provider quota and logs.",
        ) from exc
