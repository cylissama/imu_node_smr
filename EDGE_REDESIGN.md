# IMU Edge Redesign Brief

## What Changed

The IMU node is now split into two layers:

1. Pi-local hardware service
   - Runs on the Raspberry Pi host
   - Owns all direct IMU hardware access
   - Uses the Pi-only libraries such as `board`, `busio`, and `adafruit_bno08x`
   - Starts at boot with `systemd`
   - Exposes a local Unix-socket API at `/run/imu-hw/imu.sock`

2. Swarm-managed edge container
   - Runs without privileged mode
   - Does not directly import or use Pi hardware libraries
   - Talks to the Pi-local hardware service over the Unix socket
   - Starts and stops IMU sessions
   - Receives telemetry samples from the host service
   - Publishes telemetry to MQTT
   - Writes CSV output and health state

## Why This Fixes Swarm

The old container directly touched I2C and Pi hardware detection, which depended on privileged runtime behavior and Raspberry Pi platform detection inside the container.

The new container is hardware-agnostic. It only assumes:

- a local socket exists at `/run/imu-hw/imu.sock`
- the host IMU service is running
- the host IMU service can provide session control and telemetry

That makes the container much more compatible with Docker Swarm.

## What The Pi-Local Service Does

The host service:

- initializes the IMU connection
- enables IMU features
- optionally tares the device
- starts and stops capture sessions
- reads sensor data continuously
- exposes current status
- streams telemetry to local clients
- retries if the hardware disappears or read errors occur

Recommended host startup:

```bash
python -m imu_host
```

Recommended boot-time management:

- install the `systemd` unit at `deploy/systemd/imu-hw.service`
- enable and start it with `systemctl`

## What The Container Must Do To Activate The IMU

The container no longer activates the IMU by opening I2C directly.

Instead, the container activates the IMU workflow by calling the host service API:

1. wait for the host service to become ready
   - `GET /v1/readyz`
2. start a session
   - `POST /v1/session/start`
3. provide a session request payload like:

```json
{
  "session_id": "imu-node-83",
  "sample_hz": 100,
  "tare": true,
  "reset_counter": true
}
```

4. connect to the telemetry stream
   - `GET /v1/telemetry/stream`
5. for each sample received:
   - set `recorded_at_time_ms`
   - publish to MQTT
   - optionally write to CSV
6. optionally stop the session on shutdown
   - `POST /v1/session/stop`

In this repo, that behavior is implemented by:

- host service: `imu_host/`
- edge container agent: `imu_edge/`

## Local API Contract

The Pi-local service exposes these endpoints:

- `GET /v1/healthz`
- `GET /v1/readyz`
- `GET /v1/status`
- `GET /v1/telemetry/latest`
- `GET /v1/telemetry/stream`
- `POST /v1/session/start`
- `POST /v1/session/stop`
- `POST /v1/actions/tare`

Telemetry is streamed as NDJSON.

Example sample:

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

## MQTT Output

The edge container keeps the existing payload layout:

`counter,capture_time_ms,recorded_at_time_ms,accel_x,accel_y,accel_z,gyro_x,gyro_y,gyro_z,mag_x,mag_y,mag_z,yaw,pitch,roll,device_id`

The host service generates:

- `counter`
- `capture_time_ms`
- sensor values

The edge container adds:

- `recorded_at_time_ms`
- `device_id`
- MQTT forwarding behavior

## Container Runtime Requirements

The container should:

- mount `/run/imu-hw` from the host
- read `IMU_SOCKET_PATH`
- wait for the host service to be ready
- request a session start
- reconnect if the stream drops
- keep health state updated
- publish to MQTT
- never require `/dev/i2c-1` or `/dev/gpiomem`
- never require privileged mode

## Useful Environment Variables

Container-side:

- `DEVICE_ID`
- `IMU_SOCKET_PATH`
- `IMU_SESSION_ID`
- `IMU_SAMPLE_HZ`
- `IMU_REQUEST_TARE`
- `IMU_RESET_COUNTER`
- `IMU_AUTO_START_SESSION`
- `IMU_STOP_SESSION_ON_EXIT`
- `MQTT_BROKER_IP`
- `MQTT_BROKER_PORT`
- `MQTT_TOPIC`
- `IMU_CSV_PATH`
- `IMU_EDGE_HEALTH_PATH`

Host-side:

- `IMU_SOCKET_PATH`
- `IMU_SERVICE_BACKEND`
- `IMU_SERVICE_AUTO_TARE`
- `IMU_SERVICE_START_ON_BOOT`
- `IMU_SERVICE_SAMPLE_HZ`
- `IMU_SAMPLE_FILE`

## Deployment Notes

### Docker Compose

Use the socket mount:

```yaml
volumes:
  - ./data:/app/data
  - /run/imu-hw:/run/imu-hw
```

Do not use:

- `privileged: true`
- `/dev/i2c-1`
- `/dev/gpiomem`

### Docker Swarm

Your swarm service should:

- run only on Pi nodes that have the host IMU service installed
- bind-mount `/run/imu-hw`
- use normal network access for MQTT/platform integration
- use a container healthcheck

## Recommended Bring-Up Order

1. Install host dependencies:

```bash
pip install -r requirements-host.txt
```

2. Start the Pi-local service:

```bash
python -m imu_host
```

3. Verify the socket exists:

```bash
ls -l /run/imu-hw/imu.sock
```

4. Build and run the container:

```bash
docker compose up -d --build
```

5. For Swarm:

```bash
docker stack deploy -c swarm.yml imu
```

## Health And Troubleshooting

If the container is not streaming:

1. Check the host service is running
2. Check `/run/imu-hw/imu.sock` exists
3. Check the host service can see the IMU hardware
4. Check MQTT broker connectivity
5. Check container health output:

```bash
python -m imu_edge healthcheck
```

If the IMU is missing or not ready:

- `GET /v1/readyz` should report not ready
- `GET /v1/status` should show the last error
- the edge container should keep retrying instead of crashing

## Files To Know

- `imu_host/__main__.py`
- `imu_host/manager.py`
- `imu_host/server.py`
- `imu_edge/__main__.py`
- `imu_edge/agent.py`
- `imu_edge/service_client.py`
- `imu/DataWriter.py`
- `deploy/systemd/imu-hw.service`
- `docker-compose.yml`
- `swarm.yml`

## Short Summary

The Raspberry Pi host now owns the physical IMU.
The container now owns control, forwarding, and integration.
To activate the IMU from the container, the container must start a session through the host service API, then consume the telemetry stream and publish it onward.
