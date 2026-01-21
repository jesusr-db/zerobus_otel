# Databricks Observability Platform - POC Project Plan

## Executive Summary

**Objective**: Build a proof-of-concept observability platform on Databricks that ingests OpenTelemetry (OTEL) data (traces, metrics, logs) from Bronze tables, transforms it through Silver enrichment layers, aggregates insights in Gold tables, and serves interactive dashboards for operational monitoring.

**Scope**: POC implementation with sample OTEL data from OpenTelemetry Demo application  
**Timeline**: 4-6 weeks  
**Key Deliverables**: End-to-end data pipeline, interactive Streamlit application, operational dashboards

---

## Current Status (Updated: 2026-01-20)

**Overall Progress**: Phase 1-2 Complete, Phase 3 In Progress, Phases 4-5 Pending

### Completed
- ✅ **Phase 1**: Foundation setup complete
  - Bronze tables validated: `jmr_demo.zerobus.otel_spans/metrics/logs`
  - Databricks Asset Bundle deployed with 5 jobs, 16+ tasks
  - Unity Catalog schemas configured
  - SQL Warehouse provisioned (ID: `03560442e95cb440`)
  - Lakebase sync pipeline operational for external data access

- ✅ **Phase 2**: Silver layer transformations complete
  - All 5 silver notebooks deployed and executed
  - Silver tables populated: `traces_silver`, `traces_assembled_silver`, `service_health_silver`, `logs_silver`, `metrics_silver`
  - Cross-signal correlation validated (traces ↔ logs linkage working)
  - Streaming checkpoints and watermarks operational

- ✅ **Code Created**:
  - All 5 silver notebooks (Phase 2) - **DEPLOYED & RUNNING**
  - All 4 gold notebooks (Phase 3) - Ready for execution
  - Anomaly alerting notebook (Phase 4) - Ready for deployment
  - 3 data quality validation notebooks (Phase 5) - Ready for execution
  - 1 DLT streaming pipeline - Operational
  - SQL maintenance scripts - Deployed

### In Progress
- 🔄 **Phase 3**: Gold aggregations
  - Service health rollups notebook deployed
  - Metric rollups under review (data quality issues identified)
  - Service dependencies and anomaly baselines pending execution

### Pending Execution
- ⏳ **Phase 4**: Application layer - Streamlit app and dashboards not started
- ⏳ **Phase 5**: Testing and validation - Notebooks created, not executed

