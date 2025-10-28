# ZeroBus-1 Troubleshooting Guide

## Quick Diagnosis

| Symptom | Likely Cause | Quick Fix |
|---------|-------------|-----------|
| Silver tables not updating | Job failure or bronze data stale | Check job logs, verify bronze freshness |
| Anomaly alert flood | Stale baselines or legitimate spike | Check baseline_timestamp, run gold job |
| Data quality FAIL | Incomplete ingestion or schema change | Review validation query, check upstream |
| Job timeout | Data volume spike | Increase timeout_seconds in config |
| Schema mismatch error | Bronze schema changed | Update transformation logic, use mergeSchema |
| Checkpoint corruption | Interrupted streaming job | Delete checkpoint dir, reprocess |
| No anomalies detected | Baselines table empty | Run gold_aggregations first |
| Orphaned spans high | Incomplete trace ingestion | Check trace collection at source |

---

## Common Issues & Resolutions

### 1. Silver Transformations Failing

#### Issue: `TABLE_OR_VIEW_NOT_FOUND` on bronze tables
**Error Message**:
```
The table or view `jmr_demo`.`zerobus`.`otel_spans` cannot be found
```

**Root Cause**: Bronze tables don't exist or catalog/schema misconfigured

**Resolution**:
```sql
-- Verify bronze tables exist
SHOW TABLES IN jmr_demo.zerobus LIKE 'otel_%';

-- Check if DLT pipeline created tables
SELECT * FROM jmr_demo.zerobus.otel_spans LIMIT 1;
```

If tables missing:
1. Verify DLT pipeline is running and publishing to correct catalog/schema
2. Check `databricks.yml` variables:
   ```yaml
   bronze_catalog: jmr_demo
   bronze_schema: zerobus
   ```
3. Redeploy: `databricks bundle deploy -t dev --profile DEFAULT`

---

#### Issue: `STREAM_FAILED` checkpoint corruption
**Error Message**:
```
Failed to read checkpoint from /checkpoint/silver/traces
```

**Root Cause**: Checkpoint directory corrupted or schema incompatible

**Resolution**:
```bash
# Option 1: Delete checkpoint (will reprocess all data)
databricks fs rm -r dbfs:/checkpoint/silver/traces

# Option 2: If data volume is huge, try checkpoint recovery
databricks fs ls dbfs:/checkpoint/silver/traces/commits/
# Manually remove corrupt commit files
```

**Warning**: Deleting checkpoints causes full reprocessing. Monitor for duplicates if using append mode.

---

#### Issue: `UNRESOLVED_COLUMN` after schema change
**Error Message**:
```
A column, variable, or function parameter with name `http_status_code` cannot be resolved
```

**Root Cause**: Bronze schema evolved but transformation code hasn't updated

**Resolution**:
1. Check current bronze schema:
   ```sql
   DESCRIBE jmr_demo.zerobus.otel_spans;
   ```
2. Update notebook to handle column:
   ```python
   # Add null check for optional columns
   .withColumn("http_status_code", 
       when(col("Attributes.http.status_code").isNotNull(), 
            col("Attributes.http.status_code"))
       .otherwise(lit(None).cast("integer"))
   )
   ```
3. Consider schema evolution:
   ```python
   spark.readStream.option("mergeSchema", "true").table(...)
   ```

---

### 2. Gold Aggregations Issues

#### Issue: `DIVIDE_BY_ZERO` in anomaly_baselines
**Error Message**:
```
Division by zero
```

**Root Cause**: No data in lookback window or service with zero requests

**Resolution**:
```sql
-- Check if service_health_silver has data in lookback window
SELECT MIN(timestamp), MAX(timestamp), COUNT(*)
FROM jmr_demo.zerobus.service_health_silver
WHERE timestamp >= current_timestamp() - INTERVAL 7 DAYS;
```

Fix in code:
```python
# Add null handling in baseline calculation
.withColumn("error_rate_stddev", 
    when(col("request_count") > 0, stddev("error_rate"))
    .otherwise(lit(0.0))
)
```

---

#### Issue: Empty service_dependencies table
**Root Cause**: No parent-child span relationships in data

