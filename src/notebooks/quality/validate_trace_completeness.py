# Databricks notebook source
"""
Data Quality: Validate Trace Completeness
Checks for orphaned spans and incomplete traces
"""

from pyspark.sql.functions import *
from pyspark.sql.types import *

dbutils.widgets.text("catalog_name", "observability_poc", "Catalog Name")

catalog_name = dbutils.widgets.get("catalog_name")
traces_table = f"{catalog_name}.zerobus.traces_silver"

traces = spark.table(traces_table)

orphaned_spans = traces.filter(
    col("parent_span_id").isNotNull()
).alias("child").join(
    traces.alias("parent"),
    (col("child.parent_span_id") == col("parent.span_id")) & 
    (col("child.trace_id") == col("parent.trace_id")),
    "left_anti"
)

orphan_count = orphaned_spans.count()
total_spans = traces.count()
completeness_rate = ((total_spans - orphan_count) / total_spans * 100) if total_spans > 0 else 0

root_spans = traces.filter(col("parent_span_id").isNull())
traces_with_roots = root_spans.count()

validation_result = spark.createDataFrame([(
    total_spans,
    orphan_count,
    completeness_rate,
    traces_with_roots,
    "PASS" if completeness_rate >= 95 else "FAIL"
)], ["total_spans", "orphaned_spans", "completeness_rate", "traces_with_roots", "status"]).withColumn("validation_timestamp", current_timestamp())

validation_result.write.mode("append").saveAsTable(f"{catalog_name}.zerobus.trace_completeness_results")

print(f"✅ Trace completeness validation: {completeness_rate:.2f}% complete ({orphan_count}/{total_spans} orphaned)")
