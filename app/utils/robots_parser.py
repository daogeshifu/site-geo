from __future__ import annotations

from collections import defaultdict
from urllib.parse import urlparse

import httpx

from app.models.discovery import RobotsResult, RobotsUserAgentRule
from app.utils.fetcher import fetch_url
from app.utils.url_utils import get_site_root

# 需要检查访问权限的 AI 爬虫列表
AI_CRAWLERS = [
    "GPTBot",          # OpenAI 训练爬虫
    "OAI-SearchBot",   # OpenAI 搜索爬虫
    "ChatGPT-User",    # ChatGPT 实时搜索
    "ClaudeBot",       # Anthropic Claude 爬虫
    "PerplexityBot",   # Perplexity AI 爬虫
    "Google-Extended", # Google Gemini/AI Overviews 爬虫
]


def _match_rule(target_path: str, rules: dict[str, list[str]]) -> bool:
    """判断 target_path 是否被允许访问

    使用最长前缀匹配规则（robots.txt 标准）：
    - Allow 和 Disallow 中最长的匹配规则优先
    - Allow 胜出时返回 True，Disallow 胜出时返回 False
    - 无匹配规则时返回 True（默认允许）
    """
    allow_matches = [path for path in rules.get("allow", []) if target_path.startswith(path or "/")]
    disallow_matches = [path for path in rules.get("disallow", []) if target_path.startswith(path or "/")]

    if not allow_matches and not disallow_matches:
        return True  # 无规则，默认允许

    longest_allow = max((len(path) for path in allow_matches), default=-1)
    longest_disallow = max((len(path) for path in disallow_matches), default=-1)
    return longest_allow >= longest_disallow


def _parse_robots_text(text: str) -> tuple[dict[str, dict[str, list[str]]], list[str]]:
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


def _resolve_agent_rule(agent_name: str, parsed_rules: dict[str, dict[str, list[str]]]) -> RobotsUserAgentRule:
    """解析特定爬虫的访问规则

    优先使用精确匹配的规则，无匹配时回退到 * 通配符规则
    """
    lowered = agent_name.lower()
    matched_agent = lowered if lowered in parsed_rules else "*"
    rules = parsed_rules.get(matched_agent, {"allow": [], "disallow": []})
    return RobotsUserAgentRule(allowed=_match_rule("/", rules), matched_user_agent=matched_agent)


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

    parsed_rules, sitemaps = _parse_robots_text(response.text)
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
        raw_preview=response.text[:300],  # 前 300 字符用于调试
    )
