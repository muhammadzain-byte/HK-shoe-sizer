from __future__ import annotations

from app.services.research_model_service import ResearchModelService


def test_research_model_service_stays_disabled_by_default() -> None:
    service = ResearchModelService(enabled=False)

    assert service.is_enabled() is False
    assert service.score_mask_quality_debug([0.0])["enabled"] is False


def test_research_model_service_does_not_override_hard_gates() -> None:
    result = ResearchModelService(enabled=False).score_mask_quality_debug([0.0])

    assert result["hard_gate_override"] is False
