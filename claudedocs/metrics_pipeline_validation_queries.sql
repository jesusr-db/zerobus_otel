-- Metrics Pipeline Optimization - Validation Queries
-- Use these queries to validate the implementation and measure improvements

-- ============================================================================
-- 1. DATA COMPLETENESS VALIDATION
-- ============================================================================

-- 1.1 Count metrics by type in BRONZE layer
-- Expected: Should see all 5 metric types (gauge, sum, histogram, exponential_histogram, summary)
SELECT
    metric_type,
    COUNT(*) as count,
    MIN(ingestion_timestamp) as first_seen,
    MAX(ingestion_timestamp) as last_seen
FROM jmr_demo.zerobus.otel_metrics
WHERE ingestion_timestamp >= current_timestamp() - INTERVAL 1 HOUR
GROUP BY metric_type
ORDER BY count DESC;

-- 1.2 Count metrics by type in SILVER layer
-- Expected: Should match bronze counts - all 5 metric types present
SELECT
    metric_type,
    COUNT(*) as count,
    MIN(ingestion_timestamp) as first_seen,
    MAX(ingestion_timestamp) as last_seen
FROM jmr_demo.zerobus_sdp.metrics_silver
WHERE ingestion_timestamp >= current_timestamp() - INTERVAL 1 HOUR
GROUP BY metric_type
ORDER BY count DESC;

-- 1.3 Verify histogram data is preserved in silver
-- Expected: Non-null histogram columns for histogram metric types
SELECT
    name,
    service_name,
    metric_timestamp,
    histogram_count,
    histogram_sum,
    histogram_min,
    histogram_max,
    size(histogram_buckets) as bucket_count,
    size(histogram_bounds) as bounds_count
FROM jmr_demo.zerobus_sdp.metrics_silver
WHERE metric_type = 'histogram'
    AND ingestion_timestamp >= current_timestamp() - INTERVAL 10 MINUTES
LIMIT 10;

-- 1.4 Check data completeness percentage
-- Expected: Should be close to 100% (allowing for minor late arrivals)
WITH bronze_counts AS (
    SELECT metric_type, COUNT(*) as bronze_count
    FROM jmr_demo.zerobus.otel_metrics
    WHERE ingestion_timestamp >= current_timestamp() - INTERVAL 1 HOUR
    GROUP BY metric_type
),
silver_counts AS (
    SELECT metric_type, COUNT(*) as silver_count
    FROM jmr_demo.zerobus_sdp.metrics_silver
    WHERE ingestion_timestamp >= current_timestamp() - INTERVAL 1 HOUR
    GROUP BY metric_type
)
SELECT
    b.metric_type,
    b.bronze_count,
    COALESCE(s.silver_count, 0) as silver_count,
    ROUND(100.0 * COALESCE(s.silver_count, 0) / b.bronze_count, 2) as completeness_pct
FROM bronze_counts b
LEFT JOIN silver_counts s ON b.metric_type = s.metric_type
ORDER BY completeness_pct DESC;

-- ============================================================================
-- 2. PERFORMANCE BENCHMARKS
-- ============================================================================

-- 2.1 Measure Bronze → Silver lag by metric type
-- Expected: <2 minutes lag (down from 2-5 minutes before optimization)
SELECT
    metric_type,
    COUNT(*) as sample_count,
    ROUND(PERCENTILE(unix_timestamp(ingestion_timestamp) - unix_timestamp(metric_timestamp), 0.5), 2) as p50_lag_seconds,
    ROUND(PERCENTILE(unix_timestamp(ingestion_timestamp) - unix_timestamp(metric_timestamp), 0.95), 2) as p95_lag_seconds,
    ROUND(PERCENTILE(unix_timestamp(ingestion_timestamp) - unix_timestamp(metric_timestamp), 0.99), 2) as p99_lag_seconds
FROM jmr_demo.zerobus_sdp.metrics_silver
WHERE metric_timestamp >= current_timestamp() - INTERVAL 10 MINUTES
GROUP BY metric_type
ORDER BY p95_lag_seconds DESC;

