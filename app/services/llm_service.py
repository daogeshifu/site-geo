from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from app.core.config import settings
from app.models.requests import LLMConfig

logger = logging.getLogger(__name__)


class LLMServiceError(Exception):
    """Raised when an LLM provider call cannot be completed or parsed."""


class OpenRouterProvider:
    async def _post_json(self, url: str, headers: dict[str, str], payload: dict[str, Any]) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=httpx.Timeout(settings.llm_request_timeout_seconds)) as client:
            try:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as exc:
                body = exc.response.text[:500] if exc.response is not None else ""
                raise LLMServiceError(f"OpenRouter HTTP {exc.response.status_code}: {body}") from exc
            except httpx.HTTPError as exc:
                raise LLMServiceError(f"OpenRouter request failed: {exc}") from exc

    def _extract_json_object(self, text: str) -> dict[str, Any]:
        stripped = text.strip()
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            start = stripped.find("{")
            end = stripped.rfind("}")
            if start >= 0 and end > start:
                return json.loads(stripped[start : end + 1])
        raise LLMServiceError("LLM response was not valid JSON.")

    async def generate_json(self, system_prompt: str, user_prompt: str, config: LLMConfig) -> dict[str, Any]:
        api_key = config.api_key or settings.openrouter_api_key
        if not api_key:
            raise LLMServiceError("OPENROUTER_API_KEY is not configured.")
        base_url = (config.base_url or settings.openrouter_base_url).rstrip("/")
        logger.info("OpenRouter request started", extra={"model": config.model or settings.default_openrouter_model})
        payload = {
            "model": config.model or settings.default_openrouter_model,
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        response = await self._post_json(
            f"{base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": settings.openrouter_site_url,
                "X-Title": settings.openrouter_app_name,
            },
            payload=payload,
        )
        content = response["choices"][0]["message"]["content"]
        logger.info("OpenRouter request completed", extra={"model": config.model or settings.default_openrouter_model})
        return self._extract_json_object(content)


class LLMService:
    def __init__(self) -> None:
        self.provider = OpenRouterProvider()

    def resolve_config(self, llm_config: LLMConfig | None) -> LLMConfig:
        config = llm_config or LLMConfig()
        if config.model:
            return config
        return config.model_copy(update={"model": settings.default_openrouter_model})

    async def generate_json(
        self,
        system_prompt: str,
        user_payload: dict[str, Any],
        llm_config: LLMConfig | None = None,
    ) -> tuple[dict[str, Any], LLMConfig]:
        config = self.resolve_config(llm_config)
        user_prompt = (
            "Return a strict JSON object only. No markdown, no prose outside JSON.\n\n"
            f"{json.dumps(user_payload, ensure_ascii=True, indent=2)}"
        )
        result = await self.provider.generate_json(system_prompt, user_prompt, config)
        return result, config
