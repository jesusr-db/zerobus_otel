# Databricks notebook source
"""
Alerting: Detect Anomalies
Compares current service health against baselines and triggers alerts
"""

from pyspark.sql.functions import *
import requests
import json

dbutils.widgets.text("catalog_name", "observability_poc", "Catalog Name")
dbutils.widgets.text("webhook_url", "", "Alert Webhook URL")
dbutils.widgets.text("lookback_minutes", "2", "Lookback Minutes")

catalog_name = dbutils.widgets.get("catalog_name")
webhook_url = dbutils.widgets.get("webhook_url")
lookback_minutes = int(dbutils.widgets.get("lookback_minutes"))

service_health_table = f"{catalog_name}.zerobus_silver.service_health_silver"
baselines_table = f"{catalog_name}.jmr_demo.anomaly_baselines"

recent_health = spark.table(service_health_table).filter(
    col("timestamp") >= current_timestamp() - expr(f"INTERVAL {lookback_minutes} MINUTES")
)

baselines = spark.table(baselines_table)

anomalies = (
    recent_health
    .join(baselines, "service_name")
    .filter(
        (col("error_rate") > col("error_rate_threshold")) |
        (col("p95_latency_ms") > col("latency_threshold"))
    )
    .select(
        "service_name",
        "timestamp",
        "error_rate",
        "error_rate_threshold",
        "p95_latency_ms",
        "latency_threshold"
    )
)

anomaly_count = anomalies.count()

if anomaly_count > 0 and webhook_url:
    anomalies_list = anomalies.collect()
    for anomaly in anomalies_list:
        alert_payload = {
            "service": anomaly.service_name,
            "timestamp": str(anomaly.timestamp),
            "error_rate": float(anomaly.error_rate),
            "error_threshold": float(anomaly.error_rate_threshold),
            "p95_latency": float(anomaly.p95_latency_ms),
            "latency_threshold": float(anomaly.latency_threshold)
        }
        try:
            requests.post(webhook_url, json=alert_payload, timeout=5)
        except Exception as e:
            print(f"⚠️ Failed to send alert for {anomaly.service_name}: {str(e)}")

print(f"✅ Anomaly detection completed: {anomaly_count} anomalies detected")
