from __future__ import annotations

import time

from app.models.audit import TechnicalAuditResult
from app.models.requests import LLMConfig
from app.services.audit.base import AuditBaseService
from app.services.audit.scoring import ScoringService
from app.utils.heuristics import assess_render_blocking, assess_ssr_signal
from app.utils.security_headers import evaluate_security_headers
from app.utils.url_utils import base_locale, locales_match


class TechnicalService(AuditBaseService):
    """技术基础审计模块（占 GEO 总分 15%）

    检查项（共 15 项，总权重 100 分）：
    - HTTPS(8)、SSR(10)、meta_description(5)、canonical(5)、lang(4)
    - unique_h1(4)、sitemap(8)、robots_sitemap_directive(4)
    - open_graph(5)、twitter_card(3)、hreflang(4)
    - security_headers(16)、image_optimization(4)、render_blocking(8)、performance(8)
    - revalidation_headers(4)
    """

    def __init__(self, discovery_service=None) -> None:
        super().__init__(discovery_service)
        self.scoring = ScoringService()

    def _image_optimization_score(self, images: list[dict]) -> tuple[int, dict]:
        """评估图片优化情况：懒加载比例（50%）+ 声明尺寸比例（50%）

        无图片时返回基础分 70（不因无图片而被惩罚）
        """
        if not images:
            return 70, {"image_count": 0, "lazyload_ratio": 0, "dimension_ratio": 0}

        lazyload_count = sum(1 for image in images if (image.get("loading") or "").lower() == "lazy")
        dimension_count = sum(1 for image in images if image.get("width") and image.get("height"))
        lazyload_ratio = lazyload_count / len(images)
        dimension_ratio = dimension_count / len(images)
        score = self.scoring.clamp_score((lazyload_ratio * 50 + dimension_ratio * 50))
        return score, {
            "image_count": len(images),
            "lazyload_ratio": round(lazyload_ratio, 2),
            "dimension_ratio": round(dimension_ratio, 2),
        }

    def _performance_score(self, response_time_ms: int) -> dict:
        """基于服务器响应时间评估性能等级

        ≤300ms: 100分(fast) | ≤800ms: 75分(good) | ≤1500ms: 50分(moderate) | >1500ms: 25分(slow)
        """
        if response_time_ms <= 300:
            return {"score": 100, "classification": "fast"}
        if response_time_ms <= 800:
            return {"score": 75, "classification": "good"}
        if response_time_ms <= 1500:
            return {"score": 50, "classification": "moderate"}
        return {"score": 25, "classification": "slow"}

    async def audit(
        self,
        url: str,
        discovery=None,
        mode: str = "standard",
        llm_config: LLMConfig | None = None,
        target_locale: str | None = None,
    ) -> TechnicalAuditResult:
        """执行技术基础审计

        注：technical 模块在 premium 模式下仍保持规则驱动（确定性结果）
        """
        started_at = time.perf_counter()
        resolved = await self.ensure_discovery(url, discovery, target_locale=target_locale)
        homepage = resolved.homepage
        homepage_profile = resolved.page_profiles.get("homepage")

        # 各子项检查
        security_headers = evaluate_security_headers(resolved.fetch.headers)
        ssr_signal = assess_ssr_signal(homepage.html_length, homepage.word_count)
        render_blocking_risk = assess_render_blocking(
            homepage.model_dump()["scripts"],
            homepage.model_dump()["stylesheets"],
        )
        image_score, image_details = self._image_optimization_score(homepage.model_dump()["images"])
        performance_score = self._performance_score(resolved.fetch.response_time_ms)
        h1_count = sum(1 for heading in homepage.headings if heading.level == "h1")
        unique_h1 = h1_count == 1
        revalidation_headers = {
            "etag": bool(resolved.fetch.headers.get("etag")),
            "last_modified": bool(resolved.fetch.headers.get("last-modified")),
        }
        freshness_signal_score = self.scoring.clamp_score(
            (45 if revalidation_headers["etag"] else 0)
            + (25 if revalidation_headers["last_modified"] else 0)
            + (15 if homepage_profile and homepage_profile.has_publish_date else 0)
            + (15 if homepage_profile and homepage_profile.has_update_log else 0)
        )
        target_locale = base_locale(resolved.requested_target_locale)
        homepage_locale = base_locale(homepage.lang)
        locale_target_match = not target_locale or locales_match(homepage_locale, target_locale)
        hreflang_target_present = not target_locale or any(locales_match(item, target_locale) for item in homepage.hreflang)

        # 各项检查点的权重定义（总和约等于 100）
        weights = {
            "https": 8,
            "ssr": 10,
            "meta_description": 5,
            "canonical": 5,
            "lang": 4,
            "unique_h1": 4,
            "sitemap": 8,
            "robots_sitemap_directive": 4,
            "open_graph": 5,
            "twitter_card": 3,
            "hreflang": 4,
            "security_headers": 16,   # 最高权重：安全响应头
            "image_optimization": 4,
            "render_blocking": 8,
            "performance": 8,
            "revalidation_headers": 4,
        }

        checks = {
            "https": resolved.final_url.startswith("https://"),
            "ssr": ssr_signal,
            "meta_description": bool(homepage.meta_description),
            "canonical": bool(homepage.canonical),
            "lang": bool(homepage.lang),
            "viewport": bool(homepage.viewport),
            "unique_h1": unique_h1,
            "h1_count": h1_count,
            "sitemap": resolved.sitemap.exists,
            "robots_sitemap_directive": resolved.robots.has_sitemap_directive,
            "open_graph": bool(homepage.open_graph),
            "twitter_card": bool(homepage.twitter_cards),
            "hreflang": bool(homepage.hreflang),
            "locale_target_match": locale_target_match,
            "hreflang_target_present": hreflang_target_present,
            "security_headers": security_headers,
            "image_optimization": image_details,
            "render_blocking": render_blocking_risk,
            "performance": performance_score,
            "revalidation_headers": revalidation_headers,
            "freshness_signal_score": freshness_signal_score,
        }

        # 加权求和计算技术分数
        technical_score = self.scoring.clamp_score(
            weights["https"] * int(checks["https"])
            + weights["ssr"] * (ssr_signal["score"] / 100)
            + weights["meta_description"] * int(checks["meta_description"])
            + weights["canonical"] * int(checks["canonical"])
            + weights["lang"] * int(checks["lang"])
            + weights["unique_h1"] * int(checks["unique_h1"])
            + weights["sitemap"] * int(checks["sitemap"])
            + weights["robots_sitemap_directive"] * int(checks["robots_sitemap_directive"])
            + weights["open_graph"] * int(checks["open_graph"])
            + weights["twitter_card"] * int(checks["twitter_card"])
            + weights["hreflang"] * int(checks["hreflang"])
            + weights["security_headers"] * (security_headers["score"] / 100)
            + weights["image_optimization"] * (image_score / 100)
            + weights["render_blocking"] * (render_blocking_risk["score"] / 100)
            + weights["performance"] * (performance_score["score"] / 100)
            + weights["revalidation_headers"] * int(
                revalidation_headers["etag"] or revalidation_headers["last_modified"]
            )
        )
        status = self.scoring.status_from_score(technical_score)

        strengths: list[str] = []
        issues: list[str] = []
        recommendations: list[str] = []

        # 根据各项检查结果生成问题和建议
        if checks["https"]:
            strengths.append("Site resolves over HTTPS.")
        else:
            issues.append("Site does not consistently enforce HTTPS.")
            recommendations.append("Redirect all traffic to HTTPS and preload HSTS once validated.")

        if security_headers["score"] >= 80:
            strengths.append("Core security headers are largely in place.")
        else:
            issues.append("Important security headers are missing.")
            recommendations.append("Add HSTS, CSP, X-Frame-Options, X-Content-Type-Options, and Referrer-Policy headers.")

        if not checks["meta_description"]:
            issues.append("Homepage is missing a meta description.")
            recommendations.append("Add a concise meta description that describes the primary offer and location/entity.")
        if target_locale and not locale_target_match:
            issues.append("Homepage language declaration does not match the requested target locale.")
            recommendations.append("Align html lang, visible copy, and the requested locale scope before running GEO diagnostics.")
        elif target_locale and homepage_locale:
            strengths.append("Homepage language declaration aligns with the requested locale.")
        if not checks["canonical"]:
            issues.append("Homepage is missing a canonical tag.")
            recommendations.append("Expose self-referencing canonical tags on primary pages.")
        if not checks["unique_h1"]:
            issues.append("Homepage semantic structure should expose exactly one H1.")
            recommendations.append("Keep a single descriptive H1 and nest supporting sections under logical H2/H3 headings.")
        if render_blocking_risk["risk_level"] != "low":
            issues.append("Homepage has medium or high render-blocking risk.")
            recommendations.append("Defer non-critical JavaScript and reduce synchronous CSS/JS payloads.")
        else:
            strengths.append("Render-blocking risk looks manageable.")

        if performance_score["score"] < 60:
            issues.append("Observed response time is slower than ideal for AI retrieval and user experience.")
            recommendations.append("Reduce server response latency and optimize page-critical assets.")
        else:
            strengths.append("Observed response time is within a healthy baseline.")

        if image_score < 60:
            issues.append("Images are missing lazy loading and/or explicit dimensions.")
            recommendations.append("Add lazy loading and width/height attributes to primary images.")
        else:
            strengths.append("Image delivery patterns show baseline optimization.")
        if target_locale and homepage.hreflang and not hreflang_target_present:
            issues.append("hreflang annotations do not expose the requested target locale.")
            recommendations.append("Add hreflang coverage for the requested locale and keep alternate links mutually consistent.")
        if not (revalidation_headers["etag"] or revalidation_headers["last_modified"]):
            issues.append("Response headers do not expose ETag or Last-Modified freshness signals.")
            recommendations.append("Add ETag and/or Last-Modified headers so crawlers can revalidate content efficiently.")
        elif freshness_signal_score >= 60:
            strengths.append("Technical freshness signals support efficient crawler revalidation.")

        findings = {
            "response_time_ms": resolved.fetch.response_time_ms,
            "security_headers_score": security_headers["score"],
            "ssr_classification": ssr_signal["classification"],
            "performance_classification": performance_score["classification"],
            "render_blocking_risk": render_blocking_risk["risk_level"],
            "image_optimization": image_details,
            "h1_count": h1_count,
            "freshness_signal_score": freshness_signal_score,
            "target_locale": target_locale,
            "homepage_locale": homepage_locale,
            "locale_target_match": locale_target_match,
            "hreflang_target_present": hreflang_target_present,
        }
        result = TechnicalAuditResult(
            score=technical_score,
            status=status,
            findings=findings,
            issues=issues,
            strengths=strengths,
            recommendations=recommendations,
            technical_score=technical_score,
            checks=checks,
            security_headers=security_headers,
            ssr_signal=ssr_signal,
            render_blocking_risk=render_blocking_risk,
        )
        self.set_execution_metadata(result, mode, llm_config)
        # 技术模块保持规则驱动，premium 模式仅记录说明
        if mode == "premium":
            result.processing_notes.append("Premium mode currently keeps technical audit rule-based for determinism.")
        result = self.finalize_audit_result(
            result,
            module_key="technical",
            input_pages=self.collect_input_pages(resolved, "homepage"),
            started_at=started_at,
            confidence=0.95,   # 技术检查完全基于规则，置信度固定较高
        )
        return result
