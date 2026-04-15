# IMU Edge Node

This repo now supports a split IMU edge-node architecture:

1. A Pi-local hardware service owns the BNO08X connection and all I2C / GPIO logic.
2. A Docker-managed edge agent consumes telemetry from that local service and forwards it to MQTT.

The goal is to keep Raspberry Pi hardware access out of the swarm container so the container can run without privileged mode or direct device mounts.

## Runtime Roles

### Pi-local hardware service

- Entry point: `python -m imu_host`
- Owns:
  - `board`, `busio`, `adafruit_bno08x`
  - IMU connection and feature enablement
  - tare / calibration
  - the sample loop
  - local control and telemetry API over a Unix socket

### Containerized edge agent

- Entry point: `python -m imu_edge`
- Owns:
  - session start/stop requests to the host service
  - telemetry consumption from the local Unix socket API
  - CSV output
  - MQTT publishing
  - edge health tracking for container health checks

## API Contract

The Pi-local service exposes a Unix domain socket API at `/run/imu-hw/imu.sock` by default.

- `GET /v1/healthz`
- `GET /v1/readyz`
- `GET /v1/status`
- `GET /v1/telemetry/latest`
- `GET /v1/telemetry/stream`
- `POST /v1/session/start`
- `POST /v1/session/stop`
- `POST /v1/actions/tare`

Session start payload:

```json
{
  "session_id": "imu-node-83",
  "sample_hz": 100,
  "tare": true,
  "reset_counter": true
}
```

Telemetry stream format is NDJSON. Each line contains:

```json
{
  "session_id": "imu-node-83",
  "source": "imu-hw-service",
  "counter": 0,
  "capture_time_ms": 1711111111111,
  "recorded_at_time_ms": 0,
  "accel_x": 0.0,
  "accel_y": 0.0,
  "accel_z": 0.0,
  "gyro_x": 0.0,
  "gyro_y": 0.0,
  "gyro_z": 0.0,
  "mag_x": 0.0,
  "mag_y": 0.0,
  "mag_z": 0.0,
  "yaw": 0.0,
  "pitch": 0.0,
  "roll": 0.0
}
```

The edge agent preserves the existing CSV / MQTT payload order:

`counter,capture_time_ms,recorded_at_time_ms,accel_x,accel_y,accel_z,gyro_x,gyro_y,gyro_z,mag_x,mag_y,mag_z,yaw,pitch,roll,device_id`

## Running The Pi-Local Hardware Service

Install host dependencies:

```bash
pip install -r requirements-host.txt
```

Run the service directly:

```bash
python -m imu_host
```

Useful environment variables:

- `IMU_SOCKET_PATH`: Unix socket path, default `/run/imu-hw/imu.sock`
- `IMU_SERVICE_BACKEND`: `real` or `fake`
- `IMU_SERVICE_AUTO_TARE`: tare when the hardware connects
- `IMU_SERVICE_START_ON_BOOT`: automatically begin sampling when the host service starts
- `IMU_SERVICE_SAMPLE_HZ`: sample rate used for boot-time auto-start
- `IMU_SAMPLE_FILE`: fake-data CSV path when using the fake backend

Example systemd unit file:

- [`deploy/systemd/imu-hw.service`](deploy/systemd/imu-hw.service)

## Running The Edge Agent

Install edge dependencies:

```bash
pip install -r requirements-edge.txt
```

Run the agent directly:

```bash
python -m imu_edge
```

Helpful environment variables:

- `IMU_SOCKET_PATH`
- `IMU_SESSION_ID`
- `IMU_SAMPLE_HZ`
- `IMU_REQUEST_TARE`
- `IMU_RESET_COUNTER`
- `IMU_AUTO_START_SESSION`
- `IMU_STOP_SESSION_ON_EXIT`
- `DEVICE_ID`
- `MQTT_BROKER_IP`
- `MQTT_BROKER_PORT`
- `MQTT_TOPIC`
- `IMU_CSV_PATH`
- `IMU_EDGE_HEALTH_PATH`

Health check command:

```bash
python -m imu_edge healthcheck
```

## Docker

The container is now hardware-agnostic:

- no privileged mode
- no `/dev/i2c-1`
- no `/dev/gpiomem`
- no `board` / `adafruit_blinka` imports at runtime

Instead, the container mounts the Unix socket directory and talks to the host service.

Local compose example:

```bash
docker compose --env-file env/imu-83.env up -d --build
```

Swarm stack example:

```bash
docker stack deploy -c swarm.yml imu
```

## Direct Mode

The original direct process still exists for transition and debugging:

- `python -m imu`
- `python -m imu -u`
- `python -m imu -t`

That path still touches hardware directly and is not the recommended swarm deployment path.

## Testing

Run the test suite with:

```bash
python -m pytest -q
```
# imu_node_smr
