# Databricks notebook source
# MAGIC %md
# MAGIC # Silver Layer - Enrich Logs
# MAGIC 
# MAGIC Flattens log structures and enriches with trace context.
# MAGIC 
# MAGIC **Input**: `{catalog}.bronze.otel_logs` (streaming)
# MAGIC **Output**: `{catalog}.jmr_demo.logs_silver` (Delta table)

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
dbutils.widgets.text("checkpoint_location", "/Volumes/main/jmr_demo/storage/checkpoint/silver/logs", "Checkpoint Location")

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
# MAGIC ## Read from Bronze Logs (Streaming)

# COMMAND ----------

logs_table = f"{bronze_catalog}.{bronze_schema}.{bronze_table_prefix}_logs"
logger.info(f"Reading from {logs_table}...")

logs_df = spark.readStream.table(logs_table)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Flatten Log Structures

# COMMAND ----------

flattened_logs = (
    logs_df
    .withColumn("service_name", col("resource.attributes")["service.name"])
    .withColumn("service_version", col("resource.attributes")["service.version"])
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
        "service_version",
        "attributes",
        "ingestion_timestamp"
    )
)

logger.info("Log flattening completed")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Enrich with Trace Context
# MAGIC 
# MAGIC Join with traces_silver to add span-level context (stream-static join)

# COMMAND ----------

traces_table = f"{catalog_name}.jmr_demo.traces_silver"
logger.info(f"Loading trace context from {traces_table}...")

traces_batch = spark.table(traces_table).select(
    "trace_id",
    "span_id",
    col("name").alias("span_name"),
    "kind",
    "http_url",
    "http_method",
    "http_status_code"
)

enriched_logs = (
    flattened_logs
    .join(
        traces_batch,
        ["trace_id", "span_id"],
        "left"
    )
)

logger.info("Log enrichment with trace context completed")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Write to Silver (Streaming)

# COMMAND ----------

logs_silver_table = f"{catalog_name}.jmr_demo.logs_silver"
logger.info(f"Writing to {logs_silver_table}...")

query = (
    enriched_logs.writeStream
    .format("delta")
    .outputMode("append")
    .option("checkpointLocation", checkpoint_location)
    .option("mergeSchema", "true")
    .trigger(availableNow=True)
    .table(logs_silver_table)
)

logger.info(f"Stream started: {logs_silver_table}")
logger.info(f"Query ID: {query.id}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Monitor Stream

# COMMAND ----------
