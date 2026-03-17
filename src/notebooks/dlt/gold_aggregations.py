# Databricks notebook source
# MAGIC %md
# MAGIC # Gold Layer - Aggregations and Analytics
# MAGIC
# MAGIC Gold layer tables for business intelligence, reporting, and anomaly detection.
# MAGIC
# MAGIC **Inputs**:
# MAGIC - `{catalog}.zerobus_sdp.traces_silver`
# MAGIC - `{catalog}.zerobus_sdp.metrics_silver`
# MAGIC
# MAGIC **Outputs**:
# MAGIC - `{catalog}.zerobus_sdp.traces_assembled` (moved from silver - batch aggregation)
# MAGIC - `{catalog}.zerobus_sdp.service_health_5min`
# MAGIC - `{catalog}.zerobus_sdp.service_health_hourly`
# MAGIC - `{catalog}.zerobus_sdp.service_dependencies`
# MAGIC - `{catalog}.zerobus_sdp.anomaly_baselines`
# MAGIC
# MAGIC **Note**:
# MAGIC - Service health metrics are computed directly from traces_silver with 5-minute windows
# MAGIC - This replaces the previous service_health_realtime (1-minute) approach
# MAGIC - 80% fewer rows, single-pass percentile computation, statistically correct aggregations

# COMMAND ----------

import dlt
from pyspark.sql.functions import *
from pyspark.sql.types import *
from pyspark.sql.window import Window

# Get configuration from pipeline settings
catalog_name = spark.conf.get("catalog_name", "jmr_demo")
schema_name = spark.conf.get("schema_name", "zerobus_sdp")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Service Health 5-Minute Windows
# MAGIC
# MAGIC Direct computation from traces_silver with 5-minute windows.
# MAGIC
# MAGIC Key improvements:
# MAGIC - 80% fewer rows than 1-minute windows (288 vs 1,440 rows/day per service)
# MAGIC - Single-pass percentile computation (not double aggregation)
# MAGIC - Correct statistical computation (percentiles on raw data)
# MAGIC - Gold layer placement (appropriate for aggregations)

# COMMAND ----------

@dlt.table(
    name="service_health_5min",
    comment="5-minute service health metrics computed directly from traces (replaces service_health_realtime)",
    table_properties={
        "quality": "gold",
        "pipelines.autoOptimize.managed": "true",
        "delta.enableChangeDataFeed": "true"
    }
)
def service_health_5min():
    """
    Direct computation from traces_silver with 5-minute windows.
    """
    # Read from traces_silver (cross-pipeline reference)
    # Use 90 days to capture historical data
    traces = spark.read.table(f"{catalog_name}.{schema_name}.traces_silver").filter(
        col("start_timestamp") >= current_timestamp() - expr("INTERVAL 90 DAYS")
    )

    return (
        traces
        .withColumn("window_5min", date_trunc("5 minutes", col("start_timestamp")))
        .groupBy("service_name", "window_5min")
        .agg(
            # Error rate calculation
            (sum(when(col("is_error") == True, 1).otherwise(0)) / count("*")).alias("error_rate"),

            # Latency percentiles - computed once from raw durations
            expr("percentile_approx(duration_ms, 0.50)").alias("p50_latency_ms"),
            expr("percentile_approx(duration_ms, 0.95)").alias("p95_latency_ms"),
            expr("percentile_approx(duration_ms, 0.99)").alias("p99_latency_ms"),

            # Basic stats
            count("*").alias("total_requests"),
            avg("duration_ms").alias("avg_latency_ms"),
            min("duration_ms").alias("min_latency_ms"),
            max("duration_ms").alias("max_latency_ms")
        )
        .withColumn("ingestion_timestamp", current_timestamp())
        .select(
            col("window_5min").alias("timestamp"),
            "service_name",
            "error_rate",
            "p50_latency_ms",
            "p95_latency_ms",
            "p99_latency_ms",
            "total_requests",
            "avg_latency_ms",
            "min_latency_ms",
            "max_latency_ms",
            "ingestion_timestamp"
        )
    )

