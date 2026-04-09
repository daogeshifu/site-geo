from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from app.core.config import settings
from app.models.requests import LLMConfig

logger = logging.getLogger(__name__)


class LLMServiceError(Exception):
    """LLM 调用失败或响应无法解析时抛出"""


class OpenRouterProvider:
    """OpenRouter API 调用封装，支持 JSON 模式响应"""

    async def _post_json(self, url: str, headers: dict[str, str], payload: dict[str, Any]) -> dict[str, Any]:
        """发送 POST 请求，HTTP 错误时抛出 LLMServiceError"""
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
        """从 LLM 响应文本中提取 JSON 对象

        先尝试直接解析；若失败则定位第一个 '{' 到最后一个 '}' 之间的子串
        """
        stripped = text.strip()
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            # 兼容 LLM 在 JSON 前后添加说明性文字的情况
            start = stripped.find("{")
            end = stripped.rfind("}")
            if start >= 0 and end > start:
                return json.loads(stripped[start : end + 1])
        raise LLMServiceError("LLM response was not valid JSON.")

    async def generate_json(self, system_prompt: str, user_prompt: str, config: LLMConfig) -> dict[str, Any]:
        """调用 OpenRouter chat/completions 接口，返回解析后的 JSON 对象

        使用 response_format=json_object 强制模型输出 JSON
        """
        api_key = config.api_key or settings.openrouter_api_key
        if not api_key:
            raise LLMServiceError("OPENROUTER_API_KEY is not configured.")
        base_url = (config.base_url or settings.openrouter_base_url).rstrip("/")
        logger.info("OpenRouter request started", extra={"model": config.model or settings.default_openrouter_model})
        payload = {
            "model": config.model or settings.default_openrouter_model,
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
            "response_format": {"type": "json_object"},  # 强制 JSON 输出
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
    """LLM 服务入口：解析配置并委托给具体 Provider"""

    def __init__(self) -> None:
        self.provider = OpenRouterProvider()

    def resolve_config(self, llm_config: LLMConfig | None) -> LLMConfig:
        """解析 LLM 配置：若未指定 model，填充全局默认模型"""
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
        """生成 JSON 响应并返回 (结果, 实际使用的配置)

        在 user_prompt 头部添加严格 JSON 要求，避免模型输出 Markdown 包裹
        """
        config = self.resolve_config(llm_config)
        user_prompt = (
            "Return a strict JSON object only. No markdown, no prose outside JSON.\n\n"
            f"{json.dumps(user_payload, ensure_ascii=True, indent=2)}"
        )
        result = await self.provider.generate_json(system_prompt, user_prompt, config)
        return result, config
