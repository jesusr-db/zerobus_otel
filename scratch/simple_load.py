# Databricks notebook source
"""
SCRATCH: Simple CSV to Delta - Load sample data
"""

# COMMAND ----------

# Read and write spans
spark.sql("CREATE SCHEMA IF NOT EXISTS main.jmr_demo")

# COMMAND ----------

# Load traces/spans
traces_df = spark.read.option("header", "true").csv("dbfs:/Users/jesus.rodriguez@databricks.com/zerobus-1/SampleData/traces.csv")

# Parse JSON columns
from pyspark.sql.functions import *
from pyspark.sql.types import *

traces_parsed = (traces_df
  .withColumn("attributes", from_json(col("attributes"), "map<string,string>"))
  .withColumn("resource", from_json(col("resource"), "struct<attributes:map<string,string>,dropped_attributes_count:int>"))
  .withColumn("status", from_json(col("status"), "struct<message:string,code:string>"))
  .withColumn("instrumentation_scope", from_json(col("instrumentation_scope"), "struct<name:string,version:string,attributes:map<string,string>,dropped_attributes_count:int>"))
  .withColumn("start_time_unix_nano", col("start_time_unix_nano").cast("long"))
  .withColumn("end_time_unix_nano", col("end_time_unix_nano").cast("long"))
)

traces_parsed.write.mode("overwrite").format("delta").saveAsTable("main.jmr_demo.otel_spans")
print(f"✅ Loaded {traces_parsed.count()} spans")

# COMMAND ----------

# Load metrics  
metrics_df = spark.read.option("header", "true").csv("dbfs:/Users/jesus.rodriguez@databricks.com/zerobus-1/SampleData/Metrics.csv")

metrics_parsed = (metrics_df
  .withColumn("resource", from_json(col("resource"), "struct<attributes:map<string,string>,dropped_attributes_count:int>"))
  .withColumn("gauge", from_json(col("gauge"), "struct<time_unix_nano:long,value:double,attributes:map<string,string>>"))
  .withColumn("sum", from_json(col("sum"), "struct<time_unix_nano:long,value:double,attributes:map<string,string>,is_monotonic:boolean,aggregation_temporality:string>"))
  .withColumn("histogram", from_json(col("histogram"), "struct<time_unix_nano:long,count:long,sum:double,bucket_counts:array<long>,explicit_bounds:array<double>,attributes:map<string,string>>"))
)

metrics_parsed.write.mode("overwrite").format("delta").saveAsTable("main.jmr_demo.otel_metrics")
print(f"✅ Loaded {metrics_parsed.count()} metrics")

# COMMAND ----------

# Load logs
logs_df = spark.read.option("header", "true").csv("dbfs:/Users/jesus.rodriguez@databricks.com/zerobus-1/SampleData/Logs.csv")

logs_parsed = (logs_df
  .withColumn("attributes", from_json(col("attributes"), "map<string,string>"))
  .withColumn("resource", from_json(col("resource"), "struct<attributes:map<string,string>,dropped_attributes_count:int>"))
  .withColumn("instrumentation_scope", from_json(col("instrumentation_scope"), "struct<name:string,version:string,attributes:map<string,string>,dropped_attributes_count:int>"))
  .withColumn("time_unix_nano", col("time_unix_nano").cast("long"))
  .withColumn("observed_time_unix_nano", col("observed_time_unix_nano").cast("long"))
)

logs_parsed.write.mode("overwrite").format("delta").saveAsTable("main.jmr_demo.otel_logs")
print(f"✅ Loaded {logs_parsed.count()} logs")

# COMMAND ----------

print("""
✅ Bronze tables created:
- main.jmr_demo.otel_spans
- main.jmr_demo.otel_metrics  
- main.jmr_demo.otel_logs

Run: SELECT * FROM main.jmr_demo.otel_spans LIMIT 10
""")
