from llm.llm_interface import LLMInterface


class PlannerAgent:
    _valid_agents = {
        "research_agent",
        "analysis_agent",
        "code_agent",
        "report_agent",
    }
    _agent_aliases = {
        "research": "research_agent",
        "researcher": "research_agent",
        "research agent": "research_agent",
        "analysis": "analysis_agent",
        "analyst": "analysis_agent",
        "analysis agent": "analysis_agent",
        "code": "code_agent",
        "coder": "code_agent",
        "code agent": "code_agent",
        "report": "report_agent",
        "reporter": "report_agent",
        "report agent": "report_agent",
        "summarizer": "report_agent",
        "summary": "report_agent",
    }

    def __init__(self, llm_client: LLMInterface) -> None:
        self._llm_client = llm_client

    async def create_plan(self, task: str) -> dict:
        raw_plan = await self._llm_client.plan_task(task)
        return self._normalize_plan(raw_plan, task)

    def _normalize_plan(self, plan: dict, task: str) -> dict:
        steps = plan.get("steps", []) if isinstance(plan, dict) else []
        if not isinstance(steps, list) or not steps:
            return self._default_plan(task)

        normalized_steps: list[dict] = []
        previous_id: str | None = None

        for index, step in enumerate(steps, start=1):
            if not isinstance(step, dict):
                continue

            node_id = str(step.get("id") or f"step_{index}")
            agent = self._normalize_agent_name(step.get("agent"))
            step_task = step.get("task") if isinstance(step.get("task"), str) and step.get("task") else task

            if not agent:
                agent = self._default_agent_for_index(index)

            depends_on = step.get("depends_on")
            if not isinstance(depends_on, list):
                depends_on = [previous_id] if previous_id else []

            normalized_step = {
                "id": node_id,
                "agent": agent,
                "task": step_task,
                "depends_on": [str(dep) for dep in depends_on if dep],
            }
            normalized_steps.append(normalized_step)
            previous_id = node_id

        if not normalized_steps:
            return self._default_plan(task)

        return {"steps": normalized_steps}

    def _normalize_agent_name(self, agent: object) -> str | None:
        if not isinstance(agent, str) or not agent.strip():
            return None

        cleaned = agent.strip().lower().replace("-", "_")
        cleaned = " ".join(cleaned.split())

        if cleaned in self._valid_agents:
            return cleaned

        underscored = cleaned.replace(" ", "_")
        if underscored in self._valid_agents:
            return underscored

        alias_match = self._agent_aliases.get(cleaned) or self._agent_aliases.get(underscored)
        if alias_match in self._valid_agents:
            return alias_match

        return None

    @staticmethod
    def _default_agent_for_index(index: int) -> str:
        if index <= 1:
            return "research_agent"
        if index == 2:
            return "analysis_agent"
        return "report_agent"

    @staticmethod
    def _default_plan(task: str) -> dict:
        return {
            "steps": [
                {"id": "step_1", "agent": "research_agent", "task": f"Research context for: {task}", "depends_on": []},
                {
                    "id": "step_2",
                    "agent": "analysis_agent",
                    "task": "Analyze collected context and identify key findings",
                    "depends_on": ["step_1"],
                },
                {
                    "id": "step_3",
                    "agent": "report_agent",
                    "task": "Create a concise final report",
                    "depends_on": ["step_2"],
                },
            ]
        }