# COMMAND ----------

# MAGIC %md
# MAGIC ## Service Health Hourly Rollups
# MAGIC
# MAGIC Aggregate 5-minute windows to hourly.
# MAGIC
# MAGIC Note: We compute percentiles from the 12 5-min windows per hour.
# MAGIC This is more accurate than averaging pre-computed percentiles.

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
    """
    Aggregate 5-minute windows to hourly.
    """
    # Read from service_health_5min table in the same pipeline
    service_health_5min = dlt.read("service_health_5min").filter(
        col("timestamp") >= current_timestamp() - expr("INTERVAL 30 DAYS")
    )

    return (
        service_health_5min
        .withColumn("hour", date_trunc("hour", col("timestamp")))
        .groupBy("service_name", "hour")
        .agg(
            # Weighted average for error rate (by request count)
            sum(col("error_rate") * col("total_requests")).alias("weighted_error_sum"),
            sum("total_requests").alias("total_requests"),

            # For percentiles: use max of 5-min p95/p99 as approximation
            # Better than average, conservative upper bound
            max("p95_latency_ms").alias("p95_latency_ms"),
            max("p99_latency_ms").alias("p99_latency_ms"),

            # Simple aggregations
            avg("avg_latency_ms").alias("avg_latency_ms"),
            max("max_latency_ms").alias("max_latency_ms"),
            min("min_latency_ms").alias("min_latency_ms")
        )
        .withColumn("error_rate", col("weighted_error_sum") / col("total_requests"))
        .withColumn("ingestion_timestamp", current_timestamp())
        .select(
            "service_name",
            "hour",
            "error_rate",
            "p95_latency_ms",
            "p99_latency_ms",
            "avg_latency_ms",
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
    comment="Service-to-service dependency graph with call counts and activity timestamps",
    table_properties={
        "quality": "gold",
        "pipelines.autoOptimize.managed": "true"
    }
)
def service_dependencies():
    """
    Build service-to-service dependency graph from parent-child span relationships.

    Columns:
    - first_seen/last_seen: When this specific dependency was observed (parent-child relationship)
    - last_active: Most recent trace involving either source or target service (any trace, not just dependencies)

    Note: Requires traces to have parent_span_id populated for nested calls.
    If no results, check:
    1. Do traces have parent_span_id? (Run: SELECT COUNT(*) FROM traces_silver WHERE parent_span_id IS NOT NULL)
    2. Do parent-child relationships exist within same trace_id?
    3. Is there data in the time window?
    """
    # Read from silver layer table created by another pipeline
    # Use 90 days to capture historical data for dependency detection
    traces = spark.read.table(f"{catalog_name}.{schema_name}.traces_silver").filter(
        col("start_timestamp") >= current_timestamp() - expr("INTERVAL 90 DAYS")
    )

    # Get last activity timestamp per service (from ALL traces, not just parent-child)
    service_last_active = (
        traces
        .groupBy("service_name")
        .agg(max("start_timestamp").alias("service_last_active"))
    )

    # Filter to only child spans (those with a parent)
    child_spans = traces.filter(col("parent_span_id").isNotNull()).alias("child")

    # Self-join to find parent spans
    # Note: This assumes parent and child are in the same trace_id
    dependencies = (
        child_spans
        .join(
            traces.alias("parent"),
            (col("child.parent_span_id") == col("parent.span_id")) &
            (col("child.trace_id") == col("parent.trace_id")),
            "inner"
        )
        .select(
            col("parent.service_name").alias("source_service"),
            col("child.service_name").alias("target_service"),
            col("child.trace_id").alias("trace_id"),
            col("child.start_timestamp").alias("call_timestamp")
        )
        # Include both cross-service and same-service calls
        # Filter out if needed: .filter(col("source_service") != col("target_service"))
    )

    # Aggregate dependencies
    deps_aggregated = (
        dependencies
        .groupBy("source_service", "target_service")
        .agg(
            count("*").alias("call_count"),
            countDistinct("trace_id").alias("unique_traces"),
            min("call_timestamp").alias("first_seen"),
            max("call_timestamp").alias("last_seen")
        )
    )

    # Join with service activity to get last_active for source and target
    result = (
        deps_aggregated
        .join(
            service_last_active.alias("src_activity"),
            col("source_service") == col("src_activity.service_name"),
            "left"
        )
        .withColumn("source_last_active", col("src_activity.service_last_active"))
        .drop("service_name", "service_last_active")
        .join(
            service_last_active.alias("tgt_activity"),
            col("target_service") == col("tgt_activity.service_name"),
            "left"
        )
        .withColumn("target_last_active", col("tgt_activity.service_last_active"))
        .drop("service_name", "service_last_active")
        # last_active = max of source and target last activity
        .withColumn("last_active", greatest("source_last_active", "target_last_active"))
        .withColumn("ingestion_timestamp", current_timestamp())
        .select(
            "source_service",
            "target_service",
            "call_count",
            "unique_traces",
            "first_seen",
            "last_seen",
            "last_active",
            "ingestion_timestamp"
        )
    )

    return result

# COMMAND ----------

# MAGIC %md
# MAGIC ## Traces Assembled
# MAGIC
# MAGIC Batch aggregation of traces from traces_silver.
# MAGIC
# MAGIC **Moved from silver streaming pipeline** to fix:
# MAGIC - Watermark dropping late data (was 2 minutes - too aggressive)
# MAGIC - 5-minute window grouping splitting traces incorrectly
# MAGIC
# MAGIC Now groups by trace_id only (one row per trace).

# COMMAND ----------

@dlt.table(
    name="traces_assembled",
    comment="Assembled traces with aggregated span information - batch computed from traces_silver",
    table_properties={
        "quality": "gold",
        "pipelines.autoOptimize.managed": "true"
    }
)
def traces_assembled():
    """
    Batch aggregation of traces - no watermark issues, no window splitting.

    Groups by trace_id only (not time window) so each trace is one row.
    Lookback window is configurable - default 24 hours for recent traces.
    """
    traces = spark.read.table(f"{catalog_name}.{schema_name}.traces_silver").filter(
        col("start_timestamp") >= current_timestamp() - expr("INTERVAL 24 HOURS")
    )

    return (
        traces
        .groupBy("trace_id")
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
            "span_count",
            "trace_start",
            "trace_end",
            "total_trace_duration_ms",
            "services_involved",
            "service_count",
            "error_count",
            "has_errors",
            "max_span_duration_ms",
            "avg_span_duration_ms",
            "span_details",
            "ingestion_timestamp"
        )
    )

