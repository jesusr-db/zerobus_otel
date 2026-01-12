# Project Overview

**Project Name**: Databricks Observability Platform (zerobus-1)

**Purpose**: Production-ready OpenTelemetry (OTEL) observability platform built on Databricks with Unity Catalog, deployed via Databricks Asset Bundles for seamless CI/CD.

## Key Objectives
- Transform raw OpenTelemetry data (traces, metrics, logs) into actionable insights
- Automated ETL pipelines with medallion architecture (Bronze/Silver/Gold)
- Real-time anomaly detection and alerting
- Interactive dashboards for operational monitoring

## Architecture Pattern
Bronze (Raw OTEL) → Silver (Enriched) → Gold (Aggregated) → Dashboards

### Data Layers
- **Bronze**: Streaming OTEL data (spans, metrics, logs) from collector gateway
  - Location: `main.jmr_demo.otel_spans`, `otel_metrics`, `otel_logs`
  - Complex types: MAP, STRUCT, ARRAY structures
  
- **Silver**: Flattened and enriched data
  - `traces_silver`: Flattened spans with extracted attributes
  - `traces_assembled_silver`: Complete traces with hierarchy
  - `service_health_silver`: Golden signals (SLIs)
  - `logs_silver`: Enriched logs with trace correlation
  - `metrics_silver`: Flattened metric values
  
- **Gold**: Aggregated analytics
  - `service_health_hourly_gold`: Time-series health metrics
  - `service_dependencies_gold`: Service call graph
  - `metrics_rollups_gold`: Infrastructure metric rollups
  - `anomaly_baselines_gold`: Statistical baselines

## Current Status
- ✅ Phase 1 Complete: Foundation setup, Unity Catalog schemas
- ✅ Code Created: All silver/gold/quality notebooks completed
- ⏳ Phase 2-5 Pending: Execution and validation of pipelines

## Key Features
- Serverless compute (no cluster management)
- Unity Catalog integration with governance
- Infrastructure as Code via Databricks Asset Bundles
- CI/CD ready with GitHub Actions
- Cross-signal correlation (traces ↔ metrics ↔ logs)
