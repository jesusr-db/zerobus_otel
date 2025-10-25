-- Vacuum old versions (retain 7 days)
-- Bronze: main.jmr_demo.otel_*
VACUUM main.jmr_demo.otel_spans RETAIN 168 HOURS;
VACUUM main.jmr_demo.otel_metrics RETAIN 168 HOURS;
VACUUM main.jmr_demo.otel_logs RETAIN 168 HOURS;
-- Silver: observability_poc_dev.silver.*
VACUUM {{catalog_name}}.silver.traces_silver RETAIN 168 HOURS;
VACUUM {{catalog_name}}.silver.service_health_silver RETAIN 168 HOURS;
