from imu.service_contract import ServiceError, SessionRequest

from .config import HostServiceConfig
from .manager import IMUHardwareService, build_hardware_factory
from .server import run_server


def main() -> None:
    config = HostServiceConfig.from_env()
    hardware_factory = build_hardware_factory(config.backend, config.sample_file)
    service = IMUHardwareService(
        backend_name=config.backend,
        hardware_factory=hardware_factory,
        auto_tare=config.auto_tare,
        reconnect_delay_s=config.reconnect_delay_s,
        stream_queue_size=config.stream_queue_size,
    )
    service.start()

    if config.startup_session:
        try:
            service.start_session(
                SessionRequest(
                    session_id="boot-session",
                    sample_hz=config.startup_sample_hz,
                    tare=config.auto_tare,
                    reset_counter=True,
                )
            )
        except ServiceError:
            pass

    try:
        run_server(config.socket_path, service)
    finally:
        service.close()


if __name__ == "__main__":
    main()
