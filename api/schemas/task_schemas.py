from pydantic import BaseModel, Field


class TaskRequest(BaseModel):
    task: str = Field(..., min_length=1)


class TaskResponse(BaseModel):
    workflow_id: str
    status: str
    result: str
    node_outputs: dict