**Resolution**:
```sql
-- Check if traces have parent_span_id
SELECT COUNT(*) as total_spans,
       SUM(CASE WHEN parent_span_id IS NOT NULL THEN 1 ELSE 0 END) as child_spans
FROM jmr_demo.zerobus.traces_silver;
```

If no child spans:
- Verify distributed tracing is properly instrumented at source
- Check trace context propagation between services
- Review OTEL SDK configuration in applications

---

### 3. Anomaly Detection Issues

#### Issue: No anomalies ever detected
**Root Cause**: Baselines table empty or thresholds too high

**Resolution**:
```sql
-- Check if baselines exist
SELECT * FROM jmr_demo.zerobus.anomaly_baselines LIMIT 5;

-- Check baseline freshness
SELECT MAX(baseline_timestamp) FROM jmr_demo.zerobus.anomaly_baselines;
```

If empty:
1. Manually run gold_aggregations: 
   ```bash
   databricks bundle run -t dev gold_aggregations --profile DEFAULT
   ```
2. Wait for anomaly_baselines task to complete
3. Rerun anomaly_alerting

If baselines exist but no detections:
- Lower threshold from 2 stddev to 1.5 stddev
- Verify services are actually experiencing errors/latency spikes

---

#### Issue: False positive anomaly flood
**Root Cause**: Baseline calculated during abnormal period or insufficient history

**Resolution**:
```sql
-- Analyze baseline vs current metrics
SELECT 
  a.service_name,
  a.error_rate as current_error_rate,
  b.baseline_error_rate,
  b.error_rate_stddev,
  (a.error_rate - b.baseline_error_rate) / b.error_rate_stddev as z_score
FROM jmr_demo.zerobus.service_health_silver a
JOIN jmr_demo.zerobus.anomaly_baselines b ON a.service_name = b.service_name
WHERE a.timestamp >= current_timestamp() - INTERVAL 5 MINUTES
ORDER BY z_score DESC;
```

If baselines are wrong:
1. Temporarily pause anomaly_alerting
2. Wait for 7 days of normal traffic to recalculate proper baselines
3. Or manually update baselines table with known-good values
4. Resume anomaly_alerting

---

### 4. Data Quality Validation Failures

#### Issue: Trace completeness below 95%
**Root Cause**: Orphaned spans from incomplete trace collection

**Resolution**:
```sql
-- Identify orphaned spans
WITH orphaned AS (
  SELECT child.span_id, child.parent_span_id, child.trace_id, child.service_name
  FROM jmr_demo.zerobus.traces_silver child
  LEFT ANTI JOIN jmr_demo.zerobus.traces_silver parent
    ON child.parent_span_id = parent.span_id 
    AND child.trace_id = parent.trace_id
  WHERE child.parent_span_id IS NOT NULL
)
SELECT service_name, COUNT(*) as orphaned_count
FROM orphaned
GROUP BY service_name
ORDER BY orphaned_count DESC;
```

Common causes:
- **Sampling at source**: Parent span sampled out but child span kept
- **Clock skew**: Parent span outside retention window
- **Collection lag**: Parent span not yet ingested

Fixes:
- Align sampling decisions across trace
- Increase retention/lookback window
- Add grace period for late-arriving spans

---

#### Issue: Cross-signal correlation below 80%
**Root Cause**: Logs missing trace_id or log collection incomplete

**Resolution**:
```sql
-- Check trace_id presence in logs
SELECT 
  COUNT(*) as total_logs,
  SUM(CASE WHEN trace_id IS NOT NULL THEN 1 ELSE 0 END) as logs_with_trace_id,
  SUM(CASE WHEN trace_id IS NOT NULL THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as percentage
FROM jmr_demo.zerobus.logs_silver;
```

If trace_id missing:
- Verify OTEL SDK in applications is injecting trace context into logs
- Check log parsing/enrichment logic in `04_enrich_logs.py`
- Review OTEL collector configuration for log processing

---

#### Issue: Service health quality score below 99%
**Root Cause**: Nulls or invalid values in metrics

