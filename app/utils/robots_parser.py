from __future__ import annotations

from collections import defaultdict
from urllib.parse import urlparse

import httpx

from app.models.discovery import RobotsResult, RobotsUserAgentRule
from app.utils.fetcher import fetch_url
from app.utils.url_utils import get_site_root

AI_CRAWLERS = [
    "GPTBot",
    "OAI-SearchBot",
    "ChatGPT-User",
    "ClaudeBot",
    "PerplexityBot",
    "Google-Extended",
]


def _match_rule(target_path: str, rules: dict[str, list[str]]) -> bool:
    allow_matches = [path for path in rules.get("allow", []) if target_path.startswith(path or "/")]
    disallow_matches = [path for path in rules.get("disallow", []) if target_path.startswith(path or "/")]

    if not allow_matches and not disallow_matches:
        return True

    longest_allow = max((len(path) for path in allow_matches), default=-1)
    longest_disallow = max((len(path) for path in disallow_matches), default=-1)
    return longest_allow >= longest_disallow


def _parse_robots_text(text: str) -> tuple[dict[str, dict[str, list[str]]], list[str]]:
    rules: dict[str, dict[str, list[str]]] = defaultdict(lambda: {"allow": [], "disallow": []})
    sitemaps: list[str] = []
    current_agents: list[str] = []
    seen_directive = False

    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        directive = key.strip().lower()
        content = value.strip()

        if directive == "user-agent":
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
                current_agents = ["*"]
            seen_directive = True
            for agent in current_agents:
                rules[agent][directive].append(content)

    return dict(rules), sitemaps


def _resolve_agent_rule(agent_name: str, parsed_rules: dict[str, dict[str, list[str]]]) -> RobotsUserAgentRule:
    lowered = agent_name.lower()
    matched_agent = lowered if lowered in parsed_rules else "*"
    rules = parsed_rules.get(matched_agent, {"allow": [], "disallow": []})
    return RobotsUserAgentRule(allowed=_match_rule("/", rules), matched_user_agent=matched_agent)


async def inspect_robots(base_url: str, client: httpx.AsyncClient | None = None) -> RobotsResult:
    robots_url = f"{get_site_root(base_url)}/robots.txt"
    try:
        response = await fetch_url(robots_url, client=client)
    except Exception:
        return RobotsResult(url=robots_url, exists=False)

    if response.status_code >= 400:
        return RobotsResult(url=robots_url, exists=False, status_code=response.status_code)

    parsed_rules, sitemaps = _parse_robots_text(response.text)
    agents = {name: _resolve_agent_rule(name, parsed_rules) for name in AI_CRAWLERS}
    allows_all = _match_rule("/", parsed_rules.get("*", {"allow": [], "disallow": []}))
    return RobotsResult(
        url=robots_url,
        exists=True,
        status_code=response.status_code,
        allows_all=allows_all,
        has_sitemap_directive=bool(sitemaps),
        sitemaps=sitemaps,
        user_agents=agents,
        raw_preview=response.text[:300],
    )
