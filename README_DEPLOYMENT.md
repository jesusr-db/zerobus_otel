# Databricks Asset Bundle - Deployment Guide

## Overview

This project uses **Databricks Asset Bundles (DAB)** for infrastructure-as-code deployment and CI/CD management of the observability platform.

## Prerequisites

1. **Databricks CLI** (v0.200.0+)
   ```bash
   pip install databricks-cli
   databricks --version
   ```

2. **Databricks Workspace** with:
   - Unity Catalog enabled
   - Serverless compute available
   - SQL Warehouse created

3. **Permissions**:
   - Workspace Admin or appropriate permissions to create jobs, schemas, tables
   - Unity Catalog permissions: CREATE CATALOG, CREATE SCHEMA

## Quick Start

### 1. Configure Credentials

Create `.env` file from template:
```bash
cp .env.template .env
```

Edit `.env` and fill in your values:
```bash
DATABRICKS_HOST=https://your-workspace.cloud.databricks.com
DATABRICKS_TOKEN=dapi1234567890abcdef
TF_VAR_warehouse_id=abc123def456
TF_VAR_alert_webhook_url=https://your-webhook.com/alerts
TF_VAR_alert_email=your-email@company.com
```

Load environment variables:
```bash
source .env
```

### 2. Validate Bundle

```bash
databricks bundle validate -t dev
```

### 3. Deploy to Development

```bash
databricks bundle deploy -t dev
```

This will create:
- Unity Catalog schemas (bronze, silver, gold)
- 6 scheduled jobs (serverless compute)
- Delta Live Tables pipeline
- All notebooks and SQL scripts

### 4. Run Initial Data Load

```bash
databricks bundle run bronze_data_loader -t dev
```

### 5. View Deployment

```bash
# List all deployed resources
databricks bundle resources -t dev

# View job runs
databricks jobs list
```

## Bundle Structure

```
.
├── databricks.yml              # Main bundle configuration
├── resources/
│   ├── schemas.yml             # Unity Catalog schemas
│   ├── jobs.yml                # Databricks jobs (serverless)
│   └── pipelines.yml           # Delta Live Tables
├── src/
│   ├── notebooks/
│   │   ├── bronze/             # Bronze layer notebooks
│   │   ├── silver/             # Silver transformation notebooks
│   │   ├── gold/               # Gold aggregation notebooks
│   │   ├── alerting/           # Anomaly detection & alerting
│   │   ├── quality/            # Data quality validation
│   │   └── dlt/                # Delta Live Tables
│   ├── sql/                    # SQL scripts
│   └── python/                 # Python utilities
└── .github/
    └── workflows/
        └── deploy.yml          # CI/CD pipeline
```

## Environments

### Development (`dev`)
- **Purpose**: Local development and testing
- **Compute**: Single-node serverless clusters
- **Catalog**: `observability_poc_dev`
- **Schedule**: Jobs paused by default
- **Deploy**: `databricks bundle deploy -t dev`

### Staging (`staging`)
- **Purpose**: Pre-production validation
- **Compute**: Small serverless clusters
- **Catalog**: `observability_poc_staging`
- **Schedule**: Jobs run on schedule
- **Deploy**: `databricks bundle deploy -t staging`

### Production (`prod`)
- **Purpose**: Production workloads
- **Compute**: Medium serverless clusters with autoscaling
- **Catalog**: `observability_poc`
- **Schedule**: Jobs run on schedule
- **Run As**: Service principal (configured in bundle)
- **Deploy**: `databricks bundle deploy -t prod`

## Jobs Overview

| Job | Schedule | Purpose |
|-----|----------|---------|
| `bronze_data_loader` | On-demand | Load sample OTEL data from CSV |
| `silver_transformations` | Every 5 min | Parse JSON, assemble traces, compute golden signals |
| `gold_aggregations` | Hourly | Create rollups and service dependencies |
| `anomaly_alerting` | Every 1 min | Detect anomalies and send alerts |
| `data_quality_validation` | Daily (2 AM) | Validate data completeness and quality |
| `table_maintenance` | Weekly (Sun 3 AM) | OPTIMIZE and VACUUM Delta tables |

## Common Commands

### Deploy

```bash
# Deploy to dev
databricks bundle deploy -t dev

# Deploy to staging
databricks bundle deploy -t staging

# Deploy to prod (requires manual approval in CI/CD)
databricks bundle deploy -t prod
```

### Run Jobs

```bash
# Run a specific job
databricks bundle run <job_name> -t dev

# Examples:
databricks bundle run bronze_data_loader -t dev
databricks bundle run silver_transformations -t dev
databricks bundle run data_quality_validation -t dev
```

### View Resources

```bash
# List all resources in bundle
databricks bundle resources -t dev

# View job details
databricks jobs get --job-id <job-id>

# View job runs
databricks runs list --job-id <job-id>
```

### Destroy

```bash
# WARNING: This will delete all resources
databricks bundle destroy -t dev --auto-approve
```

## CI/CD Pipeline

### GitHub Actions Workflow

The `.github/workflows/deploy.yml` file provides automated deployment:

