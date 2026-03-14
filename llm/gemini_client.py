import json
import re
from typing import Any

import httpx

from core.config import Settings
from .llm_interface import LLMInterface


class GeminiClient(LLMInterface):
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def generate_text(self, prompt: str) -> str:
        if not self._settings.gemini_api_key:
            return f"[Gemini key missing] Placeholder response for prompt: {prompt[:120]}"

        endpoint = (
            f"{self._settings.gemini_base_url}/models/{self._settings.gemini_model}:generateContent"
            f"?key={self._settings.gemini_api_key}"
        )
        payload = {"contents": [{"parts": [{"text": prompt}]}]}

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(endpoint, json=payload)
            response.raise_for_status()
            body = response.json()

        candidates = body.get("candidates", [])
        if not candidates:
            return ""

        parts = candidates[0].get("content", {}).get("parts", [])
        return "\n".join(part.get("text", "") for part in parts if part.get("text"))

    async def plan_task(self, task: str) -> dict[str, Any]:
        prompt = (
            "You are an orchestration planner. Return ONLY strict JSON (no markdown, no comments). "
            "The JSON must match this schema exactly: "
            '{"steps":[{"id":"step_1","agent":"research_agent","task":"...","depends_on":[]}]}.'
            "Use ONLY these agent names: research_agent, analysis_agent, code_agent, report_agent. "
            "Always include non-empty string values for 'agent' and 'task'. "
            f"Task: {task}"
        )
        raw = await self.generate_text(prompt)

        parsed = self._extract_json(raw)
        if parsed and isinstance(parsed.get("steps"), list):
            return parsed

        return {
            "steps": [
                {"agent": "research_agent", "task": f"Research context for: {task}", "depends_on": []},
                {
                    "agent": "analysis_agent",
                    "task": "Analyze collected context and identify key findings",
                    "depends_on": ["step_1"],
                },
                {
                    "agent": "report_agent",
                    "task": "Create a concise final report",
                    "depends_on": ["step_2"],
                },
            ]
        }

    @staticmethod
    def _extract_json(raw: str) -> dict[str, Any] | None:
        if not raw:
            return None

        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if not match:
                return None
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                return None