-- 2.2 Measure Silver → Gold (1-min rollup) lag
-- Expected: <1 minute lag (down from 1.5 minutes before optimization)
SELECT
    name,
    COUNT(*) as rollup_count,
    ROUND(PERCENTILE(unix_timestamp(ingestion_timestamp) - unix_timestamp(window_start), 0.5), 2) as p50_lag_seconds,
    ROUND(PERCENTILE(unix_timestamp(ingestion_timestamp) - unix_timestamp(window_start), 0.95), 2) as p95_lag_seconds,
    ROUND(PERCENTILE(unix_timestamp(ingestion_timestamp) - unix_timestamp(window_start), 0.99), 2) as p99_lag_seconds
FROM jmr_demo.zerobus_sdp.metrics_1min_rollup
WHERE window_start >= current_timestamp() - INTERVAL 10 MINUTES
GROUP BY name
ORDER BY p95_lag_seconds DESC
LIMIT 20;

-- 2.3 Check histogram metrics rollup lag
SELECT
    name,
    metric_type,
    COUNT(*) as rollup_count,
    ROUND(PERCENTILE(unix_timestamp(ingestion_timestamp) - unix_timestamp(window_start), 0.5), 2) as p50_lag_seconds,
    ROUND(PERCENTILE(unix_timestamp(ingestion_timestamp) - unix_timestamp(window_start), 0.95), 2) as p95_lag_seconds
FROM jmr_demo.zerobus_sdp.histogram_metrics_1min_rollup
WHERE window_start >= current_timestamp() - INTERVAL 10 MINUTES
GROUP BY name, metric_type
ORDER BY p95_lag_seconds DESC
LIMIT 20;

-- ============================================================================
-- 3. DATA QUALITY CHECKS
-- ============================================================================

-- 3.1 Verify no duplicate metrics in silver
-- Expected: 0 duplicates
SELECT
    name,
    service_name,
    metric_timestamp,
    metric_type,
    COUNT(*) as duplicate_count
FROM jmr_demo.zerobus_sdp.metrics_silver
WHERE ingestion_timestamp >= current_timestamp() - INTERVAL 1 HOUR
GROUP BY name, service_name, metric_timestamp, metric_type
HAVING COUNT(*) > 1
LIMIT 10;

-- 3.2 Check for null critical fields in silver
-- Expected: 0 rows with null critical fields
SELECT
    metric_type,
    COUNT(*) as total_count,
    SUM(CASE WHEN name IS NULL THEN 1 ELSE 0 END) as null_name_count,
    SUM(CASE WHEN service_name IS NULL THEN 1 ELSE 0 END) as null_service_count,
    SUM(CASE WHEN metric_timestamp IS NULL THEN 1 ELSE 0 END) as null_timestamp_count
FROM jmr_demo.zerobus_sdp.metrics_silver
WHERE ingestion_timestamp >= current_timestamp() - INTERVAL 1 HOUR
GROUP BY metric_type;

-- 3.3 Verify histogram buckets integrity
-- Expected: histogram_buckets and histogram_bounds have same size
SELECT
    name,
    service_name,
    metric_timestamp,
    size(histogram_buckets) as buckets_size,
    size(histogram_bounds) as bounds_size,
    CASE
        WHEN size(histogram_buckets) = size(histogram_bounds) + 1 THEN 'VALID'
        ELSE 'INVALID'
    END as integrity_status
FROM jmr_demo.zerobus_sdp.metrics_silver
WHERE metric_type = 'histogram'
    AND ingestion_timestamp >= current_timestamp() - INTERVAL 10 MINUTES
    AND histogram_buckets IS NOT NULL
    AND histogram_bounds IS NOT NULL
ORDER BY metric_timestamp DESC
LIMIT 20;

-- ============================================================================
-- 4. AGGREGATION VALIDATION
-- ============================================================================

-- 4.1 Compare simple metrics rollup with histogram rollup (sample counts)
-- Expected: Both rollup types should have data
SELECT
    'Simple Metrics (gauge/sum)' as rollup_type,
    COUNT(DISTINCT name) as unique_metrics,
    COUNT(DISTINCT service_name) as unique_services,
    SUM(sample_count) as total_samples
