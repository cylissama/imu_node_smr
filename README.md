# Running
In the future, there will be a dockerfile to make setup easier.
For now, you must do the following:

1. Create a python virtual environment (optional but recommended)
    a. `python -m venv .venv`
    b. Activate it:
       - Windows PowerShell: `.venv\\Scripts\\Activate.ps1`
       - Windows CMD: `.venv\\Scripts\\activate.bat`
       - macOS/Linux: `source .venv/bin/activate`
2. Install dependencies
    a. `pip install -r requirements.txt`
3. Run the `imu` module
    a. `python -m imu`
    b. Run `python -m imu -u` to see real-time data being collected
    c. Run `python -m imu -t` to use fake/sample IMU data
    d. Run `python -m imu -t -u` to use fake/sample IMU data with UI
    e. Run `python -m imu -u --tare` to zero yaw/pitch/roll at startup

# Container Environment Variables
You can configure per-device identity and startup tare via environment variables.

- `DEVICE_ID` (integer): numeric identity for this IMU container. Defaults to `0` if unset/invalid.
- `AUTO_TARE` (boolean): if `true`, `1`, `yes`, or `on`, tare is applied automatically at startup.

Resolution order for `device_id` is:

1. `DEVICE_ID` from environment
2. Existing configured value passed into the writer
3. Safe numeric default `0`

Example per-device env files (already included in `env/`):

- IMU Pi `.83`: `env/imu-83.env`
- IMU Pi `.84`: `env/imu-84.env`

Run with a specific device env file:

- `docker compose --env-file env/imu-83.env up -d --build`
- `docker compose --env-file env/imu-84.env up -d --build`

# Testing
Run unit tests with:

`python -m pytest -q`

# Output format
Each IMU sample now includes a per-session monotonically increasing `counter` that starts at `0` when the IMU process starts and increments by `1` for each generated sample.

CSV header:

`counter,capture_time_ms,recorded_at_time_ms,accel_x,accel_y,accel_z,gyro_x,gyro_y,gyro_z,mag_x,mag_y,mag_z,yaw,pitch,roll,device_id`

MQTT payload order:

`counter,capture_time_ms,recorded_at_time_ms,accel_x,accel_y,accel_z,gyro_x,gyro_y,gyro_z,mag_x,mag_y,mag_z,yaw,pitch,roll,device_id`

Units: `accel_*` in m/s², `gyro_*` in rad/s, and `yaw/pitch/roll` in degrees.
