from typing import Any

from .base_tool import BaseTool


class SQLTool(BaseTool):
    name = "sql_query"
    description = "Placeholder SQL query tool"

    async def execute(self, params: dict[str, Any]) -> dict[str, Any]:
        query = params.get("query", "")
        return {"tool": self.name, "query": query, "rows": []}