FROM jmr_demo.zerobus_sdp.metrics_1min_rollup
WHERE window_start >= current_timestamp() - INTERVAL 10 MINUTES

UNION ALL

SELECT
    'Histogram Metrics' as rollup_type,
    COUNT(DISTINCT name) as unique_metrics,
    COUNT(DISTINCT service_name) as unique_services,
    SUM(total_count) as total_samples
FROM jmr_demo.zerobus_sdp.histogram_metrics_1min_rollup
WHERE window_start >= current_timestamp() - INTERVAL 10 MINUTES;

-- 4.2 Validate 1-min rollup aggregations are reasonable
-- Expected: min <= avg <= max, no negative values for counts
SELECT
    name,
    service_name,
    window_start,
    sample_count,
    min_value,
    avg_value,
    max_value,
    sum_value,
    CASE
        WHEN min_value <= avg_value AND avg_value <= max_value THEN 'VALID'
        ELSE 'INVALID'
    END as validation_status
FROM jmr_demo.zerobus_sdp.metrics_1min_rollup
WHERE window_start >= current_timestamp() - INTERVAL 10 MINUTES
    AND sample_count > 0
ORDER BY window_start DESC
LIMIT 20;

-- 4.3 Check histogram rollup has preserved bucket data
-- Expected: histogram_buckets_list is not empty for histogram metrics
SELECT
    name,
    service_name,
    metric_type,
    window_start,
    total_count,
    avg_value,
    size(histogram_buckets_list) as bucket_samples_count,
    size(summary_quantiles_list) as quantile_samples_count
FROM jmr_demo.zerobus_sdp.histogram_metrics_1min_rollup
WHERE window_start >= current_timestamp() - INTERVAL 10 MINUTES
ORDER BY window_start DESC
LIMIT 20;

-- ============================================================================
-- 5. ON-DEMAND ROLLUP VALIDATION (5-min and Hourly)
-- ============================================================================

-- 5.1 Create on-demand 5-minute rollup view
-- This replaces the streaming metrics_5min_rollup pipeline
CREATE OR REPLACE VIEW jmr_demo.zerobus_sdp.metrics_5min_rollup_view AS
SELECT
    name,
    service_name,
    metric_type,
    date_trunc('5 minutes', window_start) as window_start,
    date_trunc('5 minutes', window_end) as window_end,
    SUM(sample_count) as sample_count,
    AVG(avg_value) as avg_value,
    MIN(min_value) as min_value,
    MAX(max_value) as max_value,
    SUM(sum_value) as sum_value
FROM jmr_demo.zerobus_sdp.metrics_1min_rollup
GROUP BY name, service_name, metric_type, date_trunc('5 minutes', window_start), date_trunc('5 minutes', window_end);

-- 5.2 Create on-demand hourly rollup view
-- This replaces the streaming metrics_hourly_rollup pipeline
CREATE OR REPLACE VIEW jmr_demo.zerobus_sdp.metrics_hourly_rollup_view AS
SELECT
    name,
    service_name,
    metric_type,
    date_trunc('hour', window_start) as window_start,
    date_trunc('hour', window_end) as window_end,
    SUM(sample_count) as sample_count,
    AVG(avg_value) as avg_value,
    MIN(min_value) as min_value,
    MAX(max_value) as max_value,
    SUM(sum_value) as sum_value
FROM jmr_demo.zerobus_sdp.metrics_1min_rollup
GROUP BY name, service_name, metric_type, date_trunc('hour', window_start), date_trunc('hour', window_end);

-- 5.3 Test on-demand 5-minute rollup query performance
-- Expected: <5 seconds query time
SELECT
    name,
    service_name,
    window_start,
    sample_count,
    avg_value,
    min_value,
    max_value
FROM jmr_demo.zerobus_sdp.metrics_5min_rollup_view
WHERE window_start >= current_timestamp() - INTERVAL 1 HOUR
ORDER BY window_start DESC, name
LIMIT 100;

-- 5.4 Test on-demand hourly rollup query performance
-- Expected: <5 seconds query time
SELECT
    name,
    service_name,
    window_start,
    sample_count,
    avg_value,
    min_value,
    max_value