### Next Steps
1. ✅ COMPLETED: Bronze table sync with Lakebase pipeline
2. ✅ COMPLETED: Silver transformations deployed and running
3. 🔄 IN PROGRESS: Fix metrics silver table data quality issues
4. Deploy remaining gold aggregation notebooks
5. Validate gold table outputs and service dependency graph
6. Begin Streamlit application development
7. Execute data quality validation notebooks
8. Combine gold and silver pipeline -- PRIORITY
9. use only one pipeline for lakebase sync -- PRIORITY
10. Actionable AI/BI dashboard
11. Genie with QA
12. MAS for troubleshooting guides and GENIE combined interface for Chatbot

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│  OTEL Gateway → Bronze Layer (Streaming)                    │
│  - otel_spans: Structured trace spans (MAP/STRUCT types)    │
│  - otel_metrics: Structured metrics (gauge/sum/histogram)   │
│  - otel_logs: Structured logs with trace context            │
│  Note: Already streaming from OTEL collector                │
└─────────────────────────────────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  Silver Layer (Flattened & Enriched)                        │
│  - traces_silver: Flattened spans with extracted attrs      │
│  - traces_assembled_silver: Complete traces with hierarchy  │
│  - service_health_silver: Golden signals (SLIs)             │
│  - logs_silver: Enriched logs with trace correlation        │
│  - metrics_silver: Flattened metric values                  │
└─────────────────────────────────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  Gold Layer (Aggregated Analytics)                          │
│  - service_health_hourly_gold: Time-series health metrics   │
│  - service_dependencies_gold: Service call graph            │
│  - metrics_rollups_gold: Infrastructure metric rollups      │
│  - anomaly_baselines_gold: Statistical baselines            │
└─────────────────────────────────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  Application Layer                                          │
│  - Lakeview Dashboards: Operational monitoring              │
│  - Streamlit App: Interactive trace viewer & log explorer   │
│  - SQL Warehouse: Ad-hoc query interface                    │
└─────────────────────────────────────────────────────────────┘
```

---

## Phase 1: Foundation Setup (Week 1)

### Goals
- Validate existing Bronze streaming tables
- Establish Unity Catalog structure (silver/gold schemas)
- Create Databricks Asset Bundle configuration
- Deploy foundation infrastructure

### Tasks

#### 1.1 Validate Bronze Streaming Tables
- **Verify Existing Bronze Tables**
  - Confirm `{catalog}.bronze.otel_spans` schema matches DDL
  - Confirm `{catalog}.bronze.otel_metrics` schema matches DDL
  - Confirm `{catalog}.bronze.otel_logs` schema matches DDL
  - Validate streaming write patterns and latency
  
- **Bronze Schema Analysis**
  - Document complex types: MAP<STRING, STRING>, STRUCT, ARRAY<STRUCT>
  - Identify key fields for Silver flattening:
    - `attributes` MAP: http.method, http.status_code, rpc.service
    - `resource.attributes` MAP: service.name, service.version
    - `events` ARRAY<STRUCT>: time_unix_nano, name, attributes
    - `status` STRUCT: message, code
  - Check data quality: null counts, invalid timestamps, orphaned spans

#### 1.2 Unity Catalog Configuration
- **Deploy Silver/Gold Schemas**
  - Update `resources/schemas.yml` with bronze table references
  - Deploy via Databricks Asset Bundle: `databricks bundle deploy -t dev`
  - Configure table properties:
    - Enable liquid clustering on `trace_id`, `service_name`, `timestamp`
    - Set retention policies (7d raw, 30d silver, 90d gold)
  
- **Permissions Setup**
  - Grant READ on bronze tables to service principal
  - Grant CREATE, WRITE on silver/gold schemas
  - Configure Unity Catalog governance policies

#### 1.3 Databricks Asset Bundle Setup
- **Remove Bronze Data Loader**
  - Delete `bronze_data_loader` job from `resources/jobs.yml`
  - Remove CSV loading notebook from `src/notebooks/bronze/`
  - Update job count: 6 jobs → 5 jobs
  
- **Update Job Configurations**
  - Ensure all jobs use `serverless_compute: enabled: true`
  - Configure `silver_transformations` to read from streaming bronze
  - Set appropriate schedules:
    - `silver_transformations`: Every 5 minutes
    - `gold_aggregations`: Hourly
    - `anomaly_alerting`: Every 1 minute
    - `data_quality_validation`: Daily at 2 AM
    - `table_maintenance`: Weekly Sunday 3 AM

#### 1.4 Environment Configuration
- **Databricks Workspace Setup**
  - SQL Warehouse already provisioned (confirm warehouse_id)
  - Configure `.env` with credentials:
    - `DATABRICKS_HOST`
    - `DATABRICKS_TOKEN`
    - `TF_VAR_warehouse_id`
    - `TF_VAR_alert_webhook_url`
  
- **Deploy Foundation**
  - Validate bundle: `make validate`
  - Deploy to dev: `make deploy-dev`
  - Verify resource creation in Databricks UI

### Deliverables
- ✅ Bronze streaming tables validated and documented
  - **Location**: `main.jmr_demo.otel_spans`, `otel_metrics`, `otel_logs`
  - **Schema**: Confirmed STRUCT types match DDL (resource.attributes, instrumentation_scope)
- ✅ Unity Catalog silver/gold schemas created
  - **Target catalog**: `observability_poc_dev` (dev), `observability_poc` (prod)
  - **Schemas**: silver, gold, quality
- ✅ Databricks Asset Bundle deployed (5 jobs, serverless)
  - silver_transformations (5 tasks)
  - gold_aggregations (4 tasks)
  - anomaly_alerting (1 task)
  - data_quality_validation (3 tasks)
  - table_maintenance (3 tasks)
- ✅ Foundation infrastructure operational
  - Bundle validates successfully
  - SQL Warehouse ID: `03560442e95cb440`
  - Alert webhook configured
- ✅ Additional notebooks created beyond plan
  - Gold: 4 notebooks (service_health_rollups, service_dependencies, metric_rollups, anomaly_baselines)
  - Alerting: 1 notebook (detect_anomalies)
  - Quality: 3 notebooks (trace_completeness, cross_signal_correlation, service_health_metrics)
  - DLT: 1 pipeline (service_health_streaming)

---

## Phase 2: Silver Layer Transformations (Week 2-3)

### Goals
- Flatten nested Bronze structures (MAP, STRUCT, ARRAY)
- Assemble complete traces from spans
- Compute service health golden signals
- Enable cross-signal correlation (traces ↔ logs ↔ metrics)

### Tasks

#### 2.1 Flatten Traces (from otel_spans)
- **Notebook**: `01_flatten_traces.py`
  - Read from streaming `{catalog}.bronze.otel_spans`
  - Flatten nested structures:
    - Extract `resource.attributes["service.name"]` → `service_name`
    - Extract `resource.attributes["service.version"]` → `service_version`
    - Extract `attributes["http.method"]` → `http_method`
    - Extract `attributes["http.status_code"]` → `http_status_code`
    - Extract `attributes["rpc.service"]` → `rpc_service`
    - Extract `status.code` → `is_error` (boolean)
  - Calculate derived fields:
    - `duration_ms` = (end_time_unix_nano - start_time_unix_nano) / 1e6
    - `start_timestamp` = from_unixtime(start_time_unix_nano / 1e9)
    - `end_timestamp` = from_unixtime(end_time_unix_nano / 1e9)

- **Output**: `traces_silver` table
  ```
  trace_id | span_id | parent_span_id | name | kind | service_name | 
  http_method | http_status_code | rpc_service | duration_ms | 
  start_timestamp | end_timestamp | is_error | attributes (map)
  ```

#### 2.2 Assemble Traces
- **Notebook**: `02_assemble_traces.py`
  - Group spans by `trace_id` from `traces_silver`
  - Build trace-level aggregations:
    - `span_count` = count(*)
    - `trace_start` = min(start_timestamp)
    - `trace_end` = max(end_timestamp)
    - `services_involved` = collect_list(service_name)
    - `error_count` = sum(is_error)
    - `has_errors` = error_count > 0
    - `max_span_duration_ms` = max(duration_ms)

- **Output**: `traces_assembled_silver` table
  ```
  trace_id | span_count | trace_start | trace_end | services_involved | 
  error_count | has_errors | max_span_duration_ms
  ```

#### 2.3 Service Health Golden Signals
- **Notebook**: `03_compute_service_health.py`
  - Read from streaming `traces_silver` with watermark
  - Compute per-service, per-1-minute window aggregations:
    - **Traffic**: `request_count` = count(*)
    - **Errors**: `error_count`, `error_rate` = error_count / request_count
    - **Latency**: `latency_p50_ms`, `latency_p95_ms`, `latency_p99_ms`
  - Use `approx_percentile()` for latency calculations
  - Window: 1 minute tumbling window

- **Output**: `service_health_silver` table (streaming)
  ```
  timestamp | service_name | request_count | error_count | error_rate | 
  latency_p50_ms | latency_p95_ms | latency_p99_ms
  ```

#### 2.4 Enrich Logs
- **Notebook**: `04_enrich_logs.py`
  - Read from streaming `{catalog}.bronze.otel_logs`
  - Flatten log structures:
    - Extract `resource.attributes["service.name"]` → `service_name`
    - Convert `time_unix_nano` → `log_timestamp`
    - Convert `observed_time_unix_nano` → `observed_timestamp`
  - Join with `traces_silver` on (trace_id, span_id):
    - Add span.name, span.http_url for context
  - Stream-static join pattern

- **Output**: `logs_silver` table
  ```
  trace_id | span_id | service_name | log_timestamp | severity_text | 
  body | attributes (map) | span_name | span_http_url
  ```

#### 2.5 Flatten Metrics
- **Notebook**: `05_flatten_metrics.py`
  - Read from streaming `{catalog}.bronze.otel_metrics`
  - Flatten metric-type-specific STRUCT columns:
    - **Gauge**: Extract `gauge.value`, `gauge.time_unix_nano`, `gauge.attributes`
    - **Sum**: Extract `sum.value`, `sum.is_monotonic`, `sum.attributes`
    - **Histogram**: Extract `histogram.count`, `histogram.sum`, `histogram.bucket_counts`
  - Extract `resource.attributes["service.name"]` → `service_name`
  - Convert unix nano timestamps to human-readable
  - Union all metric types into single table

- **Output**: `metrics_silver` table
  ```
  name | service_name | metric_timestamp | value | metric_type | 
  metric_attributes (map) | is_monotonic | histogram_count | histogram_sum
  ```

### Deliverables
- ✅ 5 Silver transformation notebooks deployed and operational
  - `01_flatten_traces.py` - Reads from `main.jmr_demo.otel_spans` ✅ RUNNING
  - `02_assemble_traces.py` - Groups spans into complete traces ✅ RUNNING
  - `03_compute_service_health.py` - Calculates SLI metrics ✅ RUNNING
  - `04_enrich_logs.py` - Reads from `main.jmr_demo.otel_logs` ✅ RUNNING
  - `05_flatten_metrics.py` - Reads from `main.jmr_demo.otel_metrics` ✅ RUNNING
- ✅ Silver transformations job executed and populating tables
- ✅ Output schemas validated and match expected structure
- ✅ Streaming checkpoints and watermarks operational
- ✅ Cross-signal correlation validated (logs successfully linked to traces via trace_id)

---

## Phase 3: Gold Layer Aggregations (Week 3-4)

### Goals
- Create time-series rollups for historical analysis
- Build service dependency topology
- Implement anomaly detection baselines
- Optimize query performance with materialized views

### Tasks

#### 3.1 Service Health Time-Series Rollups
- **Notebook**: `07_gold_service_health_rollups.py`
  - Aggregate service health metrics:
    - **Hourly rollups**: Average, min, max, p95 latency
    - **Daily rollups**: Long-term trend analysis
  - Retention policy: 7d raw, 30d hourly, 90d daily

- **Output**: `service_health_hourly_gold`, `service_health_daily_gold`

#### 3.2 Service Dependency Map
- **Notebook**: `08_gold_service_dependencies.py`
  - Extract service call relationships from traces:
    - Parent span service → Child span service
    - Call frequency, average latency, error rate
  - Build directed graph of service dependencies

- **Output**: `service_dependencies_gold`
  ```
  source_service | target_service | call_count | avg_duration_ms | 
  error_count | last_seen_timestamp
  ```

#### 3.3 Metric Rollups
- **Notebook**: `09_gold_metric_rollups.py`
  - Aggregate infrastructure metrics (Redis, Nginx, PostgreSQL):
    - 1-minute, 5-minute, hourly windows
    - Store percentiles, averages, counts
  - Reduce data volume for long-term storage

- **Output**: `metrics_rollups_gold`

#### 3.4 Anomaly Detection Baselines
- **Notebook**: `10_gold_anomaly_baselines.py`
  - Calculate historical baselines per service:
    - Mean and stddev for request rate, error rate, latency
    - Seasonal patterns (hourly, daily, weekly)
  - Store baseline models for real-time anomaly detection

- **Output**: `anomaly_baselines_gold`

### Deliverables
- ✅ Gold notebooks created and partially deployed
  - `01_service_health_rollups.py` - Hourly aggregations ✅ DEPLOYED
  - `02_service_dependencies.py` - Service call graph ⏳ PENDING
  - `03_metric_rollups.py` - Infrastructure metric rollups 🔄 UNDER REVIEW (data quality issues)
  - `04_anomaly_baselines.py` - Statistical baselines (7-day lookback) ⏳ PENDING
- 🔄 **IN PROGRESS**: Execute gold_aggregations job (1 of 4 complete)
- 🔄 **IN PROGRESS**: Validate gold table schemas and data quality
- ⏳ **PENDING**: Test anomaly detection thresholds

---

## Phase 4: Application Layer (Week 4-5)

### Goals
- Deploy interactive Streamlit application
- Create operational Lakeview dashboards
- Implement alerting workflow (HTTP webhook)
- Enable ad-hoc SQL query access

### Tasks

#### 4.1 Streamlit Application Development
- **Application**: `databricks_app/observability_app.py`

**Features**:
1. **Trace Viewer**
   - Input: Trace ID
   - Output: Waterfall chart, span details, correlated logs
   - Technology: Plotly for waterfall visualization

2. **Log Explorer**
   - Filters: Service, severity, time range, search text
   - Output: Log table with trace links
   - Click trace_id → Navigate to trace viewer

3. **Service Health Dashboard**
   - Real-time service status grid (🟢🟡🔴)
   - Golden signals: Traffic, errors, latency
   - Anomaly highlights

4. **Service Map**
   - Network graph of service dependencies
   - Node size = request volume
   - Edge thickness = call frequency
   - Color = error rate

- **Deployment**: Databricks Apps (serverless)

#### 4.2 Lakeview Dashboards
- **Dashboard 1: Service Health Overview**
  - Grid of services with status indicators
  - Request rate, error rate, p95 latency tiles
  - Auto-refresh: 1 minute
  - Drill-down to service detail

- **Dashboard 2: Anomaly Detection**
  - Timeline of detected anomalies
  - Service breakdown by anomaly type
  - Top 10 anomalous services
  - Link to investigation (trace viewer)

- **Dashboard 3: Metrics Explorer**
  - Time-series line charts for key metrics
  - Service selector, metric type selector
  - Historical trends (24h, 7d, 30d)

#### 4.3 Alerting Workflow
- **Workflow**: `workflows/anomaly_alerting.yml`
  - Schedule: Every 1 minute
  - Query: `SELECT * FROM service_health_silver WHERE is_anomalous = true AND timestamp >= CURRENT_TIMESTAMP() - INTERVAL 2 MINUTE`
  - Action: HTTP POST to webhook with payload:
    ```json
    {
      "alert_type": "service_anomaly",
      "service": "frontend",
      "timestamp": "2025-10-24T22:23:57Z",
      "anomaly_score": 4.2,
      "metrics": {
        "error_rate": 0.15,
        "latency_p95": 1523
      },
      "investigation_link": "https://databricks.com/app/traces?service=frontend"
    }
    ```

#### 4.4 SQL Query Library
- **File**: `sql_queries/observability_queries.sql`
  - Common queries for operational use:
    - Find traces by service and time range
    - Calculate service latency percentiles
    - Search logs with trace context
    - Service dependency analysis
    - Error rate trends

### Deliverables
- ✅ Alerting notebook created (ahead of schedule)
  - `detect_anomalies.py` - Compares current health vs baselines, triggers webhooks
- ⏳ **PENDING**: Streamlit application development
- ⏳ **PENDING**: Lakeview dashboards creation
- ⏳ **PENDING**: Test alerting webhook integration
- ⏳ **PENDING**: SQL query library documentation

---

## Phase 5: Validation & Handoff (Week 5-6)

### Goals
- End-to-end testing with sample data
- Performance validation
- Documentation and training
- Production readiness assessment

### Tasks

#### 5.1 End-to-End Testing
- ✅ **Data Quality Notebooks Created** (ahead of schedule):
  - `validate_trace_completeness.py` - Checks for orphaned spans, completeness rate
  - `validate_cross_signal_correlation.py` - Validates trace-log correlation
  - `validate_service_health_metrics.py` - Data quality checks on SLI metrics
  
- ⏳ **Test Scenarios** (pending execution):
  1. **Trace Assembly**: Verify complete traces assembled correctly
     - Pick 5 random trace IDs from Bronze
     - Validate Silver trace structure (parent-child relationships)
     - Confirm all spans accounted for
  
  2. **Golden Signals**: Validate metrics match source data
     - Sample 10 services
     - Calculate expected request rate, error rate manually
     - Compare with `service_health_silver` output
  
  3. **Anomaly Detection**: Trigger synthetic anomaly
     - Inject high error rate data
     - Verify anomaly flagged within 2 minutes
     - Confirm alert webhook fired
  
  4. **Cross-Signal Correlation**: Verify trace-log linkage
     - Pick trace with errors
     - Confirm ERROR logs linked via `trace_id`
     - Validate trace context in log enrichment

#### 5.2 Performance Validation
- **Query Performance**:
  - Dashboard queries < 5 seconds (p95)
  - Trace lookup by ID < 3 seconds
  - Log search < 5 seconds (100 results)
  - Service dependency map < 10 seconds

- **Data Freshness**:
  - Silver layer lag < 5 minutes
  - Gold layer lag < 15 minutes
  - Alerting latency < 2 minutes from anomaly detection

- **Optimization**:
  - Enable adaptive query execution
  - Z-order key columns (trace_id, service_name, timestamp)
  - Vacuum old versions (retain 7 days)

#### 5.3 Documentation
- **Technical Documentation**:
  1. Architecture diagram (visual)
  2. Schema documentation (data dictionary)
  3. ETL pipeline flow (Bronze → Silver → Gold)
  4. Query patterns and best practices
  5. Troubleshooting guide

- **Operational Runbook**:
  1. How to investigate service issues
  2. How to query traces by service/time
  3. How to interpret anomaly scores
  4. How to add new services to monitoring

- **Next Steps Roadmap**:
  1. Production hardening checklist
  2. ML-based anomaly detection (MLflow)
  3. Advanced correlation (automatic RCA)
  4. Performance optimization (sampling, caching)
  5. RBAC and SSO integration

#### 5.4 Training & Handoff
- **Training Sessions**:
  1. Platform overview and architecture (1 hour)
  2. Dashboard and application walkthrough (1 hour)
  3. SQL query workshop (1 hour)
  4. Troubleshooting and operations (1 hour)

- **Handoff Artifacts**:
  - All notebooks (.py files)
  - SQL scripts (.sql files)
  - Streamlit application code
  - Workflow definitions (.yml)
  - Documentation (markdown/PDF)

### Deliverables
- ✅ End-to-end test results validated
- ✅ Performance benchmarks met
- ✅ Complete documentation package
- ✅ Training completed
- ✅ Production readiness checklist

---

## Success Criteria

### Technical Validation
- ✅ Ingest all 3 OTEL signals (traces, metrics, logs) into Delta Lake
- ✅ Assemble complete traces with < 5 min latency
- ✅ Compute golden signals (traffic, errors, latency) in real-time
- ✅ Detect anomalies with < 2 min alert delivery
- ✅ Query traces by ID in < 3 seconds
- ✅ Correlate logs to traces via trace_id

### User Validation
- ✅ Service health dashboard shows real-time status
- ✅ Interactive app allows trace drill-down
- ✅ Log search with trace context works
- ✅ Anomaly alerts trigger HTTP webhook

### Business Validation
- ✅ Demonstrates Splunk replacement viability
- ✅ Shows Unity Catalog governance value
- ✅ Validates hybrid (real-time + batch) architecture

---

## Risk Assessment & Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| JSON parsing performance issues | High | Medium | Use built-in Delta Lake JSON functions, optimize with Z-ordering |
| Data volume explosion | High | Low | Implement sampling strategies for POC, document production limits |
| Query performance degradation | Medium | Medium | Pre-aggregate common queries, enable caching, use materialized views |
| OTEL schema evolution | Medium | Low | Schema enforcement with graceful degradation, versioned pipelines |
| Skill gap (team unfamiliar with Databricks) | Medium | Medium | Comprehensive training, documentation, phased rollout |

---

## Resource Requirements

### Databricks Resources
- **Compute**:
  - Serverless SQL Warehouse (X-Small): $0.50/DBU, ~10 DBU/day = $5/day
  - Shared cluster for development: Standard_DS3_v2, 1 worker = $10/day
  - **Estimated POC cost**: $300-500 for 4-6 weeks

- **Storage**:
  - Delta Lake storage: ~10 GB (sample data)
  - Unity Catalog metadata: Minimal

### Personnel
- **Data Engineer**: 60% time (Bronze/Silver/Gold pipelines)
- **Application Developer**: 40% time (Streamlit app, dashboards)
- **DevOps/Platform Engineer**: 20% time (Databricks setup, workflows)

### Timeline
- **Total Duration**: 4-6 weeks
- **Effort**: ~2-3 person-weeks of development

---

## Roadmap

### Immediate Priorities (Current Sprint)
1. **Complete Gold Layer Aggregations**
   - Fix metrics silver table data quality issues
   - Deploy and validate service dependencies gold table
   - Deploy and validate anomaly baselines gold table
   - Complete metric rollups gold table

2. **Data Quality & Validation**
   - Execute data quality validation notebooks
   - Establish baseline quality metrics for all layers
   - Document known data quality issues and mitigation strategies

3. **Application Layer Foundation**
   - Begin Streamlit application development
   - Create initial service health dashboard
   - Implement basic trace viewer functionality

### Architecture Optimization (Next Phase)
1. **Consolidate Pipelines** 🎯 *Strategic Priority*
   - **Phase 1**: Consolidate bronze sync pipelines
     - Currently: Separate Lakebase sync pipelines for spans, metrics, logs
     - Target: Single unified Lakebase sync pipeline for all OTEL signals
     - Benefits: Reduced compute cost, simpler operations, unified monitoring
     - Status: Script created at `scripts/setup_synced_tables.py`, testing single pipeline approach

   - **Phase 2**: Consolidate silver and gold pipelines
     - Currently: Separate silver transformation jobs and gold aggregation jobs
     - Target: Unified multi-stage pipeline with dependencies
     - Benefits: Improved orchestration, reduced scheduling overhead, clearer data lineage
     - Approach: Create single DLT pipeline or workflow with sequential stages

   - **Phase 3**: Consolidate app and pipelines
     - Currently: Separate Streamlit app deployment and data pipeline execution
     - Target: Integrated platform with unified deployment and monitoring
     - Benefits: End-to-end observability, simplified CI/CD, consistent versioning
     - Approach: Bundle Databricks App with pipeline definitions in single Asset Bundle

2. **Performance Optimization**
   - Implement intelligent trace sampling strategies
   - Add query result caching layer
   - Optimize with materialized views
   - Enable compaction and Z-ordering schedules

3. **Enhanced Observability**
   - Add pipeline monitoring and alerting
   - Implement data quality metrics tracking
   - Create operational dashboards for pipeline health
   - Document SLOs for each pipeline stage

### Production Hardening (Future)
1. **ML-Based Anomaly Detection**
   - Replace z-score with MLflow models
   - Train on historical data
   - Deploy as Databricks Model Serving endpoint

2. **Advanced Correlation**
   - Automatic root cause analysis
   - Cross-service error propagation tracking
   - Intelligent alert grouping

3. **Security & Governance**
   - Implement RBAC with Azure AD/Okta SSO
   - Team-based data access controls
   - PII masking for sensitive logs
   - Audit logging for compliance

4. **Cost Management**
   - Sampling strategies (tail-based, probabilistic)
   - Tiered retention policies (hot/warm/cold)
   - Query cost monitoring and optimization

5. **Integration Enhancements**
   - Native PagerDuty/Slack alerting
   - Grafana data source plugin
   - CI/CD pipeline integration for deployment observability

---

## Appendix

### A. Technology Stack Summary
| Layer | Technology | Rationale |
|-------|-----------|-----------|
| Data Collection | OTEL Collector Gateway | Already in place, standard protocol |
| Data Platform | Databricks (Unity Catalog) | Required governance, SQL analytics |
| Storage Format | Delta Lake | ACID, time travel, performance |
| Compute | Serverless SQL Warehouse | Cost-optimized for POC |
| Orchestration | Databricks Workflows | Native integration, alerting |
| Dashboards | Lakeview | Quick operational views |
| Interactive App | Streamlit (Databricks Apps) | Fast development, native hosting |
| Visualization | Plotly | Interactive charts, trace waterfall |
| Anomaly Detection | Z-score (Phase 1) → MLflow (Future) | Simple POC → production ML |
| Alerting | HTTP Webhook | Integration flexibility |

### B. Sample Services in Data
- `frontend` (Node.js)
- `frontend-proxy` (Envoy/C++)
- `cart` (.NET)
- `ad` (Java)
- `currency` (C++)
- `product-catalog` (Go)
- `payment` (Node.js)
- `load-generator` (Python)
- `accounting` (.NET)
- `quote` (PHP)
- `kafka` (Java)

### C. Key Metrics to Monitor
- Request rate (requests/second)
- Error rate (%)
- Latency percentiles (p50, p95, p99)
- Infrastructure metrics (CPU, memory, connections)
- Service dependencies (call graph)

### D. Contact Information
- **Project Lead**: [Name]
- **Technical Lead**: [Name]
- **Databricks Account Team**: [Contact]
