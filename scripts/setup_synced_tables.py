# Databricks notebook source
# MAGIC %md
# MAGIC # Setup Databricks Synced Tables
# MAGIC
# MAGIC **Note**: Online Tables are deprecated. Use Synced Tables instead.
# MAGIC
# MAGIC Creates synced tables for:
# MAGIC - metrics_1min_rollup → metrics_1min_synced
# MAGIC - traces_silver → traces_silver_synced
# MAGIC - traces_assembled_silver → traces_assembled_synced
# MAGIC - logs_silver → logs_synced
# MAGIC - service_dependencies → service_dependencies_synced

# COMMAND ----------

from databricks.sdk import WorkspaceClient
import requests

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
# MAGIC ## Step 1: Create or Start Database Instance

# COMMAND ----------

print(f"🔍 Checking database instance: {database_instance_name}")

try:
    instance_response = api_client.do('GET', f'/api/2.0/database/instances/{database_instance_name}')
    instance = instance_response.get('instance', instance_response)
    instance_status = instance.get('status', {}).get('state', 'UNKNOWN')
    
    print(f"   ✅ Instance exists: {database_instance_name}")
    print(f"   📊 Status: {instance_status}")
    
    if instance_status in ['STOPPED', 'STOPPING']:
        print(f"   🔄 Starting instance...")
        start_payload = {"stopped": False}
        api_client.do('PATCH', f'/api/2.0/database/instances/{database_instance_name}', body=start_payload)
        print(f"   ⏳ Waiting for instance to start (this may take 2-3 minutes)...")
        
        import time
        max_wait = 300
        wait_interval = 10
        elapsed = 0
        
        while elapsed < max_wait:
            time.sleep(wait_interval)
            elapsed += wait_interval
            status_response = api_client.do('GET', f'/api/2.0/database/instances/{database_instance_name}')
            current_status = status_response.get('instance', status_response).get('status', {}).get('state', 'UNKNOWN')
            print(f"      Status: {current_status} ({elapsed}s elapsed)")
            
            if current_status == 'AVAILABLE':
                print(f"   ✅ Instance started successfully")
                break
            elif current_status in ['FAILED', 'TERMINATED']:
                raise Exception(f"Instance failed to start: {current_status}")
        
        if elapsed >= max_wait:
            print(f"   ⚠️  Timeout waiting for instance to start, but proceeding...")
    
    elif instance_status == 'AVAILABLE':
        print(f"   ✅ Instance is already running")
    
    elif instance_status in ['CREATING', 'STARTING']:
        print(f"   ⏳ Instance is {instance_status}, waiting...")
        import time
        time.sleep(30)
    
    else:
        print(f"   ⚠️  Instance status: {instance_status}")

except Exception as e:
    if "does not exist" in str(e).lower() or "not found" in str(e).lower():
        print(f"   ❌ Instance does not exist: {database_instance_name}")
        print(f"   📝 Creating new instance...")
        
        instance_payload = {
            "name": database_instance_name,
            "capacity": "CU_1"
        }
        
        try:
            create_response = api_client.do('POST', '/api/2.0/database/instances', body=instance_payload)
            print(f"   ✅ Instance creation started")
            print(f"   ⏳ Waiting for instance to become available (this may take 5-10 minutes)...")
            
            import time
            max_wait = 600
            wait_interval = 15
            elapsed = 0
            
            while elapsed < max_wait:
                time.sleep(wait_interval)
                elapsed += wait_interval
                
                try:
                    status_response = api_client.do('GET', f'/api/2.0/database/instances/{database_instance_name}')
                    current_status = status_response.get('instance', status_response).get('status', {}).get('state', 'UNKNOWN')
                    print(f"      Status: {current_status} ({elapsed}s elapsed)")
                    
                    if current_status == 'AVAILABLE':
                        print(f"   ✅ Instance created and available")
                        instance = status_response.get('instance', status_response)
                        print(f"   🔗 Connection: {instance.get('read_write_dns', 'N/A')}")
                        break
                    elif current_status in ['FAILED', 'TERMINATED']:
                        raise Exception(f"Instance creation failed: {current_status}")
                except Exception as check_error:
                    print(f"      Waiting for instance to be queryable...")
            
            if elapsed >= max_wait:
                print(f"   ⚠️  Timeout, but instance may still be provisioning")
                
        except Exception as create_error:
            print(f"   ❌ Error creating instance: {str(create_error)}")
            raise
    else:
        print(f"   ❌ Error checking instance: {str(e)}")
        raise

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 2: Create Synced Tables
# MAGIC 
# MAGIC **Optimization**: Uses a single shared pipeline for all synced tables.
# MAGIC - First table creates a new pipeline with `new_pipeline_spec`
# MAGIC - Subsequent tables reuse the pipeline with `existing_pipeline_spec`
# MAGIC - More efficient resource usage and management

