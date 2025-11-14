# Databricks notebook source
"""
Delta Live Tables: Real-time Service Health Streaming
Processes service health metrics in real-time using Delta Live Tables
"""

import dlt
from pyspark.sql.functions import *

catalog_name = spark.conf.get("catalog_name", "observability_poc")

@dlt.table(
    name="service_health_realtime_dlt",
    comment="Real-time service health metrics from traces",
    table_properties={"quality": "silver"}
)
def service_health_realtime():
    # Read from the streaming traces table in the same pipeline
    return (
        dlt.read_stream("traces_silver_dlt")
        .groupBy(
            window("start_timestamp", "1 minute"),
            "service_name"
        )
        .agg(
            (sum(when(col("is_error") == True, 1).otherwise(0)) / count("*")).alias("error_rate"),
            expr("percentile_approx(duration_ms, 0.95)").alias("p95_latency_ms"),
            expr("percentile_approx(duration_ms, 0.99)").alias("p99_latency_ms"),
            count("*").alias("total_requests")
        )
        .select(
            col("window.start").alias("timestamp"),
            col("service_name"),
            col("error_rate"),
            col("p95_latency_ms"),
            col("p99_latency_ms"),
            col("total_requests")
        )
    )
