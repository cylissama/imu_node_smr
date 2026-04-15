FROM python:3.11-slim

WORKDIR /app

COPY requirements-edge.txt /app/requirements-edge.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /app/requirements-edge.txt

COPY . /app

CMD ["python3", "-m", "imu_edge"]
