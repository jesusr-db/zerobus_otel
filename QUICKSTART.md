# Quick Start Guide - Databricks Observability Platform

Get up and running in 5 minutes with Databricks Asset Bundles.

## Prerequisites

✅ Databricks CLI installed (`pip install databricks-cli`)  
✅ Databricks workspace with Unity Catalog enabled  
✅ SQL Warehouse created  
✅ Workspace permissions (create jobs, schemas, tables)

## Step-by-Step Setup

### 1. Configure Environment (2 minutes)

```bash
# Copy environment template
cp .env.template .env

# Edit .env with your details
nano .env
```

**Required values**:
```bash
DATABRICKS_HOST=https://your-workspace.cloud.databricks.com
DATABRICKS_TOKEN=dapi1234567890abcdef  # Create from User Settings > Access Tokens
TF_VAR_warehouse_id=abc123def456        # Get from SQL Warehouses page
TF_VAR_alert_webhook_url=https://webhook.site/your-unique-id  # Use webhook.site for testing
TF_VAR_alert_email=you@company.com
```

**Load environment**:
```bash
source .env
```

### 2. Validate Bundle (30 seconds)

```bash
# Quick validation
make validate

# Or manually:
databricks bundle validate -t dev
```

Expected output:
```
✓ Validating bundle configuration
✓ All resources validated successfully
```

### 3. Deploy to Dev (1 minute)

```bash
# Deploy everything
make deploy-dev

# Or manually:
databricks bundle deploy -t dev
```

This creates:
- Unity Catalog: `observability_poc_dev`
- Schemas: `bronze`, `silver`, `gold`
- 6 Jobs (serverless compute)
- Delta Live Tables pipeline
- All notebooks uploaded

### 4. Load Sample Data (1 minute)

```bash
# Run bronze data loader
make run-loader

# Or manually:
databricks bundle run bronze_data_loader -t dev
```

This loads:
- 1000 trace spans → `traces_bronze`
- 1000 metrics → `metrics_bronze`
- 1700 logs → `logs_bronze`

### 5. Run Transformations (30 seconds)

```bash
# Run silver transformations
make run-silver

# Or manually:
databricks bundle run silver_transformations -t dev
```

This creates:
- Assembled traces
- Service health golden signals
- Enriched logs with trace context
- Parsed metrics

### 6. Verify Deployment (30 seconds)

**View in Databricks UI**:

1. Go to **Workflows** → See 6 jobs deployed
2. Go to **Data** → See catalogs and tables
3. Go to **SQL Editor** → Query tables

**Quick verification query**:
```sql
-- View service health
SELECT * FROM observability_poc_dev.silver.service_health_silver
ORDER BY timestamp DESC
LIMIT 10;

-- View traces
SELECT trace_id, service_name, duration_ms 
FROM observability_poc_dev.bronze.traces_bronze
LIMIT 10;
```

## What You Get

### ✅ Data Pipeline
- **Bronze**: Raw OTEL data (traces, metrics, logs)
- **Silver**: Parsed JSON, assembled traces, golden signals
- **Gold**: Aggregated analytics, service dependencies

### ✅ Scheduled Jobs
| Job | Schedule | Purpose |
|-----|----------|---------|
| Silver Transformations | Every 5 min | Parse and enrich data |
| Gold Aggregations | Hourly | Create rollups |
| Anomaly Alerting | Every 1 min | Detect & alert |
| Data Quality | Daily | Validate data |
| Table Maintenance | Weekly | OPTIMIZE/VACUUM |

### ✅ Tables Created
```
observability_poc_dev
├── bronze
│   ├── traces_bronze (1000 spans)
│   ├── metrics_bronze (1000 metrics)
│   └── logs_bronze (1700 logs)
├── silver
│   ├── traces_silver (assembled traces)
│   ├── service_health_silver (golden signals)
│   ├── logs_silver (enriched logs)
│   └── metrics_silver (parsed metrics)
└── gold
    ├── service_health_hourly_gold
    ├── service_dependencies_gold
    └── metrics_rollups_gold
```

## Sample Queries

### Service Health Dashboard
```sql
-- Service health overview
SELECT 
    service_name,
    request_count,
    error_rate,
    latency_p95_ms,
    is_anomalous,
    CASE 
        WHEN error_rate > 0.05 OR is_anomalous THEN '🔴'
        WHEN error_rate > 0.01 OR latency_p95_ms > 500 THEN '🟡'
        ELSE '🟢'
    END as status
FROM observability_poc_dev.silver.service_health_silver
WHERE timestamp >= CURRENT_TIMESTAMP() - INTERVAL 1 HOUR
ORDER BY timestamp DESC;
```

