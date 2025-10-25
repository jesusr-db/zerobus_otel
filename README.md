# Databricks Observability Platform

Production-ready OpenTelemetry (OTEL) observability platform built on Databricks with Unity Catalog, deployed via Databricks Asset Bundles for seamless CI/CD.

## Overview

Transform raw OpenTelemetry data (traces, metrics, logs) into actionable insights with automated ETL pipelines, real-time anomaly detection, and interactive dashboards.

### Key Features

✅ **Serverless Compute** - All jobs run on Databricks serverless compute (no cluster management)  
✅ **Unity Catalog Integration** - Bronze/Silver/Gold medallion architecture with governance  
✅ **Infrastructure as Code** - Complete deployment via Databricks Asset Bundles  
✅ **CI/CD Ready** - GitHub Actions workflow for automated deployment  
✅ **Real-time Monitoring** - Service health golden signals updated every minute  
✅ **Anomaly Detection** - Statistical anomaly detection with webhook alerting  
✅ **Cross-Signal Correlation** - Link traces ↔ metrics ↔ logs seamlessly  

## Architecture

```
Bronze (Raw OTEL)  →  Silver (Enriched)  →  Gold (Aggregated)  →  Dashboards
    Traces                 Assembled             Hourly Rollups        Lakeview
    Metrics                Golden Signals        Dependencies          Streamlit
    Logs                   Parsed JSON           Anomaly Baselines     SQL Editor
```

**Services Monitored** (from sample data):
- `frontend` (Node.js)
- `frontend-proxy` (Envoy)
- `cart` (.NET)
- `ad` (Java)
- `currency` (C++)
- `product-catalog` (Go)
- `payment` (Node.js)
- And more...

## Quick Start

### Prerequisites

- Databricks workspace with Unity Catalog enabled
- Databricks CLI installed: `pip install databricks-cli`
- SQL Warehouse created
- Personal access token

### 5-Minute Setup

```bash
# 1. Configure environment
cp .env.template .env
# Edit .env with your Databricks credentials
source .env

# 2. Validate configuration
make validate

# 3. Deploy to dev
make deploy-dev

# 4. Load sample data
make run-loader

# 5. Run transformations
make run-silver
```

**That's it!** Your observability platform is running.

See **[QUICKSTART.md](QUICKSTART.md)** for detailed setup instructions.

## Project Structure

```
zerobus-1/
├── databricks.yml              # Main bundle configuration
├── resources/                  # Infrastructure definitions
│   ├── schemas.yml            # Unity Catalog schemas
│   ├── jobs.yml               # 6 scheduled jobs (serverless)
│   └── pipelines.yml          # Delta Live Tables
├── src/
│   ├── notebooks/             # PySpark notebooks
│   │   ├── bronze/           # Data loading
│   │   ├── silver/           # Transformations (5 notebooks)
│   │   ├── gold/             # Aggregations (4 notebooks)
│   │   ├── alerting/         # Anomaly detection
│   │   └── quality/          # Data validation
│   ├── sql/                  # SQL scripts
│   └── python/               # Utility libraries
├── SampleData/               # OTEL sample data (1000+ records)
├── .github/workflows/        # CI/CD pipeline
├── PROJECT_PLAN.md           # 6-phase implementation plan
├── QUICKSTART.md             # 5-minute setup guide
└── README_DEPLOYMENT.md      # Detailed deployment docs
```

## Sample Queries

### Service Health Dashboard
```sql
SELECT 
    service_name,
    request_count,
    error_rate,
    latency_p95_ms,
    CASE 
        WHEN error_rate > 0.05 THEN '🔴 Critical'
        WHEN error_rate > 0.01 THEN '🟡 Warning'
        ELSE '🟢 Healthy'
    END as status
FROM observability_poc_dev.silver.service_health_silver
WHERE timestamp >= CURRENT_TIMESTAMP() - INTERVAL 1 HOUR
ORDER BY error_rate DESC;
```

### Trace Lookup
```sql
-- Find complete trace with all spans
SELECT * FROM observability_poc_dev.silver.traces_silver
WHERE trace_id = '8152f86a9264ac1ebcdaa867facd5719';
```

### Service Dependencies
```sql
-- Service call graph
SELECT 
    source_service,
    target_service,
    call_count,
    avg_duration_ms
FROM observability_poc_dev.gold.service_dependencies_gold
ORDER BY call_count DESC;
```

