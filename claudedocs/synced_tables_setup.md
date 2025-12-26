# Synced Tables Setup for Zerobus Observability Platform

## Overview

**Note**: Databricks Online Tables are deprecated as of 2025. Use **Synced Tables** instead for low-latency data serving.

Synced Tables provide real-time synchronization of Delta tables to external databases (PostgreSQL, MySQL) for low-latency serving and operational workloads.

## Architecture

```
DLT Streaming Tables → Synced Tables → Database Instance (PostgreSQL)
   ├─ metrics_1min_rollup     → metrics_1min_synced
   ├─ traces_assembled_silver → traces_assembled_synced
   └─ logs_silver             → logs_synced
```

## Prerequisites

### 1. Database Instance Required

Synced Tables require a **Database Instance** to be created first. This represents a logical PostgreSQL database hosted by Databricks.

**Options:**

#### Option A: Using Databricks UI
1. Navigate to **Data** → **Database Instances**
2. Click **Create Database Instance**
3. Configure:
   - **Name**: `zerobus-instance`
   - **Capacity**: `CU_1` (1 compute unit for dev/test)
   - **Region**: Same as your workspace
4. Wait for provisioning (5-10 minutes)

#### Option B: Using Python SDK
```python
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.database import DatabaseInstance

w = WorkspaceClient()

instance = w.database.create_database_instance(
    database_instance=DatabaseInstance(
        name="zerobus-instance",
        capacity="CU_1"
    )
)
print(f"✅ Database Instance created: {instance.name}")
```

#### Option C: Using DABS (Recommended)
Create `resources/database_instances.yml`:

```yaml
resources:
  database_instances:
    zerobus_instance:
      name: "zerobus-${bundle.target}"
      capacity: CU_1
```

Deploy with:
```bash
databricks bundle deploy -t dev
```

### 2. Database Catalog

Create a Database Catalog to map the Unity Catalog schema to the Database Instance:

```yaml
resources:
  database_catalogs:
    zerobus_catalog:
      database_instance_name: "zerobus-${bundle.target}"
      database_name: "${var.schema_name}"
      name: "${var.catalog_name}.${var.schema_name}_catalog"
      create_database_if_not_exists: true
```

## Synced Tables Configuration

### Tables to Sync

1. **metrics_1min_synced**: 1-minute metric rollups for real-time dashboards
   - Source: `jmr_demo.zerobus_sdp.metrics_1min_rollup`
   - Primary Keys: `name`, `service_name`, `window_start`
   - Use Case: Low-latency queries for metrics dashboards

2. **traces_assembled_synced**: Assembled trace data with span details
   - Source: `jmr_demo.zerobus_sdp.traces_assembled_silver`
   - Primary Keys: `trace_id`, `window_start`
   - Use Case: Real-time trace lookup and visualization

3. **logs_synced**: Enriched logs with trace context
   - Source: `jmr_demo.zerobus_sdp.logs_silver`
   - Primary Keys: `trace_id`, `span_id`, `log_timestamp`
   - Use Case: Log correlation and real-time log analysis

### Scheduling Policies

- **CONTINUOUS**: Real-time sync (recommended for streaming sources)
- **TRIGGERED**: Manual sync on demand
- **SNAPSHOT**: Periodic full snapshot

## Setup Methods

### Method 1: Via Databricks Job (Recommended)

The setup script is integrated as a Databricks job in the Asset Bundle. The Database Instance name is configured via bundle variables.

**Configure Database Instance Name:**

Edit `databricks.yml` for your target environment:

```yaml
targets:
  dev:
    variables:
      database_instance_name: "zerobus-dev"  # Set your Database Instance name
```

**Deploy and Run:**

```bash
# Deploy the bundle (includes the setup job)
databricks bundle deploy -t dev --profile DEFAULT

# Run the setup job (uses database_instance_name from variables)
databricks bundle run -t dev setup_synced_tables --profile DEFAULT
```

**Job Configuration:**
- **Name**: `[dev] Setup Synced Tables`
- **Cluster**: Single-node serverless (i3.xlarge)
- **Timeout**: 30 minutes
- **Max Concurrent Runs**: 1
- **Libraries**: `databricks-sdk>=0.20.0`

**Variables Used:**
- `database_instance_name`: Name of the Database Instance (must be set in target variables)
- `catalog_name`: Unity Catalog name (default: `jmr_demo`)
- `schema_name`: Schema name (default: `zerobus_sdp`)

### Method 2: Direct Script Execution

Run the provided script to create synced tables:

```bash
python scripts/setup_online_tables.py --database-instance zerobus-instance
```

**Script Options:**
- `--database-instance`: Database Instance name (required)
- `--catalog-name`: Catalog name (default: `jmr_demo`)
- `--schema-name`: Schema name (default: `zerobus_sdp`)

**Script Workflow:**
1. Validates Database Instance name
2. Creates 3 synced tables with continuous sync
3. Configures primary keys and storage locations
4. Reports status of each table

**Expected Output:**
```
🚀 Creating Databricks Synced Tables...
📍 Catalog: jmr_demo, Schema: zerobus_sdp
📍 Database Instance: zerobus-instance

📦 Creating synced table: jmr_demo.zerobus_sdp.metrics_1min_synced
   └─ Source: jmr_demo.zerobus_sdp.metrics_1min_rollup
   └─ Primary Keys: name, service_name, window_start
   └─ Scheduling: CONTINUOUS
   ✅ Created: jmr_demo.zerobus_sdp.metrics_1min_synced

...

✅ Synced Tables setup complete!
```

