from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from app.core.config import settings
from app.core.exceptions import AppError
from app.services.crawlers.catalog import BY_ID, Agent
from app.services.crawlers.http import FetchResult, fetch_public
from app.services.google_crawler.common import inspect_html, request_http_metadata
from app.services.google_crawler.google_render import GoogleRenderService
from app.utils.public_url import normalize_public_url
from app.utils.robots_parser import RobotsRules, parse_robots_text, robot_path_rule
from app.utils.url_utils import get_site_root


logger = logging.getLogger(__name__)


class RobotsPolicy:
    """Fetch robots once per origin, with the selected HTTP identity, for this test only."""

    def __init__(self, client: httpx.AsyncClient, agent: Agent) -> None:
        self.client = client
        self.agent = agent
        self.documents: dict[str, asyncio.Task[tuple[FetchResult, RobotsRules]]] = {}

    async def _load(self, url: str) -> tuple[FetchResult, RobotsRules]:
        response = await fetch_public(url, client=self.client, headers=self.agent.headers(robots=True))
        rules, _ = parse_robots_text(response.text) if 200 <= response.status_code < 300 else ({}, [])
        return response, rules

    async def inspect(self, url: str) -> dict[str, Any]:
        robots_url = get_site_root(url) + "/robots.txt"
        if robots_url not in self.documents:
            self.documents[robots_url] = asyncio.create_task(self._load(robots_url))
        result = {
            "url": robots_url,
            "target": url,
            "token": self.agent.token,
            "allowed": None,
            "status_code": None,
        }
        try:
            response, rules = await self.documents[robots_url]
        except (AppError, httpx.HTTPError) as exc:
            return {**result, "detail": f"无法读取 robots.txt（{exc}）"}
        result.update(status_code=response.status_code, request_headers=response.request_headers)
        missing = response.status_code in {404, 410}
        if not missing and not 200 <= response.status_code < 300:
            return {**result, "detail": f"robots.txt 返回 HTTP {response.status_code}，抓取规则待确认。"}
        rule = robot_path_rule(rules, self.agent.token, url)
        detail = (
            "没有 robots.txt 路径限制。"
            if missing
            else (
                f"匹配 {rule.matched_user_agent} 规则，{'允许' if rule.allowed else '禁止'}抓取当前路径。"
            )
        )
        result.update(allowed=rule.allowed, matched=rule.matched_user_agent, detail=detail)
        if self.agent.usage_token:
            usage = robot_path_rule(rules, self.agent.usage_token, url)
            result["content_use"] = {
                "token": self.agent.usage_token,
                "allowed": usage.allowed,
                "matched": usage.matched_user_agent,
            }
        return result

    async def allowed(self, url: str) -> bool:
        return (await self.inspect(url))["allowed"] is True


class _RobotsStop(Exception):
    pass


async def _spider(url: str, agent: Agent, client: httpx.AsyncClient, policy: RobotsPolicy) -> dict:
    robots: dict = {}

    async def check_path(target: str) -> None:
        nonlocal robots
        robots = await policy.inspect(target)
        if robots["allowed"] is not True:
            raise _RobotsStop

    try:
        response = await fetch_public(
            url, client=client, headers=agent.headers(), before_request=check_path
        )
    except _RobotsStop:
        return {"status": "skipped", "robots": robots, "reason": robots["detail"]}
    except httpx.TimeoutException:
        return {"status": "failed", "robots": robots, "reason": "目标页面响应超时。"}
    except httpx.RequestError as exc:
        return {"status": "failed", "robots": robots, "reason": f"无法获取目标页面（{exc}）。"}

    status = response.status_code
    content_type = response.headers.get("content-type", "")
    mime = content_type.partition(";")[0].strip().lower()
    is_html = mime in {"text/html", "application/xhtml+xml"}
    textual = is_html or mime.startswith("text/") or mime.endswith(("json", "xml"))
    request = {
        "requested_url": response.requested_url,
        "final_url": response.final_url,
        "status_code": status,
        "headers": response.request_headers,
        **request_http_metadata(
            status_code=status, headers=response.headers, redirect_chain=response.redirect_chain
        ),
        "redirect_chain": response.redirect_chain,
        "response_time_ms": response.response_time_ms,
        "content_type": content_type,
        "size_bytes": response.size_bytes,
        "response_headers": {
            key: response.headers[key]
            for key in (
                "content-type",
                "content-length",
                "content-encoding",
                "content-range",
                "x-robots-tag",
                "retry-after",
            )
            if key in response.headers
        },
    }
    result = {
        "status": "passed" if 200 <= status < 300 else "failed",
        "request": request,
        "robots": robots,
        "is_html": is_html,
        "raw_html": response.text if textual else None,
        "truncated": response.truncated,
    }
    if is_html:
        content = inspect_html(response.text, response.final_url, agent_token=agent.token)
        content.pop("visible_text")
        result["content"] = content
    return result


async def simulate(url: str, platform_id: str, agent_token: str | None = None) -> dict:
    platform = BY_ID.get(platform_id)
    if platform is None:
        raise AppError(422, "未知的爬虫平台")
    agent = platform.agent(agent_token)
    if agent is None:
        raise AppError(422, "该平台不支持所选爬虫标识")
    normalized = await normalize_public_url(url)
    timeout = httpx.Timeout(
        settings.request_timeout_seconds, connect=min(10, settings.request_timeout_seconds)
    )
    async with httpx.AsyncClient(timeout=timeout) as client:
        policy = RobotsPolicy(client, agent)
        spider = await _spider(normalized, agent, client, policy)
        result = {
            "platform": platform.id,
            "agent": agent.token,
            "identity": platform.identity,
            "url": normalized,
            "spider": spider,
        }
        if platform.render is None:
            return result

        request = spider.get("request", {})
        if spider["status"] != "passed" or request.get("status_code") != 200 or not spider.get("is_html"):
            result["render"] = {
                "status": "skipped",
                "reason": "渲染需要抓取阶段取得 HTTP 200 的 HTML 响应。",
            }
            return result
        render_agent = platform.render
        render_policy = policy if render_agent == agent else RobotsPolicy(client, render_agent)
        target = request["final_url"]
        rules = await render_policy.inspect(target)
        if rules["allowed"] is not True:
            result["render"] = {"status": "skipped", "reason": rules["detail"], "robots": rules}
            return result
        try:
            render = await GoogleRenderService().capture(
                target,
                initial_html=spider["raw_html"],
                user_agent=render_agent.user_agent,
                agent_token=render_agent.token,
                mobile=render_agent.mobile,
                allow_resource=render_policy.allowed,
            )
        except Exception:
            # A browser process can exit between navigation and DOM serialization.
            # The spider evidence is already complete and remains independently usable.
            logger.exception("Chromium capture failed for platform %s", platform.id)
            render = {"status": "failed", "reason": "渲染过程已中断，可查看上方的原始抓取结果。"}
        result["render"] = {**render, "robots": rules}
        return result
