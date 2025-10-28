-- Optimize Silver Tables
OPTIMIZE {{catalog_name}}.zerobus_silver.traces_silver ZORDER BY (trace_id);
OPTIMIZE {{catalog_name}}.zerobus_silver.service_health_silver ZORDER BY (service_name, timestamp);
OPTIMIZE {{catalog_name}}.zerobus_silver.logs_silver ZORDER BY (trace_id, timestamp);
