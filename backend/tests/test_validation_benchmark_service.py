import os

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://test:test@localhost/test")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")

from app.services.validation_benchmark_service import ValidationBenchmarkService


def test_error_calculation_uses_measured_minus_ground_truth() -> None:
    service = ValidationBenchmarkService(None)  # type: ignore[arg-type]

    assert service._error(243.5, 240.0) == 3.5
    assert service._error_percent(3.5, 240.0) == 1.458
    assert service._error(None, 240.0) is None
