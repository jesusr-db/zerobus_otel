# Codebase Structure

## Root Directory
```
zerobus-1/
├── databricks.yml              # Main Databricks Asset Bundle configuration
├── Makefile                    # Command automation for common operations
├── README.md                   # Project overview and quick start
├── PROJECT_PLAN.md            # 6-phase implementation plan with status
├── QUICKSTART.md              # 5-minute setup guide
├── README_DEPLOYMENT.md       # Detailed deployment documentation
├── .env.template              # Environment variables template
├── .gitignore                 # Git ignore patterns
└── .databrickscfg.template    # Databricks CLI config template
```

## Resources (Infrastructure as Code)
```
resources/
├── schemas.yml                # Unity Catalog schema definitions
├── jobs.yml                   # Job definitions (pipeline_setup, gold_aggregations, etc.)
└── pipelines.yml              # Delta Live Tables pipeline configurations
```

## Source Code
```
src/
├── notebooks/                 # PySpark notebooks organized by layer
│   ├── silver/               # 5 notebooks for Silver transformations
│   │   ├── 01_flatten_traces.py
│   │   ├── 02_assemble_traces.py
│   │   ├── 03_compute_service_health.py
│   │   ├── 04_enrich_logs.py
│   │   └── 05_flatten_metrics.py
│   │
│   ├── gold/                 # 4 notebooks for Gold aggregations
│   │   ├── 01_service_health_rollups.py
│   │   ├── 02_service_dependencies.py
│   │   ├── 03_metric_rollups.py
│   │   └── 04_anomaly_baselines.py
│   │
│   ├── alerting/             # Anomaly detection and alerting
│   │   └── detect_anomalies.py
│   │
│   ├── quality/              # Data quality validation notebooks
│   │   ├── validate_trace_completeness.py
│   │   ├── validate_cross_signal_correlation.py
│   │   └── validate_service_health_metrics.py
│   │
│   └── dlt/                  # Delta Live Tables notebooks
│       ├── silver_transformations.py
│       ├── service_health_streaming.py
│       └── gold_aggregations.py
│
└── sql/                       # SQL scripts
    └── maintenance/          # Table maintenance scripts
        ├── optimize_bronze.sql
        ├── optimize_silver.sql
        └── vacuum_tables.sql
```

## Sample Data
```
SampleData/                    # OTEL sample data (1000+ records)
├── traces.csv                # Sample trace spans
├── metrics.csv               # Sample metrics
└── logs.csv                  # Sample logs
```

## Documentation
```
docs/                         # Additional documentation
claudedocs/                   # Claude-generated analyses and reports
```

## CI/CD
```
.github/
└── workflows/                # GitHub Actions workflows
    └── deploy.yml            # Automated deployment workflow
```

## Configuration Management
```
.databricks/                  # Databricks bundle cache (gitignored)
.bundle/                      # Build artifacts (gitignored)
.serena/                      # Serena MCP project data
```

## Key File Patterns

### Notebooks
- **Silver**: Read from Bronze streaming tables → Transform → Write to Silver
- **Gold**: Read from Silver → Aggregate → Write to Gold
- **DLT**: Define tables/views with @dlt.table decorators
- **Quality**: Read from multiple layers → Validate → Report

### Configuration Files
- **databricks.yml**: Main bundle config with variables and targets
- **resources/*.yml**: Resource definitions (jobs, pipelines, schemas)
- **Makefile**: Command shortcuts for development workflow

### Data Flow
Bronze (`main.jmr_demo.zerobus`) 
  ↓
Silver (`jmr_demo.zerobus_sdp` in dev)
  ↓
Gold (`jmr_demo.zerobus_sdp` in dev)
  ↓
Dashboards & Applications
