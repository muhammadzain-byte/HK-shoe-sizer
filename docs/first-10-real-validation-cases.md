# First 10 Real Validation Cases

Do not use synthetic images in real validation.

For each real case:

1. Measure foot length manually from longest toe to back of heel.
2. Record length in millimeters.
3. Measure width across the widest forefoot/ball area.
4. Record width in millimeters.
5. Place a credit card or A4 paper flat beside the foot.
6. Keep the reference object fully visible and on the same floor plane.
7. Open `/validation`.
8. Create a validation case.
9. Upload or capture the real foot image.
10. Enter manual measurements.
11. Select the reference object.
12. Draw the box around the reference object.
13. Save annotation.
14. Link or create a scan.
15. Mark benchmark-ready.
16. Run benchmark.
17. Record the result and blocker, if any.

Minimum testing plan:

- First smoke test: 10 real cases.
- Early validation: 30 real cases.
- Internal accuracy gate: 50+ completed cases.

Device groups:

- Android Chrome.
- iPhone Safari.
- Desktop webcam as control only.
