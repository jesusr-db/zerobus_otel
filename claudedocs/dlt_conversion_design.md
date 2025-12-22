# Delta Live Tables (DLT) Conversion Design
## Zerobus Silver Layer Migration to Spark Declarative Pipelines

**Date**: 2025-12-22  
**Status**: Design Complete  
**Target**: Convert batch streaming notebooks to DLT pipeline

---

## Executive Summary

This design converts the current silver layer notebooks from batch-style Structured Streaming to **Spark Declarative Pipelines** (formerly Delta Live Tables). The conversion will:

1. Replace `readStream` → `writeStream` pattern with `@dp.table` decorators
2. Create unified DLT pipeline replacing 5 separate notebooks
3. Introduce new schema: `{catalog}.zerobus_dlt` for DLT-managed tables
4. Add data quality expectations at ingestion
5. Simplify operations and improve maintainability

---

## Current Architecture Analysis

### Existing Notebooks (Batch Streaming Pattern)

| Notebook | Input | Output | Pattern |
|----------|-------|--------|---------|
| `01_flatten_traces.py` | `bronze.otel_spans` | `zerobus.traces_silver` | readStream → transform → writeStream |
| `02_assemble_traces.py` | `zerobus.traces_silver` | `zerobus.traces_assembled_silver` | readStream → groupBy/window → writeStream |
| `03_compute_service_health.py` | `zerobus.traces_silver` | `zerobus.service_health_silver` | readStream → groupBy/agg → writeStream |
| `04_enrich_logs.py` | `bronze.otel_logs` | `zerobus.logs_silver` | readStream + batch join → writeStream |
| `05_flatten_metrics.py` | `bronze.otel_metrics` | `zerobus.metrics_silver` | readStream → union → writeStream |

### Current Challenges

1. **Manual checkpoint management**: Each notebook manages its own checkpoint location
2. **No declarative data quality**: Quality checks happen downstream, not at ingestion
3. **Complex orchestration**: 5 separate notebooks require job orchestration
4. **Mixed streaming semantics**: Some use watermarks, some use windows, some use batch joins
5. **Schema drift handling**: Manual `mergeSchema` flags scattered across notebooks

---

## Target Architecture: DLT Pipeline

### Schema Design

**New Schema**: `{catalog}.zerobus_dlt`

This separates DLT-managed tables from manually managed tables, providing:
- Clear ownership boundaries
- Simplified permissions management
- Easier debugging and lineage tracking
- Non-disruptive migration path

### DLT Pipeline Structure

```
Pipeline: otel_silver_dlt_pipeline
├── Bronze Sources (streaming reads)
│   ├── bronze.otel_spans
│   ├── bronze.otel_logs
│   └── bronze.otel_metrics
│
├── Silver Tables (streaming transformations)
│   ├── traces_silver (@dp.table with expectations)
│   ├── logs_silver (@dp.table with expectations)
│   ├── metrics_silver (@dp.table with expectations)
│   ├── traces_assembled_silver (@dp.table)
│   └── service_health_silver (@dp.table)
│
└── Expectations (data quality rules)
    ├── valid_trace_id
    ├── valid_timestamps
    ├── valid_service_name
    └── valid_metric_values
```

---

## Conversion Patterns

### Pattern 1: Basic Streaming Transformation
**Before** (Structured Streaming):
```python
spans_df = spark.readStream.table(bronze_table)
flattened_traces = spans_df.withColumn(...).select(...)
query = flattened_traces.writeStream \
    .format("delta") \
    .option("checkpointLocation", checkpoint_location) \
    .trigger(availableNow=True) \
    .table(silver_table)
```

**After** (DLT):
```python
from pyspark import pipelines as dp

@dp.table(
    comment="Flattened trace spans with extracted attributes",
    table_properties={"quality": "silver", "layer": "silver"}
)
@dp.expect("valid_trace_id", "trace_id IS NOT NULL")
@dp.expect("valid_timestamps", "start_timestamp <= end_timestamp")
def traces_silver():
    return (
        spark.readStream.table(f"{bronze_catalog}.{bronze_schema}.otel_spans")
        .withColumn("service_name", col("resource.attributes")["service.name"])
        .withColumn(...)
        .select(...)
    )
```

