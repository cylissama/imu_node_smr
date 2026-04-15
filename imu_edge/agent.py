import signal
import time

from imu.DataWriter import DataWriter
from imu.service_contract import ServiceError, SessionRequest

from .config import EdgeAgentConfig
from .health import EdgeHealthTracker
from .service_client import LocalIMUServiceClient


class EdgeAgent:
    def __init__(self, config: EdgeAgentConfig):
        self.config = config
        self.client = LocalIMUServiceClient(config.socket_path)
        self.health = EdgeHealthTracker(config.health_path)
        self._stop_requested = False

    def install_signal_handlers(self) -> None:
        def _handle_signal(_signum, _frame):
            self._stop_requested = True

        signal.signal(signal.SIGINT, _handle_signal)
        signal.signal(signal.SIGTERM, _handle_signal)

    def run(self) -> None:
        self.install_signal_handlers()

        with DataWriter(
            csv_fname=self.config.csv_path or DataWriter.DEFAULT_CSV_FNAME,
            mqtt_broker_ip=self.config.mqtt_broker_ip,
            mqtt_broker_port=self.config.mqtt_broker_port,
            device_id=self.config.device_id,
        ) as writer:
            while not self._stop_requested:
                try:
                    self._wait_until_ready()
                    if self.config.start_session_on_boot:
                        self._start_session()

                    with self.client.stream() as stream:
                        for sample in stream:
                            if self._stop_requested:
                                break

                            writer.write_data(sample)
                            self.health.update(
                                state="streaming",
                                session_id=self.config.session_id,
                                last_capture_time_ms=sample.capture_time_ms,
                                last_counter=sample.counter,
                            )
                except ServiceError as error:
                    self.health.update(
                        state="degraded",
                        error_code=error.code,
                        error_message=error.message,
                    )
                    time.sleep(self.config.reconnect_delay_s)
                except Exception as error:
                    self.health.update(
                        state="degraded",
                        error_code="EDGE_FAILURE",
                        error_message=str(error),
                    )
                    time.sleep(self.config.reconnect_delay_s)

        if self.config.stop_session_on_exit:
            try:
                self.client.stop_session()
            except ServiceError:
                pass

    def _wait_until_ready(self) -> None:
        while not self._stop_requested:
            try:
                ready = self.client.readiness()
            except OSError as error:
                self.health.update(
                    state="waiting",
                    error_code="SERVICE_UNAVAILABLE",
                    error_message=str(error),
                )
                time.sleep(self.config.reconnect_delay_s)
                continue
            except ServiceError as error:
                self.health.update(
                    state="waiting",
                    error_code=error.code,
                    error_message=error.message,
                )
                time.sleep(self.config.reconnect_delay_s)
                continue

            if ready.get("ready"):
                return

            time.sleep(self.config.reconnect_delay_s)

    def _start_session(self) -> None:
        request = SessionRequest(
            session_id=self.config.session_id,
            sample_hz=self.config.sample_hz,
            tare=self.config.request_tare,
            reset_counter=self.config.reset_counter,
        )

        try:
            self.client.start_session(request)
        except ServiceError as error:
            if error.code != "SESSION_ALREADY_ACTIVE":
                raise
