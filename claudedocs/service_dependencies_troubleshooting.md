# Service Dependencies Troubleshooting Guide

## Problem
The `service_dependencies` table is not producing results (empty or zero rows).

## Root Cause Analysis

The `service_dependencies` function builds a service-to-service dependency graph by:
1. Finding spans with `parent_span_id` (child spans)
2. Self-joining to find the corresponding parent span
3. Extracting service names to create dependency edges

### Most Common Issues

#### 1. No Parent-Child Relationships in Data ⚠️ MOST COMMON
**Symptom**: All traces have `parent_span_id = NULL`

**Why this happens**:
- Traces contain only root spans (no nested service calls)
- Distributed tracing isn't capturing parent-child relationships
- The `parent_span_id` field isn't being populated from source data

**Diagnostic Query**:
```sql
-- Check parent_span_id population
SELECT
    COUNT(*) as total_traces,
    COUNT(CASE WHEN parent_span_id IS NOT NULL THEN 1 END) as traces_with_parent,
    COUNT(CASE WHEN parent_span_id IS NULL THEN 1 END) as root_traces,
    ROUND(COUNT(CASE WHEN parent_span_id IS NOT NULL THEN 1 END) * 100.0 / COUNT(*), 2) as pct_with_parent
FROM jmr_demo.zerobus_sdp.traces_silver
WHERE start_timestamp >= current_timestamp() - INTERVAL 7 DAYS;
```

**Expected**: `pct_with_parent` should be >0% (typically 40-80% for distributed systems)

**Solutions**:
- **If 0%**: Check upstream data ingestion - is `parent_span_id` being captured?
- **If low %**: This is expected for root spans, dependencies should still be detected from child spans
- **If >50%**: Data looks healthy, issue is elsewhere

#### 2. Time Window Too Narrow
**Previous**: 24 hours
**Updated**: 7 days ✅

The time window was extended from 24 hours to 7 days to ensure sufficient data for dependency detection.

#### 3. Join Condition Not Matching
**Symptom**: Traces have parent_span_id but self-join returns no results

**Why this happens**:
- Parent span not in the same trace_id
- Parent span outside the time window
- span_id format mismatch with parent_span_id

**Diagnostic Query**:
```sql
-- Check if parent-child matches exist
SELECT
    COUNT(*) as potential_dependencies
FROM jmr_demo.zerobus_sdp.traces_silver child
JOIN jmr_demo.zerobus_sdp.traces_silver parent
    ON child.parent_span_id = parent.span_id
    AND child.trace_id = parent.trace_id
WHERE child.start_timestamp >= current_timestamp() - INTERVAL 7 DAYS
  AND child.parent_span_id IS NOT NULL;
```

**Expected**: Should find matches if data is healthy

**Solutions**:
- If 0 matches: Check if parent spans are within the time window
- Verify span_id and parent_span_id formats match (both strings, same format)
- Check if parent and child spans are in the same trace_id

#### 4. No Data in Time Window
**Diagnostic Query**:
```sql
-- Check data availability
SELECT
    COUNT(*) as total_traces,
    MIN(start_timestamp) as earliest,
    MAX(start_timestamp) as latest,
    COUNT(DISTINCT service_name) as unique_services
FROM jmr_demo.zerobus_sdp.traces_silver
WHERE start_timestamp >= current_timestamp() - INTERVAL 7 DAYS;
```

**Expected**: Should see traces from multiple services

## Changes Applied

### File: `src/notebooks/dlt/gold_aggregations.py`

#### Change 1: Extended Time Window
```python
# Before: 24 hours
traces = dlt.read("traces_silver").filter(
    col("start_timestamp") >= current_timestamp() - expr("INTERVAL 24 HOURS")
)

# After: 7 days
traces = spark.read.table(f"{catalog_name}.{schema_name}.traces_silver").filter(
    col("start_timestamp") >= current_timestamp() - expr("INTERVAL 7 DAYS")
)
```

**Impact**: More data available for dependency detection

#### Change 2: Changed to Cross-Pipeline Read
```python
# Before: In-pipeline read (assumes traces_silver in same pipeline)
traces = dlt.read("traces_silver")

# After: Cross-pipeline read (traces_silver from silver pipeline)
traces = spark.read.table(f"{catalog_name}.{schema_name}.traces_silver")
```

