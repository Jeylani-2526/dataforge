FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

ENV KAFKA_BOOTSTRAP_SERVERS=kafka:29092
ENV KAFKA_TOPIC_RADAR=sensor-radar
ENV KAFKA_TOPIC_LIDAR=sensor-lidar
ENV KAFKA_TOPIC_TELEMETRY=sensor-telemetry
ENV SENSOR_PUBLISH_INTERVAL_MS=200
ENV SENSOR_SCHEMA_PATH=/app/schemas/sensor_schema_v1.avsc

VOLUME ["/app/schemas"]

CMD ["python", "src/sensor_producer.py"]
