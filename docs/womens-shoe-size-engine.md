# Women's Shoe Size Engine

## What Was Built

Phase 4E adds a women-only generic shoe size engine. It supports EU, US, UK, and PK/common local charts stored as editable JSON under `backend/app/data/size_charts`.

The engine is not a brand recommendation system and does not claim production accuracy.

## Safety Gates

The engine blocks recommendations unless all of these are true:

- Capture quality is not rejected.
- Measurement status is `trusted`.
- Scale status is `available`.
- Scale confidence is at least `0.85`.
- Foot length and width in millimeters exist.
- Gender is women/woman.
- Region is supported.

## Generic Charts

The current charts are generic starting points with explicit source notes. Brand-specific sizing, customer fit feedback, and local retailer validation are future work.

## Width Category

Width is reported as advisory:

- `narrow`
- `regular`
- `wide`

Wide or narrow results add fit notes instead of pretending a generic chart can guarantee fit.

## Fit And Shoe Type

Fit preference and shoe type can adjust the effective length slightly:

- `snug`
- `regular`
- `relaxed`
- `flat`
- `heel`
- `sandal`
- `sneaker`
- `khussa`
- `formal`

These adjustments are conservative and advisory.

## Unsafe Behavior

It is unsafe to recommend shoe size from pixels alone. It is unsafe to recommend when measurement is `needs_review`, `failed_quality_gate`, or scale is unavailable/low confidence.

## Future Work

Future phases can add brand chart uploads, regional validation, and user fit feedback. Those should remain blocked behind trusted measurement and trusted scale.
