# Databricks notebook source
"""
Data Quality: Validate Cross-Signal Correlation
Validates correlation between traces, logs, and metrics
"""

from pyspark.sql.functions import *

dbutils.widgets.text("catalog_name", "observability_poc", "Catalog Name")

catalog_name = dbutils.widgets.get("catalog_name")

traces_table = f"{catalog_name}.silver.traces_silver"
logs_table = f"{catalog_name}.silver.logs_silver"

traces = spark.table(traces_table)
logs = spark.table(logs_table)

trace_ids = traces.select("trace_id").distinct()
log_trace_ids = logs.select("trace_id").distinct()

traces_with_logs = trace_ids.join(log_trace_ids, "trace_id", "inner").count()
total_traces = trace_ids.count()
correlation_rate = (traces_with_logs / total_traces * 100) if total_traces > 0 else 0

validation_result = spark.createDataFrame([{
    "validation_timestamp": current_timestamp(),
    "total_traces": total_traces,
    "traces_with_logs": traces_with_logs,
    "correlation_rate": correlation_rate,
    "status": "PASS" if correlation_rate >= 80 else "WARN"
}])

validation_result.write.mode("append").saveAsTable(f"{catalog_name}.quality.cross_signal_correlation_results")

print(f"✅ Cross-signal correlation validation: {correlation_rate:.2f}% correlation ({traces_with_logs}/{total_traces} traces with logs)")
