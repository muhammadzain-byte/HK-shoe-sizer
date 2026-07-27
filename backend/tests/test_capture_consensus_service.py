from app.services.capture_consensus_service import CaptureConsensusService
from app.services.capture_quality_service import CaptureQualityAnalysis


def analysis(status: str, score: float, issue: str | None = None) -> CaptureQualityAnalysis:
    return CaptureQualityAnalysis(
        capture_status=status,
        score=score,
        issues=[issue] if issue else [],
        instructions=["Adjust capture."] if issue else [],
        frame_quality={"blur_score": 0.9, "lighting_score": 0.9, "overexposure_score": 0.9},
        foot_visibility={"foot_detected": True, "one_foot_only": True},
        pose_quality={"top_down_score": 0.9},
        distance_quality={"distance_confidence": 0.9},
        guidance={"primary_instruction": "Ready to capture.", "secondary_instructions": []},
    )


def test_stable_ready_frames_pass_consensus() -> None:
    result = CaptureConsensusService().combine([analysis("ready", 0.91), analysis("ready", 0.88)])
    assert result.analysis.capture_status == "ready"
    assert result.stability["stable"] is True


def test_one_risky_frame_needs_adjustment() -> None:
    result = CaptureConsensusService().combine(
        [analysis("ready", 0.91), analysis("needs_adjustment", 0.74, "heel_near_frame_edge")]
    )
    assert result.analysis.capture_status == "needs_adjustment"
    assert "heel_near_frame_edge" in result.analysis.issues


def test_unstable_scores_are_not_accepted() -> None:
    result = CaptureConsensusService().combine([analysis("ready", 0.95), analysis("ready", 0.7)])
    assert result.analysis.capture_status == "needs_adjustment"
    assert "capture_unstable" in result.analysis.issues
