from dataclasses import dataclass
from typing import Any

from .IMUData import IMUData


@dataclass
class SessionRequest:
    session_id: str
    sample_hz: int = 100
    tare: bool = False
    reset_counter: bool = True

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SessionRequest":
        return cls(
            session_id=str(payload.get("session_id") or ""),
            sample_hz=max(1, int(payload.get("sample_hz", 100))),
            tare=bool(payload.get("tare", False)),
            reset_counter=bool(payload.get("reset_counter", True)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "sample_hz": self.sample_hz,
            "tare": self.tare,
            "reset_counter": self.reset_counter,
        }


@dataclass
class ServiceError(Exception):
    code: str
    message: str
    retryable: bool = False
    status_code: int = 400

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "retryable": self.retryable,
        }


@dataclass
class ServiceStatus:
    state: str
    backend: str
    imu_connected: bool
    session_active: bool
    session_id: str | None
    sample_hz: int
    last_sample_time_ms: int | None
    last_error_code: str | None
    last_error_message: str | None
    tare_applied: bool
    auto_tare: bool
    buffer_depth: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "backend": self.backend,
            "imu_connected": self.imu_connected,
            "session_active": self.session_active,
            "session_id": self.session_id,
            "sample_hz": self.sample_hz,
            "last_sample_time_ms": self.last_sample_time_ms,
            "last_error_code": self.last_error_code,
            "last_error_message": self.last_error_message,
            "tare_applied": self.tare_applied,
            "auto_tare": self.auto_tare,
            "buffer_depth": self.buffer_depth,
        }


def sample_payload(
    sample: IMUData,
    session_id: str | None,
    source: str = "imu-hw-service",
) -> dict[str, Any]:
    payload = sample.to_dict()
    payload["session_id"] = session_id
    payload["source"] = source
    return payload
