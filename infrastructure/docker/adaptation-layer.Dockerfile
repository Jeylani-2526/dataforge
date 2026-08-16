# DataForge — Adaptation Layer (M4W14T5)
# JVM (Spark requires Java) + Python 3.11 + pyspark + fastavro.
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

CMD ["python3", "smoke_test.py"]
