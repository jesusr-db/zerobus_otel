# ZeroBus-1 Operations Runbook

## Table of Contents
1. [Job Descriptions](#job-descriptions)
2. [Monitoring & Health Checks](#monitoring--health-checks)
3. [Common Operations](#common-operations)
4. [Emergency Procedures](#emergency-procedures)

---

## Job Descriptions

### 1. Silver Transformations
**Job Name**: `[dev] Silver Transformations`  
**Schedule**: Every 5 minutes  
**Duration**: ~3 minutes  
**Purpose**: Process raw OTEL data from bronze layer into queryable silver tables

**Tasks**:
1. **flatten_traces** (`01_flatten_traces.py`)
   - Reads: `jmr_demo.zerobus.otel_spans`
   - Writes: `jmr_demo.zerobus.traces_silver`
   - Extracts nested span attributes, resource tags, events
   - Checkpoint: `/checkpoint/silver/traces`

2. **assemble_traces** (`02_assemble_traces.py`)
   - Reads: `jmr_demo.zerobus.traces_silver`
   - Writes: `jmr_demo.zerobus.traces_assembled_silver`
   - Groups spans by trace_id for trace-level aggregations
   - Depends on: flatten_traces
   - Checkpoint: `/checkpoint/silver/traces_assembled`

3. **compute_service_health** (`03_compute_service_health.py`)
   - Reads: `jmr_demo.zerobus.traces_silver`
   - Writes: `jmr_demo.zerobus.service_health_silver`
   - Computes golden signals per service (error rate, latency, request count)
   - Window: 1 minute, Watermark: 5 minutes
   - Depends on: flatten_traces
   - Checkpoint: `/checkpoint/silver/service_health`

4. **enrich_logs** (`04_enrich_logs.py`)
   - Reads: `jmr_demo.zerobus.otel_logs`, `jmr_demo.zerobus.traces_silver`
   - Writes: `jmr_demo.zerobus.logs_silver`
   - Enriches logs with trace/span context
   - Depends on: flatten_traces
   - Checkpoint: `/checkpoint/silver/logs`

5. **flatten_metrics** (`05_flatten_metrics.py`)
   - Reads: `jmr_demo.zerobus.otel_metrics`
   - Writes: `jmr_demo.zerobus.metrics_silver`
   - Flattens metric type-specific structures (gauge, sum, histogram, summary)
   - Checkpoint: `/checkpoint/silver/metrics`

**Configuration**:
```yaml
catalog_name: jmr_demo
bronze_catalog: jmr_demo
bronze_schema: zerobus
bronze_table_prefix: otel_
```

**Success Criteria**:
- All 5 tasks complete within 5 minutes
- No checkpoint corruption
- Output tables contain new records

**Failure Modes**:
- Schema mismatch in bronze tables
- Checkpoint directory permission errors
- Out of memory on large batches

---

### 2. Gold Aggregations
**Job Name**: `[dev] Gold Aggregations`  
**Schedule**: Hourly (top of hour)  
**Duration**: ~1.5 minutes  
**Purpose**: Create business-level aggregations for dashboards and analytics

**Tasks**:
1. **service_health_rollups** (`01_service_health_rollups.py`)
   - Reads: `jmr_demo.zerobus.service_health_silver` (last 2 hours)
   - Writes: `jmr_demo.zerobus.service_health_hourly`
   - Hourly aggregations of service health metrics
   - Mode: overwrite

2. **service_dependencies** (`02_service_dependencies.py`)
   - Reads: `jmr_demo.zerobus.traces_silver` (last 24 hours)
   - Writes: `jmr_demo.zerobus.service_dependencies`
   - Maps parent-child service relationships
   - Mode: overwrite

3. **metric_rollups** (`03_metric_rollups.py`)
   - Reads: `jmr_demo.zerobus.metrics_silver` (last 2 hours)
   - Writes: `jmr_demo.zerobus.metric_rollups_hourly`
   - Hourly metric aggregations by name and labels
   - Mode: overwrite

4. **anomaly_baselines** (`04_anomaly_baselines.py`)
   - Reads: `jmr_demo.zerobus.service_health_silver` (last 7 days)
   - Writes: `jmr_demo.zerobus.anomaly_baselines`
   - Computes baseline statistics for anomaly detection
   - Calculates: avg, stddev for error rate and latency per service
   - Depends on: service_health_rollups
   - Mode: overwrite

**Configuration**:
```yaml
catalog_name: jmr_demo
lookback_hours: 2 (or 24 for dependencies)
lookback_days: 7 (for baselines)
```

**Success Criteria**:
- All aggregations complete within 2 minutes
- Output tables updated with latest hour
- Anomaly baselines have stddev > 0

**Failure Modes**:
- Insufficient data in lookback window
- Division by zero if no requests
- Memory issues on large historical data

---

### 3. Anomaly Alerting
**Job Name**: `[dev] Anomaly Alerting`  
**Schedule**: Every minute  
**Duration**: ~30 seconds  
**Purpose**: Detect service health anomalies and trigger alerts

**Tasks**:
1. **detect_anomalies** (`detect_anomalies.py`)
   - Reads: 
     - `jmr_demo.zerobus.service_health_silver` (last 2 minutes)
     - `jmr_demo.zerobus.anomaly_baselines`
   - Writes: `jmr_demo.zerobus.detected_anomalies`
   - Logic: Flags services where:
     - `error_rate > baseline_error_rate + 2*error_rate_stddev`
     - `latency_p95_ms > baseline_latency + 2*latency_stddev`
   - Mode: append

**Configuration**:
```yaml
catalog_name: jmr_demo
lookback_minutes: 2
```

**Success Criteria**:
- Completes in < 1 minute
- Anomalies written to table
- (Future) Alerts sent via webhook/email

**Failure Modes**:
- Baselines table missing (first run before gold job completes)
- No recent service health data
- Webhook/email delivery failures (when enabled)

---

### 4. Data Quality Validation
**Job Name**: `[dev] Data Quality Validation`  
**Schedule**: Daily at 2 AM UTC  
**Duration**: ~1 minute  
**Purpose**: Validate data quality and completeness across layers

**Tasks**:
1. **validate_trace_completeness** (`validate_trace_completeness.py`)
   - Reads: `jmr_demo.zerobus.traces_silver`
   - Writes: `jmr_demo.zerobus.trace_completeness_results`
   - Checks: Orphaned spans (parent_span_id references missing spans)
   - Target: 95%+ completeness
   - Status: PASS/FAIL

2. **validate_cross_signal_correlation** (`validate_cross_signal_correlation.py`)
   - Reads: 
     - `jmr_demo.zerobus.traces_silver`
     - `jmr_demo.zerobus.logs_silver`
   - Writes: `jmr_demo.zerobus.cross_signal_correlation_results`
   - Checks: Percentage of traces with corresponding logs
   - Target: 80%+ correlation
   - Status: PASS/WARN

3. **validate_service_health_metrics** (`validate_service_health_metrics.py`)
   - Reads: `jmr_demo.zerobus.service_health_silver`
   - Writes: `jmr_demo.zerobus.service_health_quality_results`
   - Checks: 
     - Null values in critical columns
     - Invalid ranges (negative values, error_rate > 1)
   - Target: 99%+ data quality score
   - Status: PASS/FAIL

**Configuration**:
```yaml
catalog_name: jmr_demo
```

**Success Criteria**:
- All validations complete
- Results written to quality tables
- PASS status on all checks (or acceptable WARN)

**Failure Modes**:
- Empty silver tables (data ingestion issues)
- Schema changes breaking validation logic

---

## Monitoring & Health Checks

### Job Run History
Check job status in Databricks UI:
```
Workflows → Jobs → [job_name] → Runs
```

### CLI Monitoring
```bash
# List all jobs
databricks jobs list --profile DEFAULT

# Check specific job runs
databricks jobs runs list --job-id <job_id> --profile DEFAULT

# Get run details
databricks jobs runs get --run-id <run_id> --profile DEFAULT
```

### Data Quality Checks
```sql
-- Check latest validation results
SELECT * FROM jmr_demo.zerobus.trace_completeness_results 
ORDER BY validation_timestamp DESC LIMIT 10;

SELECT * FROM jmr_demo.zerobus.cross_signal_correlation_results 
ORDER BY validation_timestamp DESC LIMIT 10;

SELECT * FROM jmr_demo.zerobus.service_health_quality_results 
ORDER BY validation_timestamp DESC LIMIT 10;
```

### Anomaly Monitoring
```sql
-- Check recent anomalies
SELECT * FROM jmr_demo.zerobus.detected_anomalies 
ORDER BY detection_timestamp DESC LIMIT 20;

-- Anomalies by service
SELECT service_name, COUNT(*) as anomaly_count
FROM jmr_demo.zerobus.detected_anomalies
WHERE detection_timestamp >= current_timestamp() - INTERVAL 24 HOURS
GROUP BY service_name
ORDER BY anomaly_count DESC;
```

### Pipeline Health
```sql
-- Check silver table freshness
SELECT 
  'traces_silver' as table_name,
  MAX(start_timestamp) as latest_record,
  TIMESTAMPDIFF(MINUTE, MAX(start_timestamp), current_timestamp()) as minutes_ago
FROM jmr_demo.zerobus.traces_silver

UNION ALL

SELECT 
  'logs_silver',
  MAX(log_timestamp),
  TIMESTAMPDIFF(MINUTE, MAX(log_timestamp), current_timestamp())
FROM jmr_demo.zerobus.logs_silver

UNION ALL

SELECT 
  'service_health_silver',
  MAX(timestamp),
  TIMESTAMPDIFF(MINUTE, MAX(timestamp), current_timestamp())
FROM jmr_demo.zerobus.service_health_silver;
```

---

## Common Operations

### Deploy Changes
```bash
# Deploy to dev
databricks bundle deploy -t dev --profile DEFAULT

# Deploy to staging
databricks bundle deploy -t staging --profile DEFAULT

# Deploy to prod
databricks bundle deploy -t prod --profile DEFAULT
```

### Run Jobs Manually
```bash
# Run individual job
databricks bundle run -t dev silver_transformations --profile DEFAULT
databricks bundle run -t dev gold_aggregations --profile DEFAULT
databricks bundle run -t dev anomaly_alerting --profile DEFAULT
databricks bundle run -t dev data_quality_validation --profile DEFAULT
```

### Pause/Resume Schedules
```bash
# Pause a job (via UI or API)
databricks jobs update --job-id <job_id> --json '{
  "schedule": {
    "pause_status": "PAUSED"
  }
}'

# Resume a job
databricks jobs update --job-id <job_id> --json '{
  "schedule": {
    "pause_status": "UNPAUSED"
  }
}'
```

### Reset Checkpoints
If a streaming job is stuck or corrupt:
```bash
# Delete checkpoint directory
databricks fs rm -r dbfs:/checkpoint/silver/traces

# Rerun the job (will reprocess all data)
databricks bundle run -t dev silver_transformations --profile DEFAULT
```

**WARNING**: Resetting checkpoints causes full reprocessing. Use only when necessary.

### Backfill Data
```sql
-- For gold aggregations, simply rerun with wider lookback window
-- Edit lookback_hours parameter in job config or pass as parameter

-- Example: Backfill last 7 days of service health rollups
-- Update resources/jobs.yml temporarily:
-- lookback_hours: "168"  -- 7 days

-- Then redeploy and run
```

### Clear Old Data
```sql
-- Example: Purge validation results older than 90 days
DELETE FROM jmr_demo.zerobus.trace_completeness_results
WHERE validation_timestamp < current_timestamp() - INTERVAL 90 DAYS;

-- Run OPTIMIZE after large deletes
OPTIMIZE jmr_demo.zerobus.trace_completeness_results;
```

---

## Emergency Procedures

### Pipeline Stopped/Not Processing
**Symptoms**: Silver tables not updating, data freshness > 10 minutes

**Steps**:
1. Check job status: `Workflows → Jobs → Silver Transformations`
2. Check recent run logs for errors
3. Verify bronze tables have new data:
   ```sql
   SELECT MAX(Timestamp) FROM jmr_demo.zerobus.otel_spans;
   ```
4. If bronze is stale, check upstream ingestion (DLT, Kafka, etc.)
5. If bronze is fresh but silver is stale:
   - Check checkpoint corruption
   - Review error logs for schema issues
   - Consider checkpoint reset (last resort)

### Anomaly Alert Storm
**Symptoms**: Hundreds of anomalies detected, alert flood

**Steps**:
1. Verify if legitimate spike or baseline issue:
   ```sql
   SELECT service_name, error_rate, baseline_error_rate, error_rate_stddev
   FROM jmr_demo.zerobus.detected_anomalies
   WHERE detection_timestamp >= current_timestamp() - INTERVAL 5 MINUTES;
   ```
2. Check if baselines are stale (should update hourly):
   ```sql
   SELECT MAX(baseline_timestamp) FROM jmr_demo.zerobus.anomaly_baselines;
   ```
3. If baselines outdated, manually run gold_aggregations
4. If legitimate spike, investigate root cause in traces/logs
5. Temporarily pause anomaly_alerting job if false positives:
   ```bash
   # Pause via UI: Workflows → Jobs → Anomaly Alerting → Pause
   ```

### Data Quality Failures
**Symptoms**: FAIL status in validation results

**Steps**:
1. Check which validation failed:
   ```sql
   SELECT * FROM jmr_demo.zerobus.trace_completeness_results 
   WHERE status = 'FAIL' 
   ORDER BY validation_timestamp DESC LIMIT 1;
   ```
2. For trace completeness failures:
   - Review orphaned span patterns
   - Check for incomplete trace ingestion
   - Verify parent-child span linking logic
3. For correlation failures:
   - Verify log collection is enabled
   - Check trace_id propagation in logs
4. For service health quality failures:
   - Identify null/invalid records
   - Fix upstream data quality issues

### Job Timeout
**Symptoms**: Job exceeds timeout_seconds and is killed

**Steps**:
1. Check recent data volume spike:
   ```sql
   SELECT DATE_TRUNC('hour', start_timestamp) as hour, COUNT(*) 
   FROM jmr_demo.zerobus.traces_silver
   WHERE start_timestamp >= current_timestamp() - INTERVAL 24 HOURS
   GROUP BY hour
   ORDER BY hour DESC;
   ```
2. If volume spike, increase timeout in `resources/jobs.yml`:
   ```yaml
   timeout_seconds: 3600  # Increase from 1800
   ```
3. Consider optimizing slow queries:
   - Add indexes/partitions
   - Adjust window/watermark settings
   - Increase cluster size (if using dedicated clusters)

### Schema Evolution Issues
**Symptoms**: Jobs fail with schema mismatch errors

**Steps**:
1. Identify schema change in error logs
2. Update notebook code to handle new schema
3. Use schema evolution safely:
   ```python
   # Add mergeSchema option
   .option("mergeSchema", "true")
   ```
4. Test changes in dev before production
5. Consider versioned transformations for major changes

### Contact Information
- **On-Call Engineer**: [Your team's pager/slack]
- **Databricks Support**: support@databricks.com
- **Escalation**: [Team lead contact]
