# Databricks notebook source
# MAGIC %md
# MAGIC # Gold Layer - Aggregations and Analytics
# MAGIC 
# MAGIC Gold layer tables for business intelligence, reporting, and anomaly detection.
# MAGIC 
# MAGIC **Inputs**:
# MAGIC - `{catalog}.zerobus_sdp.service_health_silver`
# MAGIC - `{catalog}.zerobus_sdp.traces_silver`
# MAGIC - `{catalog}.zerobus_sdp.metrics_silver`
# MAGIC 
# MAGIC **Outputs**:
# MAGIC - `{catalog}.zerobus_sdp.service_health_hourly`
# MAGIC - `{catalog}.zerobus_sdp.service_dependencies`
# MAGIC - `{catalog}.zerobus_sdp.anomaly_baselines`
# MAGIC 
# MAGIC **Note**: Hourly metric rollups are provided by `metrics_hourly_rollup` in silver layer (streaming)

# COMMAND ----------

import dlt
from pyspark.sql.functions import *
from pyspark.sql.types import *
from pyspark.sql.window import Window

# Get configuration from pipeline settings
catalog_name = spark.conf.get("catalog_name", "jmr_demo")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Service Health Hourly Rollups

# COMMAND ----------

@dlt.table(
    name="service_health_hourly",
    comment="Hourly aggregated service health metrics (error rates, latency, request counts)",
    table_properties={
        "quality": "gold",
        "pipelines.autoOptimize.managed": "true"
    }
)
def service_health_hourly():
    service_health = dlt.read("service_health_realtime")
    
    return (
        service_health
        .filter(col("timestamp") >= current_timestamp() - expr("INTERVAL 7 DAYS"))
        .withColumn("hour", date_trunc("hour", col("timestamp")))
        .groupBy("service_name", "hour")
        .agg(
            avg("error_rate").alias("avg_error_rate"),
            max("error_rate").alias("max_error_rate"),
            avg("p95_latency_ms").alias("avg_p95_latency_ms"),
            max("p95_latency_ms").alias("max_p95_latency_ms"),
            avg("p99_latency_ms").alias("avg_p99_latency_ms"),
            max("p99_latency_ms").alias("max_p99_latency_ms"),
            sum("total_requests").alias("total_requests")
        )
        .withColumn("ingestion_timestamp", current_timestamp())
        .select(
            "service_name",
            "hour",
            "avg_error_rate",
            "max_error_rate",
            "avg_p95_latency_ms",
            "max_p95_latency_ms",
            "avg_p99_latency_ms",
            "max_p99_latency_ms",
            "total_requests",
            "ingestion_timestamp"
        )
    )

# COMMAND ----------

# MAGIC %md
# MAGIC ## Service Dependencies Graph

# COMMAND ----------

@dlt.table(
    name="service_dependencies",
    comment="Service-to-service dependency graph with call counts",
    table_properties={
        "quality": "gold",
        "pipelines.autoOptimize.managed": "true"
    }
)
def service_dependencies():
    traces = dlt.read("traces_silver").filter(
        col("start_timestamp") >= current_timestamp() - expr("INTERVAL 24 HOURS")
    )
    
    return (
        traces
        .filter(col("parent_span_id").isNotNull())
        .alias("child")
        .join(
            traces.alias("parent"),
            (col("child.parent_span_id") == col("parent.span_id")) & 
            (col("child.trace_id") == col("parent.trace_id"))
        )
        .select(
            col("parent.service_name").alias("source_service"),
            col("child.service_name").alias("target_service"),
            col("child.trace_id").alias("trace_id")
        )
        .groupBy("source_service", "target_service")
        .agg(
            count("*").alias("call_count"),
            countDistinct("trace_id").alias("unique_traces")
        )
        .withColumn("ingestion_timestamp", current_timestamp())
        .select(
            "source_service",
            "target_service",
            "call_count",
            "unique_traces",
            "ingestion_timestamp"
        )
    )

# COMMAND ----------

# MAGIC %md
# MAGIC ## Anomaly Detection Baselines

# COMMAND ----------

@dlt.table(
    name="anomaly_baselines",
    comment="Statistical baselines for service health anomaly detection (7-day rolling window)",
    table_properties={
        "quality": "gold",
        "pipelines.autoOptimize.managed": "true"
    }
)
def anomaly_baselines():
    service_health = dlt.read("service_health_realtime").filter(
        col("timestamp") >= current_timestamp() - expr("INTERVAL 7 DAYS")
    )
    
    return (
        service_health
        .groupBy("service_name")
        .agg(
            avg("error_rate").alias("baseline_error_rate"),
            stddev("error_rate").alias("error_rate_stddev"),
            avg("p95_latency_ms").alias("baseline_p95_latency_ms"),
            stddev("p95_latency_ms").alias("latency_stddev"),
            (avg("error_rate") + 3 * stddev("error_rate")).alias("error_rate_threshold"),
            (avg("p95_latency_ms") + 3 * stddev("p95_latency_ms")).alias("latency_threshold"),
            min("timestamp").alias("baseline_start_timestamp"),
            max("timestamp").alias("baseline_end_timestamp")
        )
        .withColumn("baseline_computed_at", current_timestamp())
        .select(
            "service_name",
            "baseline_error_rate",
            "error_rate_stddev",
            "error_rate_threshold",
            "baseline_p95_latency_ms",
            "latency_stddev",
            "latency_threshold",
            "baseline_start_timestamp",
            "baseline_end_timestamp",
            "baseline_computed_at"
        )
    )

# COMMAND ----------
