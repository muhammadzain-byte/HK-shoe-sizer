# Multi-Frame Capture Readiness

The camera capture flow now samples three nearby frames over roughly 360 milliseconds. The middle frame remains the uploaded image; the surrounding frames are used only for the pre-upload quality gate.

The backend evaluates each frame using the existing capture-quality service, then applies a conservative consensus rule:

- a capture is `ready` only when every submitted frame is independently ready and their scores remain within a 0.12 spread;
- a uniformly failed capture is rejected;
- any mixed result, or material instability, becomes `needs_adjustment`;
- the response includes `stability.frame_count`, ready/rejected counts, score spread, and a stable flag.

This prevents a transient, lucky frame from silently passing the capture gate. It does not create real-world scale, replace reference-object evidence, or override the measurement, landmark, scale, or shoe-size safety gates.

The API remains backward compatible. A request with only `image` keeps its single-frame behavior. The optional multipart field `supporting_images` accepts at most two additional images.
