from dataclasses import dataclass
from typing import Any

from typing_extensions import override


@dataclass
class IMUData:
    """Convenience class for keeping data read from the IMU"""

    counter: int
    capture_time_ms: int
    recorded_at_time_ms: int

    accel_x: float
    accel_y: float
    accel_z: float

    gyro_x: float
    gyro_y: float
    gyro_z: float

    mag_x: float
    mag_y: float
    mag_z: float

    yaw: float
    pitch: float
    roll: float

    def to_dict(self) -> dict[str, float | int]:
        return {
            "counter": self.counter,
            "capture_time_ms": self.capture_time_ms,
            "recorded_at_time_ms": self.recorded_at_time_ms,
            "accel_x": self.accel_x,
            "accel_y": self.accel_y,
            "accel_z": self.accel_z,
            "gyro_x": self.gyro_x,
            "gyro_y": self.gyro_y,
            "gyro_z": self.gyro_z,
            "mag_x": self.mag_x,
            "mag_y": self.mag_y,
            "mag_z": self.mag_z,
            "yaw": self.yaw,
            "pitch": self.pitch,
            "roll": self.roll,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "IMUData":
        return cls(
            int(payload["counter"]),
            int(payload["capture_time_ms"]),
            int(payload.get("recorded_at_time_ms", 0)),
            float(payload["accel_x"]),
            float(payload["accel_y"]),
            float(payload["accel_z"]),
            float(payload["gyro_x"]),
            float(payload["gyro_y"]),
            float(payload["gyro_z"]),
            float(payload["mag_x"]),
            float(payload["mag_y"]),
            float(payload["mag_z"]),
            float(payload["yaw"]),
            float(payload["pitch"]),
            float(payload["roll"]),
        )

    @override
    def __str__(self):
        return (
            f"{self.counter},{self.capture_time_ms},{self.recorded_at_time_ms},"
            + f"{self.accel_x},{self.accel_y},{self.accel_z},"
            + f"{self.gyro_x},{self.gyro_y},{self.gyro_z},{self.mag_x},{self.mag_y},"
            + f"{self.mag_z},{self.yaw},{self.pitch},{self.roll}"
        )
