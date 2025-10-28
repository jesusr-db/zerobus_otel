# ZeroBus-1 Architecture

## Overview

ZeroBus-1 is an OpenTelemetry observability pipeline built on Databricks lakehouse platform. It processes traces, logs, and metrics through a medallion architecture (bronze → silver → gold) with automated data quality validation and anomaly detection.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         DATA INGESTION LAYER                             │
│                                                                          │
│  OpenTelemetry SDKs → Collectors → Kafka/Kinesis → Delta Live Tables   │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         BRONZE LAYER                                     │
│                      (jmr_demo.zerobus)                                  │
│                                                                          │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                │
│  │ otel_spans  │    │ otel_logs   │    │otel_metrics │                │
│  │ (raw JSON)  │    │ (raw JSON)  │    │ (raw JSON)  │                │
│  └─────────────┘    └─────────────┘    └─────────────┘                │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         SILVER LAYER                                     │
│                      (jmr_demo.zerobus)                                  │
│                   Runs Every 5 Minutes                                   │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────┐      │
│  │  1. flatten_traces (01_flatten_traces.py)                    │      │
│  │     - Unnests nested OTEL span structures                     │      │
│  │     - Extracts attributes, resource tags, events              │      │
│  │     → traces_silver                                           │      │
│  └──────────────────────────────────────────────────────────────┘      │
│                           │                                              │
│         ┌─────────────────┼─────────────────┬─────────────┐            │
│         ▼                 ▼                 ▼             ▼            │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────┐ ┌─────────────┐  │
│  │2. assemble  │  │3. compute    │  │4. enrich    │ │5. flatten   │  │
│  │   _traces   │  │   _service   │  │   _logs     │ │   _metrics  │  │
│  │             │  │   _health    │  │             │ │             │  │
│  │Groups by    │  │Golden Signals│  │Join w/trace │ │Unnest metric│  │
│  │trace_id     │  │per service:  │  │context      │ │structures   │  │
│  │             │  │- Error rate  │  │             │ │             │  │
│  │→ traces_    │  │- Latency p95 │  │→ logs_      │ │→ metrics_   │  │
│  │  assembled_ │  │- Request cnt │  │  silver     │ │  silver     │  │
│  │  silver     │  │              │  │             │ │             │  │
│  │             │  │→ service_    │  │             │ │             │  │
│  │             │  │  health_     │  │             │ │             │  │
│  │             │  │  silver      │  │             │ │             │  │
│  └─────────────┘  └──────────────┘  └─────────────┘ └─────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         GOLD LAYER                                       │
│                      (jmr_demo.zerobus)                                  │
│                       Runs Hourly                                        │
│                                                                          │
│  ┌────────────────┐  ┌──────────────────┐  ┌─────────────────┐        │
│  │1. service_     │  │2. service_       │  │3. metric_       │        │
│  │   health_      │  │   dependencies   │  │   rollups       │        │
│  │   rollups      │  │                  │  │                 │        │
│  │                │  │Trace parent/child│  │Hourly metric    │        │
│  │Hourly service  │  │relationships     │  │aggregations     │        │
│  │health metrics  │  │                  │  │by name & labels │        │
│  │                │  │→ service_        │  │                 │        │
│  │→ service_      │  │  dependencies    │  │→ metric_        │        │
│  │  health_hourly │  │                  │  │  rollups_hourly │        │
│  └────────────────┘  └──────────────────┘  └─────────────────┘        │
│                                  │                                       │
│                                  ▼                                       │
│                      ┌──────────────────────┐                           │
│                      │4. anomaly_baselines  │                           │
│                      │                      │                           │
│                      │Compute 7-day baseline│                           │
│                      │statistics per service│                           │
│                      │- Avg error rate      │                           │
│                      │- Avg latency         │                           │
│                      │- Stddev calculations │                           │
│                      │                      │                           │
│                      │→ anomaly_baselines   │                           │
│                      └──────────────────────┘                           │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      ANOMALY ALERTING                                    │
│                      (jmr_demo.zerobus)                                  │
│                     Runs Every Minute                                    │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────┐      │
│  │  detect_anomalies (detect_anomalies.py)                      │      │
│  │                                                               │      │
│  │  Compares recent service health vs baselines:                │      │
│  │  - Error rate > baseline_error_rate + 2*stddev               │      │
│  │  - Latency > baseline_latency + 2*stddev                     │      │
│  │                                                               │      │
│  │  → detected_anomalies table                                  │      │
│  │  → Alerts via webhook/email (future)                         │      │
│  └──────────────────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────────────────┘
                                    
