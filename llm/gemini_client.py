import asyncio
import json
import logging
import re
from typing import Any

import httpx

from core.config import Settings
from .llm_interface import LLMInterface


logger = logging.getLogger(__name__)


class GeminiClient(LLMInterface):
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def generate_text(self, prompt: str) -> str:
        key_chain = [self._settings.gemini_api_key]
        if self._settings.gemini_api_key_fallback:
            key_chain.append(self._settings.gemini_api_key_fallback)
        key_chain = [key for key in key_chain if key]
        key_chain = list(dict.fromkeys(key_chain))

        if not key_chain:
            return f"[Gemini key missing] Placeholder response for prompt: {prompt[:120]}"

        payload = {"contents": [{"parts": [{"text": prompt}]}]}

        for key_index, api_key in enumerate(key_chain, start=1):
            endpoint = (
                f"{self._settings.gemini_base_url}/models/{self._settings.gemini_model}:generateContent"
                f"?key={api_key}"
            )
            body = await self._request_with_retries(endpoint=endpoint, payload=payload)
            if body is not None:
                return self._extract_text_or_fallback(body, prompt)

            logger.warning("Gemini key %s/%s exhausted or unavailable.", key_index, len(key_chain))

        return self._fallback_response("all_keys_exhausted", prompt)

    async def _request_with_retries(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        max_attempts = 3
        base_delay_seconds = 1.0

        for attempt in range(1, max_attempts + 1):
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    response = await client.post(endpoint, json=payload)
                    response.raise_for_status()
                    return response.json()
            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code
                is_retryable = status_code in {429, 500, 502, 503, 504}
                error_hint = self._extract_error_hint(exc.response)
                if is_retryable and attempt < max_attempts:
                    logger.warning(
                        "Gemini HTTP %s attempt %s/%s for active key; retrying. reason=%s",
                        status_code,
                        attempt,
                        max_attempts,
                        error_hint,
                    )
                    await asyncio.sleep(base_delay_seconds * (2 ** (attempt - 1)))
                    continue

                if status_code == 429:
                    logger.warning(
                        "Gemini rate limited after %s attempts for active key. reason=%s",
                        attempt,
                        error_hint,
                    )
                    return None

                logger.warning(
                    "Gemini returned HTTP %s after %s attempts for active key. reason=%s",
                    status_code,
                    attempt,
                    error_hint,
                )
                return None
            except httpx.HTTPError:
                if attempt < max_attempts:
                    await asyncio.sleep(base_delay_seconds * (2 ** (attempt - 1)))
                    continue
                logger.warning("Gemini network error after %s attempts for active key.", attempt)
                return None

        return None

    def _extract_text_or_fallback(self, body: dict[str, Any], prompt: str) -> str:
        candidates = body.get("candidates", [])
        if not candidates:
            return self._fallback_response("empty_candidates", prompt)

        parts = candidates[0].get("content", {}).get("parts", [])
        text = "\n".join(part.get("text", "") for part in parts if part.get("text"))
        if not text:
            return self._fallback_response("empty_text", prompt)
        return text

    @staticmethod
    def _extract_error_hint(response: httpx.Response) -> str:
        try:
            payload = response.json()
            error = payload.get("error", {}) if isinstance(payload, dict) else {}
            status = error.get("status")
            message = error.get("message")
            details = error.get("details")

            detail_reason = None
            if isinstance(details, list):
                for item in details:
                    if isinstance(item, dict) and item.get("reason"):
                        detail_reason = item.get("reason")
                        break

            parts = [str(part) for part in [status, detail_reason, message] if part]
            if parts:
                return " | ".join(parts)[:300]
        except Exception:
            pass

        text = response.text or ""
        return text[:300] if text else "unknown"

    @staticmethod
    def _fallback_response(reason: str, prompt: str) -> str:
        return f"[Gemini fallback:{reason}] Placeholder response for prompt: {prompt[:120]}"

    async def plan_task(self, task: str) -> dict[str, Any]:
        prompt = (
            "You are an orchestration planner. Return ONLY strict JSON (no markdown, no comments). "
            "The JSON must match this schema exactly: "
            '{"steps":[{"id":"step_1","agent":"research_agent","task":"...","tool":"web_search","depends_on":[]}]}.'
            "Use ONLY these agent names: research_agent, analysis_agent, code_agent, report_agent. "
            "Use ONLY these tools when needed: web_search, file_reader, sql_query, vector_search. "
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
