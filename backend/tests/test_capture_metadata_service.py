from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

from app.models.capture_session import CaptureSession
from app.services.capture_metadata_service import CaptureMetadataService


def quality_payload() -> dict:
    return {
        "capture_status": "needs_adjustment",
        "score": 0.74,
        "issues": ["lower_leg_too_visible"],
        "instructions": ["Move your leg back; too much lower leg is visible."],
        "frame_quality": {
            "blur_score": 0.91,
            "lighting_score": 0.82,
            "overexposure_score": 0.97,
        },
        "foot_visibility": {
            "foot_detected": True,
            "one_foot_only": True,
            "toes_visible": True,
            "heel_visible": True,
            "full_foot_visible": True,
            "lower_leg_ratio": 0.31,
            "toe_margin_ratio": 0.08,
            "heel_margin_ratio": 0.07,
            "side_margin_ratio": 0.11,
        },
        "pose_quality": {
            "top_down_score": 0.86,
            "rotation_angle_degrees": 2.0,
            "perspective_risk": 0.14,
            "foot_flatness_risk": 0.1,
        },
        "distance_quality": {
            "foot_frame_coverage": 0.26,
            "too_close": False,
            "too_far": False,
            "distance_confidence": 0.88,
        },
        "guidance": {
            "primary_instruction": "Move your leg back; too much lower leg is visible.",
            "secondary_instructions": ["Hold phone directly above the foot."],
        },
    }


def device_metadata() -> dict:
    return {
        "user_agent": (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
            "AppleWebKit/605.1.15 Version/17.0 Mobile/15E148 Safari/604.1"
        ),
        "viewport_width": 390,
        "viewport_height": 844,
        "video_width": 1920,
        "video_height": 1080,
        "device_pixel_ratio": 3,
        "facing_mode": "environment",
        "orientation": {"alpha": 1.0, "beta": 4.0, "gamma": 2.0},
        "motion": {"available": False},
        "timestamp": "2026-06-15T10:00:00.000Z",
    }


class FakeScalarResult:
    def __init__(self, values: list) -> None:
        self.values = values

    def __iter__(self):
        return iter(self.values)


class FakeDb:
    def __init__(self, scalar_values: list | None = None, scalars_values: list | None = None) -> None:
        self.scalar_values = scalar_values or []
        self.scalars_values = scalars_values or []
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
        if getattr(value, "created_at", None) is None:
            value.created_at = datetime.now(UTC)
        if getattr(value, "updated_at", None) is None:
            value.updated_at = datetime.now(UTC)
        self.refreshed = value

    def scalar(self, _statement):
        return self.scalar_values.pop(0) if self.scalar_values else None

    def scalars(self, _statement):
        values = self.scalars_values.pop(0) if self.scalars_values else []
        return FakeScalarResult(values)


def user(user_id: UUID | None = None):
    return SimpleNamespace(id=user_id or uuid4())


def persisted_session(owner_id: UUID) -> CaptureSession:
    session = CaptureSession(
        user_id=owner_id,
        capture_status="ready",
        capture_quality_score=0.93,
        issues=[],
        instructions=[],
    )
    session.id = uuid4()
    session.created_at = datetime.now(UTC)
    session.updated_at = datetime.now(UTC)
    return session


def test_create_capture_session_flattens_device_and_quality_payload() -> None:
    current_user = user()
    db = FakeDb()
    service = CaptureMetadataService(db)

    session = service.create_capture_session(
        current_user,
        capture_quality=quality_payload(),
        device_metadata=device_metadata(),
    )

    assert db.added is session
    assert db.committed is True
    assert db.refreshed is session
    assert session.user_id == current_user.id
    assert session.capture_status == "needs_adjustment"
    assert session.capture_quality_score == 0.74
    assert session.primary_instruction == "Move your leg back; too much lower leg is visible."
    assert session.blur_score == 0.91
    assert session.lower_leg_ratio == 0.31
    assert session.top_down_score == 0.86
    assert session.foot_frame_coverage == 0.26
    assert session.browser == "Safari"
    assert session.os == "iOS"
    assert session.device_type == "mobile"
    assert session.device_family == "iPhone"
    assert session.video_width == 1920
    assert session.orientation_beta == 4.0
    assert session.raw_capture_quality_result["issues"] == ["lower_leg_too_visible"]


def test_capture_session_read_schema_reconstructs_nested_payloads() -> None:
    current_user = user()
    db = FakeDb()
    service = CaptureMetadataService(db)
    session = service.create_capture_session(current_user, quality_payload(), device_metadata())

    payload = service.to_read(session)

    assert payload.id == session.id
    assert payload.issues == ["lower_leg_too_visible"]
    assert payload.frame_quality.blur_score == 0.91
    assert payload.foot_visibility.lower_leg_ratio == 0.31
    assert payload.device_metadata.facing_mode == "environment"
    assert payload.device_metadata.browser == "Safari"


def test_missing_or_other_user_capture_session_is_rejected() -> None:
    service = CaptureMetadataService(FakeDb())

    with pytest.raises(HTTPException) as exc:
        service.get_capture_session(user(), uuid4())

    assert exc.value.status_code == 404


def test_attach_scan_and_uploaded_image_updates_owned_session() -> None:
    current_user = user()
    session = persisted_session(current_user.id)
    scan = SimpleNamespace(id=uuid4(), user_id=current_user.id)
    image = SimpleNamespace(id=uuid4(), user_id=current_user.id)
    db = FakeDb(scalar_values=[session, scan, image])
    service = CaptureMetadataService(db)

    attached = service.attach(current_user, session.id, foot_scan_id=scan.id, uploaded_image_id=image.id)

    assert attached.foot_scan_id == scan.id
    assert attached.uploaded_image_id == image.id
    assert db.added is session
    assert db.committed is True


def test_user_agent_helpers_classify_unknown_values_safely() -> None:
    service = CaptureMetadataService(FakeDb())

    assert service.browser_from_user_agent(None) is None
    assert service.os_from_user_agent("SomeBot/1.0") == "Unknown"
    assert service.device_family_from_user_agent("SomeBot/1.0") == "Unknown"
    assert service.device_type_from_metadata({"viewport_width": 1200}) == "desktop"
