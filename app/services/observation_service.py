from __future__ import annotations

from app.models.audit import ObservationInput, ObservationResult, ObservationSourceMetric


class ObservationService:
    """可选观测层服务：汇总 GA4/日志/人工引用观测，但不参与 GEO 评分"""

    def build(self, observation: ObservationInput | None) -> ObservationResult:
        """将可选输入归一化为可展示结果"""
        if observation is None:
            return ObservationResult(
                provided=False,
                scored=False,
                status="not_provided",
                measurement_maturity="none",
                summary=(
                    "No external observation data was uploaded. GEO scoring in v2 is based on on-site readiness only, "
                    "while observation metrics remain optional and unscored."
                ),
                data_gaps=[
                    "No GA4 AI traffic metrics provided.",
                    "No source-platform breakdown provided.",
                    "No citation observations provided.",
                ],
            )

        metrics = {
            "data_period": observation.data_period,
            "ga4_ai_sessions": observation.ga4_ai_sessions,
            "ga4_ai_users": observation.ga4_ai_users,
            "ga4_ai_conversions": observation.ga4_ai_conversions,
            "ga4_ai_revenue": observation.ga4_ai_revenue,
        }

        source_breakdown = [self._normalize_source(item) for item in observation.source_breakdown]
        citation_total = len(observation.citation_observations)
        citation_hits = sum(1 for item in observation.citation_observations if item.cited)
        cited_positions = [item.position for item in observation.citation_observations if item.cited and item.position]

        if citation_total:
            metrics["citation_hit_rate"] = round(citation_hits / citation_total, 2)
        if cited_positions:
            metrics["average_citation_position"] = round(sum(cited_positions) / len(cited_positions), 2)
        if observation.ga4_ai_sessions and observation.ga4_ai_conversions is not None:
            metrics["ga4_conversion_rate"] = round(observation.ga4_ai_conversions / max(observation.ga4_ai_sessions, 1), 4)

        measurement_maturity = self._measurement_maturity(observation, source_breakdown, citation_total)
        highlights = self._highlights(observation, source_breakdown, citation_total, citation_hits)
        data_gaps = self._data_gaps(observation, source_breakdown, citation_total)
        summary = self._summary(observation, source_breakdown, citation_total, citation_hits, measurement_maturity)

        return ObservationResult(
            provided=True,
            scored=False,
            status="provided",
            measurement_maturity=measurement_maturity,
            summary=summary,
            metrics=metrics,
            platform_breakdown=source_breakdown,
            citation_observations=observation.citation_observations,
            highlights=highlights,
            data_gaps=data_gaps,
        )

    def _normalize_source(self, item: ObservationSourceMetric) -> ObservationSourceMetric:
        if item.conversion_rate is None and item.sessions and item.conversions is not None:
            item.conversion_rate = round(item.conversions / max(item.sessions, 1), 4)
        return item

    def _measurement_maturity(
        self,
        observation: ObservationInput,
        source_breakdown: list[ObservationSourceMetric],
        citation_total: int,
    ) -> str:
        signals = 0
        if observation.ga4_ai_sessions is not None:
            signals += 1
        if source_breakdown:
            signals += 1
        if citation_total:
            signals += 1
        return "advanced" if signals == 3 else "intermediate" if signals == 2 else "basic" if signals == 1 else "none"

    def _highlights(
        self,
        observation: ObservationInput,
        source_breakdown: list[ObservationSourceMetric],
        citation_total: int,
        citation_hits: int,
    ) -> list[str]:
        highlights: list[str] = []
        if observation.ga4_ai_sessions is not None:
            highlights.append(f"Observed {observation.ga4_ai_sessions} AI-attributed sessions in the uploaded data.")
        if source_breakdown:
            top_source = max(source_breakdown, key=lambda item: item.sessions or 0)
            highlights.append(
                f"Top observed AI source: {top_source.platform} ({top_source.sessions or 0} sessions)."
            )
        if citation_total:
            highlights.append(f"Observed citation hit rate: {citation_hits}/{citation_total}.")
        return highlights

    def _data_gaps(
        self,
        observation: ObservationInput,
        source_breakdown: list[ObservationSourceMetric],
        citation_total: int,
    ) -> list[str]:
        gaps: list[str] = []
        if observation.ga4_ai_sessions is None:
            gaps.append("GA4 AI traffic totals were not provided.")
        if not source_breakdown:
            gaps.append("No source-platform traffic breakdown was provided.")
        if citation_total == 0:
            gaps.append("No citation observation samples were provided.")
        return gaps

    def _summary(
        self,
        observation: ObservationInput,
        source_breakdown: list[ObservationSourceMetric],
        citation_total: int,
        citation_hits: int,
        measurement_maturity: str,
    ) -> str:
        parts = [
            f"Optional observation data is available and classified as {measurement_maturity} measurement maturity."
        ]
        if observation.ga4_ai_sessions is not None:
            parts.append(f"Uploaded GA4 data shows {observation.ga4_ai_sessions} AI-attributed sessions.")
        if source_breakdown:
            platform_count = len({item.platform for item in source_breakdown})
            parts.append(f"Source breakdown covers {platform_count} AI platforms.")
        if citation_total:
            parts.append(f"Citation observations show {citation_hits}/{citation_total} observed hits.")
        parts.append("These metrics are displayed for context only and do not change the GEO score.")
        return " ".join(parts)
