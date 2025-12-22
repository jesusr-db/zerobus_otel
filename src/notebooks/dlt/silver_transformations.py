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
    name="traces_silver",
    comment="Flattened trace spans from bronze layer with deduplication",
    table_properties={
        "quality": "silver",
        "pipelines.autoOptimize.managed": "true",
        "delta.enableChangeDataFeed": "true"
    }
)
def traces_silver():
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
        .dropDuplicates(["trace_id", "span_id"])
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
    name="logs_silver",
    comment="Enriched logs from bronze layer with trace context and deduplication",
    table_properties={
        "quality": "silver",
        "pipelines.autoOptimize.managed": "true",
        "delta.enableChangeDataFeed": "true"
    }
)
def logs_silver():
    logs_df = spark.readStream.table(f"{bronze_catalog}.{bronze_schema}.{bronze_table_prefix}_logs")
    
    return (
        logs_df
        .withColumn("service_name", col("resource.attributes")["service.name"])
        .withColumn("log_timestamp", from_unixtime(col("time_unix_nano") / 1e9).cast("timestamp"))
        .withColumn("observed_timestamp", from_unixtime(col("observed_time_unix_nano") / 1e9).cast("timestamp"))
        .withColumn("ingestion_timestamp", current_timestamp())
        .dropDuplicates(["trace_id", "span_id", "log_timestamp", "body"])
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
    name="metrics_silver",
    comment="Flattened metrics from bronze layer with deduplication",
    table_properties={
        "quality": "silver",
        "pipelines.autoOptimize.managed": "true",
        "delta.enableChangeDataFeed": "true"
    }
)
def metrics_silver():
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
        .dropDuplicates(["name", "service_name", "metric_timestamp", "metric_type"])
    )

# COMMAND ----------

# MAGIC %md
# MAGIC ## Metrics Rollups

# COMMAND ----------

@dlt.table(
    name="metrics_1min_rollup",
    comment="1-minute aggregated metrics rollup from metrics_silver",
    table_properties={
        "quality": "silver",
        "pipelines.autoOptimize.managed": "true",
        "delta.enableChangeDataFeed": "true"
    }
)
def metrics_1min_rollup():
    metrics = dlt.read_stream("metrics_silver").withWatermark("metric_timestamp", "5 minutes")
    
    return (
        metrics
        .groupBy(
            "name",
            "service_name",
            "metric_type",
            window("metric_timestamp", "1 minute")
        )
        .agg(
            count("*").alias("sample_count"),
            avg("value").alias("avg_value"),
            min("value").alias("min_value"),
            max("value").alias("max_value"),
            sum("value").alias("sum_value"),
            approx_percentile("value", 0.5).alias("p50_value"),
            approx_percentile("value", 0.95).alias("p95_value"),
            approx_percentile("value", 0.99).alias("p99_value")
        )
        .withColumn("window_start", col("window.start"))
        .withColumn("window_end", col("window.end"))
        .withColumn("ingestion_timestamp", current_timestamp())
        .select(
            "name",
            "service_name",
            "metric_type",
            "window_start",
            "window_end",
            "sample_count",
            "avg_value",
            "min_value",
            "max_value",
            "sum_value",
            "p50_value",
            "p95_value",
            "p99_value",
            "ingestion_timestamp"
        )
    )

# COMMAND ----------

@dlt.table(
    name="metrics_5min_rollup",
    comment="5-minute aggregated metrics rollup from metrics_silver",
    table_properties={
        "quality": "silver",
        "pipelines.autoOptimize.managed": "true",
        "delta.enableChangeDataFeed": "true"
    }
)
def metrics_5min_rollup():
    metrics = dlt.read_stream("metrics_silver").withWatermark("metric_timestamp", "10 minutes")
    
    return (
        metrics
        .groupBy(
            "name",
            "service_name",
            "metric_type",
            window("metric_timestamp", "5 minutes")
        )
        .agg(
            count("*").alias("sample_count"),
            avg("value").alias("avg_value"),
            min("value").alias("min_value"),
            max("value").alias("max_value"),
            sum("value").alias("sum_value"),
            approx_percentile("value", 0.5).alias("p50_value"),
            approx_percentile("value", 0.95).alias("p95_value"),
            approx_percentile("value", 0.99).alias("p99_value")
        )
        .withColumn("window_start", col("window.start"))
        .withColumn("window_end", col("window.end"))
        .withColumn("ingestion_timestamp", current_timestamp())
        .select(
            "name",
            "service_name",
            "metric_type",
            "window_start",
            "window_end",
            "sample_count",
            "avg_value",
            "min_value",
            "max_value",
            "sum_value",
            "p50_value",
            "p95_value",
            "p99_value",
            "ingestion_timestamp"
        )
    )