**Impact**: Correctly references traces_silver from the silver streaming pipeline

#### Change 3: Added Documentation and Comments
Added comprehensive docstring explaining:
- What the function does
- Data requirements (parent_span_id must be populated)
- Troubleshooting steps if no results

#### Change 4: Code Clarity
Separated child span filtering from join for better readability:
```python
# Filter to only child spans first
child_spans = traces.filter(col("parent_span_id").isNotNull()).alias("child")

# Then join to find parents
dependencies = child_spans.join(traces.alias("parent"), ...)
```

## Validation Steps

### Step 1: Run Diagnostic Queries
Execute the queries in `claudedocs/service_dependencies_debug.sql` to identify the issue.

### Step 2: Check Data Quality
```sql
-- Sample parent-child relationships
SELECT
    parent.service_name as source_service,
    child.service_name as target_service,
    child.trace_id,
    COUNT(*) as span_count
FROM jmr_demo.zerobus_sdp.traces_silver child
JOIN jmr_demo.zerobus_sdp.traces_silver parent
    ON child.parent_span_id = parent.span_id
    AND child.trace_id = parent.trace_id
WHERE child.start_timestamp >= current_timestamp() - INTERVAL 7 DAYS
  AND child.parent_span_id IS NOT NULL
GROUP BY 1, 2, 3
LIMIT 20;
```

### Step 3: Re-run Pipeline
```bash
databricks pipelines update --pipeline-id <gold_pipeline_id>
```

### Step 4: Verify Results
```sql
SELECT
    source_service,
    target_service,
    call_count,
    unique_traces
FROM jmr_demo.zerobus_sdp.service_dependencies
ORDER BY call_count DESC
LIMIT 20;
```

## Alternative Approaches (If Still No Results)

### Option 1: Loosen Join Condition
If parent spans are in a different time window:
```python
# Read more data for parent lookup
parent_traces = spark.read.table(...).filter(
    col("start_timestamp") >= current_timestamp() - expr("INTERVAL 30 DAYS")
)

child_spans = spark.read.table(...).filter(
    col("start_timestamp") >= current_timestamp() - expr("INTERVAL 7 DAYS")
).filter(col("parent_span_id").isNotNull())

# Join with extended parent data
dependencies = child_spans.join(
    parent_traces.alias("parent"),
    ...
)
```

### Option 2: Use Service Name in Traces
If parent_span_id isn't available but traces have service metadata:
```python
# Infer dependencies from trace structure
dependencies = (
    traces
    .groupBy("trace_id")
    .agg(collect_set("service_name").alias("services"))
    .filter(size("services") > 1)  # Multi-service traces
    # ... expand services array to create edges
)
```

### Option 3: Use Network-Based Dependencies
If you have network/HTTP metadata:
```python
# Use HTTP request metadata
dependencies = (
    traces
    .filter(col("http_target_service").isNotNull())
    .groupBy(col("service_name"), col("http_target_service"))
    .agg(count("*").alias("call_count"))
)
```

## Expected Outcomes After Fix

### Healthy Dependency Graph
```
source_service   | target_service | call_count | unique_traces
-----------------|----------------|------------|---------------
api-gateway      | auth-service   | 1,234      | 567
api-gateway      | user-service   | 890        | 432
auth-service     | database       | 2,345      | 567
user-service     | cache          | 445        | 234
```

### Dependency Metrics
- **Total edges**: 5-20 (depending on microservices count)
- **Call counts**: Should reflect actual traffic patterns
- **Unique traces**: Should be reasonable subset of total traces

## Further Investigation

If the issue persists after these changes:

1. **Check silver layer transformation** (`silver_transformations.py`)
   - Is `parent_span_id` being extracted correctly?
   - Are trace relationships preserved?

2. **Check bronze/source data**
   - Does the source telemetry include parent-child relationships?
   - Are OpenTelemetry spans properly nested?

3. **Check tracing instrumentation**
   - Is distributed tracing properly configured?
   - Are service-to-service calls being traced?

## Contact Points

- **Data Quality Issues**: Check with data engineering team about trace ingestion
- **Instrumentation Issues**: Check with platform team about OpenTelemetry configuration
- **Pipeline Issues**: Review DLT pipeline logs for errors or warnings
