# DataForge — ALICE Kafka Producer (M5W17T1)
# Python 3.11 + confluent-kafka + fastavro + psycopg2.
# confluent-kafka ships a manylinux wheel with librdkafka bundled, so no
# apt-get librdkafka-dev step is needed here (unlike Spark's JRE requirement
# in adaptation-layer.Dockerfile).

FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python3", "src/alice_producer.py"]
