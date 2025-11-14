# Databricks notebook source
# MAGIC %md
# MAGIC # Silver Layer - Assemble Traces
# MAGIC 
# MAGIC Groups spans by trace_id and creates trace-level aggregations.
# MAGIC 
# MAGIC **Input**: `{catalog}.zerobus.traces_silver` (streaming)
# MAGIC **Output**: `{catalog}.zerobus.traces_assembled_silver` (Delta table)

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

dbutils.widgets.text("catalog_name", "observability_poc", "Catalog Name")
dbutils.widgets.text("schema_name", "zerobus", "Target Schema")
dbutils.widgets.text("checkpoint_location", "/Volumes/main/jmr_demo/storage/checkpoint/silver/traces_assembled", "Checkpoint Location")

catalog_name = dbutils.widgets.get("catalog_name")
schema_name = dbutils.widgets.get("schema_name")
checkpoint_location = dbutils.widgets.get("checkpoint_location")

logger.info(f"Catalog: {catalog_name}")
logger.info(f"Checkpoint: {checkpoint_location}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Create Volume if Not Exists

# COMMAND ----------

if checkpoint_location.startswith('/Volumes/'):
    parts = checkpoint_location.split('/')
    volume_name = parts[4] if len(parts) > 4 else None
    if volume_name:
        try:
            spark.sql(f"CREATE VOLUME IF NOT EXISTS {catalog_name}.{schema_name}.{volume_name}")
            logger.info(f"Volume {catalog_name}.{schema_name}.{volume_name} ready")
        except Exception as e:
            logger.warning(f"Could not create volume: {e}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Read from Traces Silver (Streaming)

# COMMAND ----------

traces_table = f"{catalog_name}.{schema_name}.traces_silver"
logger.info(f"Reading from {traces_table}...")

traces_df = (
    spark.readStream
    .table(traces_table)
    .withWatermark("start_timestamp", "10 minutes")
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Assemble Traces

# COMMAND ----------

assembled_traces = (
    traces_df
    .groupBy(
        "trace_id",
        window("start_timestamp", "5 minutes")
    )
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
)

logger.info("Trace assembly aggregations completed")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Write to Silver (Streaming)

# COMMAND ----------

assembled_table = f"{catalog_name}.{schema_name}.traces_assembled_silver"
logger.info(f"Writing to {assembled_table}...")

query = (
    assembled_traces.writeStream
    .format("delta")
    .outputMode("append")
    .option("checkpointLocation", checkpoint_location)
    .option("mergeSchema", "true")
    .trigger(availableNow=True)
    .table(assembled_table)
)

logger.info(f"Stream started: {assembled_table}")
logger.info(f"Query ID: {query.id}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Monitor Stream

# COMMAND ----------
