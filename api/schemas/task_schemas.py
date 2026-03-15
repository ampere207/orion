from pydantic import BaseModel, Field


class TaskRequest(BaseModel):
    task: str = Field(..., min_length=1)


class WorkflowStepResponse(BaseModel):
    node_id: str
    agent: str | None = None
    task: str | None = None
    tool: str | None = None
    depends_on: list[str] = Field(default_factory=list)
    status: str
    attempts: int = 0
    output: dict | None = None
    error: str | None = None


class TaskResponse(BaseModel):
    workflow_id: str
    status: str
    result: str | None = None
    steps: list[WorkflowStepResponse] = Field(default_factory=list)
    node_outputs: dict = Field(default_factory=dict)
    timeline: list[dict] = Field(default_factory=list)
    shared_context: dict = Field(default_factory=dict)