### Pattern 2: Windowed Aggregation with Complex Struct Collection
**Before** (Structured Streaming):
```python
traces_df = spark.readStream.table(traces_table) \
    .withWatermark("start_timestamp", "10 minutes")

assembled_traces = (
    traces_df
    .groupBy("trace_id", window("start_timestamp", "5 minutes"))
    .agg(
        count("*").alias("span_count"),
        min("start_timestamp").alias("trace_start"),
        max("end_timestamp").alias("trace_end"),
        collect_set("service_name").alias("services_involved"),
        sum(col("is_error").cast("int")).alias("error_count"),
        max("duration_ms").alias("max_span_duration_ms"),
        avg("duration_ms").alias("avg_span_duration_ms"),
        collect_list(
            struct(
                "span_id", "parent_span_id", "name", "kind",
                "service_name", "duration_ms", "is_error"
            )
        ).alias("span_details")
    )
    .withColumn("has_errors", col("error_count") > 0)
    .withColumn("total_trace_duration_ms", 
                (unix_timestamp("trace_end") - unix_timestamp("trace_start")) * 1000)
    .withColumn("service_count", size("services_involved"))
)

query = assembled_traces.writeStream...
```

**After** (DLT):
```python
@dp.table(
    comment="Trace-level aggregations with complete span details array"
)
@dp.expect_or_fail("valid_span_count", "span_count > 0")
def traces_assembled_silver():
    return (
        spark.readStream.table("traces_silver")
        .withWatermark("start_timestamp", "10 minutes")
        .groupBy("trace_id", window("start_timestamp", "5 minutes"))
        .agg(
            count("*").alias("span_count"),
            min("start_timestamp").alias("trace_start"),
            max("end_timestamp").alias("trace_end"),
            collect_set("service_name").alias("services_involved"),
            sum(col("is_error").cast("int")).alias("error_count"),
            max("duration_ms").alias("max_span_duration_ms"),
            avg("duration_ms").alias("avg_span_duration_ms"),
            collect_list(
                struct(
                    "span_id",
                    "parent_span_id",
                    "name",
                    "kind",
                    "service_name",
                    "duration_ms",
                    "is_error"
                )
            ).alias("span_details")
        )
        .withColumn("has_errors", col("error_count") > 0)
        .withColumn("total_trace_duration_ms", 
                    (unix_timestamp("trace_end") - unix_timestamp("trace_start")) * 1000)
        .withColumn("service_count", size("services_involved"))
        .withColumn("ingestion_timestamp", current_timestamp())
        .select(
            "trace_id",
            col("window.start").alias("window_start"),
            col("window.end").alias("window_end"),
            "span_count",
            "trace_start",
            "trace_end",
            "services_involved",
            "error_count",
            "has_errors",
            "max_span_duration_ms",
            "avg_span_duration_ms",
            "span_details",
            "total_trace_duration_ms",
            "service_count",
            "ingestion_timestamp"
        )
    )
```

**Key Preservation**:
- `span_details`: Array of structs containing full span context
- All aggregation columns maintained
- Derived columns (`has_errors`, `total_trace_duration_ms`, `service_count`)
- Window columns extracted and aliased for compatibility

### Pattern 3: Stream-Static Join (Special Handling)
**Before** (Structured Streaming):
```python
logs_df = spark.readStream.table(logs_table)
traces_batch = spark.table(traces_table).select(...)
enriched_logs = logs_df.join(traces_batch, ["trace_id", "span_id"], "left")
```

**After** (DLT - Two Options):

**Option A**: Stream-Stream Join (Recommended)
```python
@dp.table(
    comment="Logs enriched with trace context"
)
def logs_silver():
    logs_stream = spark.readStream.table(f"{bronze_catalog}.{bronze_schema}.otel_logs")
    traces_stream = spark.readStream.table("traces_silver")
    
    return (
        logs_stream
        .withWatermark("log_timestamp", "10 minutes")
        .join(
            traces_stream.withWatermark("start_timestamp", "10 minutes"),
            ["trace_id", "span_id"],
            "left"
        )
    )
```

