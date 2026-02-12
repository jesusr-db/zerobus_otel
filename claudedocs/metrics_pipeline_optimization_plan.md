# Metrics Pipeline Optimization Plan

**Date**: 2026-01-23
**Status**: Ready for Implementation
**Expected Impact**: 50-70% latency reduction, 40-60% cost savings, 2.5x data coverage

---

## Critical Issues Found

### 1. Missing Metric Types (60-70% data loss)
- Only processing **gauge** and **sum** metrics
- **Dropping histogram, exponential_histogram, summary** metrics
- Histogram metrics contain pre-computed percentiles (P95/P99 latencies)

### 2. Expensive Percentile Calculations (40-50% compute cost)
- Computing `approx_percentile` 36,000 times per minute
- 3 percentiles × 3 rollup windows × 400 metrics × 10 services

### 3. Streaming State Bloat (20-30% memory overhead)
- `dropDuplicates` without watermark = unbounded state
- 345M state entries per day

### 4. Double Bronze Table Scan (15-20% I/O overhead)
- Scanning bronze table twice (once for gauge, once for sum)

---

## Implementation Phases

### ✅ Phase 1: Add Histogram Support (Week 1)
**Priority**: CRITICAL
**File**: `src/notebooks/dlt/silver_transformations.py` (lines 133-188)

**Changes**:
- Replace double-scan (gauge + sum) with single-scan conditional extraction
- Add histogram field extraction (count, sum, min, max, buckets, bounds)
- Add exponential_histogram and summary support
- Add watermark to dropDuplicates: `.withWatermark("metric_timestamp", "2 minutes")`

**Success Criteria**:
- All 5 metric types in silver table
- Histogram bucket data preserved
- Lag stays under 2 minutes

---

### ✅ Phase 2: Optimize Aggregations (Week 2)
**Priority**: HIGH
**File**: `src/notebooks/dlt/silver_transformations.py` (lines 197-246)

**Option B (Recommended for MVP)**:
1. Create `metrics_1min_rollup_simple` - gauge/sum only, NO percentiles
2. Create `histogram_metrics_1min_rollup` - histogram rollups with bucket aggregation

**Success Criteria**:
- 40-60% reduction in compute time
- 1-minute rollup lag < 2 minutes end-to-end

---

### ✅ Phase 3: Remove Redundant Windows (Week 3)
**Priority**: MEDIUM
**File**: `src/notebooks/dlt/silver_transformations.py` (lines 250-352)

**Changes**:
- Comment out `metrics_5min_rollup` and `metrics_hourly_rollup`
- Create on-demand SQL views for 5-min/hourly aggregations

**Success Criteria**:
- 66% reduction in streaming compute
- On-demand queries < 5 seconds

---

### ✅ Phase 4: Table Optimizations (Week 4)
**Priority**: LOW
**Files**:
- `src/notebooks/dlt/silver_transformations.py` (line 133)
- `resources/pipelines.yml` (lines 22-27)

**Changes**:
- Add liquid clustering: `cluster_by=["service_name", "metric_type", "metric_timestamp"]`
- Enable optimizeWrite and autoCompact

**Success Criteria**:
- 10-20% query latency improvement

---

## Quick Reference

### Current Bronze → Silver → Gold Flow
```
Bronze: jmr_demo.zerobus.otel_metrics (76.5M rows, ~3GB)
  ↓ readStream (double scan)
Silver: jmr_demo.zerobus_sdp.metrics_silver (gauge + sum only)
  ↓ dlt.read_stream (cascading)
Gold: metrics_1min_rollup / metrics_5min_rollup / metrics_hourly_rollup
  ↓ 9 × approx_percentile per metric
```

### After Optimization
```
Bronze: jmr_demo.zerobus.otel_metrics (76.5M rows, ~3GB)
  ↓ readStream (single scan, all types)
Silver: metrics_silver (gauge + sum + histogram + exponential_histogram + summary)
  ↓ dlt.read_stream (watermarked)
Gold:
  - metrics_1min_rollup_simple (gauge/sum, NO percentiles)
  - histogram_metrics_1min_rollup (histogram buckets preserved)
```

---

## Verification Queries

### Check metric type coverage
```sql
-- Bronze
SELECT metric_type, COUNT(*) FROM jmr_demo.zerobus.otel_metrics
WHERE ingestion_timestamp >= current_timestamp() - INTERVAL 1 HOUR
GROUP BY metric_type;

-- Silver (should match bronze)
SELECT metric_type, COUNT(*) FROM jmr_demo.zerobus_sdp.metrics_silver
WHERE ingestion_timestamp >= current_timestamp() - INTERVAL 1 HOUR
GROUP BY metric_type;
```

### Measure lag
```sql
-- Bronze → Silver lag
SELECT metric_type,
  percentile_approx(unix_timestamp(ingestion_timestamp) - unix_timestamp(metric_timestamp), array(0.5, 0.95, 0.99)) as lag_seconds
FROM jmr_demo.zerobus_sdp.metrics_silver
WHERE metric_timestamp >= current_timestamp() - INTERVAL 10 MINUTES
GROUP BY metric_type;
```

---

## Expected Results

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Bronze → Silver lag | 2-5 min | 1-2 min | **50% faster** |
| Silver → Gold lag | 1.5 min | 30-45 sec | **50% faster** |
| End-to-end lag | 6-8 min | 2-3 min | **60-70% faster** |
| Pipeline cost | 100% | 60% | **40% savings** |
| Data coverage | 40% | 100% | **2.5x more** |

---

## Rollback

If issues occur in any phase:
1. Revert `src/notebooks/dlt/silver_transformations.py`
2. Restart pipeline: `databricks pipelines start-update 64388933-9204-47f9-8741-1a80b402a914`
3. Monitor for 30 minutes

---

## Pipeline ID
Silver Streaming Pipeline: `64388933-9204-47f9-8741-1a80b402a914`
