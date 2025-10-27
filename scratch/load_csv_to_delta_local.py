# Databricks notebook source
"""
SCRATCH: Local CSV to Delta Conversion
Converts SampleData CSV files to Delta tables locally for testing
NOT PART OF PRODUCTION WORKFLOW
"""

from pyspark.sql.functions import *
from pyspark.sql.types import *

# COMMAND ----------

# MAGIC %md
# MAGIC ## Configuration

# COMMAND ----------

# DBFS paths
csv_base_path = "/dbfs/Users/jesus.rodriguez@databricks.com/zerobus-1/SampleData"
delta_output_path = "dbfs:/Users/jesus.rodriguez@databricks.com/zerobus-1/scratch/delta_tables"

# Bronze table names
bronze_catalog = "main"
bronze_schema = "jmr_demo"

print(f"CSV Source: {csv_base_path}")
print(f"Delta Output: {delta_output_path}")
print(f"Target: {bronze_catalog}.{bronze_schema}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Load Traces CSV to Delta

# COMMAND ----------

traces_df = (
    spark.read
    .option("header", "true")
    .option("inferSchema", "false")
    .csv(f"{csv_base_path}/traces.csv")
    .withColumn("attributes", from_json(col("attributes"), MapType(StringType(), StringType())))
    .withColumn("events", from_json(col("events"), ArrayType(StructType([
        StructField("time_unix_nano", LongType()),
        StructField("name", StringType()),
        StructField("attributes", MapType(StringType(), StringType())),
        StructField("dropped_attributes_count", IntegerType())
    ]))))
    .withColumn("links", from_json(col("links"), ArrayType(StructType([
        StructField("trace_id", StringType()),
        StructField("span_id", StringType()),
        StructField("trace_state", StringType()),
        StructField("attributes", MapType(StringType(), StringType())),
        StructField("dropped_attributes_count", IntegerType()),
        StructField("flags", IntegerType())
    ]))))
    .withColumn("status", from_json(col("status"), StructType([
        StructField("message", StringType()),
        StructField("code", StringType())
    ])))
    .withColumn("resource", from_json(col("resource"), StructType([
        StructField("attributes", MapType(StringType(), StringType())),
        StructField("dropped_attributes_count", IntegerType())
    ])))
    .withColumn("instrumentation_scope", from_json(col("instrumentation_scope"), StructType([
        StructField("name", StringType()),
        StructField("version", StringType()),
        StructField("attributes", MapType(StringType(), StringType())),
        StructField("dropped_attributes_count", IntegerType())
    ])))
    .withColumn("start_time_unix_nano", col("start_time_unix_nano").cast(LongType()))
    .withColumn("end_time_unix_nano", col("end_time_unix_nano").cast(LongType()))
    .withColumn("flags", col("flags").cast(IntegerType()))
    .withColumn("dropped_attributes_count", col("dropped_attributes_count").cast(IntegerType()))
    .withColumn("dropped_events_count", col("dropped_events_count").cast(IntegerType()))
    .withColumn("dropped_links_count", col("dropped_links_count").cast(IntegerType()))
)

# Write to Delta
traces_df.write.mode("overwrite").format("delta").save(f"{delta_output_path}/otel_spans")

# Register as table
spark.sql(f"DROP TABLE IF EXISTS {bronze_catalog}.{bronze_schema}.otel_spans")
spark.sql(f"""
CREATE TABLE {bronze_catalog}.{bronze_schema}.otel_spans
USING DELTA
LOCATION '{delta_output_path}/otel_spans'
""")

print(f"✅ Loaded {traces_df.count()} spans to {bronze_catalog}.{bronze_schema}.otel_spans")
traces_df.printSchema()

# COMMAND ----------

# MAGIC %md
# MAGIC ## Load Metrics CSV to Delta

# COMMAND ----------

metrics_df = (
    spark.read
    .option("header", "true")
    .option("inferSchema", "false")
    .csv(f"{csv_base_path}/Metrics.csv")
    .withColumn("gauge", from_json(col("gauge"), StructType([
        StructField("start_time_unix_nano", LongType()),
        StructField("time_unix_nano", LongType()),
        StructField("value", DoubleType()),
        StructField("exemplars", ArrayType(StructType([
            StructField("time_unix_nano", LongType()),
            StructField("value", DoubleType()),
            StructField("span_id", StringType()),
            StructField("trace_id", StringType()),
            StructField("filtered_attributes", MapType(StringType(), StringType()))
        ]))),
        StructField("attributes", MapType(StringType(), StringType())),
        StructField("flags", IntegerType())
    ])))
    .withColumn("sum", from_json(col("sum"), StructType([
        StructField("start_time_unix_nano", LongType()),
        StructField("time_unix_nano", LongType()),
        StructField("value", DoubleType()),
        StructField("exemplars", ArrayType(StructType([
            StructField("time_unix_nano", LongType()),
            StructField("value", DoubleType()),
            StructField("span_id", StringType()),
            StructField("trace_id", StringType()),
            StructField("filtered_attributes", MapType(StringType(), StringType()))
        ]))),
        StructField("attributes", MapType(StringType(), StringType())),
        StructField("flags", IntegerType()),
        StructField("aggregation_temporality", StringType()),
        StructField("is_monotonic", BooleanType())
    ])))
    .withColumn("histogram", from_json(col("histogram"), StructType([
        StructField("start_time_unix_nano", LongType()),
        StructField("time_unix_nano", LongType()),
        StructField("count", LongType()),
        StructField("sum", DoubleType()),
        StructField("bucket_counts", ArrayType(LongType())),
        StructField("explicit_bounds", ArrayType(DoubleType())),
        StructField("exemplars", ArrayType(StructType([
            StructField("time_unix_nano", LongType()),
            StructField("value", DoubleType()),
            StructField("span_id", StringType()),
            StructField("trace_id", StringType()),
            StructField("filtered_attributes", MapType(StringType(), StringType()))
        ]))),
        StructField("attributes", MapType(StringType(), StringType())),
        StructField("flags", IntegerType()),
        StructField("min", DoubleType()),
        StructField("max", DoubleType()),
        StructField("aggregation_temporality", StringType())
    ])))
    .withColumn("exponential_histogram", from_json(col("exponential_histogram"), StructType([
        StructField("attributes", MapType(StringType(), StringType())),
        StructField("start_time_unix_nano", LongType()),
        StructField("time_unix_nano", LongType()),
        StructField("count", LongType()),
        StructField("sum", DoubleType()),
        StructField("scale", IntegerType()),
        StructField("zero_count", LongType()),
        StructField("positive_bucket", StructType([
            StructField("offset", IntegerType()),
            StructField("bucket_counts", ArrayType(LongType()))
        ])),
        StructField("negative_bucket", StructType([
            StructField("offset", IntegerType()),
            StructField("bucket_counts", ArrayType(LongType()))
        ])),
        StructField("flags", IntegerType()),
        StructField("exemplars", ArrayType(StructType([
            StructField("time_unix_nano", LongType()),
            StructField("value", DoubleType()),
            StructField("span_id", StringType()),
            StructField("trace_id", StringType()),
            StructField("filtered_attributes", MapType(StringType(), StringType()))
        ]))),
        StructField("min", DoubleType()),
        StructField("max", DoubleType()),
        StructField("zero_threshold", DoubleType()),
        StructField("aggregation_temporality", StringType())
    ])))
    .withColumn("summary", from_json(col("summary"), StructType([
        StructField("start_time_unix_nano", LongType()),
        StructField("time_unix_nano", LongType()),
        StructField("count", LongType()),
        StructField("sum", DoubleType()),
        StructField("quantile_values", ArrayType(StructType([
            StructField("quantile", DoubleType()),
            StructField("value", DoubleType())
        ]))),
        StructField("attributes", MapType(StringType(), StringType())),
        StructField("flags", IntegerType())
    ])))
    .withColumn("metadata", from_json(col("metadata"), MapType(StringType(), StringType())))
    .withColumn("resource", from_json(col("resource"), StructType([
        StructField("attributes", MapType(StringType(), StringType())),
        StructField("dropped_attributes_count", IntegerType())
    ])))
    .withColumn("instrumentation_scope", from_json(col("instrumentation_scope"), StructType([
        StructField("name", StringType()),
        StructField("version", StringType()),
        StructField("attributes", MapType(StringType(), StringType())),
        StructField("dropped_attributes_count", IntegerType())
    ])))
)

# Write to Delta
metrics_df.write.mode("overwrite").format("delta").save(f"{delta_output_path}/otel_metrics")

# Register as table
spark.sql(f"DROP TABLE IF EXISTS {bronze_catalog}.{bronze_schema}.otel_metrics")
spark.sql(f"""
CREATE TABLE {bronze_catalog}.{bronze_schema}.otel_metrics
USING DELTA
LOCATION '{delta_output_path}/otel_metrics'
""")

print(f"✅ Loaded {metrics_df.count()} metrics to {bronze_catalog}.{bronze_schema}.otel_metrics")
metrics_df.printSchema()

# COMMAND ----------

# MAGIC %md
# MAGIC ## Load Logs CSV to Delta

# COMMAND ----------

logs_df = (
    spark.read
    .option("header", "true")
    .option("inferSchema", "false")
    .csv(f"{csv_base_path}/Logs.csv")
    .withColumn("attributes", from_json(col("attributes"), MapType(StringType(), StringType())))
    .withColumn("resource", from_json(col("resource"), StructType([
        StructField("attributes", MapType(StringType(), StringType())),
        StructField("dropped_attributes_count", IntegerType())
    ])))
    .withColumn("instrumentation_scope", from_json(col("instrumentation_scope"), StructType([
        StructField("name", StringType()),
        StructField("version", StringType()),
        StructField("attributes", MapType(StringType(), StringType())),
        StructField("dropped_attributes_count", IntegerType())
    ])))
    .withColumn("time_unix_nano", col("time_unix_nano").cast(LongType()))
    .withColumn("observed_time_unix_nano", col("observed_time_unix_nano").cast(LongType()))
    .withColumn("dropped_attributes_count", col("dropped_attributes_count").cast(IntegerType()))
    .withColumn("flags", col("flags").cast(IntegerType()))
)

# Write to Delta
logs_df.write.mode("overwrite").format("delta").save(f"{delta_output_path}/otel_logs")

# Register as table
spark.sql(f"DROP TABLE IF EXISTS {bronze_catalog}.{bronze_schema}.otel_logs")
spark.sql(f"""
CREATE TABLE {bronze_catalog}.{bronze_schema}.otel_logs
USING DELTA
LOCATION '{delta_output_path}/otel_logs'
""")

print(f"✅ Loaded {logs_df.count()} logs to {bronze_catalog}.{bronze_schema}.otel_logs")
logs_df.printSchema()

# COMMAND ----------

# MAGIC %md
# MAGIC ## Summary

# COMMAND ----------

print(f"""
✅ SCRATCH: Local CSV to Delta Conversion Complete!

Delta Tables Created at: {delta_output_path}/
- otel_spans: {spark.table(f"{bronze_catalog}.{bronze_schema}.otel_spans").count()} rows
- otel_metrics: {spark.table(f"{bronze_catalog}.{bronze_schema}.otel_metrics").count()} rows  
- otel_logs: {spark.table(f"{bronze_catalog}.{bronze_schema}.otel_logs").count()} rows

Registered Tables:
- {bronze_catalog}.{bronze_schema}.otel_spans
- {bronze_catalog}.{bronze_schema}.otel_metrics
- {bronze_catalog}.{bronze_schema}.otel_logs

Next: Run silver transformations to validate pipeline
""")