**Option B**: Streaming Log Flattening Only (Simpler)
```python
@dp.table(comment="Flattened logs without trace enrichment")
def logs_silver():
    return (
        spark.readStream.table(f"{bronze_catalog}.{bronze_schema}.otel_logs")
        .withColumn("service_name", col("resource.attributes")["service.name"])
        .select(...)
    )

# Create separate enrichment as downstream table if needed
@dp.table(comment="Logs with trace context")
def logs_enriched():
    return (
        spark.readStream.table("logs_silver")
        .join(
            spark.readStream.table("traces_silver"),
            ["trace_id", "span_id"],
            "left"
        )
    )
```

### Pattern 4: Union of Heterogeneous Streams
**Before** (Structured Streaming):
```python
gauge_metrics = metrics_df.filter(col("metric_type") == "gauge").withColumn(...)
sum_metrics = metrics_df.filter(col("metric_type") == "sum").withColumn(...)
histogram_metrics = metrics_df.filter(col("metric_type") == "histogram").withColumn(...)

all_metrics = gauge_metrics \
    .unionByName(sum_metrics, allowMissingColumns=True) \
    .unionByName(histogram_metrics, allowMissingColumns=True)
```

**After** (DLT):
```python
@dp.table(
    comment="All metric types flattened to unified schema"
)
@dp.expect("valid_metric_value", "value IS NOT NULL")
def metrics_silver():
    metrics_stream = spark.readStream.table(f"{bronze_catalog}.{bronze_schema}.otel_metrics")
    
    gauge_metrics = (
        metrics_stream
        .filter(col("metric_type") == "gauge")
        .withColumn(...)
    )
    
    sum_metrics = (
        metrics_stream
        .filter(col("metric_type") == "sum")
        .withColumn(...)
    )
    
    histogram_metrics = (
        metrics_stream
        .filter(col("metric_type") == "histogram")
        .withColumn(...)
    )
    
    return (
        gauge_metrics
        .unionByName(sum_metrics, allowMissingColumns=True)
        .unionByName(histogram_metrics, allowMissingColumns=True)
    )
```

---

## Data Quality Expectations

### Expectation Strategy

| Table | Expectations | Action |
|-------|--------------|--------|
| `traces_silver` | `valid_trace_id`: trace_id IS NOT NULL<br>`valid_timestamps`: start_timestamp <= end_timestamp<br>`valid_duration`: duration_ms >= 0 | Drop invalid rows |
| `logs_silver` | `valid_log_timestamp`: log_timestamp IS NOT NULL<br>`valid_severity`: severity_number BETWEEN 1 AND 24 | Drop invalid rows |
| `metrics_silver` | `valid_metric_value`: value IS NOT NULL<br>`valid_metric_name`: name IS NOT NULL | Drop invalid rows |
| `traces_assembled_silver` | `valid_span_count`: span_count > 0 | Fail on violation |
| `service_health_silver` | `valid_service_name`: service_name IS NOT NULL<br>`valid_request_count`: request_count >= 0 | Fail on violation |

### Expectation Decorator Usage

```python
# Drop invalid rows (permissive)
@dp.expect_or_drop("valid_trace_id", "trace_id IS NOT NULL")

# Fail pipeline on violation (strict)
@dp.expect_or_fail("valid_span_count", "span_count > 0")

# Log violations but continue (monitoring)
@dp.expect("valid_http_status", "http_status_code BETWEEN 100 AND 599")
```

---

## Pipeline Configuration

### Asset Bundle Integration

The DLT pipeline is managed through Databricks Asset Bundles in `resources/pipelines.yml`.

**Current Pipeline** (`otel_streaming_pipeline`):
- Uses notebook-based approach with separate library files
- Serverless execution
- Continuous mode enabled
- Multiple notebook libraries

**Updated Pipeline Configuration** (Bundle-Managed):

