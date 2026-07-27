from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.services.capture_quality_service import CaptureQualityAnalysis


@dataclass(frozen=True)
class CaptureConsensusResult:
    """Conservative multi-frame gate used before a camera image can be accepted."""

    analysis: CaptureQualityAnalysis
    stability: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        payload = self.analysis.to_dict()
        payload["stability"] = self.stability
        return payload


class CaptureConsensusService:
    """Combines nearby capture frames without allowing a single lucky frame to pass."""

    def combine(self, analyses: list[CaptureQualityAnalysis]) -> CaptureConsensusResult:
        if not analyses:
            raise ValueError("At least one capture-quality analysis is required.")

        scores = [analysis.score for analysis in analyses]
        score_spread = max(scores) - min(scores)
        ready_count = sum(analysis.capture_status == "ready" for analysis in analyses)
        reject_count = sum(analysis.capture_status == "reject" for analysis in analyses)
        stable = score_spread <= 0.12
        best = max(analyses, key=lambda analysis: analysis.score)
        all_issues = self._dedupe([issue for analysis in analyses for issue in analysis.issues])
        all_instructions = self._dedupe(
            [instruction for analysis in analyses for instruction in analysis.instructions]
        )

        # A multi-frame capture is accepted only when every nearby frame independently passes.
        if len(analyses) > 1 and ready_count == len(analyses) and stable:
            status = "ready"
            primary = "Capture is stable and ready."
        elif reject_count == len(analyses):
            status = "reject"
            primary = all_instructions[0] if all_instructions else "Retake the photo."
        else:
            status = "needs_adjustment"
            if not stable:
                all_issues.append("capture_unstable")
                all_instructions.insert(0, "Hold the phone still and keep the foot in the same position.")
            primary = all_instructions[0] if all_instructions else "Adjust and hold steady before capturing."

        penalty = min(score_spread * 0.5, 0.12)
        consensus_score = round(max(0.0, sum(scores) / len(scores) - penalty), 4)
        analysis = CaptureQualityAnalysis(
            capture_status=status,
            score=consensus_score,
            issues=self._dedupe(all_issues),
            instructions=self._dedupe(all_instructions),
            frame_quality=best.frame_quality,
            foot_visibility=best.foot_visibility,
            pose_quality=best.pose_quality,
            distance_quality=best.distance_quality,
            guidance={
                "primary_instruction": primary,
                "secondary_instructions": self._dedupe(
                    [instruction for instruction in all_instructions if instruction != primary]
                )[:3],
            },
        )
        return CaptureConsensusResult(
            analysis=analysis,
            stability={
                "frame_count": len(analyses),
                "ready_frame_count": ready_count,
                "rejected_frame_count": reject_count,
                "score_spread": round(score_spread, 4),
                "stable": stable,
                "mode": "multi_frame" if len(analyses) > 1 else "single_frame",
            },
        )

    @staticmethod
    def _dedupe(values: list[str]) -> list[str]:
        return list(dict.fromkeys(values))
