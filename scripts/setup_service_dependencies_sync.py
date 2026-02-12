# Databricks notebook source
# MAGIC %md
# MAGIC # Setup Service Dependencies Synced Table
# MAGIC
# MAGIC Creates a SNAPSHOT synced table for service_dependencies with 3-hour refresh schedule.
# MAGIC
# MAGIC **Note**: SNAPSHOT mode is required for MATERIALIZED_VIEW sources (DLT tables).
# MAGIC This runs as a separate pipeline from the CONTINUOUS synced tables.

# COMMAND ----------

from databricks.sdk import WorkspaceClient
import time

dbutils.widgets.text("database_instance", "zerobus-dev", "Database Instance Name")
dbutils.widgets.text("catalog_name", "jmr_demo", "Catalog Name")
dbutils.widgets.text("schema_name", "zerobus_sdp", "Schema Name")

database_instance_name = dbutils.widgets.get("database_instance")
catalog_name = dbutils.widgets.get("catalog_name")
schema_name = dbutils.widgets.get("schema_name")

if not database_instance_name:
    raise ValueError("❌ Database Instance name is required")

w = WorkspaceClient()
api_client = w.api_client

# COMMAND ----------

# MAGIC %md
# MAGIC ## Create Service Dependencies Synced Table

# COMMAND ----------

table_name = f"{catalog_name}.{schema_name}.service_dependencies_synced"
source_table = f"{catalog_name}.{schema_name}.service_dependencies"

print(f"📦 Setting up synced table: {table_name}")
print(f"   └─ Source: {source_table}")
print(f"   └─ Primary Keys: source_service, target_service")
print(f"   └─ Scheduling: SNAPSHOT (required for MATERIALIZED_VIEW)")
print(f"   └─ Refresh: Every 3 hours")
print(f"   └─ Database Instance: {database_instance_name}")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Step 1: Check if synced table already exists

# COMMAND ----------

existing_table = None
needs_recreation = False

try:
    existing_table = w.database.get_synced_database_table(name=table_name)
    print(f"\n🔍 Found existing synced table: {table_name}")

    if existing_table.data_synchronization_status:
        pipeline_id = existing_table.data_synchronization_status.pipeline_id
        detailed_state = existing_table.data_synchronization_status.detailed_state
        message = existing_table.data_synchronization_status.message

        print(f"   └─ Pipeline ID: {pipeline_id}")
        print(f"   └─ Status: {detailed_state}")
        print(f"   └─ Message: {message}")

        # Check if pipeline exists
        if pipeline_id:
            try:
                pipeline_info = api_client.do('GET', f'/api/2.0/pipelines/{pipeline_id}')
                print(f"   └─ Pipeline exists and is valid")
            except Exception as pipeline_error:
                if "not found" in str(pipeline_error).lower():
                    print(f"   ⚠️  Pipeline {pipeline_id} was deleted - need to recreate synced table")
                    needs_recreation = True
                else:
                    print(f"   ⚠️  Could not verify pipeline: {pipeline_error}")
    else:
        print(f"   └─ No sync status available")

except Exception as e:
    if "not found" in str(e).lower() or "does not exist" in str(e).lower():
        print(f"\n🔍 Synced table does not exist yet: {table_name}")
        existing_table = None
    else:
        print(f"\n⚠️  Error checking existing table: {e}")
        raise

# COMMAND ----------

# MAGIC %md
# MAGIC ### Step 2: Delete orphaned synced table if needed

# COMMAND ----------

if needs_recreation and existing_table:
    print(f"\n🗑️  Deleting orphaned synced table: {table_name}")
    try:
        w.database.delete_synced_database_table(name=table_name)
        print(f"   ✅ Deleted successfully")
        time.sleep(3)  # Wait for deletion to propagate
        existing_table = None
    except Exception as delete_error:
        print(f"   ❌ Error deleting: {delete_error}")
        raise

# COMMAND ----------

# MAGIC %md
# MAGIC ### Step 3: Create synced table if needed

# COMMAND ----------

if existing_table is None or needs_recreation:
    print(f"\n🚀 Creating synced table: {table_name}")

    # SNAPSHOT spec with 3-hour cron schedule
    synced_table_spec = {
        "name": table_name,
        "database_instance_name": database_instance_name,
        "logical_database_name": schema_name,
        "spec": {
            "source_table_full_name": source_table,
            "primary_key_columns": ["source_service", "target_service"],
            "scheduling_policy": "SNAPSHOT",
            "snapshot_schedule": {
                "cron_schedule": {
                    "quartz_cron_expression": "0 0 */3 * * ?",  # Every 3 hours
                    "timezone_id": "UTC"
                }
            },
            "new_pipeline_spec": {
                "storage_catalog": catalog_name,
                "storage_schema": schema_name
            }
        }
    }

    try:
        result = api_client.do('POST', '/api/2.0/database/synced_tables', body=synced_table_spec)
        print(f"   ✅ Created synced table")
        print(f"   Response: {result}")

        # Get details
        time.sleep(3)
        synced_table_obj = w.database.get_synced_database_table(name=table_name)
        if synced_table_obj.data_synchronization_status:
            pipeline_id = synced_table_obj.data_synchronization_status.pipeline_id
            detailed_state = synced_table_obj.data_synchronization_status.detailed_state
            message = synced_table_obj.data_synchronization_status.message
            print(f"\n📊 Synced Table Details:")
            print(f"   └─ Pipeline ID: {pipeline_id}")
            print(f"   └─ Status: {detailed_state}")
            print(f"   └─ Message: {message}")

    except Exception as e:
        print(f"   ❌ Error creating synced table: {e}")
        raise
else:
    print(f"\n✅ Synced table already exists and is healthy: {table_name}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Verify Setup

# COMMAND ----------

print("\n📋 Verification:")
print(f"   Source table: {source_table}")
print(f"   Synced table: {table_name}")
print(f"   Database: {database_instance_name}.{schema_name}.service_dependencies_synced")
print(f"\n   To query from Lakebase:")
print(f"   SELECT * FROM {schema_name}.service_dependencies_synced;")
