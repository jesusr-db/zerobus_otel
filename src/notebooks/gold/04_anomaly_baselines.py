# Databricks notebook source
"""
Gold Layer: Anomaly Baselines
Computes statistical baselines for anomaly detection
"""

from pyspark.sql.functions import *
from pyspark.sql.window import Window

dbutils.widgets.text("catalog_name", "observability_poc", "Catalog Name")
dbutils.widgets.text("lookback_days", "7", "Lookback Days")

catalog_name = dbutils.widgets.get("catalog_name")
lookback_days = int(dbutils.widgets.get("lookback_days"))

service_health_table = f"{catalog_name}.jmr_demo.service_health_silver"

historical_health = spark.table(service_health_table).filter(
    col("timestamp") >= current_timestamp() - expr(f"INTERVAL {lookback_days} DAYS")
)

baselines = (
    historical_health
    .groupBy("service_name")
    .agg(
        avg("error_rate").alias("baseline_error_rate"),
        stddev("error_rate").alias("error_rate_stddev"),
        avg("p95_latency_ms").alias("baseline_p95_latency_ms"),
        stddev("p95_latency_ms").alias("latency_stddev"),
        (avg("error_rate") + 3 * stddev("error_rate")).alias("error_rate_threshold"),
        (avg("p95_latency_ms") + 3 * stddev("p95_latency_ms")).alias("latency_threshold")
    )
    .withColumn("baseline_timestamp", current_timestamp())
)

baselines.write.mode("overwrite").saveAsTable(f"{catalog_name}.jmr_demo.anomaly_baselines")

print(f"✅ Anomaly baselines computed: {baselines.count()} services")
