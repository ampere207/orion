from dataclasses import dataclass
from enum import Enum
from typing import Any


class WorkflowState(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass
class WorkflowStatus:
    workflow_id: str
    state: WorkflowState
    details: dict[str, Any]
    steps: dict[str, dict[str, Any]]
    timeline: list[dict[str, Any]]


class WorkflowStateTracker:
    def __init__(self) -> None:
        self._statuses: dict[str, WorkflowStatus] = {}

    def create(self, workflow_id: str) -> None:
        self._statuses[workflow_id] = WorkflowStatus(
            workflow_id=workflow_id,
            state=WorkflowState.PENDING,
            details={},
            steps={},
            timeline=[],
        )

    def update(self, workflow_id: str, state: WorkflowState, details: dict[str, Any] | None = None) -> None:
        current = self._statuses.get(workflow_id)
        if not current:
            current = WorkflowStatus(workflow_id=workflow_id, state=state, details={})
            self._statuses[workflow_id] = current
        current.state = state
        if details:
            current.details = {**current.details, **details}

    def get(self, workflow_id: str) -> WorkflowStatus | None:
        return self._statuses.get(workflow_id)

    def record_step(self, workflow_id: str, node_id: str, data: dict[str, Any]) -> None:
        current = self._statuses.get(workflow_id)
        if not current:
            self.create(workflow_id)
            current = self._statuses[workflow_id]
        existing = current.steps.get(node_id, {})
        current.steps[node_id] = {**existing, **data}

    def append_timeline(self, workflow_id: str, event: dict[str, Any]) -> None:
        current = self._statuses.get(workflow_id)
        if not current:
            self.create(workflow_id)
            current = self._statuses[workflow_id]
        current.timeline.append(event)
