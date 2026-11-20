from __future__ import annotations

import json
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, distribution


REVIEWED_ON = "2026-11-20"
GROUPS = ("搜索引擎", "AI 引擎 · 国内", "AI 引擎 · 国外", "社媒平台")
SEARCH, DOMESTIC_AI, GLOBAL_AI, SOCIAL = GROUPS


@dataclass(frozen=True)
class Agent:
    token: str
    purpose: str
    user_agent: str
    robots_user_agent: str = ""  # Some operators publish a distinct UA for /robots.txt.
    page_headers: tuple[tuple[str, str], ...] = ()
    usage_token: str = ""  # Content-use permission, independent of HTTP crawl permission.
    mobile: bool = False

    def headers(self, *, robots: bool = False) -> dict[str, str]:
        headers = {
            "User-Agent": self.robots_user_agent if robots and self.robots_user_agent else self.user_agent,
            "Accept": "*/*",
            "Accept-Encoding": "gzip, deflate",
        }
        if not robots:
            headers.update(self.page_headers)
        return headers


@dataclass(frozen=True)
class Platform:
    id: str
    name: str
    group: str
    agents: tuple[Agent, ...]
    description: str
    sources: tuple[tuple[str, str], ...]
    render: Agent | None = None
    identity: str = "公开标识"

    def agent(self, token: str | None) -> Agent | None:
        if token is None:
            return self.agents[0]
        return next((agent for agent in self.agents if agent.token == token), None)


GOOGLE_DOC = "https://developers.google.com/crawling/docs/crawlers-fetchers/google-common-crawlers"


def _chromium_token() -> str:
    # Google and Bing publish Chrome/W.X.Y.Z templates. Match the Chromium
    # bundled with our renderer, including when profiles are used without a render.
    try:
        manifest = distribution("playwright").locate_file("playwright/driver/package/browsers.json")
        browsers = json.loads(manifest.read_text(encoding="utf-8"))["browsers"]
        for browser in browsers:
            if browser["name"] == "chromium":
                major = browser["browserVersion"].split(".")[0]
                if major.isdecimal():
                    return f"Chrome/{major}.0.0.0"
    except (PackageNotFoundError, OSError, ValueError, KeyError):
        pass
    return "Chrome/149.0.0.0"  # Representative version for HTTP-only installations.


CHROMIUM = _chromium_token()
GOOGLEBOT_SMARTPHONE_UA = (
    "Mozilla/5.0 (Linux; Android 6.0.1; Nexus 5X Build/MMB29P) "
    f"AppleWebKit/537.36 (KHTML, like Gecko) {CHROMIUM} Mobile "
    "Safari/537.36 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
)
GOOGLE = Agent("Googlebot", "移动网页搜索", GOOGLEBOT_SMARTPHONE_UA, mobile=True)
BAIDU_URL = "+http://www.baidu.com/search/spider.html)"
BAIDU = Agent("Baiduspider", "桌面网页搜索", "Mozilla/5.0 (compatible; Baiduspider/2.0; " + BAIDU_URL)
BAIDU_RENDER = Agent(
    "Baiduspider-render", "桌面渲染抓取", "Mozilla/5.0 (compatible; Baiduspider-render/2.0; " + BAIDU_URL
)
BING = Agent(
    "bingbot",
    "移动网页搜索",
    "Mozilla/5.0 (Linux; Android 6.0.1; Nexus 5X Build/MMB29P) AppleWebKit/537.36 "
    f"(KHTML, like Gecko) {CHROMIUM} Mobile Safari/537.36 "
    "(compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)",
    mobile=True,
)
BYTESPIDER = Agent(
    "Bytespider",
    "头条网页搜索",
    "Mozilla/5.0 (compatible; Bytespider; https://zhanzhang.toutiao.com/) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/70.0.0.0 Safari/537.36",
)
TOUTIAO_DOC = ("头条站长平台 · 关于 Bytespider", "https://zhanzhang.toutiao.com/docs/intro/26899")
GENERIC = Agent("SiteGeoPreview", "通用 HTTP 预览", "SiteGeoPreview/1.0")
OAI_SEARCH_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36; compatible; OAI-SearchBot/1.4; "
)
AI_PREFIX = "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; "
KIMI_DOC = "https://www.kimi.com/policies/kimi-crawlers"

