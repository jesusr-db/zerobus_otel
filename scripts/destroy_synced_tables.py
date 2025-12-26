# Databricks notebook source
# MAGIC %md
# MAGIC # Destroy Databricks Synced Tables and Database Instance
# MAGIC
# MAGIC Deletes synced tables, pipelines, and database instance:
# MAGIC - metrics_1min_synced
# MAGIC - traces_silver_synced
# MAGIC - traces_assembled_synced
# MAGIC - logs_synced
# MAGIC - Database Instance

# COMMAND ----------

from databricks.sdk import WorkspaceClient
import time

dbutils.widgets.text("database_instance", "", "Database Instance Name")
dbutils.widgets.text("catalog_name", "jmr_demo", "Catalog Name")
dbutils.widgets.text("schema_name", "zerobus_sdp", "Schema Name")

database_instance_name = dbutils.widgets.get("database_instance")
catalog_name = dbutils.widgets.get("catalog_name")
schema_name = dbutils.widgets.get("schema_name")

if not database_instance_name:
    raise ValueError("❌ Database Instance name is required. Provide via 'database_instance' widget.")

w = WorkspaceClient()
api_client = w.api_client

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 1: List Synced Tables to Delete

# COMMAND ----------

synced_tables_to_delete = [
    f"{catalog_name}.{schema_name}.metrics_1min_synced",
    f"{catalog_name}.{schema_name}.traces_silver_synced",
    f"{catalog_name}.{schema_name}.traces_assembled_synced",
    f"{catalog_name}.{schema_name}.logs_synced"
]

print(f"🗑️  Deleting Synced Tables from {catalog_name}.{schema_name}...")
print(f"📋 Tables to delete:")
for table in synced_tables_to_delete:
    print(f"   - {table}")
print()

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 2: Delete Synced Tables

# COMMAND ----------

deleted_tables = []
failed_tables = []

for table_name in synced_tables_to_delete:
    print(f"🗑️  Deleting synced table: {table_name}")
    
    try:
        api_client.do('DELETE', f'/api/2.0/database/synced_tables/{table_name}')
        print(f"   ✅ Deleted: {table_name}\n")
        deleted_tables.append(table_name)
        
    except Exception as e:
        error_msg = str(e).lower()
        if "does not exist" in error_msg or "not found" in error_msg:
            print(f"   ⚠️  Table does not exist: {table_name}\n")
        else:
            print(f"   ❌ Error deleting table: {str(e)}\n")
            failed_tables.append((table_name, str(e)))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 3: Wait for Pipeline Deletion

# COMMAND ----------

if deleted_tables:
    print(f"⏳ Waiting for pipeline deletion to complete...")
    print(f"   This may take 1-2 minutes...\n")
    time.sleep(60)
    print(f"   ✅ Pipeline deletion should be complete\n")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 4: Delete Database Instance

# COMMAND ----------

print(f"🗑️  Deleting database instance: {database_instance_name}")

try:
    api_client.do('DELETE', f'/api/2.0/database/instances/{database_instance_name}')
    print(f"   ✅ Database instance deletion initiated")
    print(f"   ⏳ Waiting for instance to be deleted (this may take 2-3 minutes)...\n")
    
    max_wait = 180
    wait_interval = 10
    elapsed = 0
    
    while elapsed < max_wait:
        time.sleep(wait_interval)
        elapsed += wait_interval
        
        try:
            instance_response = api_client.do('GET', f'/api/2.0/database/instances/{database_instance_name}')
            status = instance_response.get('instance', instance_response).get('status', {}).get('state', 'UNKNOWN')
            print(f"      Status: {status} ({elapsed}s elapsed)")
            
            if status in ['DELETED', 'TERMINATED']:
                print(f"   ✅ Database instance deleted successfully\n")
                break
        except Exception as check_error:
            error_msg = str(check_error).lower()
            if "does not exist" in error_msg or "not found" in error_msg:
                print(f"   ✅ Database instance deleted successfully\n")
                break
            else:
                print(f"      Checking deletion status...")
    
    if elapsed >= max_wait:
        print(f"   ⚠️  Timeout waiting for deletion, but instance may still be terminating\n")
        
except Exception as e:
    error_msg = str(e).lower()
    if "does not exist" in error_msg or "not found" in error_msg:
        print(f"   ⚠️  Instance does not exist: {database_instance_name}\n")
    else:
        print(f"   ❌ Error deleting instance: {str(e)}\n")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Summary

# COMMAND ----------

print("📊 Deletion Summary:\n")

if deleted_tables:
    print(f"✅ Successfully deleted {len(deleted_tables)} synced table(s):")
    for table in deleted_tables:
        print(f"   - {table}")
    print()

if failed_tables:
    print(f"❌ Failed to delete {len(failed_tables)} synced table(s):")
    for table, error in failed_tables:
        print(f"   - {table}")
        print(f"     Error: {error}")
    print()

if not deleted_tables and not failed_tables:
    print("⚠️  No synced tables were deleted (all tables already removed)")

print(f"\n✅ Cleanup complete!")
print(f"   - Synced tables: Deleted")
print(f"   - Database instance: Deleted or deletion in progress")
