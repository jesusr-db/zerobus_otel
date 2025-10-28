# Databricks notebook source
"""
Gold Layer: Service Dependencies
Maps service-to-service dependencies and call patterns
"""

from pyspark.sql.functions import *

dbutils.widgets.text("catalog_name", "observability_poc", "Catalog Name")
dbutils.widgets.text("lookback_hours", "24", "Lookback Hours")

catalog_name = dbutils.widgets.get("catalog_name")
lookback_hours = int(dbutils.widgets.get("lookback_hours"))

traces_table = f"{catalog_name}.zerobus.traces_silver"

traces = spark.table(traces_table).filter(
    col("start_timestamp") >= current_timestamp() - expr(f"INTERVAL {lookback_hours} HOURS")
)

dependencies = (
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
        col("child.service_name").alias("target_service")
    )
    .groupBy("source_service", "target_service")
    .agg(
        count("*").alias("call_count")
    )
)

dependencies.write.mode("overwrite").saveAsTable(f"{catalog_name}.zerobus.service_dependencies")

print(f"✅ Service dependencies computed: {dependencies.count()} edges")
