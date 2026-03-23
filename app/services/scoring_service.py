from __future__ import annotations

from typing import Any


class ScoringService:
    STATUS_THRESHOLDS = [
        (24, "critical"),
        (44, "poor"),
        (64, "fair"),
        (84, "good"),
        (100, "strong"),
    ]

    def clamp_score(self, score: float | int) -> int:
        return max(0, min(100, int(round(score))))

    def status_from_score(self, score: float | int) -> str:
        normalized = self.clamp_score(score)
        for threshold, status in self.STATUS_THRESHOLDS:
            if normalized <= threshold:
                return status
        return "strong"

    def weighted_composite(self, weighted_inputs: dict[str, dict[str, Any]]) -> tuple[int, dict[str, Any]]:
        weighted_scores: dict[str, Any] = {}
        total = 0.0
        for name, payload in weighted_inputs.items():
            raw_score = self.clamp_score(payload["raw_score"])
            weight = float(payload["weight"])
            weighted_value = round(raw_score * weight, 2)
            total += weighted_value
            weighted_scores[name] = {
                "raw_score": raw_score,
                "weight": weight,
                "weighted_value": weighted_value,
            }
        return self.clamp_score(total), weighted_scores
