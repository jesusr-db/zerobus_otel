# Databricks notebook source
"""
Data Quality: Validate Service Health Metrics
Checks for anomalies and data quality issues in service health metrics
"""

from pyspark.sql.functions import *
from pyspark.sql.types import *

dbutils.widgets.text("catalog_name", "observability_poc", "Catalog Name")

catalog_name = dbutils.widgets.get("catalog_name")
service_health_table = f"{catalog_name}.zerobus.service_health_silver"

service_health = spark.table(service_health_table)

null_checks = service_health.select(
    count(when(col("service_name").isNull(), 1)).alias("null_service_names"),
    count(when(col("error_rate").isNull(), 1)).alias("null_error_rates"),
    count(when(col("latency_p95_ms").isNull(), 1)).alias("null_latencies"),
    count(when(col("request_count").isNull(), 1)).alias("null_request_counts")
).collect()[0]

invalid_ranges = service_health.filter(
    (col("error_rate") < 0) | (col("error_rate") > 1) |
    (col("latency_p95_ms") < 0) |
    (col("request_count") < 0)
).count()

total_records = service_health.count()
data_quality_score = ((total_records - invalid_ranges) / total_records * 100) if total_records > 0 else 0

validation_result = spark.createDataFrame([(
    total_records,
    int(null_checks.null_service_names),
    int(null_checks.null_error_rates),
    int(null_checks.null_latencies),
    invalid_ranges,
    data_quality_score,
    "PASS" if data_quality_score >= 99 else "FAIL"
)], ["total_records", "null_service_names", "null_error_rates", "null_latencies", "invalid_ranges", "data_quality_score", "status"]).withColumn("validation_timestamp", current_timestamp())

validation_result.write.mode("append").saveAsTable(f"{catalog_name}.zerobus.service_health_quality_results")

print(f"✅ Service health validation: {data_quality_score:.2f}% quality score ({invalid_ranges} invalid records)")
