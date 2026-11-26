from __future__ import annotations

from collections import defaultdict
import re
from urllib.parse import quote, urlparse

import httpx

from app.models.discovery import RobotsResult, RobotsUserAgentRule
from app.utils.fetcher import fetch_url
from app.utils.url_utils import get_site_root

# 需要检查访问权限的 AI 爬虫列表
AI_CRAWLERS = [
    "GPTBot",          # OpenAI 训练爬虫
    "OAI-SearchBot",   # OpenAI 搜索爬虫
    "ChatGPT-User",    # ChatGPT 实时搜索
    "ClaudeBot",       # Anthropic Claude 训练爬虫
    "Claude-SearchBot",  # Anthropic Claude 搜索爬虫
    "Claude-User",     # Anthropic Claude 实时读取
    "PerplexityBot",   # Perplexity AI 搜索爬虫
    "Perplexity-User", # Perplexity 实时读取
    "Google-Extended", # Google Gemini/AI Overviews 内容使用控制
    "Baiduspider",     # 百度搜索爬虫
    "Bytespider",      # 头条/豆包检索关联爬虫
    "Kimi-SearchBot",  # Kimi 搜索索引爬虫
]

# Search/retrieval policies are evaluated separately from training permission.
GLOBAL_SEARCH_CRAWLERS = [
    "Googlebot",
    "bingbot",
    "OAI-SearchBot",
    "ChatGPT-User",
    "PerplexityBot",
    "Perplexity-User",
    "Claude-SearchBot",
    "Claude-User",
]
DOMESTIC_SEARCH_CRAWLERS = [
    "Baiduspider",
    "Bytespider",
    "Kimi-SearchBot",
]
TRAINING_CRAWLERS = [
    "GPTBot",
    "ClaudeBot",
    "CCBot",
    "DeepseekBot",
]
SEARCH_CRAWLERS = list(GLOBAL_SEARCH_CRAWLERS)


def search_crawlers_for_site(url: str, locale: str | None = None) -> list[str]:
    """Return retrieval crawlers applicable to the target site's locale/region."""
    crawlers = list(GLOBAL_SEARCH_CRAWLERS)
    host = (urlparse(url).netloc or "").lower()
    lang = (locale or "").strip().lower()
    if lang.startswith("zh") or host.endswith(".cn"):
        crawlers.extend(DOMESTIC_SEARCH_CRAWLERS)
    return crawlers


def parse_content_signals(raw_value: str) -> dict[str, str]:
    """Parse Content-Signal directives such as 'ai-train=no, search=yes, ai-input=yes'."""
    signals: dict[str, str] = {}
    if not raw_value:
        return signals
    for part in re.split(r"[,;]", raw_value):
        token = part.strip()
        if "=" not in token:
            continue
        key, val = token.split("=", 1)
        key = key.strip().lower()
        val = val.strip().lower()
        if key in {"ai-train", "search", "ai-input", "train", "input"} and val:
            signals[key] = val
    return signals


def parse_robots_extras(text: str) -> tuple[dict[str, str], list[str]]:
    """Extract Content-Signal and LLM-Policy declarations from robots.txt."""
    content_signals: dict[str, str] = {}
    llm_policy_urls: list[str] = []
    for raw_line in (text or "").splitlines():
        cleaned = raw_line.strip().lstrip("#").strip()
        if ":" not in cleaned:
            continue
        key, value = cleaned.split(":", 1)
        directive = key.strip().lower()
        content = value.strip()
        if directive in {"content-signal", "content-signals"}:
            content_signals.update(parse_content_signals(content))
        elif directive in {"llm-policy", "ai-policy"} and content:
            if content not in llm_policy_urls:
                llm_policy_urls.append(content)
    return content_signals, llm_policy_urls


def _normalize_robot_path(value: str) -> str:
    unreserved = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-._~"
    value = re.sub(r"%([0-9a-fA-F]{2})", lambda match: chr(int(match[1], 16))
                   if chr(int(match[1], 16)) in unreserved else match[0].upper(), value)
    return quote(value, safe="/%*$?=&;:+,@!()-._~")


def _match_rule(target_path: str, rules: dict[str, list[str]]) -> bool:
    """判断 target_path 是否被允许访问

    使用最长前缀匹配规则（robots.txt 标准）：
    - Allow 和 Disallow 中最长的匹配规则优先
    - Allow 胜出时返回 True，Disallow 胜出时返回 False
    - 无匹配规则时返回 True（默认允许）
    """
    target_path = _normalize_robot_path(target_path)

    def matches(paths):
        found = []
        for raw in paths:
            if not raw:
                continue  # Empty Disallow means no restriction.
            path = _normalize_robot_path(raw)
            anchored = path.endswith("$")
            body = path[:-1] if anchored else path
            pattern = "^" + re.escape(body).replace(r"\*", ".*") + ("$" if anchored else "")
            if re.search(pattern, target_path):
                found.append(len(body.replace("*", "").encode("utf-8")))
        return found

    allow_matches = matches(rules.get("allow", []))
    disallow_matches = matches(rules.get("disallow", []))

    if not allow_matches and not disallow_matches:
        return True  # 无规则，默认允许

    longest_allow = max(allow_matches, default=-1)
    longest_disallow = max(disallow_matches, default=-1)
    return longest_allow >= longest_disallow


RobotsRules = dict[str, dict[str, list[str]]]


