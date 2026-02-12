-- Service Dependencies Debug Queries
-- Run these to diagnose why service_dependencies is empty

-- 1. Check if traces_silver has data in the last 7 days
SELECT
    COUNT(*) as total_traces,
    MIN(start_timestamp) as earliest_trace,
    MAX(start_timestamp) as latest_trace,
    COUNT(DISTINCT service_name) as unique_services
FROM jmr_demo.zerobus_sdp.traces_silver
WHERE start_timestamp >= current_timestamp() - INTERVAL 7 DAYS;
-- Expected: Should see traces with multiple services

-- 2. Check if traces have parent_span_id (critical for dependencies)
SELECT
    COUNT(*) as total_traces,
    COUNT(CASE WHEN parent_span_id IS NOT NULL THEN 1 END) as traces_with_parent,
    COUNT(CASE WHEN parent_span_id IS NULL THEN 1 END) as root_traces,
    ROUND(COUNT(CASE WHEN parent_span_id IS NOT NULL THEN 1 END) * 100.0 / COUNT(*), 2) as pct_with_parent
FROM jmr_demo.zerobus_sdp.traces_silver
WHERE start_timestamp >= current_timestamp() - INTERVAL 7 DAYS;
-- Expected: At least some traces with parent_span_id (>0%)

-- 3. Check if parent-child relationships exist within same trace
SELECT
    COUNT(*) as potential_dependencies
FROM jmr_demo.zerobus_sdp.traces_silver child
JOIN jmr_demo.zerobus_sdp.traces_silver parent
    ON child.parent_span_id = parent.span_id
    AND child.trace_id = parent.trace_id
WHERE child.start_timestamp >= current_timestamp() - INTERVAL 7 DAYS
  AND child.parent_span_id IS NOT NULL;
-- Expected: Should find matching parent-child pairs

-- 4. Sample parent-child relationships to verify data quality
SELECT
    parent.service_name as source_service,
    child.service_name as target_service,
    child.trace_id,
    parent.span_id as parent_span_id,
    child.parent_span_id as child_parent_span_id,
    parent.start_timestamp as parent_time,
    child.start_timestamp as child_time
FROM jmr_demo.zerobus_sdp.traces_silver child
JOIN jmr_demo.zerobus_sdp.traces_silver parent
    ON child.parent_span_id = parent.span_id
    AND child.trace_id = parent.trace_id
WHERE child.start_timestamp >= current_timestamp() - INTERVAL 7 DAYS
  AND child.parent_span_id IS NOT NULL
LIMIT 20;
-- Expected: Should see service-to-service calls

-- 5. Check for cross-service calls vs same-service calls
SELECT
    CASE
        WHEN parent.service_name = child.service_name THEN 'same_service'
        ELSE 'cross_service'
    END as call_type,
    COUNT(*) as call_count,
    COUNT(DISTINCT child.trace_id) as unique_traces
FROM jmr_demo.zerobus_sdp.traces_silver child
JOIN jmr_demo.zerobus_sdp.traces_silver parent
    ON child.parent_span_id = parent.span_id
    AND child.trace_id = parent.trace_id
WHERE child.start_timestamp >= current_timestamp() - INTERVAL 7 DAYS
  AND child.parent_span_id IS NOT NULL
GROUP BY 1;
-- Expected: Should see both same_service and cross_service calls

-- 6. Check the actual service_dependencies table
SELECT * FROM jmr_demo.zerobus_sdp.service_dependencies LIMIT 20;
-- Check if table exists and has data

-- 7. Show table details
DESCRIBE DETAIL jmr_demo.zerobus_sdp.service_dependencies;
-- Check table metadata
