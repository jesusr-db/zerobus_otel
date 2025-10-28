# Databricks notebook source
# MAGIC %md
# MAGIC # Silver Layer - Flatten Metrics
# MAGIC 
# MAGIC Flattens metric-type-specific STRUCT columns into queryable format.
# MAGIC 
# MAGIC **Input**: `{catalog}.bronze.otel_metrics` (streaming)
# MAGIC **Output**: `{catalog}.jmr_demo.metrics_silver` (Delta table)

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
dbutils.widgets.text("checkpoint_location", "/Volumes/main/jmr_demo/storage/checkpoint/silver/metrics", "Checkpoint Location")

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
# MAGIC ## Read from Bronze Metrics (Streaming)

# COMMAND ----------

metrics_table = f"{bronze_catalog}.{bronze_schema}.{bronze_table_prefix}_metrics"
logger.info(f"Reading from {metrics_table}...")

metrics_df = spark.readStream.table(metrics_table)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Flatten Gauge Metrics

# COMMAND ----------

gauge_metrics = (
    metrics_df
    .filter(col("metric_type") == "gauge")
    .withColumn("service_name", col("resource.attributes")["service.name"])
    .withColumn("metric_timestamp", from_unixtime(col("gauge.time_unix_nano") / 1e9).cast("timestamp"))
    .withColumn("value", col("gauge.value"))
    .withColumn("metric_attributes", col("gauge.attributes"))
    .withColumn("metric_type_detail", lit("gauge"))
    .select(
        "name",
        "description",
        "unit",
        "service_name",
        "metric_timestamp",
        "value",
        "metric_attributes",
        "metric_type_detail"
    )
)

logger.info("Gauge metrics flattened")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Flatten Sum Metrics

# COMMAND ----------

sum_metrics = (
    metrics_df
    .filter(col("metric_type") == "sum")
    .withColumn("service_name", col("resource.attributes")["service.name"])
    .withColumn("metric_timestamp", from_unixtime(col("sum.time_unix_nano") / 1e9).cast("timestamp"))
    .withColumn("value", col("sum.value"))
    .withColumn("metric_attributes", col("sum.attributes"))
    .withColumn("is_monotonic", col("sum.is_monotonic"))
    .withColumn("aggregation_temporality", col("sum.aggregation_temporality"))
    .withColumn("metric_type_detail", lit("sum"))
    .select(
        "name",
        "description",
        "unit",
        "service_name",
        "metric_timestamp",
        "value",
        "metric_attributes",
        "metric_type_detail",
        "is_monotonic",
        "aggregation_temporality"
    )
)

logger.info("Sum metrics flattened")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Flatten Histogram Metrics

# COMMAND ----------

histogram_metrics = (
    metrics_df
    .filter(col("metric_type") == "histogram")
    .withColumn("service_name", col("resource.attributes")["service.name"])
    .withColumn("metric_timestamp", from_unixtime(col("histogram.time_unix_nano") / 1e9).cast("timestamp"))
    .withColumn("histogram_count", col("histogram.count"))
    .withColumn("histogram_sum", col("histogram.sum"))
    .withColumn("bucket_counts", col("histogram.bucket_counts"))
    .withColumn("explicit_bounds", col("histogram.explicit_bounds"))
    .withColumn("histogram_min", col("histogram.min"))
    .withColumn("histogram_max", col("histogram.max"))
    .withColumn("metric_attributes", col("histogram.attributes"))
    .withColumn("metric_type_detail", lit("histogram"))
    .withColumn("value", col("histogram.sum") / col("histogram.count"))
    .select(
        "name",
        "description",
        "unit",
        "service_name",
        "metric_timestamp",
        "value",
        "metric_attributes",
        "metric_type_detail",
        "histogram_count",
        "histogram_sum",
        "histogram_min",
        "histogram_max",
        "bucket_counts",
        "explicit_bounds"
    )
)

logger.info("Histogram metrics flattened")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Union All Metric Types

# COMMAND ----------

all_metrics = (
    gauge_metrics
    .unionByName(sum_metrics, allowMissingColumns=True)
    .unionByName(histogram_metrics, allowMissingColumns=True)
    .withColumn("ingestion_timestamp", current_timestamp())
)

logger.info("All metrics union completed")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Write to Silver (Streaming)

# COMMAND ----------

metrics_silver_table = f"{catalog_name}.jmr_demo.metrics_silver"
logger.info(f"Writing to {metrics_silver_table}...")

query = (
    all_metrics.writeStream
    .format("delta")
    .outputMode("append")
    .option("checkpointLocation", checkpoint_location)
    .option("mergeSchema", "true")
    .trigger(availableNow=True)
    .table(metrics_silver_table)
)

logger.info(f"Stream started: {metrics_silver_table}")
logger.info(f"Query ID: {query.id}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Monitor Stream

# COMMAND ----------