# COMMAND ----------

synced_tables_config = [
    {
        "name": f"{catalog_name}.{schema_name}.metrics_1min_synced",
        "source": f"{catalog_name}.{schema_name}.metrics_1min_rollup",
        "primary_keys": ["name", "service_name", "window_start"],
        "scheduling_policy": "CONTINUOUS"
    },
    {
        "name": f"{catalog_name}.{schema_name}.traces_silver_synced",
        "source": f"{catalog_name}.{schema_name}.traces_silver",
        "primary_keys": ["trace_id", "span_id"],
        "scheduling_policy": "CONTINUOUS"
    },
    {
        "name": f"{catalog_name}.{schema_name}.traces_assembled_synced",
        "source": f"{catalog_name}.{schema_name}.traces_assembled_silver",
        "primary_keys": ["trace_id", "window_start"],
        "scheduling_policy": "CONTINUOUS"
    },
    {
        "name": f"{catalog_name}.{schema_name}.logs_synced",
        "source": f"{catalog_name}.{schema_name}.logs_silver",
        "primary_keys": ["log_key"],
        # "primary_keys": ["observed_timestamp", "trace_id", "span_id", "body"],
        "scheduling_policy": "CONTINUOUS"
    },
    {
        "name": f"{catalog_name}.{schema_name}.service_dependencies_synced",
        "source": f"{catalog_name}.{schema_name}.service_dependencies",
        "primary_keys": ["source_service", "target_service"],
        "scheduling_policy": "SNAPSHOT"
    }
]

print(f"🚀 Creating Databricks Synced Tables...")
print(f"📍 Catalog: {catalog_name}, Schema: {schema_name}")
print(f"📍 Database Instance: {database_instance_name}")
print(f"📍 Strategy: First table creates pipeline, subsequent tables reuse it\n")

# COMMAND ----------

# Track shared pipeline ID for all synced tables
shared_pipeline_id = None

