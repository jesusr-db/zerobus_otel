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

# MAGIC %pip install --upgrade databricks-sdk psycopg2-binary --quiet
# MAGIC dbutils.library.restartPython()

# COMMAND ----------

import logging
import uuid
import psycopg2
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
# MAGIC ## Get Database Instance and Generate Credentials

# COMMAND ----------

logger.info(f"Getting database instance: {database_instance_name}")
instance = w.database.get_database_instance(name=database_instance_name)

logger.info(f"Generating database credentials")
cred = w.database.generate_database_credential(
    request_id=str(uuid.uuid4()), 
    instance_names=[database_instance_name]
)

# Extract username from credential object or use workspace user
db_username = getattr(cred, 'username', None)
if not db_username:
    # Fallback to current workspace user
    current_user = w.current_user.me()
    db_username = current_user.user_name

db_password = cred.token

logger.info(f"Database host: {instance.read_write_dns}")
logger.info(f"Database username: {db_username}")
logger.info(f"Credentials generated successfully")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Create Database Catalog

# COMMAND ----------

from databricks.sdk.service.database import DatabaseCatalog

try:
    logger.info(f"Creating database catalog: {lakebase_catalog}")
    
    catalog = w.database.create_database_catalog(
        DatabaseCatalog(
            name=lakebase_catalog,
            database_instance_name=database_instance_name,
            database_name=lakebase_schema,
            create_database_if_not_exists=True
        )
    )
    
    logger.info(f"Created database catalog: {catalog.name}")
    
except Exception as e:
    if "already exists" in str(e).lower():
        logger.info(f"Database catalog {lakebase_catalog} already exists")
    else:
        logger.error(f"Failed to create database catalog: {str(e)}")
        raise

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
    lakebase_schema: str,
    instance_host: str,
    db_username: str,
    db_password: str
):
    """
    Sync a Delta table to Lakebase database using direct SQL connection.
    """
    source_full_name = f"{source_catalog}.{source_schema}.{table_name}"
    
    try:
        logger.info(f"{table_name}: Reading from {source_full_name}")
        
        table_df = spark.table(source_full_name)
        row_count = table_df.count()
        
        logger.info(f"{table_name}: Found {row_count} rows")
        logger.info(f"{table_name}: Connecting to Lakebase database")
        
        conn = psycopg2.connect(
            host=instance_host,
            dbname="databricks_postgres",
            user=db_username,
            password=db_password,
            sslmode="require"
        )
        
        logger.info(f"{table_name}: Creating schema if not exists")
        with conn.cursor() as cur:
            cur.execute(f"CREATE SCHEMA IF NOT EXISTS {lakebase_schema}")
            conn.commit()
        
        logger.info(f"{table_name}: Writing data to Lakebase")
        
        table_df.write \
            .format("jdbc") \
            .option("url", f"jdbc:postgresql://{instance_host}/databricks_postgres?ssl=true&sslmode=require") \
            .option("dbtable", f"{lakebase_schema}.{table_name}") \
            .option("user", db_username) \
            .option("password", db_password) \
            .option("driver", "org.postgresql.Driver") \
            .mode("overwrite") \
            .save()
        
        conn.close()
        
        logger.info(f"{table_name}: Successfully synced {row_count} rows")
        
        return {
            "table": table_name,
            "status": "success",
            "rows": row_count
        }
        
    except Exception as e:
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
        lakebase_schema=lakebase_schema,
        instance_host=instance.read_write_dns,
        db_username=db_username,
        db_password=db_password
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