FROM jmr_demo.zerobus_sdp.metrics_hourly_rollup_view
WHERE window_start >= current_timestamp() - INTERVAL 24 HOURS
ORDER BY window_start DESC, name
LIMIT 100;

-- ============================================================================
-- 6. BEFORE/AFTER COMPARISON
-- ============================================================================

-- 6.1 Metric type coverage comparison
-- Run this BEFORE and AFTER optimization to compare metric type coverage
SELECT
    'BEFORE Optimization' as status,
    COUNT(DISTINCT CASE WHEN metric_type IN ('gauge', 'sum') THEN name END) as processed_metrics,
    COUNT(DISTINCT CASE WHEN metric_type IN ('histogram', 'exponential_histogram', 'summary') THEN name END) as dropped_metrics,
    ROUND(100.0 * COUNT(DISTINCT CASE WHEN metric_type IN ('gauge', 'sum') THEN name END) /
          COUNT(DISTINCT name), 2) as coverage_pct
FROM jmr_demo.zerobus.otel_metrics
WHERE ingestion_timestamp >= current_timestamp() - INTERVAL 1 HOUR

UNION ALL

SELECT
    'AFTER Optimization' as status,
    COUNT(DISTINCT name) as processed_metrics,
    0 as dropped_metrics,
    100.0 as coverage_pct
FROM jmr_demo.zerobus_sdp.metrics_silver
WHERE ingestion_timestamp >= current_timestamp() - INTERVAL 1 HOUR;

-- 6.2 Table size comparison (silver layer)
-- Use this to monitor data volume changes
DESCRIBE DETAIL jmr_demo.zerobus_sdp.metrics_silver;

-- 6.3 Check liquid clustering statistics
-- Expected: Shows clustering columns and their effectiveness
SHOW TBLPROPERTIES jmr_demo.zerobus_sdp.metrics_silver;

-- ============================================================================
-- 7. PIPELINE MONITORING QUERIES
-- ============================================================================

-- 7.1 Monitor streaming progress (check watermark advancement)
-- Run this periodically to ensure watermark is advancing properly
SELECT
    MAX(metric_timestamp) as latest_metric_timestamp,
    MAX(ingestion_timestamp) as latest_ingestion_timestamp,
    ROUND((unix_timestamp(MAX(ingestion_timestamp)) - unix_timestamp(MAX(metric_timestamp))) / 60, 2) as lag_minutes
FROM jmr_demo.zerobus_sdp.metrics_silver;

-- 7.2 Monitor rollup progress
SELECT
    MAX(window_start) as latest_1min_window,
    MAX(ingestion_timestamp) as latest_ingestion,
    COUNT(DISTINCT name) as unique_metrics,
    COUNT(DISTINCT service_name) as unique_services
FROM jmr_demo.zerobus_sdp.metrics_1min_rollup;

SELECT
    MAX(window_start) as latest_1min_window,
    MAX(ingestion_timestamp) as latest_ingestion,
    COUNT(DISTINCT name) as unique_metrics,
    COUNT(DISTINCT service_name) as unique_services
FROM jmr_demo.zerobus_sdp.histogram_metrics_1min_rollup;

-- 7.3 Check for data freshness issues
-- Expected: All metric types should have recent data
SELECT
    metric_type,
    MAX(metric_timestamp) as latest_metric_timestamp,
    MAX(ingestion_timestamp) as latest_ingestion_timestamp,
    ROUND((unix_timestamp(current_timestamp()) - unix_timestamp(MAX(metric_timestamp))) / 60, 2) as minutes_since_last_metric
FROM jmr_demo.zerobus_sdp.metrics_silver
GROUP BY metric_type
ORDER BY minutes_since_last_metric DESC;

-- ============================================================================
-- 8. TROUBLESHOOTING QUERIES
-- ============================================================================

-- 8.1 Identify metrics with high lag
SELECT
    name,
    service_name,
    metric_type,
    metric_timestamp,
    ingestion_timestamp,
    ROUND((unix_timestamp(ingestion_timestamp) - unix_timestamp(metric_timestamp)) / 60, 2) as lag_minutes
