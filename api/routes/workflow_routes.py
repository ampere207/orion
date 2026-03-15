from fastapi import APIRouter, HTTPException, Request

from api.schemas.workflow_schemas import WorkflowStatusResponse
from core.dependencies import AppContainer

router = APIRouter(prefix="", tags=["workflow"])


@router.get("/workflow/{workflow_id}", response_model=WorkflowStatusResponse)
async def get_workflow_status(workflow_id: str, request: Request) -> WorkflowStatusResponse:
    container: AppContainer = request.app.state.container

    in_memory_status = container.state_tracker.get(workflow_id)
    history = await container.long_term_memory.get_workflow_history(workflow_id)
    progress = await container.context_manager.get_progress(workflow_id)

    if not in_memory_status and not history:
        raise HTTPException(status_code=404, detail="Workflow not found")

    status_value = in_memory_status.state.value if in_memory_status else history["status"]
    details = in_memory_status.details if in_memory_status else {}
    steps = list(in_memory_status.steps.values()) if in_memory_status else history.get("steps", [])
    timeline = in_memory_status.timeline if in_memory_status and in_memory_status.timeline else progress
    execution_history = history.get("agent_tasks", []) + history.get("task_results", []) if history else []

    return WorkflowStatusResponse(
        workflow_id=workflow_id,
        status=status_value,
        details=details,
        input_task=history.get("input_task") if history else None,
        result=history.get("result") if history else None,
        error=history.get("error") if history else None,
        steps=steps,
        execution_timeline=timeline,
        execution_history=execution_history,
    )