┌─────────────────────────────────────────────────────────────────────────┐
│                   DATA QUALITY VALIDATION                                │
│                      (jmr_demo.zerobus)                                  │
│                     Runs Daily at 2 AM UTC                               │
│                                                                          │
│  ┌─────────────────────┐  ┌─────────────────────┐  ┌───────────────┐  │
│  │1. validate_trace_   │  │2. validate_cross_   │  │3. validate_   │  │
│  │   completeness      │  │   signal_correlation│  │   service_    │  │
│  │                     │  │                     │  │   health_     │  │
│  │Check for orphaned   │  │Verify traces have   │  │   metrics     │  │
│  │spans, incomplete    │  │corresponding logs   │  │               │  │
│  │traces               │  │                     │  │Check for nulls│  │
│  │                     │  │Target: 80%+         │  │invalid ranges │  │
│  │Target: 95%+         │  │correlation          │  │               │  │
│  │completeness         │  │                     │  │Target: 99%+   │  │
│  │                     │  │                     │  │quality        │  │
│  │→ trace_             │  │→ cross_signal_      │  │               │  │
│  │  completeness_      │  │  correlation_       │  │→ service_     │  │
│  │  results            │  │  results            │  │  health_      │  │
│  │                     │  │                     │  │  quality_     │  │
│  │                     │  │                     │  │  results      │  │
│  └─────────────────────┘  └─────────────────────┘  └───────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

## Data Flow

### 1. Bronze Layer (Raw Ingestion)
- **Input**: OpenTelemetry data from collectors
- **Tables**: `otel_spans`, `otel_logs`, `otel_metrics`
- **Format**: Raw JSON/STRUCT with nested attributes
- **Update Frequency**: Real-time streaming via DLT

### 2. Silver Layer (Cleaned & Enriched)
- **Trigger**: Every 5 minutes (availableNow mode)
- **Processing**:
  - Flatten nested OTEL structures
  - Extract resource attributes and span events
  - Compute service health metrics (golden signals)
  - Enrich logs with trace context
  - Standardize metric formats
- **Tables**:
  - `traces_silver`: Flattened spans with full attribute extraction
  - `traces_assembled_silver`: Trace-level aggregations
  - `service_health_silver`: Per-service golden signals (error rate, latency, request count)
  - `logs_silver`: Logs enriched with trace/span context
  - `metrics_silver`: Flattened metrics (gauge, sum, histogram, summary)

### 3. Gold Layer (Business Aggregations)
- **Trigger**: Hourly
- **Processing**:
  - Time-based rollups for dashboards
  - Service dependency mapping
  - Baseline calculation for anomaly detection
- **Tables**:
  - `service_health_hourly`: Hourly service health rollups
  - `service_dependencies`: Parent-child service relationships
  - `metric_rollups_hourly`: Hourly metric aggregations
  - `anomaly_baselines`: 7-day baseline statistics per service

### 4. Anomaly Alerting
- **Trigger**: Every minute
- **Logic**: Detects services with error rates or latencies exceeding 2 standard deviations from baseline
- **Output**: `detected_anomalies` table

### 5. Data Quality Validation
- **Trigger**: Daily at 2 AM UTC
- **Checks**:
  - Trace completeness (orphaned spans)
  - Cross-signal correlation (traces ↔ logs)
  - Service health metric quality (nulls, invalid ranges)
- **Output**: Validation result tables with PASS/FAIL status

## Technology Stack

- **Platform**: Databricks on AWS
- **Compute**: Serverless SQL warehouses
- **Storage**: Delta Lake (Unity Catalog)
- **Orchestration**: Databricks Workflows
- **Schema**: `jmr_demo.zerobus` (all layers)
- **Languages**: Python, SQL
- **Libraries**: PySpark, Delta Lake

## Job Schedule

| Job | Frequency | Duration | Dependencies |
|-----|-----------|----------|--------------|
| Silver Transformations | Every 5 min | ~3 min | Bronze tables |
| Gold Aggregations | Hourly | ~1.5 min | Silver tables |
| Anomaly Alerting | Every minute | ~30 sec | Gold baselines |
| Data Quality Validation | Daily 2 AM | ~1 min | Silver tables |

## Scalability

- **Streaming**: Uses Delta Lake checkpointing for exactly-once processing
- **Incremental**: All silver jobs process only new data since last checkpoint
- **Parallel**: Gold aggregations run independent tasks concurrently
- **Idempotent**: All jobs can be safely re-run without data duplication

## Monitoring

- Job run history in Databricks UI
- Data quality metrics in validation result tables
- Anomaly alerts in `detected_anomalies` table
- (Future) Real-time alerts via webhook/email integration
