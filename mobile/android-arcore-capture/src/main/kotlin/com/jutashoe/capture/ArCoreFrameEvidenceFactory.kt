package com.jutashoe.capture

/**
 * Adapter boundary for the Android app. The app passes values from the same
 * ARCore frame used to capture the RGB image, preventing cross-frame scale.
 */
object ArCoreFrameEvidenceFactory {
    fun create(
        focalLengthX: Float,
        focalLengthY: Float,
        principalPointX: Float,
        principalPointY: Float,
        imageWidth: Int,
        imageHeight: Int,
        distanceToFloorMeters: Float,
        distanceToFootPlaneMeters: Float,
        planeConfidence: Float,
        depthConfidence: Float,
        timestamp: Long,
        sourceDevice: String,
        trackingFrames: Int,
    ) = ArEvidence(
        depthAvailable = true,
        cameraIntrinsics = CameraIntrinsicsEvidence(
            focalLengthX, focalLengthY, principalPointX, principalPointY, imageWidth, imageHeight,
        ),
        distanceToFloorMm = distanceToFloorMeters * 1000f,
        distanceToFootPlaneMm = distanceToFootPlaneMeters * 1000f,
        planeConfidence = planeConfidence,
        depthConfidence = depthConfidence,
        timestamp = timestamp,
        sourceDevice = sourceDevice,
        trackingFrames = trackingFrames,
    )
}