## DABS Configuration (Future Enhancement)

**Current Status**: DABS does not yet natively support `synced_database_tables` resources in YAML.

**Workaround**: Use Python SDK script (provided) or Databricks UI.

**Expected Future YAML Format**:
```yaml
resources:
  synced_database_tables:
    metrics_1min_synced:
      name: "${var.catalog_name}.${var.schema_name}.metrics_1min_synced"
      database_instance_name: "zerobus-${bundle.target}"
      logical_database_name: "${var.schema_name}"
      spec:
        source_table_full_name: "${var.catalog_name}.${var.schema_name}.metrics_1min_rollup"
        primary_key_columns:
          - name
          - service_name
          - window_start
        scheduling_policy: CONTINUOUS
        new_pipeline_spec:
          storage_catalog: "${var.catalog_name}"
          storage_schema: "${var.schema_name}"
```

## Verification

### Check Synced Table Status

```python
from databricks.sdk import WorkspaceClient

w = WorkspaceClient()
table = w.database.get_synced_database_table(
    name="jmr_demo.zerobus_sdp.metrics_1min_synced"
)
print(f"Status: Active")
print(f"Source: {table.spec.source_table_full_name}")
```

### Query Synced Table via SQL

```sql
-- Query the synced table directly from the Database Instance
SELECT * FROM zerobus_sdp.metrics_1min_synced
WHERE window_start >= CURRENT_TIMESTAMP() - INTERVAL 1 HOUR
LIMIT 100;
```

### Access via PostgreSQL Client

Synced Tables can be queried using standard PostgreSQL clients:

```bash
psql -h <database-instance-host> -U <username> -d zerobus_sdp -c "SELECT COUNT(*) FROM metrics_1min_synced;"
```

Connection details available in Databricks UI under Database Instance → Connection Details.

## Performance Considerations

### Latency
- **Continuous Sync**: Sub-second latency (typically < 1 second)
- **Triggered Sync**: On-demand (manual trigger required)
- **Snapshot Sync**: Configurable intervals (e.g., every 5 minutes)

### Throughput
- CU_1: ~1000 writes/sec (suitable for dev/test)
- CU_2: ~5000 writes/sec (suitable for production)
- CU_4+: 10000+ writes/sec (high-throughput production)

### Storage
- Synced Tables store data in both:
  1. **Database Instance** (PostgreSQL) - for low-latency queries
  2. **Storage Catalog** (Delta Lake) - for pipeline management

## Cost Optimization

1. **Right-size Instance Capacity**: Start with CU_1, scale based on query load
2. **Limit Synced Data**: Only sync recent data (e.g., last 24 hours)
3. **Use Triggered Sync for Historical Data**: Reduce continuous sync overhead
4. **Monitor Pipeline Costs**: Check DLT pipeline costs in Billing Console

## Troubleshooting

### Error: "Database Instance not found"
**Solution**: Create Database Instance first (see Prerequisites)

### Error: "Source table does not exist"
**Solution**: Ensure DLT pipeline has run and source tables are populated

### Error: "Primary key columns not found"
**Solution**: Verify column names match source table schema exactly (case-sensitive)

### Sync Lag Issues
**Symptoms**: Synced data is outdated
**Solutions**:
- Check Database Instance capacity (upgrade if needed)
- Verify DLT pipeline is running continuously
- Check for backpressure in source streaming tables

## Migration from Online Tables

If you previously used Online Tables (now deprecated):

1. **Identify Online Tables**:
   ```sql
   SELECT * FROM system.billing.usage
   WHERE billing_origin_product = 'ONLINE_TABLES'
     AND usage_date > DATE_SUB(NOW(), 7);
   ```

2. **Create Equivalent Synced Tables**: Use same source tables and primary keys

3. **Update Application Code**: Change connection strings from Online Tables serving endpoint to Database Instance connection details

4. **Delete Old Online Tables**:
   ```python
   w.online_tables.delete(name="old_online_table_name")
   ```

## References

- [Databricks Synced Tables Documentation](https://docs.databricks.com/aws/en/oltp/instances/sync-data/sync-table)
- [Database Instances API](https://docs.databricks.com/api/workspace/database)
- [Databricks SDK Python - Database Module](https://github.com/databricks/databricks-sdk-py/blob/main/docs/workspace/database/database.rst)
- [Migration from Online Tables Guide](https://docs.databricks.com/aws/en/machine-learning/feature-store/migrate-from-online-tables)

## Quick Start (End-to-End)

```bash
# 1. Create Database Instance (via UI or SDK - see Prerequisites)
#    Example: "zerobus-dev" for development environment

# 2. Configure Database Instance name in databricks.yml
#    Edit targets.dev.variables.database_instance_name: "zerobus-dev"

# 3. Deploy bundle with synced tables setup job
databricks bundle deploy -t dev --profile DEFAULT

# 4. Run the setup job (uses database_instance_name from bundle variables)
databricks bundle run -t dev setup_synced_tables --profile DEFAULT

# 5. Verify synced tables are active
databricks tables list --catalog jmr_demo --schema zerobus_sdp | grep synced

# 6. Query synced data
databricks sql execute --warehouse-id <warehouse-id> \
  --query "SELECT COUNT(*) FROM jmr_demo.zerobus_sdp.metrics_1min_synced"
```

## Next Steps

1. Create Database Instance (if not already done)
2. Deploy bundle: `databricks bundle deploy -t dev`
3. Run setup job with Database Instance name
4. Verify synced tables are active and syncing
5. Update application code to query synced tables
6. Monitor sync performance and optimize capacity as needed