More examples in [QUICKSTART.md](QUICKSTART.md#sample-queries).

## Deployment Environments

| Environment | Purpose | Compute | Deploy Command |
|-------------|---------|---------|----------------|
| **Dev** | Development & testing | Single-node serverless | `make deploy-dev` |
| **Staging** | Pre-production validation | Small serverless | `make deploy-staging` |
| **Production** | Production workloads | Medium serverless (autoscale) | `make deploy-prod` |

All environments use:
- ✅ Serverless compute (no cluster management)
- ✅ Unity Catalog for governance
- ✅ Delta Lake for ACID transactions
- ✅ Automated job scheduling

## Jobs & Schedules

| Job | Schedule | Purpose | Compute |
|-----|----------|---------|---------|
| Bronze Data Loader | On-demand | Load OTEL CSV data | Serverless |
| Silver Transformations | Every 5 min | Parse JSON, assemble traces | Serverless |
| Gold Aggregations | Hourly | Create rollups, dependencies | Serverless |
| Anomaly Alerting | Every 1 min | Detect & alert anomalies | Serverless |
| Data Quality | Daily (2 AM) | Validate data completeness | Serverless |
| Table Maintenance | Weekly (Sun 3 AM) | OPTIMIZE/VACUUM tables | Serverless |

## CI/CD Pipeline

GitHub Actions workflow automatically deploys on:

- `push` to `develop` → Deploy to **dev**
- `push` to `main` → Deploy to **staging**
- Manual workflow → Deploy to **prod** (with approval)

Configure secrets in GitHub:
- `DATABRICKS_HOST_DEV`
- `DATABRICKS_TOKEN_DEV`
- `WAREHOUSE_ID_DEV`
- (Similar for staging/prod)

See [README_DEPLOYMENT.md](README_DEPLOYMENT.md#cicd-pipeline) for setup.

## Commands Reference

### Deployment
```bash
make deploy-dev      # Deploy to dev
make deploy-staging  # Deploy to staging
make deploy-prod     # Deploy to production (with confirmation)
```

### Operations
```bash
make run-loader      # Load sample OTEL data
make run-silver      # Run silver transformations
make run-gold        # Run gold aggregations
make run-quality     # Validate data quality
```

### Maintenance
```bash
make optimize        # Optimize Delta tables
make logs            # View recent job logs
make clean           # Clean deployment artifacts
```

See [Makefile](Makefile) for all commands.

## Data Pipeline

### Bronze Layer (Raw OTEL Data)
- **traces_bronze**: Raw span data from OTEL collector
- **metrics_bronze**: Infrastructure & application metrics
- **logs_bronze**: Application logs with trace context

### Silver Layer (Enriched)
- **traces_silver**: Assembled complete traces with service dependencies
- **service_health_silver**: Golden signals (traffic, errors, latency, saturation)
- **logs_silver**: Logs enriched with trace context
- **metrics_silver**: Parsed metric values with attributes

### Gold Layer (Aggregated)
- **service_health_hourly_gold**: Time-series rollups for historical analysis
- **service_dependencies_gold**: Service call graph and topology
- **metrics_rollups_gold**: Aggregated infrastructure metrics
- **anomaly_baselines_gold**: Statistical baselines for anomaly detection

## Success Metrics

### POC Validation
- ✅ Ingest 3 OTEL signals (traces, metrics, logs)
- ✅ Assemble traces with < 5 min latency
- ✅ Compute golden signals in real-time
- ✅ Detect anomalies with < 2 min alert delivery
- ✅ Query traces by ID in < 3 seconds
- ✅ Correlate logs to traces via trace_id

### Production Readiness
- [ ] ML-based anomaly detection (MLflow)
- [ ] Advanced correlation (automatic RCA)
- [ ] RBAC and SSO integration
- [ ] Cost optimization (sampling, tiered storage)
- [ ] Performance tuning (caching, materialized views)

## Documentation

- **[QUICKSTART.md](QUICKSTART.md)** - 5-minute setup guide
- **[PROJECT_PLAN.md](PROJECT_PLAN.md)** - 6-phase implementation roadmap
- **[README_DEPLOYMENT.md](README_DEPLOYMENT.md)** - Detailed deployment guide
- **[Makefile](Makefile)** - All available commands

## Technology Stack

| Component | Technology |
|-----------|-----------|
| Data Platform | Databricks (Unity Catalog) |
| Compute | Serverless SQL Warehouse + Serverless Compute |
| Storage | Delta Lake (ACID, time travel) |
| Orchestration | Databricks Workflows |
| IaC | Databricks Asset Bundles |
| CI/CD | GitHub Actions |
| Dashboards | Lakeview (Databricks SQL Analytics) |
| Alerting | HTTP Webhook |
| Language | PySpark (Python 3.11) |

## Sample Data

Included OTEL data from OpenTelemetry Demo application:

- **Traces**: 1,000 spans across 10+ services
- **Metrics**: 1,000 data points (Redis, Nginx, PostgreSQL, application)
- **Logs**: 1,700 log entries with trace correlation

Services represented:
`frontend`, `frontend-proxy`, `cart`, `ad`, `currency`, `product-catalog`, `payment`, `load-generator`, `accounting`, `quote`, `kafka`

## Roadmap

### ✅ Phase 1: Foundation (Week 1)
- Unity Catalog setup
- Bronze schema creation
- Sample data loading

### ✅ Phase 2: Silver Transformations (Week 2-3)
- JSON parsing
- Trace assembly
- Service health golden signals
- Log enrichment

### ✅ Phase 3: Gold Aggregations (Week 3-4)
- Time-series rollups
- Service dependencies
- Anomaly baselines

### 🚧 Phase 4: Application Layer (Week 4-5)
- Streamlit interactive app
- Lakeview dashboards
- Alerting workflow

### 📋 Phase 5: Validation & Handoff (Week 5-6)
- End-to-end testing
- Performance validation
- Documentation
- Training

### 🔮 Future Enhancements
- ML-based anomaly detection (MLflow)
- Automatic root cause analysis
- Advanced correlation engine
- Cost attribution by service
- Capacity planning predictions

## Contributing

1. Create feature branch: `git checkout -b feature/my-feature`
2. Make changes and test locally: `make deploy-dev`
3. Run validation: `make run-quality`
4. Commit and push: `git push origin feature/my-feature`
5. Create pull request (auto-deploys to dev via CI/CD)

## Support

- **Issues**: Open GitHub issue
- **Documentation**: See [README_DEPLOYMENT.md](README_DEPLOYMENT.md)
- **Databricks Docs**: https://docs.databricks.com/dev-tools/bundles/

## License

[Your License Here]

---

**Built with ❤️ using Databricks Asset Bundles**

**Status**: ✅ POC Ready | 🚧 Production Hardening In Progress

**Last Updated**: 2025-10-25
