-- Optimize Bronze Tables (streaming from OTEL gateway)
-- Bronze location: jmr_demo.zerobus_bronze.otel_*
OPTIMIZE jmr_demo.zerobus_bronze.otel_spans ZORDER BY (trace_id);
OPTIMIZE jmr_demo.zerobus_bronze.otel_metrics ZORDER BY (name);
OPTIMIZE jmr_demo.zerobus_bronze.otel_logs ZORDER BY (trace_id);