### Trace Lookup
```sql
-- Find trace by ID
SELECT * FROM observability_poc_dev.silver.traces_silver
WHERE trace_id = '8152f86a9264ac1ebcdaa867facd5719';

-- Spans for trace
SELECT 
    span_id,
    name,
    duration_ms,
    http_status_code
FROM observability_poc_dev.bronze.traces_bronze
WHERE trace_id = '8152f86a9264ac1ebcdaa867facd5719'
ORDER BY start_timestamp;
```

### Logs with Trace Context
```sql
-- Find logs for a trace
SELECT 
    timestamp,
    severity_text,
    body,
    service_name
FROM observability_poc_dev.bronze.logs_bronze
WHERE trace_id = '2afa6a33e6805771af1fca3b4446ea6a'
ORDER BY timestamp;
```

### Service Dependencies
```sql
-- Service call graph
SELECT 
    source_service,
    target_service,
    call_count,
    avg_duration_ms,
    error_count
FROM observability_poc_dev.gold.service_dependencies_gold
WHERE last_seen_timestamp >= CURRENT_TIMESTAMP() - INTERVAL 1 HOUR
ORDER BY call_count DESC;
```

## Common Operations

### View Job Runs
```bash
# List all jobs
databricks jobs list

# View recent runs
databricks runs list --limit 10
```

### Trigger Manual Job Run
```bash
# Run any job
databricks bundle run <job_name> -t dev

# Examples:
databricks bundle run silver_transformations -t dev
databricks bundle run data_quality_validation -t dev
```

### View Logs
```bash
# Get run output
databricks runs get-output --run-id <run-id>
```

### Update and Redeploy
```bash
# Make changes to notebooks or config
# Then redeploy
make deploy-dev

# Or force update
databricks bundle deploy -t dev --force
```

## Troubleshooting

### Issue: "Authentication failed"
**Solution**: Check `.env` has correct `DATABRICKS_HOST` and `DATABRICKS_TOKEN`

### Issue: "SQL warehouse not found"
**Solution**: 
1. Go to Databricks UI → SQL Warehouses
2. Copy warehouse ID from URL or details page
3. Update `TF_VAR_warehouse_id` in `.env`

### Issue: "Permission denied"
**Solution**: 
- Ensure your token has workspace admin or appropriate permissions
- Check Unity Catalog permissions: `GRANT CREATE CATALOG ON UNITY CATALOG TO your_user`

### Issue: Job fails with "Notebook not found"
**Solution**: Redeploy bundle: `databricks bundle deploy -t dev --force`

### Issue: No data in silver/gold tables
**Solution**: 
1. Check bronze tables have data: `SELECT COUNT(*) FROM observability_poc_dev.bronze.traces_bronze`
2. Manually run silver job: `make run-silver`
3. Check job logs in Databricks UI → Workflows

## Next Steps

### 1. Build Dashboards (Day 1)
- Go to **SQL Editor** → Create dashboard
- Add visualizations using sample queries above
- Share with team

### 2. Customize Transformations (Day 2)
- Edit notebooks in `src/notebooks/silver/`
- Add custom metrics or aggregations
- Redeploy: `make deploy-dev`

### 3. Setup Alerting (Day 2)
- Configure webhook URL (PagerDuty, Slack, etc.)
- Update `TF_VAR_alert_webhook_url` in `.env`
- Test: Trigger anomaly and verify alert

### 4. Deploy to Staging (Day 3)
```bash
# Deploy to staging for team testing
make deploy-staging
```

### 5. Build Streamlit App (Week 2)
- Create interactive trace viewer
- Add service dependency map
- Deploy as Databricks App

## Resources

- **Documentation**: See `README_DEPLOYMENT.md` for detailed guide
- **Project Plan**: See `PROJECT_PLAN.md` for full roadmap
- **Sample Data**: Located in `SampleData/` directory
- **Databricks Docs**: https://docs.databricks.com/dev-tools/bundles/

## Support Commands

```bash
# View all bundle resources
databricks bundle resources -t dev

# Validate configuration
databricks bundle validate -t dev --log-level debug

# Clean deployment artifacts
make clean

# Destroy all resources (WARNING: dev only)
make destroy
```

## Success Checklist

- [x] Environment configured (`.env` created)
- [x] Bundle validated successfully
- [x] Deployed to dev environment
- [x] Bronze data loaded (1000+ records)
- [x] Silver transformations completed
- [x] Tables queryable via SQL Editor
- [x] Jobs running on schedule
- [ ] Dashboards created in SQL Editor
- [ ] Alerting tested and working
- [ ] Team trained on platform

---

**Time to complete**: ~5 minutes  
**Next milestone**: Build operational dashboards
