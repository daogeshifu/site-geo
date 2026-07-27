from __future__ import annotations

from typing import Any


SEVERITY_ORDER = {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
}


def _rendering_assessment(
    googlebot: dict[str, Any],
    google_render: dict[str, Any],
) -> dict[str, Any]:
    initial_content = googlebot.get("content") or {}
    comparison = google_render.get("comparison") or {}
    initial_words = comparison.get("initial_word_count", initial_content.get("word_count", 0))
    rendered_words = comparison.get("rendered_word_count")
    word_delta = comparison.get("word_delta")

    if google_render.get("status") == "skipped" or rendered_words is None:
        return {
            "type": "unknown",
            "label": "暂时无法判定",
            "status": "warning",
            "detail": "Google Render 未完成，当前只能确认初始 HTML，无法判断 JavaScript 执行后的最终内容。",
            "initial_word_count": initial_words,
            "rendered_word_count": rendered_words,
            "word_delta": word_delta,
        }

    initial_words = int(initial_words or 0)
    rendered_words = int(rendered_words or 0)
    word_delta = int(word_delta or 0)

    if initial_words < 50 and rendered_words >= 50:
        return {
            "type": "client_rendered",
            "label": "客户端异步渲染（CSR）",
            "status": "warning",
            "detail": (
                f"初始 HTML 仅约 {initial_words} 个词/字符单元，执行 JavaScript 后增加到 "
                f"{rendered_words}；核心内容明显依赖异步加载。"
            ),
            "initial_word_count": initial_words,
            "rendered_word_count": rendered_words,
            "word_delta": word_delta,
        }

    if initial_words < 50 and rendered_words < 50:
        return {
            "type": "thin_content",
            "label": "内容不足，无法确认渲染模式",
            "status": "failed",
            "detail": (
                f"初始 HTML 与渲染后页面都少于 50 个词/字符单元（{initial_words} → "
                f"{rendered_words}），页面可能为空、受限或核心内容未加载。"
            ),
            "initial_word_count": initial_words,
            "rendered_word_count": rendered_words,
            "word_delta": word_delta,
        }

    if rendered_words < initial_words * 0.6:
        return {
            "type": "hydration_loss",
            "label": "服务端内容在渲染后丢失",
            "status": "failed",
            "detail": (
                f"初始 HTML 有约 {initial_words} 个词/字符单元，但渲染后仅剩 "
                f"{rendered_words}；需要检查 hydration 或客户端路由覆盖。"
            ),
            "initial_word_count": initial_words,
            "rendered_word_count": rendered_words,
            "word_delta": word_delta,
        }

    meaningful_growth = max(50, round(initial_words * 0.3))
    if word_delta >= meaningful_growth:
        return {
            "type": "hybrid_rendered",
            "label": "混合渲染（SSR + 异步增强）",
            "status": "passed",
            "detail": (
                f"初始 HTML 已包含约 {initial_words} 个词/字符单元，JavaScript 渲染后增至 "
                f"{rendered_words}；核心内容可直接抓取，页面另有异步增强内容。"
            ),
            "initial_word_count": initial_words,
            "rendered_word_count": rendered_words,
            "word_delta": word_delta,
        }

    return {
        "type": "server_rendered",
        "label": "服务端渲染 / 静态输出",
        "status": "passed",
        "detail": (
            f"初始 HTML 已包含约 {initial_words} 个词/字符单元，渲染后为 "
            f"{rendered_words}；核心正文不依赖 JavaScript 才能出现。"
        ),
        "initial_word_count": initial_words,
        "rendered_word_count": rendered_words,
        "word_delta": word_delta,
    }


def _major_issues(
    googlebot: dict[str, Any],
    google_render: dict[str, Any],
) -> list[dict[str, Any]]:
    combined: list[dict[str, Any]] = []
    for source, result in (
        ("Googlebot", googlebot),
        ("Google Render", google_render),
    ):
        for item in result.get("issues") or []:
            combined.append(
                {
                    **item,
                    "source": source,
                }
            )
    combined.sort(
        key=lambda item: (
            SEVERITY_ORDER.get(str(item.get("severity", "")).lower(), 9),
            str(item.get("title", "")),
        )
    )
    return combined[:5]


