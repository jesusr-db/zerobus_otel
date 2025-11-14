# Databricks notebook source
"""
Alerting: Detect Anomalies
Compares current service health against baselines and writes anomalies to table
"""

from pyspark.sql.functions import *

dbutils.widgets.text("catalog_name", "main", "Catalog Name")
dbutils.widgets.text("schema_name", "zerobus", "Schema Name")
dbutils.widgets.text("lookback_minutes", "2", "Lookback Minutes")

catalog_name = dbutils.widgets.get("catalog_name")
schema_name = dbutils.widgets.get("schema_name")
lookback_minutes = int(dbutils.widgets.get("lookback_minutes"))

service_health_table = f"{catalog_name}.{schema_name}.service_health_silver"
baselines_table = f"{catalog_name}.{schema_name}.anomaly_baselines"
anomalies_table = f"{catalog_name}.{schema_name}.detected_anomalies"

recent_health = spark.table(service_health_table).filter(
    col("timestamp") >= current_timestamp() - expr(f"INTERVAL {lookback_minutes} MINUTES")
)

baselines = spark.table(baselines_table)

anomalies = (
    recent_health
    .join(baselines, "service_name")
    .filter(
        (col("error_rate") > col("error_rate_threshold")) |
        (col("latency_p95_ms") > col("latency_threshold"))
    )
    .select(
        "service_name",
        "timestamp",
        "error_rate",
        "error_rate_threshold",
        col("latency_p95_ms").alias("p95_latency_ms"),
        "latency_threshold",
        when(col("error_rate") > col("error_rate_threshold"), "error_rate")
            .when(col("latency_p95_ms") > col("latency_threshold"), "latency")
            .otherwise("unknown").alias("anomaly_type")
    )
    .withColumn("detected_at", current_timestamp())
)

anomaly_count = anomalies.count()

if anomaly_count > 0:
    anomalies.write.mode("append").saveAsTable(anomalies_table)
    print(f"✅ Anomaly detection completed: {anomaly_count} anomalies detected and written to {anomalies_table}")
else:
    print(f"✅ Anomaly detection completed: No anomalies detected")
