from collections.abc import Callable
import queue
import threading
import time
from typing import TYPE_CHECKING
from uuid import uuid4

from imu.IMUData import IMUData
from imu.service_contract import ServiceError, ServiceStatus, SessionRequest, sample_payload

if TYPE_CHECKING:
    from imu.BaseIMU import BaseIMU


HardwareFactory = Callable[[], "BaseIMU"]


class IMUHardwareService:
    def __init__(
        self,
        backend_name: str,
        hardware_factory: HardwareFactory,
        auto_tare: bool = False,
        reconnect_delay_s: float = 2.0,
        stream_queue_size: int = 256,
    ):
        self.backend_name = backend_name
        self._hardware_factory = hardware_factory
        self._auto_tare = auto_tare
        self._reconnect_delay_s = reconnect_delay_s
        self._stream_queue_size = stream_queue_size

        self._imu = None
        self._imu_lock = threading.Lock()
        self._state = "starting"
        self._session_id: str | None = None
        self._sample_hz = 100
        self._session_active = False
        self._tare_applied = False
        self._last_sample: IMUData | None = None
        self._last_sample_time_ms: int | None = None
        self._last_error_code: str | None = None
        self._last_error_message: str | None = None
        self._subscribers: dict[int, queue.Queue[dict]] = {}
        self._subscriber_lock = threading.Lock()
        self._wake_event = threading.Event()
        self._stop_event = threading.Event()
        self._worker = threading.Thread(target=self._run, daemon=True, name="imu-hw")
        self._next_stream_id = 0

    def start(self) -> None:
        self._ensure_connected()
        self._worker.start()

    def close(self) -> None:
        self._stop_event.set()
        self._wake_event.set()
        if self._worker.is_alive():
            self._worker.join(timeout=5)

    def status(self) -> ServiceStatus:
        return ServiceStatus(
            state=self._state,
            backend=self.backend_name,
            imu_connected=self._imu is not None,
            session_active=self._session_active,
            session_id=self._session_id,
            sample_hz=self._sample_hz,
            last_sample_time_ms=self._last_sample_time_ms,
            last_error_code=self._last_error_code,
            last_error_message=self._last_error_message,
            tare_applied=self._tare_applied,
            auto_tare=self._auto_tare,
            buffer_depth=len(self._subscribers),
        )

    def latest_sample(self) -> IMUData | None:
        return self._last_sample

    def register_stream(self) -> tuple[int, queue.Queue[dict]]:
        with self._subscriber_lock:
            stream_id = self._next_stream_id
            self._next_stream_id += 1
            stream_queue: queue.Queue[dict] = queue.Queue(maxsize=self._stream_queue_size)
            self._subscribers[stream_id] = stream_queue
            return stream_id, stream_queue

    def unregister_stream(self, stream_id: int) -> None:
        with self._subscriber_lock:
            self._subscribers.pop(stream_id, None)

    def start_session(self, request: SessionRequest) -> ServiceStatus:
        session_id = request.session_id or str(uuid4())
        if self._session_active:
            raise ServiceError(
                "SESSION_ALREADY_ACTIVE",
                f"Session '{self._session_id}' is already active.",
                retryable=False,
                status_code=409,
            )

        if not self._ensure_connected():
            raise ServiceError(
                "IMU_NOT_READY",
                "The IMU is not connected yet.",
                retryable=True,
                status_code=503,
            )

        with self._imu_lock:
            if request.reset_counter and self._imu is not None:
                self._imu.reset_counter()
            if request.tare:
                self._apply_tare()

        self._sample_hz = request.sample_hz
        self._session_id = session_id
        self._session_active = True
        self._state = "running"
        self._wake_event.set()
        return self.status()

    def stop_session(self) -> ServiceStatus:
        if not self._session_active:
            raise ServiceError(
                "NO_ACTIVE_SESSION",
                "There is no active session to stop.",
                retryable=False,
                status_code=409,
            )

        self._session_active = False
        self._session_id = None
        self._state = "ready" if self._imu is not None else "degraded"
        self._wake_event.set()
        return self.status()

    def tare(self) -> ServiceStatus:
        if not self._ensure_connected():
            raise ServiceError(
                "IMU_NOT_READY",
                "Cannot tare because the IMU is not connected.",
                retryable=True,
                status_code=503,
            )

        with self._imu_lock:
            self._apply_tare()

        return self.status()

    def _apply_tare(self) -> None:
        if self._imu is None or not hasattr(self._imu, "tare"):
            raise ServiceError(
                "CALIBRATION_UNSUPPORTED",
                "This backend does not support tare.",
                retryable=False,
                status_code=400,
            )

        self._imu.tare()
        self._tare_applied = True

    def _set_error(self, code: str, message: str) -> None:
        self._last_error_code = code
        self._last_error_message = message
        self._state = "degraded"

    def _clear_error(self) -> None:
        self._last_error_code = None
        self._last_error_message = None

    def _ensure_connected(self) -> bool:
        with self._imu_lock:
            if self._imu is not None:
                return True

            try:
                self._imu = self._hardware_factory()
                self._tare_applied = False
                if self._auto_tare and hasattr(self._imu, "tare"):
                    self._apply_tare()
                self._state = "ready"
                self._clear_error()
                return True
            except ServiceError:
                raise
            except Exception as error:
                self._imu = None
                self._set_error("IMU_NOT_FOUND", str(error))
                return False

    def _drop_connection(self, code: str, message: str) -> None:
        with self._imu_lock:
            self._imu = None
        self._set_error(code, message)

    def _emit_sample(self, sample: IMUData) -> None:
        payload = sample_payload(sample, session_id=self._session_id)
        self._last_sample = sample
        self._last_sample_time_ms = sample.capture_time_ms

        with self._subscriber_lock:
            queues = list(self._subscribers.values())

        for stream_queue in queues:
            try:
                stream_queue.put_nowait(payload)
            except queue.Full:
                try:
                    _ = stream_queue.get_nowait()
                except queue.Empty:
                    pass
                try:
                    stream_queue.put_nowait(payload)
                except queue.Full:
                    continue

    def _run(self) -> None:
        next_read_at = time.perf_counter()

        while not self._stop_event.is_set():
            if not self._session_active:
                self._wake_event.wait(timeout=0.25)
                self._wake_event.clear()
                next_read_at = time.perf_counter()
                continue

            if not self._ensure_connected():
                time.sleep(self._reconnect_delay_s)
                continue

            interval_s = 1.0 / max(1, self._sample_hz)

            try:
                with self._imu_lock:
                    if self._imu is None:
                        raise RuntimeError("IMU disconnected")
                    sample = self._imu.read_data()
            except Exception as error:
                self._drop_connection("READ_FAILED", str(error))
                time.sleep(self._reconnect_delay_s)
                continue

            self._emit_sample(sample)

            next_read_at += interval_s
            sleep_s = next_read_at - time.perf_counter()
            if sleep_s > 0:
                self._stop_event.wait(timeout=sleep_s)
            else:
                next_read_at = time.perf_counter()


def build_hardware_factory(backend_name: str, sample_file: str) -> HardwareFactory:
    backend = backend_name.strip().lower()

    if backend == "real":
        from imu.RealIMU import connect_imu

        return connect_imu

    if backend == "fake":
        from imu.FakeIMU import connect_imu

        return lambda: connect_imu(sample_filename=sample_file)

    raise ValueError(f"Unsupported IMU backend '{backend_name}'")