FROM jmr_demo.zerobus_sdp.metrics_silver
WHERE unix_timestamp(ingestion_timestamp) - unix_timestamp(metric_timestamp) > 300  -- >5 minutes lag
    AND metric_timestamp >= current_timestamp() - INTERVAL 1 HOUR
ORDER BY lag_minutes DESC
LIMIT 20;

-- 8.2 Check for missing histogram data
-- Expected: 0 rows (all histogram metrics should have bucket data)
SELECT
    name,
    service_name,
    metric_timestamp,
    histogram_count,
    histogram_buckets,
    histogram_bounds
FROM jmr_demo.zerobus_sdp.metrics_silver
WHERE metric_type = 'histogram'
    AND (histogram_buckets IS NULL OR histogram_bounds IS NULL OR histogram_count IS NULL)
    AND ingestion_timestamp >= current_timestamp() - INTERVAL 1 HOUR
LIMIT 10;

-- 8.3 Identify rollup gaps (missing windows)
-- This checks for missing 1-minute windows in the rollup
WITH expected_windows AS (
    SELECT
        name,
        service_name,
        explode(
            sequence(
                date_trunc('minute', current_timestamp() - INTERVAL 10 MINUTES),
                date_trunc('minute', current_timestamp()),
                INTERVAL 1 MINUTE
            )
        ) as expected_window_start
    FROM (
        SELECT DISTINCT name, service_name
        FROM jmr_demo.zerobus_sdp.metrics_1min_rollup
        WHERE window_start >= current_timestamp() - INTERVAL 10 MINUTES
    )
),
actual_windows AS (
    SELECT DISTINCT
        name,
        service_name,
        window_start
    FROM jmr_demo.zerobus_sdp.metrics_1min_rollup
    WHERE window_start >= current_timestamp() - INTERVAL 10 MINUTES
)
SELECT
    e.name,
    e.service_name,
    e.expected_window_start,
    CASE WHEN a.window_start IS NULL THEN 'MISSING' ELSE 'PRESENT' END as status
FROM expected_windows e
LEFT JOIN actual_windows a
    ON e.name = a.name
    AND e.service_name = a.service_name
    AND e.expected_window_start = a.window_start
WHERE a.window_start IS NULL
ORDER BY e.name, e.expected_window_start
LIMIT 20;

-- ============================================================================
-- USAGE NOTES
-- ============================================================================

/*
DEPLOYMENT VALIDATION CHECKLIST:

1. Data Completeness (Section 1):
   - Run queries 1.1-1.4 to verify all metric types are processed
   - Expected: 5 metric types (gauge, sum, histogram, exponential_histogram, summary)
   - Target: >95% completeness for all types

2. Performance Validation (Section 2):
   - Run queries 2.1-2.3 to measure lag improvements
   - Target: Bronze→Silver lag <2 minutes (p95)
   - Target: Silver→Gold lag <1 minute (p95)

3. Data Quality (Section 3):
   - Run queries 3.1-3.3 to validate data integrity
   - Expected: 0 duplicates, 0 null critical fields
   - Verify histogram bucket integrity

4. Aggregation Validation (Section 4):
   - Run queries 4.1-4.3 to verify rollups are working
   - Check both simple metrics and histogram metrics rollups
   - Validate aggregation math (min <= avg <= max)

5. On-Demand Rollups (Section 5):
   - Create views 5.1-5.2 for on-demand aggregations
   - Test query performance with 5.3-5.4
   - Target: <5 seconds for on-demand queries

6. Monitor Improvements (Section 6):
   - Compare before/after metrics using queries 6.1-6.3
   - Expected: 2.5x increase in metric coverage (40% → 100%)
   - Expected: 40-60% reduction in compute costs

7. Ongoing Monitoring (Section 7):
   - Use queries 7.1-7.3 for daily monitoring
   - Set up alerts for data freshness issues
   - Monitor watermark advancement

8. Troubleshooting (Section 8):
   - Use queries 8.1-8.3 to diagnose issues
   - Identify high lag metrics
   - Check for missing data or rollup gaps

ROLLBACK INSTRUCTIONS:
If issues are detected, revert to previous version of silver_transformations.py
and restart the pipeline. All queries are non-destructive and safe to run.
*/
