from typing import Any

from .base_tool import BaseTool


class WebSearchTool(BaseTool):
    name = "web_search"
    description = "Placeholder web search tool"

    async def execute(self, params: dict[str, Any]) -> dict[str, Any]:
        query = params.get("query", "")
        return {"tool": self.name, "results": [f"placeholder_result_for:{query}"]}
