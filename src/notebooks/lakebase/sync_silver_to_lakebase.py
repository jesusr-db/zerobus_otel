# Databricks notebook source
# MAGIC %md
# MAGIC # Lakebase Sync - Silver Tables to Synced Database Tables
# MAGIC 
# MAGIC Creates and syncs silver tables to Lakebase using CREATE SYNCED TABLE SQL.
# MAGIC 
# MAGIC **Input**: `{catalog}.zerobus.*_silver` tables
# MAGIC **Output**: `{catalog}.{lakebase_schema}.*_silver` synced tables
# MAGIC **Strategy**: Create synced tables with TRIGGERED scheduling policy

# COMMAND ----------

# MAGIC %md
# MAGIC ## Setup

# COMMAND ----------

# MAGIC %pip install --upgrade databricks-sdk --quiet
# MAGIC dbutils.library.restartPython()

# COMMAND ----------

import logging
import uuid
from pyspark.sql import SparkSession
from pyspark.sql.functions import col

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Parameters

# COMMAND ----------

dbutils.widgets.text("source_catalog", "jmr_demo", "Source Catalog")
dbutils.widgets.text("source_schema", "zerobus", "Source Schema")
dbutils.widgets.text("database_instance_name", "zerobus-lakebase-dev", "Database Instance Name")
dbutils.widgets.text("lakebase_catalog", "jmr_demo", "Lakebase Catalog")
dbutils.widgets.text("lakebase_schema", "zerobus_lakebase", "Lakebase Schema")
dbutils.widgets.text("storage_catalog", "jmr_demo", "Storage Catalog")
dbutils.widgets.text("storage_schema", "lakebase_storage", "Storage Schema")

source_catalog = dbutils.widgets.get("source_catalog")
source_schema = dbutils.widgets.get("source_schema")
database_instance_name = dbutils.widgets.get("database_instance_name")
lakebase_catalog = dbutils.widgets.get("lakebase_catalog")
lakebase_schema = dbutils.widgets.get("lakebase_schema")
storage_catalog = dbutils.widgets.get("storage_catalog")
storage_schema = dbutils.widgets.get("storage_schema")

