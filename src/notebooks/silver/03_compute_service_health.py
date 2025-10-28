# Databricks notebook source
# MAGIC %md
# MAGIC # Silver Layer - Compute Service Health (Golden Signals)
# MAGIC 
# MAGIC Computes traffic, errors, and latency (Golden Signals) per service.
# MAGIC 
# MAGIC **Input**: `{catalog}.jmr_demo.traces_silver` (streaming)
# MAGIC **Output**: `{catalog}.jmr_demo.service_health_silver` (Delta table)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Setup

# COMMAND ----------

import logging
from pyspark.sql import SparkSession
from pyspark.sql.functions import *
from pyspark.sql.types import *

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Parameters

# COMMAND ----------

dbutils.widgets.text("catalog_name", "observability_poc", "Catalog Name")
dbutils.widgets.text("checkpoint_location", "/Volumes/main/jmr_demo/storage/checkpoint/silver/service_health", "Checkpoint Location")
dbutils.widgets.text("window_duration", "1 minute", "Window Duration")
dbutils.widgets.text("watermark_delay", "5 minutes", "Watermark Delay")

catalog_name = dbutils.widgets.get("catalog_name")
checkpoint_location = dbutils.widgets.get("checkpoint_location")
window_duration = dbutils.widgets.get("window_duration")
watermark_delay = dbutils.widgets.get("watermark_delay")

logger.info(f"Catalog: {catalog_name}")
logger.info(f"Window Duration: {window_duration}")
logger.info(f"Watermark Delay: {watermark_delay}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Read from Traces Silver (Streaming)

# COMMAND ----------

traces_table = f"{catalog_name}.jmr_demo.traces_silver"
logger.info(f"Reading from {traces_table}...")

traces_df = (
    spark.readStream
    .table(traces_table)
    .withWatermark("start_timestamp", watermark_delay)
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Compute Golden Signals

# COMMAND ----------

service_health = (
    traces_df
    .filter(col("service_name").isNotNull())
    .groupBy(
        window("start_timestamp", window_duration),
        "service_name"
    )
    .agg(
        count("*").alias("request_count"),
        sum(col("is_error").cast("int")).alias("error_count"),
        (sum(col("is_error").cast("int")) / count("*")).alias("error_rate"),
        approx_percentile("duration_ms", 0.5).alias("latency_p50_ms"),
        approx_percentile("duration_ms", 0.95).alias("latency_p95_ms"),
        approx_percentile("duration_ms", 0.99).alias("latency_p99_ms"),
        avg("duration_ms").alias("latency_avg_ms"),
        max("duration_ms").alias("latency_max_ms"),
        min("duration_ms").alias("latency_min_ms")
    )
    .withColumn("timestamp", col("window.start"))
    .withColumn("window_end", col("window.end"))
    .withColumn("requests_per_second", col("request_count") / 60.0)
    .withColumn("ingestion_timestamp", current_timestamp())
    .select(
        "timestamp",
        "window_end",
        "service_name",
        "request_count",
        "requests_per_second",
        "error_count",
        "error_rate",
        "latency_p50_ms",
        "latency_p95_ms",
        "latency_p99_ms",
        "latency_avg_ms",
        "latency_max_ms",
        "latency_min_ms",
        "ingestion_timestamp"
    )
)

logger.info("Golden signals aggregations completed")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Write to Silver (Streaming)

# COMMAND ----------

service_health_table = f"{catalog_name}.jmr_demo.service_health_silver"
logger.info(f"Writing to {service_health_table}...")

query = (
    service_health.writeStream
    .format("delta")
    .outputMode("append")
    .option("checkpointLocation", checkpoint_location)
    .option("mergeSchema", "true")
    .trigger(availableNow=True)
    .table(service_health_table)
)

logger.info(f"Stream started: {service_health_table}")
logger.info(f"Query ID: {query.id}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Monitor Stream

# COMMAND ----------
