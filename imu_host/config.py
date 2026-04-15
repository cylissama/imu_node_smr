from dataclasses import dataclass
import os


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default

    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class HostServiceConfig:
    socket_path: str = "/run/imu-hw/imu.sock"
    backend: str = "real"
    auto_tare: bool = False
    startup_session: bool = False
    startup_sample_hz: int = 100
    sample_file: str = "data/sample_data.csv"
    reconnect_delay_s: float = 2.0
    stream_queue_size: int = 256

    @classmethod
    def from_env(cls) -> "HostServiceConfig":
        return cls(
            socket_path=os.getenv("IMU_SOCKET_PATH", "/run/imu-hw/imu.sock"),
            backend=os.getenv("IMU_SERVICE_BACKEND", "real"),
            auto_tare=_env_flag("IMU_SERVICE_AUTO_TARE", False),
            startup_session=_env_flag("IMU_SERVICE_START_ON_BOOT", False),
            startup_sample_hz=max(1, int(os.getenv("IMU_SERVICE_SAMPLE_HZ", "100"))),
            sample_file=os.getenv("IMU_SAMPLE_FILE", "data/sample_data.csv"),
            reconnect_delay_s=float(os.getenv("IMU_RECONNECT_DELAY_S", "2.0")),
            stream_queue_size=max(
                8, int(os.getenv("IMU_STREAM_QUEUE_SIZE", "256"))
            ),
        )
