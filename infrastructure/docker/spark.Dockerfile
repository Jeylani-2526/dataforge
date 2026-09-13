# DataForge — Spark Structured Streaming Consumer (M5W18T8)
# Same base pattern as adaptation-layer.Dockerfile: Spark needs a JVM
# (JRE) underneath PySpark even though the application code is Python.
# python:3.11-slim + default-jre-headless, not a dedicated Spark image —
# this container runs a single Structured Streaming job, not a
# multi-node cluster, so PySpark's bundled local-mode runtime is enough.

FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends default-jre-headless \
    && rm -rf /var/lib/apt/lists/*

ENV JAVA_HOME=/usr/lib/jvm/default-java \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python3", "src/spark_consumer.py"]
