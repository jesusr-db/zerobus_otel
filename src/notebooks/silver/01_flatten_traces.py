# Databricks notebook source
# MAGIC %md
# MAGIC # Silver Layer - Flatten Traces
# MAGIC 
# MAGIC Flattens nested structures from bronze.otel_spans into queryable columns.
# MAGIC 
# MAGIC **Input**: `{catalog}.bronze.otel_spans` (streaming)
# MAGIC **Output**: `{catalog}.jmr_demo.traces_silver` (Delta table)

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

dbutils.widgets.text("catalog_name", "observability_poc", "Target Catalog (Silver/Gold)")
dbutils.widgets.text("bronze_catalog", "main", "Bronze Catalog")
dbutils.widgets.text("bronze_schema", "jmr_demo", "Bronze Schema")
dbutils.widgets.text("bronze_table_prefix", "otel", "Bronze Table Prefix")
dbutils.widgets.text("checkpoint_location", "/checkpoint/silver/traces", "Checkpoint Location")

catalog_name = dbutils.widgets.get("catalog_name")
bronze_catalog = dbutils.widgets.get("bronze_catalog")
bronze_schema = dbutils.widgets.get("bronze_schema")
bronze_table_prefix = dbutils.widgets.get("bronze_table_prefix")
checkpoint_location = dbutils.widgets.get("checkpoint_location")

logger.info(f"Target Catalog: {catalog_name}")
logger.info(f"Bronze: {bronze_catalog}.{bronze_schema}.{bronze_table_prefix}_*")
logger.info(f"Checkpoint: {checkpoint_location}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Read from Bronze (Streaming)

# COMMAND ----------

bronze_table = f"{bronze_catalog}.{bronze_schema}.{bronze_table_prefix}_spans"
logger.info(f"Reading from {bronze_table}...")

spans_df = spark.readStream.table(bronze_table)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Flatten Nested Structures

# COMMAND ----------

flattened_traces = (
    spans_df
    .withColumn("service_name", col("resource.attributes")["service.name"])
    .withColumn("service_version", col("resource.attributes")["service.version"])
    .withColumn("telemetry_sdk_language", col("resource.attributes")["telemetry.sdk.language"])
    .withColumn("telemetry_sdk_name", col("resource.attributes")["telemetry.sdk.name"])
    .withColumn("telemetry_sdk_version", col("resource.attributes")["telemetry.sdk.version"])
    .withColumn("http_method", col("attributes")["http.method"])
    .withColumn("http_status_code", col("attributes")["http.status_code"].cast("int"))
    .withColumn("http_url", col("attributes")["http.url"])
    .withColumn("http_target", col("attributes")["http.target"])
    .withColumn("rpc_service", col("attributes")["rpc.service"])
    .withColumn("rpc_method", col("attributes")["rpc.method"])
    .withColumn("rpc_grpc_status_code", col("attributes")["rpc.grpc.status_code"].cast("int"))
    .withColumn("start_timestamp", from_unixtime(col("start_time_unix_nano") / 1e9).cast("timestamp"))
    .withColumn("end_timestamp", from_unixtime(col("end_time_unix_nano") / 1e9).cast("timestamp"))
    .withColumn("duration_ms", (col("end_time_unix_nano") - col("start_time_unix_nano")) / 1e6)
    .withColumn("is_error", col("status.code") == "ERROR")
    .withColumn("status_message", col("status.message"))
    .withColumn("instrumentation_scope_name", col("instrumentation_scope.name"))
    .withColumn("instrumentation_scope_version", col("instrumentation_scope.version"))
    .withColumn("ingestion_timestamp", current_timestamp())
    .select(
        "trace_id",
        "span_id",
        "parent_span_id",
        "name",
        "kind",
        "service_name",
        "service_version",
        "telemetry_sdk_language",
        "telemetry_sdk_name",
        "telemetry_sdk_version",
        "http_method",
        "http_status_code",
        "http_url",
        "http_target",
        "rpc_service",
        "rpc_method",
        "rpc_grpc_status_code",
        "start_timestamp",
        "end_timestamp",
        "duration_ms",
        "is_error",
        "status_message",
        "instrumentation_scope_name",
        "instrumentation_scope_version",
        "attributes",
        "events",
        "links",
        "ingestion_timestamp"
    )
)

logger.info("Schema flattening completed")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Write to Silver (Streaming)

# COMMAND ----------

silver_table = f"{catalog_name}.jmr_demo.traces_silver"
logger.info(f"Writing to {silver_table}...")

query = (
    flattened_traces.writeStream
    .format("delta")
    .outputMode("append")
    .option("checkpointLocation", checkpoint_location)
    .option("mergeSchema", "true")
    .trigger(availableNow=True)
    .table(silver_table)
)

logger.info(f"Stream started: {silver_table}")
logger.info(f"Query ID: {query.id}")
logger.info(f"Status: {query.status}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Monitor Stream

# COMMAND ----------

display(query.recentProgress)