**File**: `resources/pipelines.yml`
```yaml
resources:
  pipelines:
    otel_streaming_pipeline:
      name: "[${bundle.target}] OTel Silver SDP Pipeline"
      catalog: ${var.catalog_name}
      target: ${var.schema_name}  # zerobus_sdp (from databricks.yml)
      
      serverless: true
      channel: CURRENT
      edition: ADVANCED
      
      libraries:
        - notebook:
            path: ../src/notebooks/dlt/silver_pipeline.py
      
      configuration:
        bronze_catalog: ${var.bronze_catalog}
        bronze_schema: ${var.bronze_schema}
        bronze_table_prefix: ${var.bronze_table_prefix}
      
      continuous: false  # Changed to triggered for cost control
      development: false  # Set per target in databricks.yml
```

**Target-Specific Configuration** (databricks.yml):
```yaml
targets:
  dev:
    variables:
      schema_name: zerobus_sdp  # SDP-managed schema
    resources:
      pipelines:
        otel_streaming_pipeline:
          development: true  # Fast iteration mode
          continuous: false  # On-demand for dev
```

### Key Configuration Choices

1. **Schema**: `zerobus_sdp` (from databricks.yml) - Spark Declarative Pipeline schema
2. **Serverless**: `true` - managed compute, auto-scaling
3. **Continuous Mode**: `false` - triggered execution for cost control
4. **Edition**: `ADVANCED` - supports expectations and data quality
5. **Single Notebook**: Consolidated from 5 separate notebooks
6. **Development Mode**: Per-target configuration in databricks.yml

---

## Migration Strategy

### Phase 1: Parallel Deployment (Week 1)
1. Deploy DLT pipeline writing to `zerobus_dlt` schema
2. Keep existing notebooks writing to `zerobus` schema
3. Validate data consistency between both outputs
4. Monitor pipeline performance and stability

### Phase 2: Traffic Switch (Week 2)
1. Update downstream gold layer to read from `zerobus_dlt`
2. Monitor for issues over 48 hours
3. Pause existing notebook-based jobs
4. Validate end-to-end pipeline

### Phase 3: Decommission (Week 3)
1. Archive old notebooks to `src/notebooks/silver_archived/`
2. Remove notebook-based job definitions
3. Drop tables in `zerobus` schema (after backup)
4. Update documentation

### Rollback Plan
- Keep old notebooks and jobs paused (not deleted) for 2 weeks
- Maintain ability to switch downstream consumers back to `zerobus` schema
- DLT pipeline can be stopped without affecting old pipeline

---

## File Structure Changes

### New Files to Create
```
src/
└── notebooks/
    ├── dlt/
    │   └── silver_pipeline.py         # Single consolidated SDP notebook
    └── silver_archived/               # Archive old notebooks after migration
        ├── 01_flatten_traces.py
        ├── 02_assemble_traces.py
        ├── 03_compute_service_health.py
        ├── 04_enrich_logs.py
        └── 05_flatten_metrics.py
```

### Updated Files (Bundle-Managed)
```
resources/
├── pipelines.yml                  # Update existing pipeline config
└── jobs.yml                       # Remove/update silver_transformations job

databricks.yml                     # Schema name already updated to zerobus_sdp

claudedocs/
└── dlt_conversion_design.md      # This document
```

**Note**: Pipeline is fully managed through asset bundle - no separate pipeline definition files needed. Deploy with:
```bash
databricks bundle deploy -t dev
databricks bundle run -t dev otel_streaming_pipeline
```

---

## Dependencies and Prerequisites

### Required Permissions
- Unity Catalog: `USE CATALOG`, `CREATE SCHEMA`, `USE SCHEMA`, `CREATE TABLE`
- DLT: Pipeline creation and execution permissions
- Bronze tables: `SELECT` permission on `bronze.otel_*` tables

### Databricks Runtime
- DBR 14.3 LTS or higher
- DLT Edition: Advanced (for expectations)
- Photon enabled

### External Dependencies
None - uses built-in PySpark and DLT functionality

---

## Monitoring and Observability

### DLT Pipeline Metrics
- **Data Quality**: Track expectation violations via DLT UI
- **Lineage**: Visual DAG showing table dependencies
- **Performance**: Built-in metrics for processing time and throughput
- **Cost**: Compute usage tracked per pipeline run

### Integration with Existing Monitoring
- Gold layer alerting: Update table references to `zerobus_dlt.*`
- Dashboard: Update SQL queries to read from new schema
- Data quality validation: Can remain unchanged (operates on gold layer)

---

## Performance Considerations

