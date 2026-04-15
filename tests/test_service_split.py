from imu.service_contract import SessionRequest
from imu_host.manager import IMUHardwareService, build_hardware_factory


def test_host_service_session_lifecycle_with_fake_backend():
    hardware_factory = build_hardware_factory("fake", "data/sample_data.csv")
    service = IMUHardwareService(
        backend_name="fake",
        hardware_factory=hardware_factory,
        auto_tare=False,
    )
    service.start()

    stream_id, stream_queue = service.register_stream()
    start = service.start_session(
        SessionRequest(
            session_id="test-session",
            sample_hz=25,
            tare=False,
            reset_counter=True,
        )
    )
    assert start.session_active is True

    sample = stream_queue.get(timeout=2)
    assert sample["counter"] == 0
    assert sample["session_id"] == "test-session"
    assert sample["capture_time_ms"] > 0

    stop = service.stop_session()
    assert stop.session_active is False

    service.unregister_stream(stream_id)
    service.close()