**Triggers**:
- `push` to `develop` branch → Deploy to **dev**
- `push` to `main` branch → Deploy to **staging**
- Manual workflow dispatch → Deploy to **prod** (requires approval)

**Workflow Steps**:
1. Validate bundle configuration
2. Deploy to target environment
3. Run data quality validation (staging/prod only)
4. Send deployment notification

### Setup GitHub Secrets

Required secrets in your GitHub repository:

**Development**:
- `DATABRICKS_HOST_DEV`
- `DATABRICKS_TOKEN_DEV`
- `WAREHOUSE_ID_DEV`

**Staging**:
- `DATABRICKS_HOST_STAGING`
- `DATABRICKS_TOKEN_STAGING`
- `WAREHOUSE_ID_STAGING`

**Production**:
- `DATABRICKS_HOST_PROD`
- `DATABRICKS_TOKEN_PROD`
- `WAREHOUSE_ID_PROD`
- `SERVICE_PRINCIPAL_NAME`

**Common**:
- `ALERT_WEBHOOK_URL`
- `ALERT_EMAIL`

### Deployment Flow

```
develop branch → Dev Environment (auto-deploy)
       ↓
    main branch → Staging Environment (auto-deploy)
       ↓
Manual approval → Production Environment (workflow dispatch)
```

## Monitoring & Troubleshooting

### View Job Logs

```bash
# Get latest run for a job
databricks runs list --job-id <job-id> --limit 1

# Get run output
databricks runs get-output --run-id <run-id>
```

### Common Issues

**1. Authentication Error**
```
Error: Authentication failed
```
**Solution**: Check `.env` file has correct `DATABRICKS_HOST` and `DATABRICKS_TOKEN`

**2. Warehouse Not Found**
```
Error: SQL warehouse not found
```
**Solution**: Verify `TF_VAR_warehouse_id` points to an existing SQL Warehouse

**3. Permission Denied**
```
Error: User does not have permission to create catalog
```
**Solution**: Ensure your user/service principal has Unity Catalog CREATE permissions

**4. Job Failure**
```
Error: Notebook not found
```
**Solution**: Ensure all notebooks exist in `src/notebooks/` before deploying

### Debug Mode

```bash
# Validate with verbose output
databricks bundle validate -t dev --log-level debug

# Deploy with verbose logging
databricks bundle deploy -t dev --log-level debug
```

## Best Practices

### 1. Environment Isolation
- Always test in `dev` before promoting to `staging`
- Use separate catalogs per environment
- Never share credentials between environments

### 2. Version Control
- Commit `databricks.yml` and resource files to git
- **Never commit** `.env` or `.databrickscfg` files
- Tag releases for production deployments

### 3. Serverless Compute
- All jobs use serverless compute (no cluster management)
- Faster startup times (~5-10 seconds)
- Cost-effective for POC (pay-per-use)
- Automatically scales based on workload

### 4. Monitoring
- Enable email notifications for job failures
- Configure webhook alerts for anomalies
- Review data quality validation reports daily

### 5. Cost Management
- Use `pause_status: PAUSED` for jobs in dev environment
- Enable table maintenance (OPTIMIZE/VACUUM) weekly
- Monitor Databricks usage dashboard

## Advanced Configuration

### Override Variables

```bash
# Override catalog name
databricks bundle deploy -t dev \
  --var "catalog_name=my_custom_catalog"

# Override warehouse
databricks bundle deploy -t dev \
  --var "warehouse_id=abc123xyz"
```

### Custom Job Parameters

Edit `resources/jobs.yml` and add/modify base_parameters:

```yaml
tasks:
  - task_key: my_task
    notebook_task:
      notebook_path: ./src/notebooks/my_notebook.py
      base_parameters:
        catalog_name: ${var.catalog_name}
        custom_param: "my_value"
```

### Add New Job

1. Create notebook in `src/notebooks/`
2. Add job definition to `resources/jobs.yml`
3. Deploy: `databricks bundle deploy -t dev`
4. Run: `databricks bundle run my_new_job -t dev`

## Migration from Manual Deployment

If you have existing jobs/notebooks:

1. **Export existing resources**:
   ```bash
   databricks jobs get --job-id <job-id> > existing_job.json
   ```

2. **Convert to bundle format**:
   - Copy notebook content to `src/notebooks/`
   - Define job in `resources/jobs.yml` matching existing config

3. **Deploy with `mode: production`**:
   - This prevents resource deletion on first deploy

4. **Verify and switch**:
   - Test new bundle deployment in separate workspace first
   - Once validated, deploy to production

## Next Steps

1. **Deploy to Dev**: `databricks bundle deploy -t dev`
2. **Load Sample Data**: `databricks bundle run bronze_data_loader -t dev`
3. **Verify Jobs Running**: Check Databricks Workflows UI
4. **Monitor Logs**: Review job run outputs
5. **Build Notebooks**: Create transformation logic in `src/notebooks/`
6. **Iterate**: Make changes, redeploy with `databricks bundle deploy`

## Support

- **Databricks Asset Bundles Docs**: https://docs.databricks.com/dev-tools/bundles/
- **Databricks CLI**: https://docs.databricks.com/dev-tools/cli/
- **Issues**: Open GitHub issue in this repository