def build_crawler_overview(
    googlebot: dict[str, Any],
    google_render: dict[str, Any],
) -> dict[str, Any]:
    rendering = _rendering_assessment(googlebot, google_render)
    issues = _major_issues(googlebot, google_render)
    indexability = googlebot.get("indexability") or {}
    crawlability = googlebot.get("crawlability") or {}
    googlebot_request = googlebot.get("request") or {}
    render_request = google_render.get("request") or {}
    access = googlebot.get("access") or {}

    crawl_allowed = crawlability.get("allowed")
    crawl_ok = crawl_allowed is True
    indexable = indexability.get("indexable")
    access_challenge = access.get("state") == "waf_challenge"
    http_ok = googlebot_request.get("status_code") == 200
    render_completed = google_render.get("status") != "skipped"
    render_http_ok = (
        not render_completed or render_request.get("status_code") == 200
    )
    blocking_issue = any(
        (
            str(item.get("severity", "")).lower() == "critical"
            or (
                str(item.get("severity", "")).lower() == "high"
                and item.get("code")
                not in {"thin_initial_html", "googlebot_access_challenge"}
            )
        )
        for item in issues
    )

    if crawl_allowed is False or indexable is False:
        seo_status = "failed"
        seo_label = "不符合基础 SEO 收录标准"
        seo_detail = "页面存在明确的 robots 或 noindex 阻断，不满足正常收录条件。"
    elif access_challenge:
        seo_status = "warning"
        seo_label = "渲染方式已识别，真实 Googlebot 收录待确认"
        seo_detail = (
            "模拟 Googlebot UA 被 WAF/反爬策略拦截；普通浏览器对照结果只能用于判断页面渲染方式，"
            "不能替代真实 Googlebot 索引结论。"
        )
    elif not http_ok or not render_http_ok:
        seo_status = "failed"
        seo_label = "不符合基础 SEO 收录标准"
        seo_detail = "页面存在明确的 HTTP 或渲染阻断，可能无法正常进入 Google 收录流程。"
    elif rendering["status"] == "failed" or blocking_issue:
        seo_status = "failed"
        seo_label = "当前不建议直接用于 SEO 收录"
        seo_detail = "页面可访问，但核心内容呈现或高优先级技术问题会削弱抓取、渲染与排名信号。"
    elif not render_completed:
        seo_status = "warning"
        seo_label = "基础抓取合格，渲染结果待确认"
        seo_detail = "Googlebot 抓取与索引条件正常，但本次未完成 JavaScript 渲染验证。"
    elif googlebot.get("status") == "passed" and google_render.get("status") == "passed":
        seo_status = "passed"
        seo_label = "符合基础技术 SEO 标准"
        seo_detail = "页面允许抓取和索引，核心内容可见，渲染过程未发现阻断性问题。"
    else:
        seo_status = "warning"
        seo_label = "基本符合，但仍有优化项"
        seo_detail = "页面能够进入抓取和索引流程，但仍有技术或资源问题需要处理。"

    crawl_label = (
        "允许抓取"
        if crawl_ok
        else "阻止抓取"
        if crawl_allowed is False
        else "抓取状态不确定"
    )
    index_label = (
        "允许索引"
        if indexable is True
        else "不可索引"
        if indexable is False
        else "真实索引状态待确认"
    )
    summary = (
        f"该页面判定为{rendering['label']}；{crawl_label}、{index_label}。"
        f"SEO 结论：{seo_label}。"
    )

    return {
        "summary": summary,
        "status": seo_status,
        "rendering": rendering,
        "seo": {
            "status": seo_status,
            "label": seo_label,
            "detail": seo_detail,
        },
        "crawl": {
            "status": (
                "warning"
                if access_challenge
                else
                "passed"
                if crawl_ok and http_ok
                else "failed"
                if crawl_allowed is False or not http_ok
                else "warning"
            ),
            "label": crawl_label,
            "detail": (
                f"HTTP {googlebot_request.get('status_code') or 'unknown'}；"
                f"{access.get('detail') or ''} "
                f"robots.txt：{crawlability.get('detail') or '未返回明确结果'}"
            ),
        },
        "indexing": {
            "status": (
                "passed"
                if indexable is True
                else "failed"
                if indexable is False
                else "warning"
            ),
            "label": index_label,
            "detail": (
                "未发现阻止收录的 robots/noindex 指令。"
                if indexable is True
                else "页面当前不满足正常收录条件，请查看 Googlebot 细项。"
                if indexable is False
                else "模拟请求来自非 Google IP，真实状态需通过 Search Console URL Inspection 确认。"
            ),
        },
        "major_issues": issues,
    }
