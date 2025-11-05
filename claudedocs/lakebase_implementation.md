# Lakebase Integration Implementation

**Branch**: `feature_lakebase`  
**Status**: Ready for deployment (manual Lakebase instance setup required)  
**Created**: 2025-10-31

## Overview

Implemented parallel architecture to sync silver tables to Databricks Lakebase OLTP instance for low-latency queries, while maintaining existing DBSQL for batch analytics.

## Architecture

```
Bronze → Silver (streaming) → [DBSQL (batch analytics) + Lakebase (real-time app)]
                             ↓                          ↓
                        Gold/Alerting/Quality      O11y App (future)
```

## Implementation Details

### 1. Configuration Files

**`resources/lakebase.yml`**
- Documents Lakebase instance configuration
- Defines variables for instance name and enablement
- Note: Lakebase instances cannot be provisioned via DABs yet (manual setup required)

**`resources/jobs.yml`**
- Added `lakebase_sync` job
- Schedule: Every 5 minutes (`0 0/5 * * * ?`)
- Timeout: 15 minutes
- Max concurrent runs: 1

### 2. Sync Notebook

**`src/notebooks/lakebase/sync_silver_to_lakebase.py`**

**Features**:
- Auto-discovers all `*_silver` tables in `{catalog}.zerobus` schema
- Incremental sync using timestamp-based watermarking
- Default lookback: 10 minutes (configurable)
- JDBC connection to Lakebase instance
- Error handling with detailed logging
- Summary report of sync results

**Parameters**:
- `catalog_name`: Source catalog (default: `jmr_demo`)
- `schema_name`: Source schema (default: `zerobus`)
- `lakebase_instance`: Target Lakebase instance name
- `lookback_minutes`: Incremental sync window (default: 10)

**Sync Strategy**:
1. Discover all tables ending in `_silver`
2. For each table:
   - Identify timestamp column
   - Filter rows updated in last N minutes
   - Append to Lakebase via JDBC
3. Report success/failure for each table

### 3. Tables Synced

Current silver tables:
- `traces_silver`
- `logs_silver`
- `metrics_silver`

All tables matching `*_silver` pattern will be automatically synced.

## Deployment Steps

### Prerequisites
1. **Create Lakebase instance** via Databricks UI:
   - Name: `zerobus-lakebase-dev`
   - Type: SMALL (default)
   - Region: Same as workspace

### Deploy
```bash
# Validate configuration
databricks bundle validate -t dev --profile DEFAULT

# Deploy bundle
databricks bundle deploy -t dev --profile DEFAULT

# Run sync job manually (first run)
databricks bundle run -t dev lakebase_sync --profile DEFAULT
```

### Monitor
```bash
# Check job status
databricks jobs list --profile DEFAULT | grep lakebase

# View job runs
databricks runs list --job-name "[dev] Lakebase Sync" --profile DEFAULT
```

## Configuration Options

### Adjust Sync Frequency
Edit `resources/jobs.yml`:
```yaml
schedule:
  quartz_cron_expression: "0 0/5 * * * ?"  # Every 5 minutes
```

### Adjust Lookback Window
Edit job parameters in `resources/jobs.yml`:
```yaml
base_parameters:
  lookback_minutes: "10"  # Increase for more overlap
```

### Disable Lakebase Sync
```bash
# Pause schedule
databricks jobs update --job-id <job_id> --pause-status PAUSED
```

## Future Enhancements (Backlog)

1. **O11y App Integration**
   - Update app connection strings to query Lakebase
   - Implement fallback to DBSQL on Lakebase failure
   - Add connection pooling for high concurrency

2. **Monitoring & Observability**
   - Track sync lag metrics
   - Monitor Lakebase query performance
   - Alert on sync failures
   - Dashboard for data freshness

3. **Performance Optimization**
   - Add indexes on frequently queried columns
   - Denormalize/pre-aggregate for OLTP patterns
   - Implement merge/upsert instead of append
   - Parallel sync for independent tables

4. **Schema Management**
   - Auto-detect schema changes
   - Handle schema evolution gracefully
   - Validate schema compatibility

## Testing

### Validation Checklist
- [x] Bundle validates successfully
- [ ] Lakebase instance created manually
- [ ] Sync job deploys successfully
- [ ] Sync job runs without errors
- [ ] Row counts match between silver tables and Lakebase
- [ ] Incremental sync only processes recent data
- [ ] Query latency from Lakebase < DBSQL

### Test Commands
```bash
# Validate deployment
databricks bundle validate -t dev

# Deploy and run
databricks bundle deploy -t dev
databricks bundle run -t dev lakebase_sync

# Check row counts
databricks sql-query "SELECT COUNT(*) FROM jmr_demo.zerobus.traces_silver"
# Compare with Lakebase query result
```

## Rollback

If issues arise:
```bash
# Switch back to main branch
git checkout main

# Disable sync job
databricks jobs update --job-id <job_id> --pause-status PAUSED

# Delete Lakebase instance (if needed)
# Done via Databricks UI
```

## Notes

- Lakebase instance provisioning via DABs is not yet supported (as of 2025-10-31)
- Manual instance creation required before first deployment
- JDBC connection details may need adjustment based on actual Lakebase setup
- App integration (query routing to Lakebase) is deferred to backlog
