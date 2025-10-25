# Databricks notebook source
"""
Gold Layer: Service Health Rollups
Aggregates service health metrics over various time windows (1h, 6h, 24h)
"""

from pyspark.sql.functions import *
from pyspark.sql.window import Window

dbutils.widgets.text("catalog_name", "observability_poc", "Catalog Name")
dbutils.widgets.text("lookback_hours", "2", "Lookback Hours")

catalog_name = dbutils.widgets.get("catalog_name")
lookback_hours = int(dbutils.widgets.get("lookback_hours"))

service_health_table = f"{catalog_name}.silver.service_health_silver"

service_health = spark.table(service_health_table).filter(
    col("timestamp") >= current_timestamp() - expr(f"INTERVAL {lookback_hours} HOURS")
)

hourly_rollups = (
    service_health
    .withColumn("hour", date_trunc("hour", col("timestamp")))
    .groupBy("service_name", "hour")
    .agg(
        avg("error_rate").alias("avg_error_rate"),
        max("error_rate").alias("max_error_rate"),
        avg("p95_latency_ms").alias("avg_p95_latency_ms"),
        max("p95_latency_ms").alias("max_p95_latency_ms"),
        sum("total_requests").alias("total_requests")
    )
)

hourly_rollups.write.mode("overwrite").saveAsTable(f"{catalog_name}.gold.service_health_hourly")

print(f"✅ Service health hourly rollups completed: {hourly_rollups.count()} records")
