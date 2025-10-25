-- Optimize Silver Tables
OPTIMIZE {{catalog_name}}.silver.traces_silver ZORDER BY (trace_id);
OPTIMIZE {{catalog_name}}.silver.service_health_silver ZORDER BY (service_name, timestamp);
OPTIMIZE {{catalog_name}}.silver.logs_silver ZORDER BY (trace_id, timestamp);
