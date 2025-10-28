-- Vacuum old versions (retain 7 days)
-- Bronze: jmr_demo.zerobus_bronze.otel_*
VACUUM jmr_demo.zerobus_bronze.otel_spans RETAIN 168 HOURS;
VACUUM jmr_demo.zerobus_bronze.otel_metrics RETAIN 168 HOURS;
VACUUM jmr_demo.zerobus_bronze.otel_logs RETAIN 168 HOURS;
-- Silver: jmr_demo.zerobus_silver.*
VACUUM {{catalog_name}}.zerobus_silver.traces_silver RETAIN 168 HOURS;
VACUUM {{catalog_name}}.zerobus_silver.service_health_silver RETAIN 168 HOURS;
