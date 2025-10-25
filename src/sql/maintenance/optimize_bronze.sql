-- Optimize Bronze Tables (streaming from OTEL gateway)
-- Bronze location: main.jmr_demo.otel_*
OPTIMIZE main.jmr_demo.otel_spans ZORDER BY (trace_id);
OPTIMIZE main.jmr_demo.otel_metrics ZORDER BY (name);
OPTIMIZE main.jmr_demo.otel_logs ZORDER BY (trace_id);
