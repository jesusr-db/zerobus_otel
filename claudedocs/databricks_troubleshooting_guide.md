# Databricks Systematic Troubleshooting Guide

Structured workflows for diagnosing and resolving Databricks issues across jobs, pipelines, tables, and data quality.

## Table of Contents
1. [General Troubleshooting Workflow](#general-troubleshooting-workflow)
2. [Job Failure Investigation](#job-failure-investigation)
3. [Pipeline Issues](#pipeline-issues)
4. [Schema Problems](#schema-problems)
5. [Data Quality Issues](#data-quality-issues)
6. [Performance Problems](#performance-problems)
7. [Authentication & Permissions](#authentication--permissions)

---

## General Troubleshooting Workflow

### Universal Diagnostic Pattern
```
Step 1: Identify Component
  └─ What's failing? (job, pipeline, table, query)
  └─ When did it start failing?
  └─ What changed recently?

Step 2: Gather Status
  └─ Current state of component
  └─ Recent execution history
  └─ Related component dependencies

Step 3: Extract Logs
  └─ Error messages and stack traces
  └─ Warning indicators
  └─ Event timeline

Step 4: Inspect Resources
  └─ Schema definitions
  └─ Configuration settings
  └─ Checkpoint/state data

Step 5: Analyze Patterns
  └─ Match against known errors
  └─ Identify root cause
  └─ Determine scope of impact

Step 6: Remediate
  └─ Propose solution
  └─ Test fix in isolation
  └─ Validate resolution
  └─ Document for future reference
```

### Quick Checklist
Before diving deep, check these common issues:
- [ ] Authentication working? (`databricks workspace ls /`)
- [ ] Target catalog/schema exists?
- [ ] Required tables present?
- [ ] Permissions granted?
- [ ] Recent config changes deployed?
- [ ] Upstream dependencies healthy?

---

## Job Failure Investigation

### Step 1: Identify the Job
```bash
# Search for job by name
databricks jobs list | grep "<job_name>"

# Get job ID
JOB_ID=$(databricks jobs list --output json | \
  jq -r '.jobs[] | select(.settings.name=="<job_name>") | .job_id')

echo "Job ID: $JOB_ID"
```

### Step 2: Review Recent Run History
```bash
# List last 10 runs
databricks jobs runs list --job-id $JOB_ID --limit 10

# Get detailed status
databricks jobs runs list --job-id $JOB_ID --limit 10 --output json | \
  jq '.runs[] | {run_id: .run_id, start: .start_time, state: .state.result_state, message: .state.state_message}'

# Identify failed runs
databricks jobs runs list --job-id $JOB_ID --limit 10 --output json | \
  jq '.runs[] | select(.state.result_state=="FAILED") | .run_id'
```

### Step 3: Extract Error Details
```bash
# Get most recent failed run
FAILED_RUN_ID=$(databricks jobs runs list --job-id $JOB_ID --limit 10 --output json | \
  jq -r '.runs[] | select(.state.result_state=="FAILED") | .run_id' | head -1)

echo "Investigating run: $FAILED_RUN_ID"

# Get run output with error message
databricks jobs runs get-output --run-id $FAILED_RUN_ID

# Extract just the error
databricks jobs runs get-output --run-id $FAILED_RUN_ID --output json | \
  jq -r '.error // "No error message available"'

# Get full run details
databricks jobs runs get --run-id $FAILED_RUN_ID --output json
```

### Step 4: Check Task-Level Failures
```bash
# For multi-task jobs, identify which task failed
databricks jobs runs get --run-id $FAILED_RUN_ID --output json | \
  jq '.tasks[] | {task_key: .task_key, state: .state.result_state, error: .state.state_message}'

# Get specific task output
databricks jobs runs get --run-id $FAILED_RUN_ID --output json | \
  jq '.tasks[] | select(.state.result_state=="FAILED")'
```

### Step 5: Review Job Configuration
```bash
# Get job settings
databricks jobs get --job-id $JOB_ID --output json | jq '.settings'

# Check schedule
databricks jobs get --job-id $JOB_ID --output json | jq '.settings.schedule'

# Review task definitions
databricks jobs get --job-id $JOB_ID --output json | jq '.settings.tasks'

# Check parameters
databricks jobs get --job-id $JOB_ID --output json | jq '.settings.parameters'
```

### Step 6: Common Job Issue Patterns

#### Timeout Issues
```bash
# Check run duration vs timeout
databricks jobs runs get --run-id $FAILED_RUN_ID --output json | \
  jq '{duration_seconds: (.end_time - .start_time) / 1000, timeout: .timeout_seconds}'
```

#### Dependency Failures
```bash
# Check if dependent tables exist
# Extract table references from error message, then:
databricks sql --query "SHOW TABLES IN catalog.schema LIKE 'table_pattern*'"
```

#### Cluster Issues
```bash
# Get cluster info from run
CLUSTER_ID=$(databricks jobs runs get --run-id $FAILED_RUN_ID --output json | \
  jq -r '.cluster_instance.cluster_id')

# Check cluster events
databricks clusters events --cluster-id $CLUSTER_ID --output json | \
  jq '.events[] | select(.type=="ERROR")'
```

---

## Pipeline Issues

### Step 1: Identify Pipeline
```bash
# Find pipeline by name
PIPELINE_ID=$(databricks pipelines list --output json | \
  jq -r '.statuses[] | select(.name=="<pipeline_name>") | .pipeline_id')

echo "Pipeline ID: $PIPELINE_ID"
```

### Step 2: Check Current State
```bash
# Get pipeline status
databricks pipelines get --pipeline-id $PIPELINE_ID --output json | \
  jq '{state: .state, health: .health, latest_updates: .latest_updates}'

# Check if pipeline is healthy
databricks pipelines get --pipeline-id $PIPELINE_ID --output json | \
  jq -r '.health // "UNKNOWN"'
```

### Step 3: Review Recent Updates
```bash
# Get last 5 updates
databricks pipelines list-updates --pipeline-id $PIPELINE_ID --max-results 5

# Identify failed updates
databricks pipelines list-updates --pipeline-id $PIPELINE_ID --output json | \
  jq '.updates[] | select(.state=="FAILED") | {update_id: .update_id, cause: .cause}'

# Get latest update details
LATEST_UPDATE=$(databricks pipelines list-updates --pipeline-id $PIPELINE_ID --max-results 1 --output json | \
  jq -r '.updates[0].update_id')

databricks pipelines get-update --pipeline-id $PIPELINE_ID --update-id $LATEST_UPDATE
```

### Step 4: Extract Event Logs
```bash
# Get all events
databricks api GET /api/2.0/pipelines/$PIPELINE_ID/events > pipeline_events.json

# Filter ERROR events
jq '.events[] | select(.level=="ERROR")' pipeline_events.json

# Get errors with full details
jq '.events[] | select(.level=="ERROR") | {
  timestamp: .timestamp,
  event_type: .event_type,
  message: .message,
  error: .error,
  origin: .origin
}' pipeline_events.json

# Get errors for specific dataset
jq --arg dataset "dataset_name" \
  '.events[] | select(.level=="ERROR" and .origin.dataset_name==$dataset)' \
  pipeline_events.json
```

### Step 5: Check Source Table Availability
```bash
# Extract source tables from pipeline config
databricks pipelines get --pipeline-id $PIPELINE_ID --output json | \
  jq '.spec.libraries[].notebook.path'

# Verify source tables exist
# (Extract table names from error messages or config, then:)
databricks sql --query "SELECT COUNT(*) FROM catalog.schema.source_table"
```

### Step 6: Verify Checkpoint Health
```bash
# Get checkpoint location from pipeline config
CHECKPOINT=$(databricks pipelines get --pipeline-id $PIPELINE_ID --output json | \
  jq -r '.spec.storage')

echo "Checkpoint location: $CHECKPOINT"

# Check checkpoint contents
databricks fs ls $CHECKPOINT

# Look for corruption indicators
databricks fs ls $CHECKPOINT/commits/ | tail -5

# Check metadata
databricks fs cat $CHECKPOINT/metadata 2>/dev/null || echo "No metadata file"
```

### Step 7: Common Pipeline Patterns

#### Streaming Source Issues
```bash
# Check for "no new data" warnings
jq '.events[] | select(.message | contains("no new data"))' pipeline_events.json

# Verify source table has recent data
databricks sql --query "SELECT MAX(timestamp_col) FROM source_table"
```

#### Schema Evolution Failures
```bash
# Check for schema mismatch errors
jq '.events[] | select(.message | contains("schema"))' pipeline_events.json

# Compare source and target schemas
databricks sql --query "DESCRIBE source_table" > source_schema.txt
databricks sql --query "DESCRIBE target_table" > target_schema.txt
diff source_schema.txt target_schema.txt
```

#### Expectation Failures
```bash
# Find expectation violations
jq '.events[] | select(.event_type=="flow_progress" and .details.flow_progress.data_quality_metrics)' \
  pipeline_events.json
```

---

## Schema Problems

### Step 1: Get Current Schema
```bash
# Via SQL
databricks sql --query "DESCRIBE EXTENDED catalog.schema.table"

# Via Unity Catalog API
databricks api GET /api/2.1/unity-catalog/tables/catalog.schema.table | \
  jq '.columns[] | {name: .name, type: .type_name, nullable: .nullable}'
```

### Step 2: Compare with Expected Schema
```bash
# Get schema from source
databricks sql --query "DESCRIBE source_table" > source.txt

# Get schema from target
databricks sql --query "DESCRIBE target_table" > target.txt

# Compare
diff source.txt target.txt
```

### Step 3: Identify Schema Issues

#### Missing Columns
```bash
# List column names only
databricks api GET /api/2.1/unity-catalog/tables/catalog.schema.table | \
  jq -r '.columns[].name' | sort

# Compare two tables
comm -3 \
  <(databricks api GET /api/2.1/unity-catalog/tables/catalog.schema.table1 | jq -r '.columns[].name' | sort) \
  <(databricks api GET /api/2.1/unity-catalog/tables/catalog.schema.table2 | jq -r '.columns[].name' | sort)
```

#### Type Mismatches
```bash
# Get column types
databricks sql --query "SELECT column_name, data_type FROM information_schema.columns
  WHERE table_catalog='catalog' AND table_schema='schema' AND table_name='table'"
```

#### Nullability Issues
```bash
# Check nullable columns
databricks api GET /api/2.1/unity-catalog/tables/catalog.schema.table | \
  jq '.columns[] | select(.nullable==false) | .name'

# Find null values in non-nullable columns
databricks sql --query "SELECT column_name, COUNT(*) as null_count
  FROM catalog.schema.table
  WHERE column_name IS NULL
  GROUP BY column_name"
```

### Step 4: Check Schema Evolution Settings
```bash
# Check table properties for schema evolution
databricks sql --query "SHOW TBLPROPERTIES catalog.schema.table" | \
  grep -i "schema"

# For Delta tables
databricks sql --query "DESCRIBE DETAIL catalog.schema.table" | \
  jq '{properties: .properties}'
```

### Step 5: Review Schema History
```bash
# For Delta tables, check history
databricks sql --query "DESCRIBE HISTORY catalog.schema.table LIMIT 20" | \
  grep -i "schema"

# Get specific version schema
databricks sql --query "DESCRIBE catalog.schema.table VERSION AS OF 5"
```

---

## Data Quality Issues

### Step 1: Check Table Existence and Accessibility
```bash
# Verify table exists
databricks sql --query "SHOW TABLES IN catalog.schema LIKE 'table_name'"

# Check permissions
databricks api GET /api/2.1/unity-catalog/tables/catalog.schema.table | \
  jq '{owner: .owner, created_by: .created_by}'

# Test read access
databricks sql --query "SELECT COUNT(*) FROM catalog.schema.table LIMIT 1"
```

### Step 2: Check Data Freshness
```bash
# Get latest timestamp
databricks sql --query "SELECT
  MAX(timestamp_column) as latest_record,
  COUNT(*) as total_records
FROM catalog.schema.table"

# Calculate staleness
databricks sql --query "SELECT
  TIMESTAMPDIFF(HOUR, MAX(timestamp_column), CURRENT_TIMESTAMP()) as hours_stale
FROM catalog.schema.table"

# Check for gaps in time series
databricks sql --query "SELECT
  DATE(timestamp_column) as date,
  COUNT(*) as records
FROM catalog.schema.table
WHERE timestamp_column >= CURRENT_DATE() - INTERVAL 7 DAYS
GROUP BY DATE(timestamp_column)
ORDER BY date"
```

### Step 3: Identify Null Patterns
```bash
# Count nulls per column
databricks sql --query "SELECT
  SUM(CASE WHEN col1 IS NULL THEN 1 ELSE 0 END) as col1_nulls,
  SUM(CASE WHEN col2 IS NULL THEN 1 ELSE 0 END) as col2_nulls,
  SUM(CASE WHEN col3 IS NULL THEN 1 ELSE 0 END) as col3_nulls,
  COUNT(*) as total_rows
FROM catalog.schema.table"

# Find rows with all nulls in key columns
databricks sql --query "SELECT COUNT(*) as empty_rows
FROM catalog.schema.table
WHERE col1 IS NULL AND col2 IS NULL AND col3 IS NULL"
```

### Step 4: Check for Duplicates
```bash
# Find duplicate keys
databricks sql --query "SELECT
  key_column,
  COUNT(*) as count
FROM catalog.schema.table
GROUP BY key_column
HAVING COUNT(*) > 1
ORDER BY count DESC
LIMIT 20"

# Count total duplicates
databricks sql --query "SELECT
  COUNT(*) - COUNT(DISTINCT key_column) as duplicate_count
FROM catalog.schema.table"
```

### Step 5: Validate Cross-Table Consistency
```bash
# Compare row counts between layers
databricks sql --query "
SELECT
  'bronze' as layer, COUNT(*) as rows FROM catalog.schema.bronze_table
UNION ALL
SELECT
  'silver' as layer, COUNT(*) as rows FROM catalog.schema.silver_table
UNION ALL
SELECT
  'gold' as layer, COUNT(*) as rows FROM catalog.schema.gold_table
"

# Check for orphaned records
databricks sql --query "SELECT COUNT(*) as orphaned_records
FROM catalog.schema.child_table c
LEFT JOIN catalog.schema.parent_table p ON c.parent_id = p.id
WHERE p.id IS NULL"
```

### Step 6: Statistical Validation
```bash
# Get basic statistics
databricks sql --query "SELECT
  MIN(numeric_col) as min_val,
  MAX(numeric_col) as max_val,
  AVG(numeric_col) as avg_val,
  STDDEV(numeric_col) as stddev_val
FROM catalog.schema.table"

# Find outliers
databricks sql --query "
WITH stats AS (
  SELECT
    AVG(value) as mean,
    STDDEV(value) as stddev
  FROM catalog.schema.table
)
SELECT COUNT(*) as outlier_count
FROM catalog.schema.table, stats
WHERE ABS(value - mean) > 3 * stddev
"
```

---

## Performance Problems

### Step 1: Identify Slow Operations
```bash
# Check job run durations
databricks jobs runs list --job-id $JOB_ID --limit 20 --output json | \
  jq '.runs[] | {
    run_id: .run_id,
    duration_minutes: ((.end_time // now) - .start_time) / 60000,
    state: .state.result_state
  }' | jq -s 'sort_by(.duration_minutes) | reverse'

# Get pipeline update durations
databricks pipelines list-updates --pipeline-id $PIPELINE_ID --output json | \
  jq '.updates[] | {
    update_id: .update_id,
    duration_seconds: (.update_info.end_time - .update_info.start_time) / 1000
  }'
```

### Step 2: Analyze Query Performance
```bash
# Use query profile (requires warehouse query history)
databricks sql --query "SELECT * FROM catalog.schema.table WHERE complex_condition" --profile

# Check table statistics
databricks sql --query "ANALYZE TABLE catalog.schema.table COMPUTE STATISTICS"

# Review table size
databricks sql --query "DESCRIBE DETAIL catalog.schema.table" | \
  jq '{name: .name, size_bytes: .sizeInBytes, num_files: .numFiles}'
```

### Step 3: Check Resource Utilization
```bash
# Get cluster metrics (if using dedicated cluster)
databricks clusters get --cluster-id $CLUSTER_ID --output json | \
  jq '{
    cluster_size: .num_workers,
    node_type: .node_type_id,
    autoscale: .autoscale
  }'

# Check warehouse size
databricks sql warehouses get --id $WAREHOUSE_ID --output json | \
  jq '{size: .warehouse_size, auto_stop: .auto_stop_mins}'
```

### Step 4: Identify Bottlenecks

#### Large Shuffle Operations
```bash
# Check for wide transformations in Spark
# Look for warnings about shuffle partitions in logs
databricks jobs runs get-output --run-id $RUN_ID --output json | \
  jq -r '.error' | grep -i "shuffle"
```

#### Skewed Data
```bash
# Check for data skew
databricks sql --query "SELECT
  partition_column,
  COUNT(*) as record_count
FROM catalog.schema.table
GROUP BY partition_column
ORDER BY record_count DESC
LIMIT 20"
```

#### File Proliferation
```bash
# Check number of files
databricks sql --query "DESCRIBE DETAIL catalog.schema.table" | \
  jq '{num_files: .numFiles, avg_file_size: (.sizeInBytes / .numFiles)}'

# Recommend OPTIMIZE if many small files
# avg_file_size < 128MB suggests need for compaction
```

### Step 5: Optimization Recommendations
```bash
# Check if table needs optimization
databricks sql --query "OPTIMIZE catalog.schema.table"

# Check if Z-ORDER would help
databricks sql --query "OPTIMIZE catalog.schema.table ZORDER BY (commonly_filtered_column)"

# Analyze partitioning strategy
databricks sql --query "SHOW PARTITIONS catalog.schema.table"
```

---

## Authentication & Permissions

### Step 1: Verify Credentials
```bash
# Test basic connectivity
databricks workspace ls /

# Get current user info
databricks api GET /api/2.0/preview/scim/v2/Me | \
  jq '{username: .userName, groups: [.groups[].display]}'
```

### Step 2: Check Table Permissions
```bash
# Get table grants
databricks api GET /api/2.1/unity-catalog/permissions/table/catalog.schema.table

# Check specific privilege
databricks api GET /api/2.1/unity-catalog/permissions/table/catalog.schema.table | \
  jq '.privilege_assignments[] | select(.privileges[] | contains("SELECT"))'
```

### Step 3: Check Schema/Catalog Permissions
```bash
# Schema permissions
databricks api GET /api/2.1/unity-catalog/permissions/schema/catalog.schema

# Catalog permissions
databricks api GET /api/2.1/unity-catalog/permissions/catalog/catalog
```

### Step 4: Verify Service Principal Permissions
```bash
# List service principals
databricks api GET /api/2.0/preview/scim/v2/ServicePrincipals

# Check specific SP permissions
databricks api GET /api/2.1/unity-catalog/permissions/table/catalog.schema.table | \
  jq --arg sp "service-principal-name" \
    '.privilege_assignments[] | select(.principal==$sp)'
```

---

## Troubleshooting Decision Tree

```
Issue Type?
├─ Job Failed
│  ├─ Timeout? → Increase timeout or optimize query
│  ├─ Table not found? → Check catalog/schema names, verify deployment
│  ├─ Permission denied? → Check grants and service principal permissions
│  └─ Task failed? → Investigate specific task logs
│
├─ Pipeline Error
│  ├─ Source unavailable? → Check upstream tables/streams
│  ├─ Schema mismatch? → Enable schema evolution or fix source
│  ├─ Checkpoint corrupt? → Delete and reprocess
│  └─ Expectation failed? → Review data quality rules
│
├─ Data Quality
│  ├─ No data? → Check source table, verify pipeline running
│  ├─ Stale data? → Check pipeline schedule, investigate failures
│  ├─ Duplicates? → Review deduplication logic, check for replay
│  └─ Nulls? → Validate source data, check transformations
│
├─ Performance
│  ├─ Slow query? → Check partitioning, run OPTIMIZE, review query plan
│  ├─ Pipeline lag? → Scale warehouse, optimize transformations
│  └─ High cost? → Right-size resources, enable autoscaling
│
└─ Permission
   ├─ Can't read table? → Grant SELECT
   ├─ Can't write table? → Grant MODIFY
   └─ Can't see catalog? → Grant USE CATALOG/SCHEMA
```

---

## Best Practices

### 1. Systematic Approach
- Always start with identifying the component and recent changes
- Gather logs before attempting fixes
- Document findings and solutions for future reference

### 2. Efficient Investigation
- Use JSON output with jq for structured parsing
- Save diagnostic output to files for comparison
- Chain commands with shell variables to reduce API calls

### 3. Safe Remediation
- Test fixes in development environment first
- Back up state (checkpoints, tables) before destructive operations
- Validate fixes with specific test cases
- Monitor after deployment to confirm resolution

### 4. Communication
- Provide specific error messages and run IDs when escalating
- Include relevant configuration snippets
- Document reproduction steps
- Share diagnostic command output
