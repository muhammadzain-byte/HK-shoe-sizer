# Research Models

Research models are disabled in production by default.

Set `ENABLE_RESEARCH_MODELS=true` only for explicit debug/research runs. Research model scores must never override capture, measurement, scale, or size hard gates.

Do not commit large model binaries. Keep only small metadata such as this README, `model_registry.json`, and tiny feature schemas.
