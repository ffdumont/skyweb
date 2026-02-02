"""Generic service result wrapper."""

from datetime import datetime, timezone
from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ServiceError(BaseModel):
    """Structured error from a service call."""

    code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable error message")
    details: dict[str, str | int | float | bool | None] | None = None


class ServiceResult(BaseModel, Generic[T]):
    """Generic wrapper for service responses.

    On success: ``data`` is populated.
    On failure: ``error`` is populated with structured error info.
    """

    success: bool
    data: T | None = None
    error: ServiceError | None = None
    duration_ms: float | None = Field(default=None, ge=0)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))

    @classmethod
    def ok(cls, data: T, duration_ms: float | None = None) -> "ServiceResult[T]":
        return cls(success=True, data=data, duration_ms=duration_ms)

    @classmethod
    def fail(
        cls, code: str, message: str, **details: str | int | float | bool | None
    ) -> "ServiceResult[T]":
        return cls(
            success=False,
            error=ServiceError(code=code, message=message, details=details or None),
        )
