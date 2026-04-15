from contextlib import contextmanager
import http.client
import json
import socket
from typing import Generator, Iterable

from imu.IMUData import IMUData
from imu.service_contract import ServiceError, SessionRequest


class UnixHTTPConnection(http.client.HTTPConnection):
    def __init__(self, socket_path: str, timeout: float = 10.0):
        super().__init__("localhost", timeout=timeout)
        self.socket_path = socket_path

    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        if self.timeout is not None:
            self.sock.settimeout(self.timeout)
        self.sock.connect(self.socket_path)


class LocalIMUServiceClient:
    def __init__(self, socket_path: str, timeout: float = 10.0):
        self.socket_path = socket_path
        self.timeout = timeout

    def _connection(self) -> UnixHTTPConnection:
        return UnixHTTPConnection(self.socket_path, timeout=self.timeout)

    def _request_json(self, method: str, path: str, payload: dict | None = None) -> dict:
        body = None
        headers = {}
        if payload is not None:
            body = json.dumps(payload)
            headers["Content-Type"] = "application/json"

        conn = self._connection()
        try:
            conn.request(method, path, body=body, headers=headers)
            response = conn.getresponse()
            raw = response.read()
        finally:
            conn.close()

        decoded = json.loads(raw.decode("utf-8")) if raw else {}
        if response.status >= 400:
            error_payload = decoded.get("error", {})
            raise ServiceError(
                error_payload.get("code", "HTTP_ERROR"),
                error_payload.get("message", f"HTTP {response.status}"),
                bool(error_payload.get("retryable", False)),
                response.status,
            )

        return decoded

    def health(self) -> dict:
        return self._request_json("GET", "/v1/healthz")

    def readiness(self) -> dict:
        return self._request_json("GET", "/v1/readyz")

    def status(self) -> dict:
        return self._request_json("GET", "/v1/status")

    def start_session(self, request: SessionRequest) -> dict:
        return self._request_json("POST", "/v1/session/start", request.to_dict())

    def stop_session(self) -> dict:
        return self._request_json("POST", "/v1/session/stop", {})

    def tare(self) -> dict:
        return self._request_json("POST", "/v1/actions/tare", {})

    @contextmanager
    def stream(self) -> Generator[Iterable[IMUData], None, None]:
        conn = self._connection()
        conn.request("GET", "/v1/telemetry/stream")
        response = conn.getresponse()
        if response.status >= 400:
            raw = response.read()
            decoded = json.loads(raw.decode("utf-8")) if raw else {}
            conn.close()
            error_payload = decoded.get("error", {})
            raise ServiceError(
                error_payload.get("code", "HTTP_ERROR"),
                error_payload.get("message", f"HTTP {response.status}"),
                bool(error_payload.get("retryable", False)),
                response.status,
            )

        try:
            yield self._iter_stream(response)
        finally:
            response.close()
            conn.close()

    def _iter_stream(self, response) -> Generator[IMUData, None, None]:
        while True:
            line = response.fp.readline()
            if not line:
                break

            payload = json.loads(line.decode("utf-8"))
            yield IMUData.from_dict(payload)
