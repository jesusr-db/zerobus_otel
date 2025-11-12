-- Optimize Bronze Tables (streaming from OTEL gateway)
-- Bronze location: jmr_demo.zerobus_bronze.otel_*
OPTIMIZE jmr_demo.zerobus.otel_spans ZORDER BY (trace_id);
OPTIMIZE jmr_demo.zerobus.otel_metrics ZORDER BY (name);
OPTIMIZE jmr_demo.zerobus.otel_logs ZORDER BY (trace_id);
