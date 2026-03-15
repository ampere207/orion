from llm.llm_interface import LLMInterface

from agents.agent_router import AgentRouter


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
    _valid_tools = {"web_search", "file_reader", "sql_query", "vector_search"}
    _tool_aliases = {
        "web": "web_search",
        "search": "web_search",
        "web search": "web_search",
        "file": "file_reader",
        "file reader": "file_reader",
        "sql": "sql_query",
        "sql query": "sql_query",
        "vector": "vector_search",
        "vector search": "vector_search",
    }

    def __init__(self, llm_client: LLMInterface, agent_router: AgentRouter) -> None:
        self._llm_client = llm_client
        self._agent_router = agent_router

    async def create_plan(self, task: str) -> dict:
        raw_plan = await self._llm_client.plan_task(task)
        return await self._normalize_plan(raw_plan, task)

    async def _normalize_plan(self, plan: dict, task: str) -> dict:
        steps = plan.get("steps", []) if isinstance(plan, dict) else []
        if not isinstance(steps, list) or not steps:
            return self._default_plan(task)

        normalized_steps: list[dict] = []
        previous_id: str | None = None

        for index, step in enumerate(steps, start=1):
            if not isinstance(step, dict):
                continue

            node_id = str(step.get("id") or f"step_{index}")
            step_task = step.get("task") if isinstance(step.get("task"), str) and step.get("task") else task
            agent = self._normalize_agent_name(step.get("agent"))

            if not agent:
                agent = await self._agent_router.route(step_task)

            tool = self._normalize_tool_name(step.get("tool")) or self._default_tool_for_agent(agent, step_task)

            depends_on = step.get("depends_on")
            if not isinstance(depends_on, list):
                depends_on = [previous_id] if previous_id else []

            normalized_step = {
                "id": node_id,
                "agent": agent,
                "task": step_task,
                "tool": tool,
                "depends_on": [str(dep) for dep in depends_on if dep],
            }
            normalized_steps.append(normalized_step)
            previous_id = node_id

        if not normalized_steps:
            return self._default_plan(task)

        return {"steps": normalized_steps}

    def _normalize_tool_name(self, tool: object) -> str | None:
        if not isinstance(tool, str) or not tool.strip():
            return None

        cleaned = tool.strip().lower().replace("-", "_")
        cleaned = " ".join(cleaned.split())
        if cleaned in self._valid_tools:
            return cleaned

        underscored = cleaned.replace(" ", "_")
        if underscored in self._valid_tools:
            return underscored

        alias_match = self._tool_aliases.get(cleaned) or self._tool_aliases.get(underscored)
        if alias_match in self._valid_tools:
            return alias_match

        return None

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
    def _default_tool_for_agent(agent: str, task: str) -> str | None:
        lowered = task.lower()
        if agent == "research_agent":
            return "web_search"
        if agent == "analysis_agent":
            return "vector_search"
        if agent == "code_agent":
            if any(keyword in lowered for keyword in ["sql", "database", "query"]):
                return "sql_query"
            if any(keyword in lowered for keyword in ["file", "read", "codebase", "source"]):
                return "file_reader"
        return None

    @staticmethod
    def _default_plan(task: str) -> dict:
        return {
            "steps": [
                {
                    "id": "step_1",
                    "agent": "research_agent",
                    "task": f"Research context for: {task}",
                    "tool": "web_search",
                    "depends_on": [],
                },
                {
                    "id": "step_2",
                    "agent": "analysis_agent",
                    "task": "Analyze collected context and identify key findings",
                    "tool": "vector_search",
                    "depends_on": ["step_1"],
                },
                {
                    "id": "step_3",
                    "agent": "report_agent",
                    "task": "Create a concise final report",
                    "tool": None,
                    "depends_on": ["step_2"],
                },
            ]
        }