for idx, config in enumerate(synced_tables_config):
    table_name = config["name"]
    source_table = config["source"]
    primary_keys = config["primary_keys"]
    scheduling_policy = config["scheduling_policy"]
    
    print(f"📦 Creating synced table: {table_name}")
    print(f"   └─ Source: {source_table}")
    print(f"   └─ Primary Keys: {', '.join(primary_keys)}")
    print(f"   └─ Scheduling: {scheduling_policy}")
    
    # Build spec based on whether this is the first table or not
    if shared_pipeline_id is None:
        # First table: create new pipeline
        print(f"   └─ Pipeline: Creating new shared pipeline")
        spec = {
            "source_table_full_name": source_table,
            "primary_key_columns": primary_keys,
            "scheduling_policy": scheduling_policy,
            "new_pipeline_spec": {
                "storage_catalog": catalog_name,
                "storage_schema": schema_name
            }
        }
        print(f"   └─ Spec: new_pipeline_spec with catalog={catalog_name}, schema={schema_name}")
    else:
        # Subsequent tables: use existing pipeline
        print(f"   └─ Pipeline: Reusing existing pipeline {shared_pipeline_id}")
        spec = {
            "source_table_full_name": source_table,
            "primary_key_columns": primary_keys,
            "scheduling_policy": scheduling_policy,
            "existing_pipeline_spec": {
                "pipeline_id": shared_pipeline_id
            }
        }
        print(f"   └─ Spec: existing_pipeline_spec with pipeline_id={shared_pipeline_id}")
    
    synced_table = {
        "name": table_name,
        "database_instance_name": database_instance_name,
        "logical_database_name": schema_name,
        "spec": spec
    }
    
    try:
        result = api_client.do('POST', '/api/2.0/database/synced_tables', body=synced_table)
        
        # Capture pipeline ID from first table creation using SDK
        is_first_table = (shared_pipeline_id is None)
        
        if is_first_table:
            print(f"   ⏳ Fetching pipeline ID from created table...")
            
            try:
                import time
                time.sleep(3)  # Wait for table to be fully registered
                
                synced_table_obj = w.database.get_synced_database_table(name=table_name)
                
                if synced_table_obj.data_synchronization_status:
                    shared_pipeline_id = synced_table_obj.data_synchronization_status.pipeline_id
                    
                if shared_pipeline_id:
                    print(f"   🔗 Shared Pipeline ID: {shared_pipeline_id}")
                    print(f"   ✅ Subsequent tables will reuse this pipeline")
                else:
                    print(f"   ⚠️  Warning: Could not capture pipeline_id")
                    print(f"   ⚠️  Each table will create its own pipeline (not optimal)")
                    
            except Exception as fetch_error:
                print(f"   ⚠️  Could not fetch pipeline ID: {str(fetch_error)}")
                print(f"   ⚠️  Continuing without shared pipeline (not optimal)")
        else:
            # For subsequent tables, verify they're using the shared pipeline
            print(f"   ⏳ Verifying pipeline usage...")
            try:
                import time
                time.sleep(2)  # Brief wait for table registration
                
                created_table = w.database.get_synced_database_table(name=table_name)
                if created_table.data_synchronization_status:
                    actual_pipeline_id = created_table.data_synchronization_status.pipeline_id
                    if actual_pipeline_id:
                        if actual_pipeline_id == shared_pipeline_id:
                            print(f"   ✅ Confirmed: Using shared pipeline {actual_pipeline_id}")
                        else:
                            print(f"   ⚠️  WARNING: Created NEW pipeline {actual_pipeline_id}")
                            print(f"   ⚠️  Expected to use: {shared_pipeline_id}")
                            print(f"   ⚠️  API may not support existing_pipeline_spec properly!")
                    else:
                        print(f"   ⚠️  Could not get pipeline_id from created table")
            except Exception as verify_error:
                print(f"   ⚠️  Could not verify pipeline: {str(verify_error)}")
        
        print(f"   ✅ Created synced table: {table_name}\n")
        
    except Exception as e:
        if "already exists" in str(e).lower():
            print(f"   ⚠️  Table already exists: {table_name}")
            try:
                # Use SDK to get existing synced table
                synced_table_obj = w.database.get_synced_database_table(name=table_name)
                
                # Try to capture pipeline ID from existing table if we don't have one yet
                if shared_pipeline_id is None:
                    if synced_table_obj.data_synchronization_status:
                        shared_pipeline_id = synced_table_obj.data_synchronization_status.pipeline_id
                        if shared_pipeline_id:
                            print(f"   🔗 Using existing pipeline from table: {shared_pipeline_id}")
                        else:
                            print(f"   ⚠️  No pipeline_id found in existing table")
                
                postgres_table = synced_table_obj.table_name or table_name.split('.')[-1]
                postgres_schema = synced_table_obj.logical_database_name or schema_name
                print(f"   📊 Status: Active")
                print(f"   📊 Destination: {database_instance_name}.{postgres_schema}.{postgres_table}\n")
            except Exception as get_error:
                print(f"   ⚠️  Could not retrieve status: {str(get_error)}\n")
        else:
            print(f"   ❌ Error creating table: {str(e)}\n")
            raise

# COMMAND ----------

# MAGIC %md
# MAGIC ## Summary

# COMMAND ----------

print("✅ Synced Tables setup complete!\n")

if shared_pipeline_id:
    print(f"🔗 Shared Pipeline ID: {shared_pipeline_id}")
    print(f"   All synced tables are using the same pipeline for efficiency\n")
else:
    print(f"⚠️  Warning: No shared pipeline ID captured")
    print(f"   Tables may be using individual pipelines\n")

print("📋 Summary:")
for config in synced_tables_config:
    try:
        synced_table_obj = w.database.get_synced_database_table(name=config["name"])
        
        # Get pipeline ID if available
        table_pipeline_id = None
        if synced_table_obj.data_synchronization_status:
            table_pipeline_id = synced_table_obj.data_synchronization_status.pipeline_id
        
        print(f"\n{config['name']}")
        print(f"  Status: Active")
        print(f"  Source: {config['source']}")
        if table_pipeline_id:
            print(f"  Pipeline: {table_pipeline_id}")
            # Check if this pipeline matches the shared pipeline
            if shared_pipeline_id and table_pipeline_id == shared_pipeline_id:
                print(f"  ✅ Using shared pipeline")
            else:
                print(f"  ⚠️  Using different pipeline (not optimal)")
    except Exception as e:
        print(f"\n{config['name']}")
        print(f"  ❌ Error: {str(e)}")