PLATFORMS = (
    Platform(
        "google",
        "谷歌",
        SEARCH,
        (GOOGLE,),
        "使用 Googlebot Smartphone 抓取网页，再以相同标识在 Chromium 中执行 JavaScript，供对照原始 HTML 与渲染后的 DOM。",
        (
            ("Googlebot 请求标识", GOOGLE_DOC + "#googlebot"),
            (
                "Googlebot 语言请求头",
                "https://developers.google.com/search/docs/specialty/international/locale-adaptive-pages",
            ),
            (
                "Google 网页渲染流程",
                "https://developers.google.com/search/docs/crawling-indexing/javascript/javascript-seo-basics",
            ),
        ),
        GOOGLE,
    ),
    Platform(
        "baidu",
        "百度",
        SEARCH,
        (BAIDU,),
        "使用百度桌面搜索标识抓取原始响应，再用百度公布的渲染抓取标识在本地 Chromium 中加载页面。",
        (
            ("百度蜘蛛常见问题", "https://help.baidu.com/question?prod_id=99&class=476&id=2996"),
            ("百度渲染抓取 UA 公告", "https://ziyuan.baidu.com/wiki/990"),
        ),
        BAIDU_RENDER,
    ),
    Platform(
        "bing",
        "必应",
        SEARCH,
        (BING,),
        "Bing 使用 Microsoft Edge 渲染网页。此处用 bingbot 移动标识抓取，并用本地 Chromium 近似展示渲染结果。",
        (
            (
                "Bing 爬虫与渲染引擎",
                "https://www.bing.com/webmasters/help/which-crawlers-does-bing-use-8c184ec0",
            ),
        ),
        BING,
    ),
    Platform(
        "sogou",
        "搜狗",
        SEARCH,
        (Agent("Sogou web spider", "网页搜索", "Sogou web spider/4.0"),),
        "使用搜狗站长帮助中列出的网页搜索蜘蛛标识抓取页面。",
        (("搜狗蜘蛛说明", "https://help.sogou.com/spider.html"),),
    ),
    Platform(
        "duckduckgo",
        "DuckDuckGo",
        SEARCH,
        (Agent("DuckDuckBot", "网页搜索", "DuckDuckBot/1.1; (+http://duckduckgo.com/duckduckbot.html)"),),
        "使用 DuckDuckBot 请求页面，查看 DuckDuckGo 搜索爬虫标识收到的响应。",
        (("DuckDuckBot 官方说明", "https://duckduckgo.com/duckduckgo-help-pages/results/duckduckbot"),),
    ),
    Platform(
        "doubao",
        "豆包",
        DOMESTIC_AI,
        (BYTESPIDER,),
        "豆包联网检索的专用标识尚待核实。此处用同属字节跳动的头条搜索 Bytespider 作参考。",
        (
            TOUTIAO_DOC,
            ("豆包联网搜索", "https://console.volcengine.com/ark/region:cn-beijing/docs/web-search"),
        ),
        identity="关联爬虫参考",
    ),
    Platform(
        "yuanbao",
        "腾讯元宝",
        DOMESTIC_AI,
        (GENERIC,),
        "元宝公开了联网搜索接口，其专用 HTTP 爬虫标识尚待核实。此处使用本站标识预览公开响应。",
        (("腾讯云 · 元宝搜索", "https://cloud.tencent.com/document/api/1806/121811"),),
        identity="通用预览",
    ),
    Platform(
        "deepseek",
        "DeepSeek",
        DOMESTIC_AI,
        (Agent("DeepseekBot", "模型训练", "DeepseekBot"),),
        "DeepSeek 在训练数据披露中列出了 DeepseekBot。本次使用该名称模拟训练抓取，完整请求头和实时搜索标识尚待核实。",
        (
            (
                "DeepSeek 训练数据披露 · 第 2.3 节",
                "https://cdn.deepseek.com/policies/DeepSeek-V4.1-public-summary-of-training-content.pdf",
            ),
            ("DeepSeek · Search & Fetch", "https://api-docs.deepseek.com/guides/search/"),
        ),
        identity="公开名称模拟",
    ),
    Platform(
        "kimi",
        "Kimi",
        DOMESTIC_AI,
        tuple(
            Agent(token, purpose, f"{AI_PREFIX}{token}/1.0; +{KIMI_DOC}")
            for token, purpose in (
                ("Kimi-SearchBot", "搜索索引"),
                ("Kimi-User", "用户读取"),
                ("KimiBot", "模型训练"),
            )
        ),
        "可分别模拟 Kimi 的搜索索引、用户读取和模型训练请求。",
        (("Kimi 爬虫说明", KIMI_DOC),),
    ),
    Platform(
        "openai",
        "OpenAI",
        GLOBAL_AI,
        (
            Agent(
                "OAI-SearchBot",
                "ChatGPT 搜索",
                OAI_SEARCH_UA + "+https://openai.com/searchbot",
                robots_user_agent=OAI_SEARCH_UA + "robots.txt; +https://openai.com/searchbot",
            ),
            Agent("ChatGPT-User", "用户读取", AI_PREFIX + "ChatGPT-User/1.0; +https://openai.com/bot"),
            Agent("GPTBot", "模型训练", AI_PREFIX + "GPTBot/1.4; +https://openai.com/gptbot"),
        ),
        "可分别模拟 ChatGPT 搜索、用户发起的网页读取和 GPTBot 训练抓取。",
        (("OpenAI 爬虫说明", "https://developers.openai.com/api/docs/bots"),),
    ),
    Platform(
        "claude",
        "Claude",
        GLOBAL_AI,
        tuple(
            Agent(token, purpose, token)
            for token, purpose in (
                ("Claude-SearchBot", "搜索索引"),
                ("Claude-User", "用户读取"),
                ("ClaudeBot", "模型训练"),
            )
        ),
        "按 Anthropic 公布的用途选择爬虫。模拟请求使用其公开标识作为 User-Agent。",
        (
            (
                "Anthropic 爬虫说明",
                "https://support.claude.com/en/articles/8896518-does-anthropic-crawl-data-from-the-web-and-how-can-site-owners-block-the-crawler",
            ),
        ),
    ),
    Platform(
        "gemini",
        "Gemini",
        GLOBAL_AI,
        (
            Agent(
                "Googlebot",
                "Google 抓取与内容使用规则",
                GOOGLEBOT_SMARTPHONE_UA,
                usage_token="Google-Extended",
                mobile=True,
            ),
            Agent(
                "Google-GeminiNotebook",
                "Notebook 用户读取",
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 "
                "Safari/537.36 (compatible; Google-GeminiNotebook; +https://developers.google.com/crawling/docs/crawlers-fetchers/google-gemininotebook)",
            ),
        ),
        "Google-Extended 是 Gemini 的内容使用控制标记。此处用 Googlebot 作为抓取样本，单列使用规则，也可切换至 Notebook 用户读取。",
        (
            ("Google-Extended 用途", GOOGLE_DOC + "#google-extended"),
            (
                "Gemini Notebook 抓取标识",
                "https://developers.google.com/crawling/docs/crawlers-fetchers/google-user-triggered-fetchers#gemini-notebook",
            ),
        ),
    ),
    Platform(
        "perplexity",
        "Perplexity",
        GLOBAL_AI,
        (
            Agent(
                "PerplexityBot",
                "搜索索引",
                "Mozilla/5.0 (compatible; PerplexityBot/1.0; +https://perplexity.ai/perplexitybot)",
            ),
            Agent(
                "Perplexity-User",
                "用户读取",
                "Mozilla/5.0 (compatible; Perplexity-User/1.0; +https://perplexity.ai/perplexity-user)",
            ),
        ),
        "可分别模拟 Perplexity 搜索索引和用户发起的页面读取。",
        (("Perplexity 爬虫说明", "https://docs.perplexity.ai/docs/resources/perplexity-crawlers"),),
    ),
    Platform(
        "toutiao",
        "今日头条",
        SOCIAL,
        (BYTESPIDER,),
        "使用头条站长平台公布的 Bytespider 桌面请求样本。",
        (TOUTIAO_DOC,),
    ),
    Platform(
        "xiaohongshu",
        "小红书",
        SOCIAL,
        (GENERIC,),
        "小红书分享开放平台提供客户端分享能力，外链预览爬虫的专用标识尚待核实。此处使用本站标识预览公开响应。",
        (("小红书分享开放平台", "https://agora.xiaohongshu.com/doc"),),
        identity="通用预览",
    ),
    Platform(
        "facebook",
        "Facebook",
        SOCIAL,
        (
            Agent(
                "facebookexternalhit",
                "分享链接预览",
                "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)",
                page_headers=(("Range", "bytes=0-524288"), ("Connection", "close")),
            ),
        ),
        "按 Meta 的分享预览示例发送 facebookexternalhit 与 Range，展示服务器实际返回的内容范围。",
        (
            (
                "Meta 网页抓取工具",
                "https://developers.facebook.com/documentation/sharing/webmasters/web-crawlers",
            ),
        ),
    ),
    Platform(
        "x",
        "X",
        SOCIAL,
        (Agent("Twitterbot", "分享卡片预览", "Twitterbot/1.0"),),
        "使用 X 分享卡片的 Twitterbot 请求标识获取链接内容。",
        (
            (
                "Cloudflare Radar · Twitterbot 请求样本",
                "https://radar.cloudflare.com/bots/directory/twitterbot",
            ),
        ),
    ),
    Platform(
        "slack",
        "Slack",
        SOCIAL,
        (
            Agent(
                "Slackbot-LinkExpanding",
                "分享链接预览",
                "Slackbot-LinkExpanding 1.0 (+https://api.slack.com/robots)",
                page_headers=(("Range", "bytes=0-32767"),),
            ),
        ),
        "Slack 使用范围请求生成链接预览。此模拟选取前 32 KiB，实际响应范围由目标站点决定。",
        (("Slack Robots", "https://api.slack.com/robots"),),
    ),
)
BY_ID = {platform.id: platform for platform in PLATFORMS}
