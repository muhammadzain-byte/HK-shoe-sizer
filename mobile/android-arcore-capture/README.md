# Android ARCore capture client

This module is the native Android companion contract for the hosted JUTA Size API. It is intentionally separate from the Next.js browser application: Chrome cannot reliably expose ARCore plane tracking, camera intrinsics, or metric camera-to-floor distance.

## Required environment

- Android Studio on a development machine.
- An ARCore-supported Android device with Google Play Services for AR installed.
- Current ARCore and AndroidX dependencies chosen by the Android project at build time.
- HTTPS API base URL, never a `localhost` URL.

## Capture sequence

1. Start an ARCore session with the rear camera and plane detection.
2. Wait for `TRACKING`, a stable horizontal floor plane, and a stable camera pose.
3. Capture the RGB frame and evidence in the same frame timestamp.
4. Map the ARCore frame through `ArCoreFrameEvidenceFactory`.
5. Upload the image and `capture_mode=arcore`, `ar_evidence` in the capture-quality request.
6. The server still runs capture, landmark, and scale gates. A native claim never bypasses them.

The pure Kotlin files in `src/main/kotlin` are deliberately SDK-light and testable. `ArCoreFrameEvidenceFactory` is the only ARCore-bound adapter. Add it to a normal Android app module after choosing the current supported ARCore dependency; test it on real devices before enabling no-reference sizing.

No browser, Android device, or iOS device is granted trusted millimetres merely because it reports a phone model. Real-device benchmark results remain required.
