# Real Device Testing Checklist

Phase 5A prepares the system for real-device validation. This checklist should be filled during physical testing.

## Devices

- Android Chrome
- iPhone Safari
- Desktop webcam, only as a fallback sanity check

## Capture Scenarios

- Good lighting
- Low light
- Overexposed floor
- Foot too close
- Foot too far
- Toes cropped
- Heel cropped
- Too much lower leg
- Reference object fully visible
- Reference object cropped
- Reference object tilted
- Different floor backgrounds

## Record For Each Case

- Device and browser
- Capture status
- Primary instruction
- Measurement status
- Scale status
- Shoe recommendation status
- Manual foot length in mm
- Manual foot width in mm
- AI foot length in mm, if available
- AI foot width in mm, if available
- Length error in mm
- Width error in mm
- Notes

## Pass Guidance

Good captures should move toward `ready`, trusted measurement, and available scale when a valid reference object is present.

Bad captures should ask for a retake or review. Missing scale must block millimeters and shoe size.
