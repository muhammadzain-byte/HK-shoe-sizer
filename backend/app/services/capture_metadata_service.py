from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.capture_session import CaptureSession
from app.models.foot_scan import FootScan
from app.models.uploaded_image import UploadedImage
from app.models.user import User
from app.schemas.capture_session import CaptureSessionRead


class CaptureMetadataService:
    """Persists guided-capture quality and device telemetry for later calibration work."""

    def __init__(self, db: Session):
        self.db = db

    def create_capture_session(
        self,
        user: User,
        capture_quality: Any,
        device_metadata: Any | None = None,
        foot_scan_id: UUID | None = None,
        uploaded_image_id: UUID | None = None,
    ) -> CaptureSession:
        if foot_scan_id:
            self._get_owned_scan(user, foot_scan_id)
        if uploaded_image_id:
            self._get_owned_image(user, uploaded_image_id)

        quality_payload = self.normalize_capture_quality(capture_quality)
        metadata_payload = self.normalize_device_metadata(device_metadata)
        frame_quality = quality_payload.get("frame_quality") or {}
        foot_visibility = quality_payload.get("foot_visibility") or {}
        pose_quality = quality_payload.get("pose_quality") or {}
        distance_quality = quality_payload.get("distance_quality") or {}
        guidance = quality_payload.get("guidance") or {}
        orientation = metadata_payload.get("orientation") or {}
        user_agent = metadata_payload.get("user_agent")

        session = CaptureSession(
            user_id=user.id,
            foot_scan_id=foot_scan_id,
            uploaded_image_id=uploaded_image_id,
            capture_status=str(quality_payload.get("capture_status") or "needs_adjustment"),
            capture_quality_score=self._float_or_default(quality_payload.get("score"), 0.0),
            primary_instruction=guidance.get("primary_instruction"),
            issues=list(quality_payload.get("issues") or []),
            instructions=list(quality_payload.get("instructions") or []),
            blur_score=self._float_or_none(frame_quality.get("blur_score")),
            lighting_score=self._float_or_none(frame_quality.get("lighting_score")),
            overexposure_score=self._float_or_none(frame_quality.get("overexposure_score")),
            foot_detected=self._bool_or_none(foot_visibility.get("foot_detected")),
            one_foot_only=self._bool_or_none(foot_visibility.get("one_foot_only")),
            toes_visible=self._bool_or_none(foot_visibility.get("toes_visible")),
            heel_visible=self._bool_or_none(foot_visibility.get("heel_visible")),
            full_foot_visible=self._bool_or_none(foot_visibility.get("full_foot_visible")),
            lower_leg_ratio=self._float_or_none(foot_visibility.get("lower_leg_ratio")),
            toe_margin_ratio=self._float_or_none(foot_visibility.get("toe_margin_ratio")),
            heel_margin_ratio=self._float_or_none(foot_visibility.get("heel_margin_ratio")),
            side_margin_ratio=self._float_or_none(foot_visibility.get("side_margin_ratio")),
            top_down_score=self._float_or_none(pose_quality.get("top_down_score")),
            rotation_angle_degrees=self._float_or_none(pose_quality.get("rotation_angle_degrees")),
            perspective_risk=self._float_or_none(pose_quality.get("perspective_risk")),
            foot_flatness_risk=self._float_or_none(pose_quality.get("foot_flatness_risk")),
            foot_frame_coverage=self._float_or_none(distance_quality.get("foot_frame_coverage")),
            too_close=self._bool_or_none(distance_quality.get("too_close")),
            too_far=self._bool_or_none(distance_quality.get("too_far")),
            distance_confidence=self._float_or_none(distance_quality.get("distance_confidence")),
            user_agent=user_agent,
            browser=self.browser_from_user_agent(user_agent),
            os=self.os_from_user_agent(user_agent),
            device_type=self.device_type_from_metadata(metadata_payload),
            device_family=self.device_family_from_user_agent(user_agent),
            viewport_width=self._int_or_none(metadata_payload.get("viewport_width")),
            viewport_height=self._int_or_none(metadata_payload.get("viewport_height")),
            video_width=self._int_or_none(metadata_payload.get("video_width")),
            video_height=self._int_or_none(metadata_payload.get("video_height")),
            device_pixel_ratio=self._float_or_none(metadata_payload.get("device_pixel_ratio")),
            facing_mode=metadata_payload.get("facing_mode"),
            orientation_alpha=self._float_or_none(orientation.get("alpha")),
            orientation_beta=self._float_or_none(orientation.get("beta")),
            orientation_gamma=self._float_or_none(orientation.get("gamma")),
            motion=metadata_payload.get("motion"),
            raw_device_metadata=metadata_payload,
            raw_capture_quality_result=quality_payload,
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def get_capture_session(self, user: User, capture_session_id: UUID) -> CaptureSession:
        session = self.db.scalar(
            select(CaptureSession).where(
                CaptureSession.id == capture_session_id,
                CaptureSession.user_id == user.id,
            )
        )
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Capture session not found.")
        return session

    def list_user_capture_sessions(
        self,
        user: User,
        limit: int = 25,
        offset: int = 0,
    ) -> tuple[list[CaptureSession], int]:
        total = self.db.scalar(
            select(func.count()).select_from(CaptureSession).where(CaptureSession.user_id == user.id)
        )
        sessions = list(
            self.db.scalars(
                select(CaptureSession)
                .where(CaptureSession.user_id == user.id)
                .order_by(CaptureSession.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
        )
        return sessions, total or 0

    def list_scan_capture_sessions(
        self,
        user: User,
        scan_id: UUID,
        limit: int = 25,
        offset: int = 0,
    ) -> tuple[list[CaptureSession], int]:
        self._get_owned_scan(user, scan_id)
        total = self.db.scalar(
            select(func.count())
            .select_from(CaptureSession)
            .where(CaptureSession.user_id == user.id, CaptureSession.foot_scan_id == scan_id)
        )
        sessions = list(
            self.db.scalars(
                select(CaptureSession)
                .where(CaptureSession.user_id == user.id, CaptureSession.foot_scan_id == scan_id)
                .order_by(CaptureSession.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
        )
        return sessions, total or 0

    def attach_uploaded_image(
        self,
        user: User,
        capture_session_id: UUID,
        uploaded_image_id: UUID,
    ) -> CaptureSession:
        session = self.get_capture_session(user, capture_session_id)
        self._get_owned_image(user, uploaded_image_id)
        session.uploaded_image_id = uploaded_image_id
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def attach_foot_scan(
        self,
        user: User,
        capture_session_id: UUID,
        foot_scan_id: UUID,
    ) -> CaptureSession:
        session = self.get_capture_session(user, capture_session_id)
        self._get_owned_scan(user, foot_scan_id)
        session.foot_scan_id = foot_scan_id
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def attach(
        self,
        user: User,
        capture_session_id: UUID,
        foot_scan_id: UUID | None = None,
        uploaded_image_id: UUID | None = None,
    ) -> CaptureSession:
        session = self.get_capture_session(user, capture_session_id)
        if foot_scan_id:
            self._get_owned_scan(user, foot_scan_id)
            session.foot_scan_id = foot_scan_id
        if uploaded_image_id:
            self._get_owned_image(user, uploaded_image_id)
            session.uploaded_image_id = uploaded_image_id
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def to_read(self, session: CaptureSession) -> CaptureSessionRead:
        return CaptureSessionRead(
            id=session.id,
            user_id=session.user_id,
            foot_scan_id=session.foot_scan_id,
            uploaded_image_id=session.uploaded_image_id,
            capture_status=session.capture_status,
            capture_quality_score=session.capture_quality_score,
            primary_instruction=session.primary_instruction,
            issues=session.issues or [],
            instructions=session.instructions or [],
            frame_quality={
                "blur_score": session.blur_score,
                "lighting_score": session.lighting_score,
                "overexposure_score": session.overexposure_score,
            },
            foot_visibility={
                "foot_detected": session.foot_detected,
                "one_foot_only": session.one_foot_only,
                "toes_visible": session.toes_visible,
                "heel_visible": session.heel_visible,
                "full_foot_visible": session.full_foot_visible,
                "lower_leg_ratio": session.lower_leg_ratio,
                "toe_margin_ratio": session.toe_margin_ratio,
                "heel_margin_ratio": session.heel_margin_ratio,
                "side_margin_ratio": session.side_margin_ratio,
            },
            pose_quality={
                "top_down_score": session.top_down_score,
                "rotation_angle_degrees": session.rotation_angle_degrees,
                "perspective_risk": session.perspective_risk,
                "foot_flatness_risk": session.foot_flatness_risk,
            },
            distance_quality={
                "foot_frame_coverage": session.foot_frame_coverage,
                "too_close": session.too_close,
                "too_far": session.too_far,
                "distance_confidence": session.distance_confidence,
            },
            device_metadata={
                "user_agent": session.user_agent,
                "browser": session.browser,
                "os": session.os,
                "device_type": session.device_type,
                "device_family": session.device_family,
                "viewport_width": session.viewport_width,
                "viewport_height": session.viewport_height,
                "video_width": session.video_width,
                "video_height": session.video_height,
                "device_pixel_ratio": session.device_pixel_ratio,
                "facing_mode": session.facing_mode,
                "orientation": {
                    "alpha": session.orientation_alpha,
                    "beta": session.orientation_beta,
                    "gamma": session.orientation_gamma,
                },
                "motion": session.motion or {},
                "timestamp": (session.raw_device_metadata or {}).get("timestamp"),
                "reference_mode": (session.raw_device_metadata or {}).get("reference_mode"),
                "capture_mode": (session.raw_device_metadata or {}).get("capture_mode", "browser_guidance"),
                "ar_evidence": (session.raw_device_metadata or {}).get("ar_evidence"),
            },
            created_at=session.created_at,
        )

    def normalize_capture_quality(self, capture_quality: Any) -> dict[str, Any]:
        if capture_quality is None:
            return {}
        if isinstance(capture_quality, BaseModel):
            return capture_quality.model_dump(mode="json")
        if hasattr(capture_quality, "to_dict"):
            return capture_quality.to_dict()
        if isinstance(capture_quality, dict):
            return dict(capture_quality)
        raise TypeError("capture_quality must be a dict, Pydantic model, or CaptureQualityAnalysis.")

    def normalize_device_metadata(self, device_metadata: Any | None) -> dict[str, Any]:
        if device_metadata is None:
            return {}
        if isinstance(device_metadata, BaseModel):
            return device_metadata.model_dump(mode="json")
        if isinstance(device_metadata, dict):
            return dict(device_metadata)
        raise TypeError("device_metadata must be a dict or Pydantic model.")

    def browser_from_user_agent(self, user_agent: str | None) -> str | None:
        if not user_agent:
            return None
        value = user_agent.lower()
        if "edg/" in value:
            return "Edge"
        if "firefox/" in value:
            return "Firefox"
        if "chrome/" in value or "crios/" in value:
            return "Chrome"
        if "safari/" in value:
            return "Safari"
        return "Unknown"

    def os_from_user_agent(self, user_agent: str | None) -> str | None:
        if not user_agent:
            return None
        value = user_agent.lower()
        if "android" in value:
            return "Android"
        if "iphone" in value or "ipad" in value or "ios" in value:
            return "iOS"
        if "windows" in value:
            return "Windows"
        if "mac os" in value or "macintosh" in value:
            return "macOS"
        if "linux" in value:
            return "Linux"
        return "Unknown"

    def device_family_from_user_agent(self, user_agent: str | None) -> str | None:
        if not user_agent:
            return None
        value = user_agent.lower()
        if "iphone" in value:
            return "iPhone"
        if "ipad" in value:
            return "iPad"
        if "android" in value:
            return "Android"
        if "windows" in value:
            return "Windows"
        if "macintosh" in value or "mac os" in value:
            return "Mac"
        return "Unknown"

    def device_type_from_metadata(self, metadata: dict[str, Any]) -> str | None:
        user_agent = str(metadata.get("user_agent") or "").lower()
        if "mobile" in user_agent or "iphone" in user_agent or "android" in user_agent:
            return "mobile"
        if "ipad" in user_agent or "tablet" in user_agent:
            return "tablet"
        viewport_width = self._int_or_none(metadata.get("viewport_width"))
        if viewport_width is not None and viewport_width < 768:
            return "mobile"
        if viewport_width is not None:
            return "desktop"
        return None

    def _get_owned_scan(self, user: User, scan_id: UUID) -> FootScan:
        scan = self.db.scalar(select(FootScan).where(FootScan.id == scan_id, FootScan.user_id == user.id))
        if not scan:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan not found.")
        return scan

    def _get_owned_image(self, user: User, uploaded_image_id: UUID) -> UploadedImage:
        image = self.db.scalar(
            select(UploadedImage).where(
                UploadedImage.id == uploaded_image_id,
                UploadedImage.user_id == user.id,
            )
        )
        if not image:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found.")
        return image

    def _float_or_default(self, value: Any, default: float) -> float:
        parsed = self._float_or_none(value)
        return parsed if parsed is not None else default

    def _float_or_none(self, value: Any) -> float | None:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _int_or_none(self, value: Any) -> int | None:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _bool_or_none(self, value: Any) -> bool | None:
        if value is None:
            return None
        return bool(value)