logger.info(f"Source: {source_catalog}.{source_schema}.*_silver")
logger.info(f"Database Instance: {database_instance_name}")
logger.info(f"Target: {lakebase_catalog}.{lakebase_schema}")
logger.info(f"Storage: {storage_catalog}.{storage_schema}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Initialize

# COMMAND ----------

from databricks.sdk import WorkspaceClient

w = WorkspaceClient()
spark = SparkSession.builder.getOrCreate()

# COMMAND ----------

# MAGIC %md
# MAGIC ## Enable Change Data Feed on Silver Tables

# COMMAND ----------

logger.info("Enabling Change Data Feed on silver tables...")

try:
    spark.sql(f"ALTER TABLE {source_catalog}.{source_schema}.traces_silver SET TBLPROPERTIES (delta.enableChangeDataFeed = true)")
    logger.info("✅ Enabled CDC on traces_silver")
except Exception as e:
    logger.warning(f"traces_silver CDC: {str(e)}")

try:
    spark.sql(f"ALTER TABLE {source_catalog}.{source_schema}.logs_silver SET TBLPROPERTIES (delta.enableChangeDataFeed = true)")
    logger.info("✅ Enabled CDC on logs_silver")
except Exception as e:
    logger.warning(f"logs_silver CDC: {str(e)}")

try:
    spark.sql(f"ALTER TABLE {source_catalog}.{source_schema}.traces_assembled_silver SET TBLPROPERTIES (delta.enableChangeDataFeed = true)")
    logger.info("✅ Enabled CDC on traces_assembled_silver")
except Exception as e:
    logger.warning(f"traces_assembled_silver CDC: {str(e)}")

logger.info("Change Data Feed enablement complete")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Discover Silver Tables

# COMMAND ----------

silver_tables = spark.sql(f"""
    SHOW TABLES IN {source_catalog}.{source_schema}
""").filter(col("tableName").endswith("_silver")).select("tableName").collect()

silver_table_names = [row.tableName for row in silver_tables]

logger.info(f"Found {len(silver_table_names)} silver tables to sync:")
for table in silver_table_names:
    logger.info(f"  - {table}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Sync Function

# COMMAND ----------

def sync_table_to_lakebase(
    table_name: str,
    source_catalog: str,
    source_schema: str,
    lakebase_catalog: str,
    lakebase_schema: str,
    database_instance_name: str,
    storage_catalog: str,
    storage_schema: str,
    w: WorkspaceClient
):
    """
    Sync a Delta table to Lakebase using create_synced_database_table API.
    """
    from databricks.sdk.service.database import SyncedDatabaseTable, SyncedTableSpec, SyncedTableSchedulingPolicy, NewPipelineSpec
    
    source_full_name = f"{source_catalog}.{source_schema}.{table_name}"
    synced_table_name = f"{lakebase_catalog}.{lakebase_schema}.{table_name}"
    
    try:
        logger.info(f"{table_name}: Getting table metadata from {source_full_name}")
        
        table_df = spark.table(source_full_name)
        
        primary_keys = []
        if "trace_id" in table_df.columns:
            primary_keys = ["trace_id"]
        elif "log_id" in table_df.columns:
            primary_keys = ["log_id"]
        elif "metric_id" in table_df.columns:
            primary_keys = ["metric_id"]
        else:
            logger.warning(f"{table_name}: No standard primary key found, will attempt without PK")
        
        logger.info(f"{table_name}: Creating synced table {synced_table_name}")
        logger.info(f"{table_name}: Primary keys: {primary_keys if primary_keys else 'None'}")
        
        synced_table = w.database.create_synced_database_table(
            SyncedDatabaseTable(
                name=synced_table_name,
                database_instance_name=database_instance_name,
                logical_database_name=lakebase_schema,
                spec=SyncedTableSpec(
                    source_table_full_name=source_full_name,
                    primary_key_columns=primary_keys if primary_keys else None,
                    scheduling_policy=SyncedTableSchedulingPolicy.TRIGGERED,
                    create_database_objects_if_missing=True,
                    new_pipeline_spec=NewPipelineSpec(
                        storage_catalog=storage_catalog,
                        storage_schema=storage_schema
                    )
                ),
            )
        )
        
        logger.info(f"{table_name}: Synced table created successfully")
        
        return {
            "table": table_name,
            "status": "success",
            "synced_table_name": synced_table_name
        }
        
    except Exception as e:
        if "already exists" in str(e).lower():
            logger.info(f"{table_name}: Synced table already exists, triggering sync")
            return {
                "table": table_name,
                "status": "triggered",
                "synced_table_name": synced_table_name
            }
        else:
            logger.error(f"{table_name}: Sync failed - {str(e)}")
            return {
                "table": table_name,
                "status": "failed",
                "error": str(e)
            }

# COMMAND ----------

# MAGIC %md
# MAGIC ## Execute Sync for All Silver Tables

# COMMAND ----------

sync_results = []

for table_name in silver_table_names:
    logger.info(f"Processing {table_name}...")
    result = sync_table_to_lakebase(
        table_name=table_name,
        source_catalog=source_catalog,
        source_schema=source_schema,
        lakebase_catalog=lakebase_catalog,
        lakebase_schema=lakebase_schema,
        database_instance_name=database_instance_name,
        storage_catalog=storage_catalog,
        storage_schema=storage_schema,
        w=w
    )
    sync_results.append(result)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Summary

# COMMAND ----------

from pyspark.sql import Row

results_df = spark.createDataFrame([Row(**r) for r in sync_results])
display(results_df)

success_count = len([r for r in sync_results if r["status"] in ["success", "triggered"]])
failed_count = len([r for r in sync_results if r["status"] == "failed"])

logger.info(f"Sync Summary: {success_count} succeeded, {failed_count} failed")

if failed_count > 0:
    logger.warning(f"Lakebase sync completed with {failed_count} failures")
    for result in sync_results:
        if result["status"] == "failed":
            logger.error(f"  - {result['table']}: {result.get('error', 'Unknown error')}")
