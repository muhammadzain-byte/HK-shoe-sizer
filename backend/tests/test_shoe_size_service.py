from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.models.shoe_recommendation import ShoeRecommendation
from app.schemas.shoe_size import ShoeSizeRequest
from app.services.shoe_recommendation_persistence_service import ShoeRecommendationPersistenceService
from app.services.shoe_size_service import ShoeSizeService


def valid_request(region: str = "EU", width: float = 90.0, fit: str = "regular") -> dict:
    return {
        "region": region,
        "gender": "women",
        "fit_preference": fit,
        "shoe_type": "flat",
        "foot_length_mm": 242.0,
        "foot_width_mm": width,
        "measurement_status": "trusted",
        "scale_status": "available",
        "scale_confidence": 0.92,
    }


def test_blocks_if_measurement_status_not_trusted() -> None:
    payload = {**valid_request(), "measurement_status": "needs_review"}

    result = ShoeSizeService().recommend_size(payload)

    assert result.recommendation_status == "blocked_by_measurement_quality"
    assert result.recommended_size is None


def test_blocks_if_scale_unavailable() -> None:
    payload = {**valid_request(), "scale_status": "unavailable"}

    result = ShoeSizeService().recommend_size(payload)

    assert result.recommendation_status == "blocked_by_scale"
    assert result.blocked_reason == "Scale is unavailable, so real-world size is blocked."


def test_blocks_if_scale_confidence_low() -> None:
    payload = {**valid_request(), "scale_confidence": 0.4}

    result = ShoeSizeService().recommend_size(payload)

    assert result.recommendation_status == "blocked_by_scale"
    assert "confidence" in result.blocked_reason.lower()


def test_blocks_if_foot_length_missing() -> None:
    payload = {**valid_request(), "foot_length_mm": None}

    result = ShoeSizeService().recommend_size(payload)

    assert result.recommendation_status == "blocked_by_scale"


def test_blocks_non_women_gender() -> None:
    payload = {**valid_request(), "gender": "men"}

    result = ShoeSizeService().recommend_size(payload)

    assert result.recommendation_status == "unsupported"
    assert result.blocked_reason == "Only women sizing is supported."


def test_eu_women_recommendation_works_with_trusted_mm_measurement() -> None:
    result = ShoeSizeService().recommend_size(valid_request("EU"))

    assert result.recommendation_status == "recommended"
    assert result.recommended_size == "39"
    assert result.size_system == "EU"


def test_us_women_recommendation_works_with_trusted_mm_measurement() -> None:
    result = ShoeSizeService().recommend_size(valid_request("US"))

    assert result.recommendation_status == "recommended"
    assert result.size_system == "US"
    assert result.recommended_size == "8.5"


def test_uk_women_recommendation_works_with_trusted_mm_measurement() -> None:
    result = ShoeSizeService().recommend_size(valid_request("UK"))

    assert result.recommendation_status == "recommended"
    assert result.size_system == "UK"
    assert result.recommended_size == "6"


def test_pk_common_region_recommendation_works_if_chart_exists() -> None:
    result = ShoeSizeService().recommend_size(valid_request("PK"))

    assert result.recommendation_status == "recommended"
    assert result.size_system == "PK"
    assert result.recommended_size == "7"


def test_width_category_narrow_regular_wide_works() -> None:
    service = ShoeSizeService()

    assert service.recommend_size(valid_request(width=80)).width_category == "narrow"
    assert service.recommend_size(valid_request(width=90)).width_category == "regular"
    assert service.recommend_size(valid_request(width=105)).width_category == "wide"


def test_fit_preference_changes_alternates_safely() -> None:
    regular = ShoeSizeService().recommend_size(valid_request(fit="regular"))
    relaxed = ShoeSizeService().recommend_size(valid_request(fit="relaxed"))

    assert len(relaxed.alternate_sizes) >= len(regular.alternate_sizes)
    assert any("Relaxed" in note for note in relaxed.fit_notes)


def test_shoe_type_adds_notes() -> None:
    payload = {**valid_request(), "shoe_type": "khussa"}

    result = ShoeSizeService().recommend_size(payload)

    assert any("Khussa" in note for note in result.fit_notes)


class FakeDb:
    def __init__(self, scalar_value=None) -> None:
        self.scalar_value = scalar_value
        self.added = None
        self.committed = False
        self.refreshed = None

    def add(self, value) -> None:
        self.added = value

    def commit(self) -> None:
        self.committed = True

    def refresh(self, value) -> None:
        if getattr(value, "id", None) is None:
            value.id = uuid4()
        self.refreshed = value

    def scalar(self, _statement):
        return self.scalar_value


def test_recommendation_persists() -> None:
    user = SimpleNamespace(id=uuid4())
    scan_id = uuid4()
    request = ShoeSizeRequest.model_validate(valid_request())
    response = ShoeSizeService().recommend_size(request)
    db = FakeDb()

    record = ShoeRecommendationPersistenceService(db).persist_recommendation(
        user,
        scan_id,
        request,
        response,
        scale_estimate_id=uuid4(),
    )

    assert db.added is record
    assert db.committed is True
    assert record.user_id == user.id
    assert record.foot_scan_id == scan_id
    assert record.recommendation_status == "recommended"
    assert record.recommended_size == response.recommended_size


def test_user_cannot_access_another_users_recommendation() -> None:
    db = FakeDb(scalar_value=None)

    with pytest.raises(HTTPException) as exc:
        ShoeRecommendationPersistenceService(db).get_recommendation(SimpleNamespace(id=uuid4()), uuid4())

    assert exc.value.status_code == 404


def test_shoe_recommendation_model_supports_blocked_response() -> None:
    record = ShoeRecommendation(
        user_id=uuid4(),
        foot_scan_id=uuid4(),
        region="EU",
        size_value="",
        recommendation_status="blocked_by_scale",
        blocked_reason="Scale unavailable.",
    )

    assert record.recommended_size is None
    assert record.blocked_reason == "Scale unavailable."