def parse_robots_text(text: str) -> tuple[RobotsRules, list[str]]:
    """解析 robots.txt 文本，返回 (规则字典, Sitemap URL 列表)

    规则字典格式：{user_agent: {"allow": [...], "disallow": [...]}}
    处理逻辑：
    - User-agent 块在遇到新 User-agent 或遇到指令后重置
    - 注释行（# 开头）和空行跳过
    - Sitemap 指令单独收集
    """
    rules: dict[str, dict[str, list[str]]] = defaultdict(lambda: {"allow": [], "disallow": []})
    sitemaps: list[str] = []
    current_agents: list[str] = []
    seen_directive = False  # 是否已经遇到过 Allow/Disallow 指令（用于 User-agent 块切换）

    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].strip()  # 去除注释
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        directive = key.strip().lower()
        content = value.strip()

        if directive == "user-agent":
            # 遇到新的 User-agent 行，且之前已有指令，则开始新块
            if seen_directive:
                current_agents = []
                seen_directive = False
            current_agents.append(content.lower() or "*")
            rules[content.lower() or "*"]  # Preserve explicitly empty groups.
            continue

        if directive == "sitemap":
            sitemaps.append(content)
            continue

        if directive in {"allow", "disallow"}:
            if not current_agents:
                current_agents = ["*"]  # 无 User-agent 声明时默认 *
            seen_directive = True
            for agent in current_agents:
                rules[agent][directive].append(content)

    return dict(rules), sitemaps


def _resolve_agent_rule(agent_name: str, parsed_rules: dict[str, dict[str, list[str]]], target_path: str = "/") -> RobotsUserAgentRule:
    """解析特定爬虫的访问规则

    优先使用精确匹配的规则，无匹配时回退到 * 通配符规则
    """
    lowered = agent_name.lower()
    candidates = [name for name in parsed_rules if name != "*" and name in lowered]
    matched_agent = max(candidates, key=len) if candidates else "*"
    rules = parsed_rules.get(matched_agent, {"allow": [], "disallow": []})
    return RobotsUserAgentRule(allowed=_match_rule(target_path, rules), matched_user_agent=matched_agent)


def robot_path_rule(parsed: RobotsRules, agent: str, url: str) -> RobotsUserAgentRule:
    parts = urlparse(url)
    path = parts.path or "/"
    if parts.params:
        path += ";" + parts.params
    if parts.query:
        path += "?" + parts.query
    return _resolve_agent_rule(agent, parsed, path)


def inspect_robot_path(
    robots: RobotsResult,
    url: str,
    *,
    crawlers: list[str] | None = None,
    locale: str | None = None,
) -> dict[str, bool | None]:
    """Return unknown for incomplete evidence; never infer deep paths from '/'."""
    selected = list(crawlers) if crawlers is not None else search_crawlers_for_site(url, locale=locale)
    if robots.status_code is not None and 400 <= robots.status_code < 500 and robots.status_code != 429:
        return {agent: True for agent in selected}
    if robots.raw_text is None or (robots.status_code is not None and robots.status_code >= 400):
        return {agent: None for agent in selected}
    parsed, _ = parse_robots_text(robots.raw_text)
    return {agent: robot_path_rule(parsed, agent, url).allowed for agent in selected}


def inspect_google_extended(robots: RobotsResult, url: str) -> bool | None:
    """Inspect Google-Extended (controls Gemini app citation eligibility)."""
    if robots.status_code is not None and 400 <= robots.status_code < 500 and robots.status_code != 429:
        return True
    if robots.raw_text is None or (robots.status_code is not None and robots.status_code >= 400):
        return None
    parsed, _ = parse_robots_text(robots.raw_text)
    return robot_path_rule(parsed, "Google-Extended", url).allowed


def inspect_training_crawlers(robots: RobotsResult, url: str) -> dict[str, bool | None]:
    """Inspect training-only crawlers for transparent, unscored reporting."""
    return inspect_robot_path(robots, url, crawlers=TRAINING_CRAWLERS)


async def inspect_robots(base_url: str, client: httpx.AsyncClient | None = None) -> RobotsResult:
    """抓取并解析 robots.txt，评估各 AI 爬虫的访问权限

    Args:
        base_url: 站点 URL（取根域名路径 /robots.txt）
        client: 可选的共享 HTTP 客户端

    Returns:
        RobotsResult：包含存在状态、通配符规则、各 AI 爬虫状态、Sitemap 链接
    """
    robots_url = f"{get_site_root(base_url)}/robots.txt"
    try:
        response = await fetch_url(robots_url, client=client)
    except Exception:
        return RobotsResult(url=robots_url, exists=False)

    if response.status_code >= 400:
        return RobotsResult(url=robots_url, exists=False, status_code=response.status_code)

    parsed_rules, sitemaps = parse_robots_text(response.text)
    content_signals, llm_policy_urls = parse_robots_extras(response.text)
    # 解析所有 AI 爬虫的访问状态
    agents = {name: _resolve_agent_rule(name, parsed_rules) for name in AI_CRAWLERS}
    # 检查通配符规则是否允许全站访问
    allows_all = _match_rule("/", parsed_rules.get("*", {"allow": [], "disallow": []}))
    return RobotsResult(
        url=robots_url,
        exists=True,
        status_code=response.status_code,
        allows_all=allows_all,
        has_sitemap_directive=bool(sitemaps),
        sitemaps=sitemaps,
        user_agents=agents,
        content_signals=content_signals,
        llm_policy_urls=llm_policy_urls,
        raw_preview=response.text[:300],  # 前 300 字符用于调试
        raw_text=response.text if len(response.text.encode("utf-8")) <= 512_000 else None,
    )
