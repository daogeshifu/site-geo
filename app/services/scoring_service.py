from __future__ import annotations

from typing import Any


class ScoringService:
    """评分工具服务：提供 clamp、状态映射和加权复合分计算"""

    # 分数区间到状态的映射（上界包含）
    STATUS_THRESHOLDS = [
        (24, "critical"),
        (44, "poor"),
        (64, "fair"),
        (84, "good"),
        (100, "strong"),
    ]

    def clamp_score(self, score: float | int) -> int:
        """将评分限制在 [0, 100] 范围内，四舍五入为整数"""
        return max(0, min(100, int(round(score))))

    def status_from_score(self, score: float | int) -> str:
        """将数值评分映射为文字状态标签

        0-24: critical | 25-44: poor | 45-64: fair | 65-84: good | 85-100: strong
        """
        normalized = self.clamp_score(score)
        for threshold, status in self.STATUS_THRESHOLDS:
            if normalized <= threshold:
                return status
        return "strong"

    def weighted_composite(self, weighted_inputs: dict[str, dict[str, Any]]) -> tuple[int, dict[str, Any]]:
        """计算加权复合分数

        Args:
            weighted_inputs: {name: {"raw_score": int, "weight": float}, ...}

        Returns:
            (composite_score, weighted_scores_detail)
            weighted_scores_detail 包含每个维度的 raw_score/weight/weighted_value
        """
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
