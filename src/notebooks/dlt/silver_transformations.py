# Databricks notebook source
# MAGIC %md
# MAGIC # Silver Transformations - DLT Streaming Pipeline
# MAGIC 
# MAGIC Continuous streaming pipeline for silver layer transformations using Delta Live Tables.
# MAGIC 
# MAGIC **Inputs**: 
# MAGIC - `{bronze_catalog}.{bronze_schema}.otel_spans`
# MAGIC - `{bronze_catalog}.{bronze_schema}.otel_logs`
# MAGIC - `{bronze_catalog}.{bronze_schema}.otel_metrics`
# MAGIC 
# MAGIC **Outputs**:
# MAGIC - `{catalog}.zerobus.traces_silver`
# MAGIC - `{catalog}.zerobus.logs_silver`
# MAGIC - `{catalog}.zerobus.metrics_silver`
# MAGIC - `{catalog}.zerobus.traces_assembled_silver`

# COMMAND ----------

import dlt
from pyspark.sql.functions import *
from pyspark.sql.types import *

# Get configuration from pipeline settings
catalog_name = spark.conf.get("catalog_name", "jmr_demo")
bronze_catalog = spark.conf.get("bronze_catalog", "jmr_demo")
bronze_schema = spark.conf.get("bronze_schema", "zerobus")
bronze_table_prefix = spark.conf.get("bronze_table_prefix", "otel")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Traces Silver

# COMMAND ----------

@dlt.table(
    name="traces_silver_strm",
    comment="Flattened trace spans from bronze layer",
    table_properties={
        "quality": "silver",
        "pipelines.autoOptimize.managed": "true",
        "delta.enableChangeDataFeed": "true"
    }
)
def traces_silver_strm():
    spans_df = spark.readStream.table(f"{bronze_catalog}.{bronze_schema}.{bronze_table_prefix}_spans")
    
    return (
        spans_df
        .withColumn("service_name", col("resource.attributes")["service.name"])
        .withColumn("start_timestamp", from_unixtime(col("start_time_unix_nano") / 1e9).cast("timestamp"))
        .withColumn("end_timestamp", from_unixtime(col("end_time_unix_nano") / 1e9).cast("timestamp"))
        .withColumn("duration_ms", (col("end_time_unix_nano") - col("start_time_unix_nano")) / 1e6)
        .withColumn("is_error", col("status.code") == "ERROR")
        .withColumn("status_message", col("status.message"))
        .withColumn("ingestion_timestamp", current_timestamp())
        .select(
            "trace_id",
            "span_id",
            "parent_span_id",
            "name",
            "kind",
            "service_name",
            "start_timestamp",
            "end_timestamp",
            "duration_ms",
            "is_error",
            "status_message",
            "attributes",
            "events",
            "links",
            "ingestion_timestamp"
        )
    )

# COMMAND ----------

# MAGIC %md
# MAGIC ## Logs Silver

# COMMAND ----------

@dlt.table(
    name="logs_silver_strm",
    comment="Enriched logs from bronze layer with trace context",
    table_properties={
        "quality": "silver",
        "pipelines.autoOptimize.managed": "true",
        "delta.enableChangeDataFeed": "true"
    }
)
def logs_silver_strm():
    logs_df = spark.readStream.table(f"{bronze_catalog}.{bronze_schema}.{bronze_table_prefix}_logs")
    
    return (
        logs_df
        .withColumn("service_name", col("resource.attributes")["service.name"])
        .withColumn("log_timestamp", from_unixtime(col("time_unix_nano") / 1e9).cast("timestamp"))
        .withColumn("observed_timestamp", from_unixtime(col("observed_time_unix_nano") / 1e9).cast("timestamp"))
        .withColumn("ingestion_timestamp", current_timestamp())
        .select(
            "event_name",
            "trace_id",
            "span_id",
            "log_timestamp",
            "observed_timestamp",
            "severity_number",
            "severity_text",
            "body",
            "service_name",
            "attributes",
            "ingestion_timestamp"
        )
    )

# COMMAND ----------

# MAGIC %md
# MAGIC ## Metrics Silver

# COMMAND ----------

@dlt.table(
    name="metrics_silver_strm",
    comment="Flattened metrics from bronze layer",
    table_properties={
        "quality": "silver",
        "pipelines.autoOptimize.managed": "true",
        "delta.enableChangeDataFeed": "true"
    }
)
def metrics_silver_strm():
    metrics_df = spark.readStream.table(f"{bronze_catalog}.{bronze_schema}.{bronze_table_prefix}_metrics")
    
    # Handle gauge metrics
    gauge_metrics = (
        metrics_df
        .filter(col("metric_type") == "gauge")
        .withColumn("service_name", col("resource.attributes")["service.name"])
        .withColumn("metric_timestamp", from_unixtime(col("gauge.time_unix_nano") / 1e9).cast("timestamp"))
        .withColumn("value", col("gauge.value"))
        .select(
            "name",
            "description",
            "unit",
            "service_name",
            "metric_timestamp",
            "value",
            col("gauge.attributes").alias("attributes"),
            lit("gauge").alias("metric_type")
        )
    )
    
    # Handle sum metrics
    sum_metrics = (
        metrics_df
        .filter(col("metric_type") == "sum")
        .withColumn("service_name", col("resource.attributes")["service.name"])
        .withColumn("metric_timestamp", from_unixtime(col("sum.time_unix_nano") / 1e9).cast("timestamp"))
        .withColumn("value", col("sum.value"))
        .select(
            "name",
            "description",
            "unit",
            "service_name",
            "metric_timestamp",
            "value",
            col("sum.attributes").alias("attributes"),
            lit("sum").alias("metric_type")
        )
    )
    
    # Union all metric types
    return (
        gauge_metrics.unionAll(sum_metrics)
        .withColumn("ingestion_timestamp", current_timestamp())
    )

# COMMAND ----------

# MAGIC %md
# MAGIC ## Traces Assembled Silver

# COMMAND ----------

@dlt.table(
    name="traces_assembled_silver_strm",
    comment="Assembled traces with aggregated span information",
    table_properties={
        "quality": "silver",
        "pipelines.autoOptimize.managed": "true",
        "delta.enableChangeDataFeed": "true"
    }
)
def traces_assembled_silver_strm():
    traces = dlt.read_stream("traces_silver_strm")
    
    return (
        traces
        .groupBy("trace_id")
        .agg(
            min("start_timestamp").alias("trace_start_timestamp"),
            max("end_timestamp").alias("trace_end_timestamp"),
            count("span_id").alias("span_count"),
            sum("duration_ms").alias("total_duration_ms"),
            collect_set("name").alias("span_names"),
            collect_set("kind").alias("span_kinds"),
            max(when(col("is_error") == True, 1).otherwise(0)).alias("has_error"),
            first("service_name").alias("service_name"),
            current_timestamp().alias("ingestion_timestamp")
        )
    )
