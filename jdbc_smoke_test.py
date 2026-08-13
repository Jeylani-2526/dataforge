"""
Standalone JDBC connectivity check — NOT part of the T2/T3 pipeline.
Tests one thing only: can Spark reach the TimescaleDB staging tables
through JDBC, with the Postgres driver on the classpath.

Run with:
    spark-submit --packages org.postgresql:postgresql:42.7.3 jdbc_smoke_test.py
"""

from pyspark.sql import SparkSession

spark = SparkSession.builder.appName("jdbc-smoke-test").getOrCreate()

JDBC_URL = "jdbc:postgresql://localhost:5432/dataforge"
JDBC_PROPERTIES = {
    "user": "dataforge",
    "password": "dataforge_dev",
    "driver": "org.postgresql.Driver",
}

print("\n=== ALICE staging table ===")
alice_df = spark.read.jdbc(
    url=JDBC_URL,
    table="raw_alice_events_staging",
    properties=JDBC_PROPERTIES,
)
print(f"Row count: {alice_df.count()}")
alice_df.show(5)

print("\n=== Sensor staging table ===")
sensor_df = spark.read.jdbc(
    url=JDBC_URL,
    table="raw_sensor_events_staging",
    properties=JDBC_PROPERTIES,
)
print(f"Row count: {sensor_df.count()}")
sensor_df.show(5)

spark.stop()
print("\nJDBC smoke test complete.")
