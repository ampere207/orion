from pathlib import Path
from typing import Any

from .base_tool import BaseTool


class FileTool(BaseTool):
    name = "file_reader"
    description = "Read local file content"

    async def execute(self, params: dict[str, Any]) -> dict[str, Any]:
        path = Path(str(params.get("path", "")))
        if not path.exists() or not path.is_file():
            return {"tool": self.name, "error": "file_not_found"}
        return {"tool": self.name, "content": path.read_text(encoding="utf-8")}