# COMMAND ----------

@dlt.table(
    name="metrics_hourly_rollup",
    comment="Hourly aggregated metrics rollup from metrics_silver",
    table_properties={
        "quality": "silver",
        "pipelines.autoOptimize.managed": "true",
        "delta.enableChangeDataFeed": "true"
    }
)
def metrics_hourly_rollup():
    metrics = dlt.read_stream("metrics_silver").withWatermark("metric_timestamp", "1 hour")
    
    return (
        metrics
        .groupBy(
            "name",
            "service_name",
            "metric_type",
            window("metric_timestamp", "1 hour")
        )
        .agg(
            count("*").alias("sample_count"),
            avg("value").alias("avg_value"),
            min("value").alias("min_value"),
            max("value").alias("max_value"),
            sum("value").alias("sum_value"),
            approx_percentile("value", 0.5).alias("p50_value"),
            approx_percentile("value", 0.95).alias("p95_value"),
            approx_percentile("value", 0.99).alias("p99_value")
        )
        .withColumn("window_start", col("window.start"))
        .withColumn("window_end", col("window.end"))
        .withColumn("ingestion_timestamp", current_timestamp())
        .select(
            "name",
            "service_name",
            "metric_type",
            "window_start",
            "window_end",
            "sample_count",
            "avg_value",
            "min_value",
            "max_value",
            "sum_value",
            "p50_value",
            "p95_value",
            "p99_value",
            "ingestion_timestamp"
        )
    )

# COMMAND ----------

# MAGIC %md
# MAGIC ## Traces Assembled Silver

# COMMAND ----------

@dlt.table(
    name="traces_assembled_silver",
    comment="Assembled traces with aggregated span information and span details array",
    table_properties={
        "quality": "silver",
        "pipelines.autoOptimize.managed": "true",
        "delta.enableChangeDataFeed": "true"
    }
)
def traces_assembled_silver():
    traces = dlt.read_stream("traces_silver").withWatermark("start_timestamp", "10 minutes")
    
    return (
        traces
        .groupBy("trace_id", window("start_timestamp", "5 minutes"))
        .agg(
            count("*").alias("span_count"),
            min("start_timestamp").alias("trace_start"),
            max("end_timestamp").alias("trace_end"),
            collect_set("service_name").alias("services_involved"),
            sum(col("is_error").cast("int")).alias("error_count"),
            max("duration_ms").alias("max_span_duration_ms"),
            avg("duration_ms").alias("avg_span_duration_ms"),
            collect_list(
                struct(
                    "span_id",
                    "parent_span_id",
                    "name",
                    "kind",
                    "service_name",
                    "duration_ms",
                    "is_error"
                )
            ).alias("span_details")
        )
        .withColumn("has_errors", col("error_count") > 0)
        .withColumn("total_trace_duration_ms", 
                    (unix_timestamp("trace_end") - unix_timestamp("trace_start")) * 1000)
        .withColumn("service_count", size("services_involved"))
        .withColumn("ingestion_timestamp", current_timestamp())
        .select(
            "trace_id",
            col("window.start").alias("window_start"),
            col("window.end").alias("window_end"),
            "span_count",
            "trace_start",
            "trace_end",
            "services_involved",
            "error_count",
            "has_errors",
            "max_span_duration_ms",
            "avg_span_duration_ms",
            "span_details",
            "total_trace_duration_ms",
            "service_count",
            "ingestion_timestamp"
        )
    )
