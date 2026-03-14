from pydantic import BaseModel


class WorkflowStatusResponse(BaseModel):
    workflow_id: str
    status: str
    details: dict
    input_task: str | None = None
    result: str | None = None
    error: str | None = None
