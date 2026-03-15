from llm.llm_interface import LLMInterface


class AgentRouter:
    def __init__(self, llm_client: LLMInterface | None = None) -> None:
        self._llm_client = llm_client

    async def route(self, task: str) -> str:
        lowered = task.lower()

        if any(keyword in lowered for keyword in ["research", "find", "search", "background", "source"]):
            return "research_agent"
        if any(keyword in lowered for keyword in ["analy", "insight", "trend", "diagnose"]):
            return "analysis_agent"
        if any(keyword in lowered for keyword in ["code", "python", "script", "implement", "debug"]):
            return "code_agent"
        if any(keyword in lowered for keyword in ["report", "summary", "summarize", "writeup"]):
            return "report_agent"

        return "analysis_agent"