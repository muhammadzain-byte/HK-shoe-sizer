package com.jutashoe.capture

/** Payload that maps directly to the backend's DepthMetadataInput contract. */
data class CameraIntrinsicsEvidence(
    val fx: Float,
    val fy: Float,
    val cx: Float,
    val cy: Float,
    val width: Int,
    val height: Int,
)

data class ArEvidence(
    val depthAvailable: Boolean,
    val depthMode: String = "arcore",
    val cameraIntrinsics: CameraIntrinsicsEvidence,
    val distanceToFloorMm: Float,
    val distanceToFootPlaneMm: Float,
    val planeConfidence: Float,
    val depthConfidence: Float,
    val timestamp: Long,
    val sourceDevice: String,
    val trackingFrames: Int,
)

data class ArEvidenceValidation(val accepted: Boolean, val issues: List<String>)

object ArEvidenceValidator {
    private const val MIN_CONFIDENCE = 0.80f
    private const val MIN_DISTANCE_MM = 250f
    private const val MAX_DISTANCE_MM = 2500f
    private const val MIN_STABLE_FRAMES = 12

    fun validate(evidence: ArEvidence, imageWidth: Int, imageHeight: Int): ArEvidenceValidation {
        val issues = mutableListOf<String>()
        if (!evidence.depthAvailable || evidence.depthMode != "arcore") issues += "ARCore depth is unavailable."
        if (evidence.cameraIntrinsics.fx <= 0f || evidence.cameraIntrinsics.fy <= 0f) issues += "Camera focal lengths are invalid."
        if (evidence.cameraIntrinsics.width != imageWidth || evidence.cameraIntrinsics.height != imageHeight) issues += "Image dimensions do not match ARCore intrinsics."
        if (evidence.distanceToFootPlaneMm !in MIN_DISTANCE_MM..MAX_DISTANCE_MM) issues += "Camera distance is outside the supported range."
        if (evidence.planeConfidence < MIN_CONFIDENCE) issues += "Floor plane confidence is too low."
        if (evidence.depthConfidence < MIN_CONFIDENCE) issues += "Depth confidence is too low."
        if (evidence.trackingFrames < MIN_STABLE_FRAMES) issues += "AR tracking was not stable long enough."
        return ArEvidenceValidation(issues.isEmpty(), issues)
    }
}
