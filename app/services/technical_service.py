from __future__ import annotations

from app.models.audit import TechnicalAuditResult
from app.models.requests import LLMConfig
from app.services.audit_service import AuditBaseService
from app.services.scoring_service import ScoringService
from app.utils.heuristics import assess_render_blocking, assess_ssr_signal
from app.utils.security_headers import evaluate_security_headers


class TechnicalService(AuditBaseService):
    def __init__(self, discovery_service=None) -> None:
        super().__init__(discovery_service)
        self.scoring = ScoringService()

    def _image_optimization_score(self, images: list[dict]) -> tuple[int, dict]:
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
    ) -> TechnicalAuditResult:
        resolved = await self.ensure_discovery(url, discovery)
        homepage = resolved.homepage
        security_headers = evaluate_security_headers(resolved.fetch.headers)
        ssr_signal = assess_ssr_signal(homepage.html_length, homepage.word_count)
        render_blocking_risk = assess_render_blocking(
            homepage.model_dump()["scripts"],
            homepage.model_dump()["stylesheets"],
        )
        image_score, image_details = self._image_optimization_score(homepage.model_dump()["images"])
        performance_score = self._performance_score(resolved.fetch.response_time_ms)

        weights = {
            "https": 8,
            "ssr": 10,
            "meta_description": 5,
            "canonical": 5,
            "lang": 4,
            "viewport": 4,
            "sitemap": 8,
            "robots_sitemap_directive": 4,
            "open_graph": 5,
            "twitter_card": 3,
            "hreflang": 4,
            "security_headers": 16,
            "image_optimization": 8,
            "render_blocking": 8,
            "performance": 8,
        }

        checks = {
            "https": resolved.final_url.startswith("https://"),
            "ssr": ssr_signal,
            "meta_description": bool(homepage.meta_description),
            "canonical": bool(homepage.canonical),
            "lang": bool(homepage.lang),
            "viewport": bool(homepage.viewport),
            "sitemap": resolved.sitemap.exists,
            "robots_sitemap_directive": resolved.robots.has_sitemap_directive,
            "open_graph": bool(homepage.open_graph),
            "twitter_card": bool(homepage.twitter_cards),
            "hreflang": bool(homepage.hreflang),
            "security_headers": security_headers,
            "image_optimization": image_details,
            "render_blocking": render_blocking_risk,
            "performance": performance_score,
        }

        technical_score = self.scoring.clamp_score(
            weights["https"] * int(checks["https"])
            + weights["ssr"] * (ssr_signal["score"] / 100)
            + weights["meta_description"] * int(checks["meta_description"])
            + weights["canonical"] * int(checks["canonical"])
            + weights["lang"] * int(checks["lang"])
            + weights["viewport"] * int(checks["viewport"])
            + weights["sitemap"] * int(checks["sitemap"])
            + weights["robots_sitemap_directive"] * int(checks["robots_sitemap_directive"])
            + weights["open_graph"] * int(checks["open_graph"])
            + weights["twitter_card"] * int(checks["twitter_card"])
            + weights["hreflang"] * int(checks["hreflang"])
            + weights["security_headers"] * (security_headers["score"] / 100)
            + weights["image_optimization"] * (image_score / 100)
            + weights["render_blocking"] * (render_blocking_risk["score"] / 100)
            + weights["performance"] * (performance_score["score"] / 100)
        )
        status = self.scoring.status_from_score(technical_score)

        strengths: list[str] = []
        issues: list[str] = []
        recommendations: list[str] = []

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
        if not checks["canonical"]:
            issues.append("Homepage is missing a canonical tag.")
            recommendations.append("Expose self-referencing canonical tags on primary pages.")
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

        findings = {
            "response_time_ms": resolved.fetch.response_time_ms,
            "security_headers_score": security_headers["score"],
            "ssr_classification": ssr_signal["classification"],
            "performance_classification": performance_score["classification"],
            "render_blocking_risk": render_blocking_risk["risk_level"],
            "image_optimization": image_details,
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
        if mode == "premium":
            result.processing_notes.append("Premium mode currently keeps technical audit rule-based for determinism.")
        return result