**Resolution**:
```sql
-- Identify problematic records
SELECT service_name, error_rate, latency_p95_ms, request_count
FROM jmr_demo.zerobus.service_health_silver
WHERE error_rate IS NULL 
   OR error_rate < 0 
   OR error_rate > 1
   OR latency_p95_ms IS NULL
   OR latency_p95_ms < 0
   OR request_count IS NULL
   OR request_count < 0
LIMIT 100;
```

Common patterns:
- **Null error_rate**: Division by zero when request_count = 0
- **error_rate > 1**: Integer overflow or wrong aggregation
- **Negative latency**: Clock skew or unit conversion error

Fixes in `03_compute_service_health.py`:
```python
# Safe error rate calculation
.withColumn("error_rate",
    when(col("request_count") > 0, 
         col("error_count") / col("request_count"))
    .otherwise(lit(0.0))
)

# Ensure latency is positive
.withColumn("latency_p95_ms",
    when(col("latency_p95_ms") < 0, lit(0.0))
    .otherwise(col("latency_p95_ms"))
)
```

---

### 5. Performance Issues

#### Issue: Job taking longer than expected
**Root Cause**: Data volume spike or inefficient queries

**Resolution**:
```sql
-- Check data volume trends
SELECT 
  DATE_TRUNC('hour', start_timestamp) as hour,
  COUNT(*) as span_count,
  COUNT(*) * 100.0 / LAG(COUNT(*)) OVER (ORDER BY DATE_TRUNC('hour', start_timestamp)) as pct_change
FROM jmr_demo.zerobus.traces_silver
WHERE start_timestamp >= current_timestamp() - INTERVAL 24 HOURS
GROUP BY hour
ORDER BY hour DESC;
```

If volume spike:
1. Increase job timeout in `resources/jobs.yml`
2. Consider batch size tuning:
   ```python
   .option("maxFilesPerTrigger", 100)  # Reduce batch size
   ```
3. Add partitioning to hot tables:
   ```sql
   ALTER TABLE jmr_demo.zerobus.traces_silver 
   SET TBLPROPERTIES ('delta.autoOptimize.optimizeWrite' = 'true');
   ```

If inefficient queries:
- Review query plans for full table scans
- Add Z-ORDER optimization:
  ```sql
  OPTIMIZE jmr_demo.zerobus.traces_silver ZORDER BY (service_name, start_timestamp);
  ```
- Adjust watermark/window settings to reduce state size

---

#### Issue: Out of memory errors
**Error Message**:
```
Container killed by YARN for exceeding memory limits
```

**Root Cause**: Aggregations with high cardinality or large state

**Resolution**:
1. Check cardinality:
   ```sql
   SELECT COUNT(DISTINCT service_name) FROM jmr_demo.zerobus.traces_silver;
   SELECT COUNT(DISTINCT trace_id) FROM jmr_demo.zerobus.traces_silver;
   ```
2. Optimize aggregations:
   ```python
   # Use approximations for high cardinality
   .agg(approx_count_distinct("trace_id").alias("trace_count"))
   
   # Reduce window/watermark to limit state
   .withWatermark("timestamp", "2 minutes")  # Down from 5
   ```
3. Increase cluster resources (if using dedicated clusters)

---

### 6. Deployment Issues

#### Issue: Bundle deploy fails with validation error
**Error Message**:
```
Error: invalid configuration: <validation error>
```

**Root Cause**: Syntax error or invalid value in YAML files

**Resolution**:
1. Validate YAML syntax:
   ```bash
   # Check for syntax errors
   yamllint databricks.yml resources/*.yml
   ```
2. Common issues:
   - Incorrect indentation (use 2 spaces)
   - Missing required fields
   - Invalid cron expression
3. Validate bundle before deploy:
   ```bash
   databricks bundle validate -t dev --profile DEFAULT
   ```

---

#### Issue: Job not found after deployment
**Root Cause**: Job name changed or target mismatch

**Resolution**:
```bash
# List all deployed jobs
databricks jobs list --profile DEFAULT | grep "dev jesus_rodriguez"

# Check bundle resources
databricks bundle validate -t dev --profile DEFAULT
```

If job missing:
1. Verify `resources/jobs.yml` contains job definition
2. Check target selector in deployment
3. Redeploy: `databricks bundle deploy -t dev --profile DEFAULT`

---

### 7. Authentication & Permissions

