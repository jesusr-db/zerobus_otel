# Databricks notebook source
"""
Gold Layer: Metric Rollups
Aggregates custom metrics over time windows
"""

from pyspark.sql.functions import *

dbutils.widgets.text("catalog_name", "observability_poc", "Catalog Name")
dbutils.widgets.text("lookback_hours", "2", "Lookback Hours")

catalog_name = dbutils.widgets.get("catalog_name")
lookback_hours = int(dbutils.widgets.get("lookback_hours"))

metrics_table = f"{catalog_name}.dev_jesus_rodriguez_zerobus.metrics_silver_strm"

metrics = spark.table(metrics_table).filter(
    col("metric_timestamp") >= current_timestamp() - expr("INTERVAL 2 DAYS")
)

hourly_metrics = (
    metrics
    .withColumn("hour", date_trunc("hour", col("metric_timestamp")))
    .groupBy("name", "service_name", "hour")
    .agg(
        avg("value").alias("avg_value"),
        min("value").alias("min_value"),
        max("value").alias("max_value"),
        stddev("value").alias("stddev_value"),
        count("*").alias("sample_count")
    )
)

hourly_metrics.write.mode("overwrite").saveAsTable(f"{catalog_name}.zerobus.metric_rollups_hourly")

print(f"✅ Metric hourly rollups completed: {hourly_metrics.count()} records")