### Expected Improvements
1. **Reduced Overhead**: Single pipeline vs. 5 orchestrated notebooks
2. **Automatic Optimization**: DLT handles partition pruning and compaction
3. **Photon Acceleration**: ~2-3x faster for aggregations
4. **Smart Checkpointing**: DLT manages checkpoints automatically

### Potential Challenges
1. **Initial Load**: First run processes all historical data
2. **Memory**: Windowed aggregations may require larger clusters
3. **Stream-Stream Joins**: More complex than stream-static joins

### Mitigation Strategies
- Start with `development: true` for faster iteration
- Use `autoscale` clusters for variable workloads
- Monitor DLT event log for bottlenecks
- Consider splitting very large tables into separate pipelines

---

## Cost Analysis

### Current Architecture (Notebook Jobs)
- 5 separate job clusters (cold start overhead)
- Manual checkpoint management (storage costs)
- No automatic optimization (higher compute costs)

### DLT Pipeline (Proposed)
- Single shared compute cluster (reduced cold starts)
- Automatic checkpoint management
- Built-in optimization (lower compute costs)
- **Estimated Savings**: 20-30% reduction in compute costs

### DLT Pricing Considerations
- DLT has DBU premium (~2x standard DBUs)
- Offset by reduced complexity and operational overhead
- Development mode: Lower DBU rates for testing

---

## Testing Strategy

### Unit Testing (Pre-Deployment)
1. Validate SQL transformations in notebooks
2. Test expectations with sample data
3. Verify schema compatibility

### Integration Testing (Dev Environment)
1. Deploy to `dev` target with `development: true`
2. Trigger pipeline with sample bronze data
3. Validate output tables in `zerobus_dlt` schema
4. Compare row counts and aggregates with existing `zerobus` tables

### Performance Testing (Staging)
1. Deploy to `staging` with production-sized data
2. Measure end-to-end latency
3. Monitor resource utilization
4. Validate data freshness

### Acceptance Criteria
- [ ] All 5 tables successfully created in `zerobus_dlt`
- [ ] Zero data loss (row count parity with original tables)
- [ ] Data quality expectations operational
- [ ] Pipeline completes within SLA (< 10 minutes)
- [ ] Downstream gold layer queries succeed
- [ ] Cost within budget (< $X per day)

---

## Success Metrics

### Technical Metrics
- **Pipeline Success Rate**: >99.5%
- **Data Freshness**: <5 minutes lag from bronze to silver
- **Expectation Pass Rate**: >99%
- **Compute Cost**: <$X per day

### Operational Metrics
- **Time to Deploy Changes**: <30 minutes (vs. 2+ hours)
- **Debugging Time**: 50% reduction with DLT lineage UI
- **Incident Response**: Faster root cause analysis

---

## Risks and Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Data loss during migration | High | Low | Parallel deployment, validation scripts |
| Performance degradation | Medium | Medium | Performance testing, rollback plan |
| Incompatible downstream queries | Medium | Low | Schema compatibility checks |
| Cost overrun | Medium | Medium | Development mode, monitoring |
| Learning curve for team | Low | High | Documentation, training sessions |

---

## Next Steps

1. **Review Design** (Jesus Rodriguez + team)
2. **Create DLT Pipeline Notebook** (Implementation task)
3. **Define YAML Configuration** (Implementation task)
4. **Deploy to Dev** (Testing phase)
5. **Run Validation Suite** (Testing phase)
6. **Iterate Based on Feedback** (Refinement)
7. **Deploy to Staging** (Rollout phase)
8. **Production Deployment** (Rollout phase)

---

## References

- [Databricks Delta Live Tables Documentation](https://docs.databricks.com/delta-live-tables/index.html)
- [Spark Declarative Pipelines (SDP) Migration Guide](https://docs.databricks.com/ldp/where-is-dlt.html)
- [Databricks @dp.table API Reference](https://docs.databricks.com/ldp/developer/ldp-python-ref-table.html)
- [Data Quality Expectations](https://docs.databricks.com/ldp/expectations.html)

---

**Document Version**: 1.0  
**Last Updated**: 2025-12-22  
**Author**: Claude Code (via Jesus Rodriguez)