#### Issue: Permission denied on tables/checkpoints
**Error Message**:
```
PERMISSION_DENIED: User does not have permission to access table
```

**Root Cause**: Missing Unity Catalog permissions

**Resolution**:
```sql
-- Grant necessary permissions
GRANT SELECT ON TABLE jmr_demo.zerobus.otel_spans TO `<user_or_service_principal>`;
GRANT MODIFY ON TABLE jmr_demo.zerobus.traces_silver TO `<user_or_service_principal>`;
GRANT ALL PRIVILEGES ON SCHEMA jmr_demo.zerobus TO `<user_or_service_principal>`;
```

For checkpoint directories:
```bash
# Ensure service principal has write access to DBFS
# Contact Databricks admin to grant storage credentials
```

---

#### Issue: Scheduled job runs fail but manual runs succeed
**Root Cause**: Different execution identity for scheduled vs manual

**Resolution**:
1. Check job owner:
   - Scheduled runs use job owner's identity
   - Manual runs use your identity
2. Verify job owner has necessary permissions
3. Consider using service principal for jobs:
   ```yaml
   run_as:
     service_principal_name: "<service_principal>"
   ```

---

## Debugging Techniques

### Enable Debug Logging
Add to notebook:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
logger.debug("Debug message here")
```

### Query Job Run Details
```bash
# Get detailed run info
databricks jobs runs get --run-id <run_id> --profile DEFAULT

# Get task output
databricks jobs runs get-output --run-id <run_id> --profile DEFAULT
```

### Inspect Streaming State
```python
# Check streaming query status
for query in spark.streams.active:
    print(f"Query: {query.name}")
    print(f"Status: {query.status}")
    print(f"Recent Progress: {query.recentProgress}")
```

### Delta Table History
```sql
-- View table changes
DESCRIBE HISTORY jmr_demo.zerobus.traces_silver LIMIT 20;

-- Time travel to previous version
SELECT * FROM jmr_demo.zerobus.traces_silver VERSION AS OF 5;
```

---

## Escalation Path

1. **Check this guide**: Review common issues above
2. **Check logs**: Databricks job run logs for detailed errors
3. **Query validation tables**: Data quality results may indicate issue
4. **Review recent changes**: Git history for recent deployments
5. **Contact team lead**: If issue persists or impacts production
6. **Databricks support**: For platform-level issues

---

## Useful Queries

### Pipeline Health Dashboard
```sql
-- Overall pipeline status
SELECT 
  'Silver Tables' as layer,
  COUNT(*) as table_count,
  SUM(CASE WHEN latest_record_age_minutes < 10 THEN 1 ELSE 0 END) as healthy_count
FROM (
  SELECT 
    'traces_silver' as table_name,
    TIMESTAMPDIFF(MINUTE, MAX(start_timestamp), current_timestamp()) as latest_record_age_minutes
  FROM jmr_demo.zerobus.traces_silver
  UNION ALL
  SELECT 'logs_silver', TIMESTAMPDIFF(MINUTE, MAX(log_timestamp), current_timestamp())
  FROM jmr_demo.zerobus.logs_silver
  UNION ALL
  SELECT 'service_health_silver', TIMESTAMPDIFF(MINUTE, MAX(timestamp), current_timestamp())
  FROM jmr_demo.zerobus.service_health_silver
);
```

### Error Patterns
```sql
-- Top error patterns in logs
SELECT 
  severity,
  body LIKE '%error%' as has_error_keyword,
  COUNT(*) as log_count
FROM jmr_demo.zerobus.logs_silver
WHERE log_timestamp >= current_timestamp() - INTERVAL 1 HOUR
GROUP BY severity, has_error_keyword
ORDER BY log_count DESC;
```

### Service Health Snapshot
```sql
-- Current service health
SELECT 
  service_name,
  AVG(error_rate) as avg_error_rate,
  AVG(latency_p95_ms) as avg_p95_latency,
  SUM(request_count) as total_requests
FROM jmr_demo.zerobus.service_health_silver
WHERE timestamp >= current_timestamp() - INTERVAL 10 MINUTES
GROUP BY service_name
ORDER BY avg_error_rate DESC;
```