# COMMAND ----------

# MAGIC %md
# MAGIC ## Anomaly Detection Baselines
# MAGIC
# MAGIC Compute baselines from 5-minute data.
# MAGIC
# MAGIC Using 5-min windows gives us 2,016 data points per week per service,
# MAGIC which is statistically robust for baseline computation.

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
    """
    Compute baselines from 5-minute data.
    """
    # Read from service_health_5min table in the same pipeline
    service_health_5min = dlt.read("service_health_5min").filter(
        col("timestamp") >= current_timestamp() - expr("INTERVAL 7 DAYS")
    )

    return (
        service_health_5min
        .groupBy("service_name")
        .agg(
            # Baseline statistics
            avg("error_rate").alias("baseline_error_rate"),
            stddev("error_rate").alias("error_rate_stddev"),
            avg("p95_latency_ms").alias("baseline_p95_latency_ms"),
            stddev("p95_latency_ms").alias("latency_stddev"),

            # Thresholds (3-sigma)
            (avg("error_rate") + 3 * stddev("error_rate")).alias("error_rate_threshold"),
            (avg("p95_latency_ms") + 3 * stddev("p95_latency_ms")).alias("latency_threshold"),

            # Metadata
            count("*").alias("sample_count"),
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
            "sample_count",
            "baseline_start_timestamp",
            "baseline_end_timestamp",
            "baseline_computed_at"
        )
    )

# COMMAND ----------
