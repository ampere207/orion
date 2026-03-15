from pydantic import BaseModel, Field

from api.schemas.task_schemas import WorkflowStepResponse


class WorkflowStatusResponse(BaseModel):
    workflow_id: str
    status: str
    details: dict
    input_task: str | None = None
    result: str | None = None
    error: str | None = None
    steps: list[WorkflowStepResponse] = Field(default_factory=list)
    execution_timeline: list[dict] = Field(default_factory=list)
