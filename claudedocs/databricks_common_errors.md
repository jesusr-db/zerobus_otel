# Databricks Common Errors and Solutions

Comprehensive reference of error patterns, diagnostic commands, and solutions for ZeroBus-1 Databricks implementation.

## Table of Contents
1. [Table Access Errors](#table-access-errors)
2. [Streaming & Checkpoint Errors](#streaming--checkpoint-errors)
3. [Schema Errors](#schema-errors)
4. [Aggregation & Calculation Errors](#aggregation--calculation-errors)
5. [Data Quality Errors](#data-quality-errors)
6. [Performance Errors](#performance-errors)
7. [Deployment Errors](#deployment-errors)
8. [Authentication & Permission Errors](#authentication--permission-errors)

---

## Table Access Errors

### Error: TABLE_OR_VIEW_NOT_FOUND

**Pattern**: `The table or view 'catalog.schema.table' cannot be found`

**Common Variations**:
- `The table or view 'jmr_demo.zerobus.otel_spans' cannot be found`
- `Table or view not found: catalog.schema.table`

**Diagnostic Commands**:
```bash
# Check if table exists
databricks sql --query "SHOW TABLES IN catalog.schema LIKE 'table_name'"

# List all tables in schema
databricks sql --query "SHOW TABLES IN catalog.schema"

# Verify catalog and schema exist
databricks api GET /api/2.1/unity-catalog/schemas?catalog_name=catalog

# Check table via Unity Catalog API
databricks api GET /api/2.1/unity-catalog/tables/catalog.schema.table
```

**Common Causes**:
1. Table not created yet (pipeline hasn't run)
2. Catalog/schema name mismatch in configuration
3. Bronze tables not published by DLT pipeline
4. Incorrect target environment variables
5. Insufficient permissions to view table

**Solutions**:

**Solution 1: Verify DLT Pipeline Published Tables**
```bash
# Check DLT pipeline status
PIPELINE_ID=$(databricks pipelines list --output json | \
  jq -r '.statuses[] | select(.name | contains("bronze")) | .pipeline_id')

databricks pipelines get --pipeline-id $PIPELINE_ID --output json | \
  jq '{state: .state, latest_update: .latest_updates[0].state}'

# Verify bronze tables exist
databricks sql --query "SHOW TABLES IN jmr_demo.zerobus LIKE 'otel_%'"
```

**Solution 2: Check Configuration Variables**
```bash
# Verify databricks.yml variables
grep -A 5 "variables:" databricks.yml

# Common variables to check:
# - bronze_catalog
# - bronze_schema
# - silver_catalog
# - silver_schema
```

**Solution 3: Redeploy Bundle**
```bash
# Validate bundle configuration
databricks bundle validate -t dev --profile DEFAULT

# Deploy bundle
databricks bundle deploy -t dev --profile DEFAULT
```

**Solution 4: Check Permissions**
```bash
# Check table grants
databricks api GET /api/2.1/unity-catalog/permissions/table/catalog.schema.table

# Grant SELECT if needed (as admin)
databricks sql --query "GRANT SELECT ON TABLE catalog.schema.table TO \`user@example.com\`"
```

---

## Streaming & Checkpoint Errors

### Error: STREAM_FAILED (Checkpoint Corruption)

**Pattern**: `Failed to read checkpoint from /checkpoint/path`

**Common Variations**:
- `Failed to read checkpoint from dbfs:/checkpoint/silver/traces`
- `Checkpoint is corrupted`
- `Unable to find checkpoint file`

**Diagnostic Commands**:
```bash
# Check checkpoint location exists
databricks fs ls dbfs:/checkpoint/silver/traces/

# List commits directory
databricks fs ls dbfs:/checkpoint/silver/traces/commits/

# Check for offsets
databricks fs ls dbfs:/checkpoint/silver/traces/offsets/

# Read metadata
databricks fs cat dbfs:/checkpoint/silver/traces/metadata 2>&1

# Count checkpoint files
databricks fs ls -r dbfs:/checkpoint/silver/traces/ | wc -l
```

**Common Causes**:
1. Checkpoint directory corrupted (interrupted write)
2. Schema incompatible with existing checkpoint
3. Checkpoint format version mismatch
4. Concurrent writes to checkpoint (multiple streaming queries)
5. Filesystem issues (DBFS connectivity)

**Solutions**:

**Solution 1: Delete Checkpoint (Reprocess All Data)**
```bash
# WARNING: This will cause full reprocessing of streaming data
# Back up checkpoint first if possible
databricks fs cp -r dbfs:/checkpoint/silver/traces/ dbfs:/checkpoint/backup/traces_$(date +%Y%m%d)/

# Delete corrupted checkpoint
databricks fs rm -r dbfs:/checkpoint/silver/traces/

# Restart streaming job
JOB_ID=$(databricks jobs list --output json | \
  jq -r '.jobs[] | select(.settings.name | contains("silver")) | .job_id')
databricks jobs run-now --job-id $JOB_ID
```

**Solution 2: Remove Corrupt Commits Only**
```bash
# List recent commits
databricks fs ls dbfs:/checkpoint/silver/traces/commits/ | tail -10

# Identify and remove corrupt commit file
# (Usually the most recent one if job interrupted)
databricks fs rm dbfs:/checkpoint/silver/traces/commits/12345
```

**Solution 3: Schema Evolution Fix**
```python
# In streaming notebook, enable schema evolution
df = spark.readStream \
  .format("delta") \
  .option("mergeSchema", "true") \
  .table("catalog.schema.source_table")
```

**Post-Resolution Checks**:
```sql
-- Monitor for duplicates after reprocessing
SELECT
  span_id,
  COUNT(*) as count
FROM catalog.schema.traces_silver
GROUP BY span_id
HAVING COUNT(*) > 1
LIMIT 10;
```

---

## Schema Errors

### Error: UNRESOLVED_COLUMN

**Pattern**: `A column, variable, or function parameter with name 'column_name' cannot be resolved`

**Common Variations**:
- `A column, variable, or function parameter with name 'http_status_code' cannot be resolved`
- `Cannot resolve column name 'attribute_name' among (list_of_columns)`

**Diagnostic Commands**:
```bash
# Check current table schema
databricks sql --query "DESCRIBE catalog.schema.table"

# Get detailed schema
databricks sql --query "DESCRIBE EXTENDED catalog.schema.table"

# Compare schemas between tables
databricks api GET /api/2.1/unity-catalog/tables/catalog.schema.source_table | \
  jq '.columns[].name' | sort > source_cols.txt
databricks api GET /api/2.1/unity-catalog/tables/catalog.schema.target_table | \
  jq '.columns[].name' | sort > target_cols.txt
diff source_cols.txt target_cols.txt
```

**Common Causes**:
1. Bronze schema evolved but transformation code not updated
2. Column name typo in transformation logic
3. Nested column path incorrect (e.g., `Attributes.http.status_code`)
4. Column removed from upstream source
5. Case sensitivity mismatch

**Solutions**:

**Solution 1: Add Null Handling for Optional Columns**
```python
# Update transformation to handle missing columns gracefully
from pyspark.sql.functions import col, when, lit

df = df.withColumn("http_status_code",
    when(col("Attributes.http.status_code").isNotNull(),
         col("Attributes.http.status_code"))
    .otherwise(lit(None).cast("integer"))
)
```

**Solution 2: Enable Schema Evolution**
```python
# In streaming read
df = spark.readStream \
  .format("delta") \
  .option("mergeSchema", "true") \
  .table("source_table")

# In streaming write
query = df.writeStream \
  .format("delta") \
  .option("mergeSchema", "true") \
  .option("checkpointLocation", checkpoint_path) \
  .table("target_table")
```

**Solution 3: Fix Nested Column Path**
```bash
# Inspect nested structure
databricks sql --query "SELECT Attributes.* FROM catalog.schema.table LIMIT 1"

# Update code to use correct path
# Wrong: col("Attributes.http.status_code")
# Right:  col("Attributes")["http.status_code"]
# Or:     col("Attributes.`http.status_code`")
```

**Solution 4: Schema Validation Query**
```sql
-- Check if column exists before transformation
DESCRIBE catalog.schema.source_table;

-- Test column access
SELECT http_status_code
FROM catalog.schema.source_table
LIMIT 1;
```

### Error: SCHEMA_MISMATCH

**Pattern**: `Schema mismatch detected between source and target`

**Diagnostic Commands**:
```bash
# Get full schema comparison
diff <(databricks sql --query "DESCRIBE source_table" | sort) \
     <(databricks sql --query "DESCRIBE target_table" | sort)

# Check data types
databricks sql --query "SELECT column_name, data_type
  FROM information_schema.columns
  WHERE table_catalog='catalog' AND table_schema='schema' AND table_name='table'
  ORDER BY ordinal_position"
```

**Solutions**:
```python
# Cast incompatible types
df = df.withColumn("timestamp_col", col("timestamp_col").cast("timestamp"))

# Add missing columns
df = df.withColumn("new_column", lit(None).cast("string"))

# Remove extra columns
df = df.select("col1", "col2", "col3")  # Only keep needed columns
```

---

## Aggregation & Calculation Errors

### Error: DIVIDE_BY_ZERO

**Pattern**: `Division by zero`

**Common Variations**:
- `divide by zero`
- `ArithmeticException: / by zero`

**Diagnostic Commands**:
```bash
# Check for zero values in denominator column
databricks sql --query "SELECT
  COUNT(*) as total_rows,
  SUM(CASE WHEN denominator_col = 0 THEN 1 ELSE 0 END) as zero_count
FROM catalog.schema.table"

# Find specific zero cases
databricks sql --query "SELECT *
FROM catalog.schema.table
WHERE denominator_col = 0 OR denominator_col IS NULL
LIMIT 10"
```

**Common Causes**:
1. Service with zero requests in time window
2. No data in lookback window for baseline calculation
3. Edge cases not handled (new services, cold start)
4. Aggregation over empty dataset

**Solutions**:

**Solution 1: Safe Division with NULL Handling**
```python
from pyspark.sql.functions import col, when, lit

# Safe error rate calculation
df = df.withColumn("error_rate",
    when(col("request_count") > 0,
         col("error_count") / col("request_count"))
    .otherwise(lit(0.0))
)

# Alternative with coalesce
df = df.withColumn("error_rate",
    when((col("request_count").isNull()) | (col("request_count") == 0),
         lit(0.0))
    .otherwise(col("error_count") / col("request_count"))
)
```

**Solution 2: Validate Data Availability**
```sql
-- Check if data exists in lookback window
SELECT MIN(timestamp), MAX(timestamp), COUNT(*)
FROM catalog.schema.service_health_silver
WHERE timestamp >= current_timestamp() - INTERVAL 7 DAYS;
```

**Solution 3: Add Null Handling in Aggregations**
```python
# Safe standard deviation
df = df.withColumn("error_rate_stddev",
    when(col("request_count") > 0, stddev("error_rate"))
    .otherwise(lit(0.0))
)

# Safe average with minimum threshold
df = df.withColumn("avg_latency",
    when(col("sample_count") >= 10, avg("latency_ms"))
    .otherwise(lit(None))
)
```

### Error: NULL_VALUE in Non-Nullable Column

**Pattern**: `Cannot write nullable values to non-null column`

**Diagnostic Commands**:
```bash
# Check schema nullability
databricks api GET /api/2.1/unity-catalog/tables/catalog.schema.table | \
  jq '.columns[] | select(.nullable==false) | {name: .name, nullable: .nullable}'

# Find null values
databricks sql --query "SELECT
  SUM(CASE WHEN col1 IS NULL THEN 1 ELSE 0 END) as col1_nulls,
  SUM(CASE WHEN col2 IS NULL THEN 1 ELSE 0 END) as col2_nulls,
  COUNT(*) as total
FROM catalog.schema.table"
```

**Solutions**:
```python
# Fill nulls with defaults
df = df.fillna({
    "request_count": 0,
    "error_rate": 0.0,
    "service_name": "unknown"
})

# Or use coalesce
df = df.withColumn("request_count", coalesce(col("request_count"), lit(0)))

# Filter out null rows
df = df.filter(col("critical_column").isNotNull())
```

---

## Data Quality Errors

### Error: Trace Completeness Below Threshold

**Pattern**: Data quality validation fails with "Trace completeness: 92% (threshold: 95%)"

**Diagnostic Commands**:
```bash
# Identify orphaned spans
databricks sql --query "
WITH orphaned AS (
  SELECT child.span_id, child.parent_span_id, child.trace_id, child.service_name
  FROM catalog.schema.traces_silver child
  LEFT ANTI JOIN catalog.schema.traces_silver parent
    ON child.parent_span_id = parent.span_id
    AND child.trace_id = parent.trace_id
  WHERE child.parent_span_id IS NOT NULL
)
SELECT service_name, COUNT(*) as orphaned_count
FROM orphaned
GROUP BY service_name
ORDER BY orphaned_count DESC"
```

**Common Causes**:
1. **Sampling at source**: Parent span sampled out, child span kept
2. **Clock skew**: Parent span outside retention window
3. **Collection lag**: Parent span not yet ingested
4. **Network issues**: Incomplete trace collection

**Solutions**:

**Solution 1: Increase Retention Window**
```python
# In DLT pipeline, increase watermark
df = df.withWatermark("timestamp", "10 minutes")  # Increased from 5 minutes
```

**Solution 2: Align Sampling Decisions**
```yaml
# In OTEL collector config
processors:
  probabilistic_sampler:
    sampling_percentage: 10
    hash_seed: 22  # Ensure consistent sampling across services
```

**Solution 3: Add Grace Period for Late-Arriving Data**
```python
# Allow late data up to 30 minutes
df = df.withWatermark("timestamp", "30 minutes")
```

### Error: Cross-Signal Correlation Below Threshold

**Pattern**: Data quality validation fails with "Cross-signal correlation: 75% (threshold: 80%)"

**Diagnostic Commands**:
```bash
# Check trace_id presence in logs
databricks sql --query "SELECT
  COUNT(*) as total_logs,
  SUM(CASE WHEN trace_id IS NOT NULL THEN 1 ELSE 0 END) as logs_with_trace_id,
  (SUM(CASE WHEN trace_id IS NOT NULL THEN 1 ELSE 0 END) * 100.0 / COUNT(*)) as percentage
FROM catalog.schema.logs_silver"

# Check trace_id format validity
databricks sql --query "SELECT
  trace_id,
  LENGTH(trace_id) as trace_id_length,
  COUNT(*) as count
FROM catalog.schema.logs_silver
WHERE trace_id IS NOT NULL
GROUP BY trace_id, LENGTH(trace_id)
ORDER BY count DESC
LIMIT 10"
```

**Solutions**:

**Solution 1: Fix Log Enrichment**
```python
# In log processing notebook
# Extract trace_id from log attributes
df = df.withColumn("trace_id",
    when(col("Attributes.trace_id").isNotNull(),
         col("Attributes.trace_id"))
    .when(col("Resource.trace_id").isNotNull(),
         col("Resource.trace_id"))
    .otherwise(lit(None))
)
```

**Solution 2: Verify OTEL SDK Configuration**
```yaml
# In application OTEL config, ensure trace context in logs
resource:
  attributes:
    service.name: my-service
log_record_processor:
  - type: batch
    exporter: otlp
    inject_trace_context: true  # Ensure this is enabled
```

### Error: Service Health Quality Below Threshold

**Pattern**: Data quality validation fails with "Service health quality: 97% (threshold: 99%)"

**Diagnostic Commands**:
```bash
# Identify problematic records
databricks sql --query "SELECT
  service_name,
  error_rate,
  latency_p95_ms,
  request_count,
  timestamp
FROM catalog.schema.service_health_silver
WHERE error_rate IS NULL
   OR error_rate < 0
   OR error_rate > 1
   OR latency_p95_ms IS NULL
   OR latency_p95_ms < 0
   OR request_count IS NULL
   OR request_count < 0
LIMIT 100"
```

**Solutions**:

**Solution 1: Safe Metric Calculation**
```python
# Safe error rate
df = df.withColumn("error_rate",
    when((col("request_count").isNull()) | (col("request_count") == 0),
         lit(0.0))
    .when(col("error_count") > col("request_count"),
         lit(1.0))  # Cap at 100%
    .otherwise(col("error_count") / col("request_count"))
)

# Ensure latency is positive
df = df.withColumn("latency_p95_ms",
    when(col("latency_p95_ms") < 0, lit(0.0))
    .otherwise(col("latency_p95_ms"))
)

# Ensure counts are non-negative
df = df.withColumn("request_count",
    when(col("request_count") < 0, lit(0))
    .otherwise(col("request_count"))
)
```

---

## Performance Errors

### Error: Container Killed for Exceeding Memory

**Pattern**: `Container killed by YARN for exceeding memory limits`

**Common Variations**:
- `ExecutorLostFailure: Container killed by YARN`
- `OutOfMemoryError: Java heap space`

**Diagnostic Commands**:
```bash
# Check cluster configuration
CLUSTER_ID=$(databricks jobs runs get --run-id $RUN_ID --output json | \
  jq -r '.cluster_instance.cluster_id')
databricks clusters get --cluster-id $CLUSTER_ID --output json | \
  jq '{node_type: .node_type_id, num_workers: .num_workers, spark_conf: .spark_conf}'

# Check data cardinality
databricks sql --query "SELECT
  COUNT(DISTINCT service_name) as unique_services,
  COUNT(DISTINCT trace_id) as unique_traces,
  COUNT(*) as total_rows
FROM catalog.schema.traces_silver"

# Check state size for streaming queries
databricks sql --query "SELECT
  COUNT(*) as state_rows,
  SUM(LENGTH(TO_JSON(struct(*)))) as approx_state_bytes
FROM catalog.schema.stateful_table"
```

**Common Causes**:
1. High cardinality aggregations (millions of groups)
2. Large streaming state (wide watermark window)
3. Insufficient cluster resources
4. Memory-intensive operations (collect, large joins)

**Solutions**:

**Solution 1: Use Approximate Aggregations**
```python
from pyspark.sql.functions import approx_count_distinct

# Replace exact distinct count with approximation
df = df.groupBy("service_name") \
  .agg(approx_count_distinct("trace_id", rsd=0.05).alias("trace_count"))
```

**Solution 2: Reduce Watermark/Window**
```python
# Reduce watermark to limit state size
df = df.withWatermark("timestamp", "2 minutes")  # Down from 5 minutes

# Reduce window size
df = df.groupBy(
  window("timestamp", "1 minute")  # Down from 5 minutes
).agg(...)
```

**Solution 3: Increase Cluster Resources**
```yaml
# In resources/jobs.yml
new_cluster:
  node_type_id: "i3.2xlarge"  # Upgraded from i3.xlarge
  num_workers: 4  # Increased from 2
  spark_conf:
    "spark.executor.memory": "8g"
    "spark.driver.memory": "4g"
```

**Solution 4: Optimize Shuffles**
```python
# Increase shuffle partitions for large data
spark.conf.set("spark.sql.shuffle.partitions", "200")

# Or adaptive query execution (auto-tunes)
spark.conf.set("spark.sql.adaptive.enabled", "true")
```

### Error: Job Timeout

**Pattern**: `Job timed out after X seconds`

**Diagnostic Commands**:
```bash
# Check recent job durations
databricks jobs runs list --job-id $JOB_ID --limit 10 --output json | \
  jq '.runs[] | {
    run_id: .run_id,
    duration_seconds: ((.end_time // now) - .start_time) / 1000,
    state: .state.result_state
  }'

# Check data volume trends
databricks sql --query "SELECT
  DATE_TRUNC('hour', start_timestamp) as hour,
  COUNT(*) as span_count,
  (COUNT(*) * 100.0 / LAG(COUNT(*)) OVER (ORDER BY DATE_TRUNC('hour', start_timestamp))) as pct_change
FROM catalog.schema.traces_silver
WHERE start_timestamp >= current_timestamp() - INTERVAL 24 HOURS
GROUP BY hour
ORDER BY hour DESC"
```

**Solutions**:

**Solution 1: Increase Timeout**
```yaml
# In resources/jobs.yml
tasks:
  - task_key: silver_transformations
    timeout_seconds: 7200  # Increased from 3600
```

**Solution 2: Reduce Batch Size**
```python
# Process fewer files per trigger
df = spark.readStream \
  .option("maxFilesPerTrigger", 50) \  # Reduced from 100
  .table("source_table")
```

**Solution 3: Optimize Table**
```sql
-- Compact small files
OPTIMIZE catalog.schema.traces_silver;

-- Add Z-ORDER for common filters
OPTIMIZE catalog.schema.traces_silver
ZORDER BY (service_name, start_timestamp);

-- Enable auto-optimize
ALTER TABLE catalog.schema.traces_silver
SET TBLPROPERTIES (
  'delta.autoOptimize.optimizeWrite' = 'true',
  'delta.autoOptimize.autoCompact' = 'true'
);
```

---

## Deployment Errors

### Error: Bundle Validation Failed

**Pattern**: `Error: invalid configuration: <validation error>`

**Diagnostic Commands**:
```bash
# Validate YAML syntax
yamllint databricks.yml resources/*.yml

# Validate bundle
databricks bundle validate -t dev --profile DEFAULT

# Check for common issues
grep -n "^    " databricks.yml  # Find 4-space indents (should be 2)
```

**Common Causes**:
1. YAML syntax error (indentation, missing colons)
2. Invalid cron expression
3. Missing required fields
4. Invalid resource references
5. Duplicate resource names

**Solutions**:

**Solution 1: Fix Indentation**
```yaml
# Wrong (4 spaces)
resources:
    jobs:
        my_job:

# Right (2 spaces)
resources:
  jobs:
    my_job:
```

**Solution 2: Validate Cron Expression**
```bash
# Test cron expression
# Format: "0 0 * * * ?" = Daily at midnight UTC
# Use: https://crontab.guru/ for validation
```

**Solution 3: Check Required Fields**
```yaml
# Ensure all required fields present
resources:
  jobs:
    my_job:
      name: "${bundle.target}-${bundle.git.origin_url}-my_job"  # Required
      tasks:  # Required
        - task_key: task1  # Required
          notebook_task:  # Required
            notebook_path: /path  # Required
```

### Error: Job Not Found After Deployment

**Pattern**: Job runs successfully in bundle deploy but not visible in workspace

**Diagnostic Commands**:
```bash
# List jobs with filter
databricks jobs list --output json | \
  jq '.jobs[] | select(.settings.name | contains("dev"))'

# Check bundle resources
databricks bundle validate -t dev --profile DEFAULT

# Get bundle summary
databricks bundle summary -t dev --profile DEFAULT
```

**Solutions**:

**Solution 1: Check Target Selector**
```yaml
# In databricks.yml
targets:
  dev:
    mode: development
    default: true
    workspace:
      host: "https://your-workspace.cloud.databricks.com"
```

**Solution 2: Verify Job Name Pattern**
```bash
# Jobs are prefixed with target name
# Look for: "dev_jesus_rodriguez_job_name"
databricks jobs list | grep "dev_${USER}"
```

**Solution 3: Redeploy Bundle**
```bash
# Clean deploy
databricks bundle destroy -t dev --profile DEFAULT
databricks bundle deploy -t dev --profile DEFAULT
```

---

## Authentication & Permission Errors

### Error: PERMISSION_DENIED on Table

**Pattern**: `PERMISSION_DENIED: User does not have permission to access table`

**Common Variations**:
- `Permission denied on table 'catalog.schema.table'`
- `User does not have SELECT privilege on table`

**Diagnostic Commands**:
```bash
# Check current user
databricks api GET /api/2.0/preview/scim/v2/Me | \
  jq '{username: .userName, groups: [.groups[].display]}'

# Check table permissions
databricks api GET /api/2.1/unity-catalog/permissions/table/catalog.schema.table

# Check specific privilege
databricks api GET /api/2.1/unity-catalog/permissions/table/catalog.schema.table | \
  jq '.privilege_assignments[] | select(.privileges[] | contains("SELECT"))'
```

**Solutions**:

**Solution 1: Grant Table Permissions (as admin)**
```sql
-- Grant SELECT
GRANT SELECT ON TABLE catalog.schema.table TO `user@example.com`;

-- Grant MODIFY for writes
GRANT MODIFY ON TABLE catalog.schema.table TO `user@example.com`;

-- Grant ALL PRIVILEGES
GRANT ALL PRIVILEGES ON TABLE catalog.schema.table TO `user@example.com`;
```

**Solution 2: Grant Schema-Level Permissions**
```sql
-- Grant schema access
GRANT USE SCHEMA ON SCHEMA catalog.schema TO `user@example.com`;
GRANT SELECT ON SCHEMA catalog.schema TO `user@example.com`;
GRANT ALL PRIVILEGES ON SCHEMA catalog.schema TO `user@example.com`;
```

**Solution 3: Grant Catalog-Level Permissions**
```sql
-- Grant catalog access
GRANT USE CATALOG ON CATALOG catalog TO `user@example.com`;
GRANT USE SCHEMA ON CATALOG catalog TO `user@example.com`;
```

**Solution 4: Use Service Principal**
```yaml
# In resources/jobs.yml
jobs:
  my_job:
    run_as:
      service_principal_name: "my-service-principal"
```

### Error: Scheduled Job Fails But Manual Succeeds

**Pattern**: Scheduled job runs fail with permission errors, but manual runs with "Run Now" succeed

**Diagnostic Commands**:
```bash
# Get job configuration
databricks jobs get --job-id $JOB_ID --output json | \
  jq '{run_as: .settings.run_as, owner: .creator_user_name}'

# Compare run identities
databricks jobs runs list --job-id $JOB_ID --output json | \
  jq '.runs[] | {run_id: .run_id, run_type: .run_type, user: .creator_user_name}'
```

**Common Causes**:
1. Scheduled runs use job owner's identity
2. Manual "Run Now" uses your identity
3. Job owner lacks necessary permissions
4. Service principal not configured

**Solutions**:

**Solution 1: Update Job Owner**
```yaml
# In resources/jobs.yml, specify run_as
jobs:
  my_job:
    run_as:
      user_name: "admin@example.com"  # User with all permissions
```

**Solution 2: Use Service Principal**
```yaml
# Recommended for production
jobs:
  my_job:
    run_as:
      service_principal_name: "databricks-service-principal"
```

**Solution 3: Grant Permissions to Job Owner**
```sql
-- As admin, grant permissions to job owner
GRANT ALL PRIVILEGES ON SCHEMA catalog.schema
TO `job-owner@example.com`;
```

---

## Error Pattern Quick Reference

| Error Code | Primary Cause | First Check |
|------------|--------------|-------------|
| TABLE_OR_VIEW_NOT_FOUND | Table missing or permissions | `SHOW TABLES IN catalog.schema` |
| STREAM_FAILED | Checkpoint corruption | `databricks fs ls dbfs:/checkpoint/` |
| UNRESOLVED_COLUMN | Schema mismatch | `DESCRIBE table` |
| DIVIDE_BY_ZERO | Missing null handling | Check for zero denominators |
| PERMISSION_DENIED | Missing grants | Check Unity Catalog permissions |
| Container killed (OOM) | Memory exhaustion | Check cardinality, reduce state |
| Job timeout | Data volume spike | Check recent data volumes |
| Bundle validation | YAML syntax error | `databricks bundle validate` |

---

## Debugging Workflow

1. **Capture Error Message**: Get full error text and stack trace
2. **Find Pattern**: Match against this document's error patterns
3. **Run Diagnostics**: Execute diagnostic commands for that error
4. **Apply Solution**: Choose appropriate solution based on root cause
5. **Validate**: Verify fix resolved the issue
6. **Document**: Add to project-specific troubleshooting notes

---

## Escalation Checklist

Before escalating issues:
- [ ] Error message captured completely
- [ ] Diagnostic commands executed and output saved
- [ ] Recent changes reviewed (git log, deployment history)
- [ ] Solutions from this guide attempted
- [ ] Data quality validation results checked
- [ ] Job run IDs and timestamps documented
- [ ] Configuration files reviewed for errors

---

## Additional Resources

- **CLI Reference**: `claudedocs/databricks_cli_reference.md`
- **Troubleshooting Workflows**: `claudedocs/databricks_troubleshooting_guide.md`
- **Project Troubleshooting**: `docs/TROUBLESHOOTING.md`
- **Databricks Documentation**: https://docs.databricks.com/
- **Unity Catalog Permissions**: https://docs.databricks.com/security/unity-catalog/
