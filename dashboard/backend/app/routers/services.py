from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from datetime import datetime, timedelta
from app.database import execute_query, get_table_name

router = APIRouter()


@router.get("")
async def get_all_services():
    query = f"""
    SELECT DISTINCT service_name
    FROM {get_table_name('service_health_silver')}
    ORDER BY service_name
    """
    try:
        results = execute_query(query)
        return {"services": [r["service_name"] for r in results]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{service_name}")
async def get_service_detail(service_name: str):
    query = f"""
    SELECT 
        service_name,
        error_rate,
        latency_p50_ms,
        latency_p95_ms,
        latency_p99_ms,
        request_count,
        timestamp
    FROM {get_table_name('service_health_silver')}
    WHERE service_name = :service_name
    ORDER BY timestamp DESC
    LIMIT 1
    """
    try:
        results = execute_query(query, {"service_name": service_name})
        if not results:
            raise HTTPException(status_code=404, detail=f"Service {service_name} not found")
        return results[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{service_name}/history")
async def get_service_history(
    service_name: str,
    window: str = Query("24h", regex="^(1h|6h|24h|7d)$")
):
    hours_map = {"1h": 1, "6h": 6, "24h": 24, "7d": 168}
    hours = hours_map[window]
    
    query = f"""
    SELECT 
        service_name,
        error_rate,
        latency_p50_ms,
        latency_p95_ms,
        latency_p99_ms,
        request_count,
        timestamp
    FROM {get_table_name('service_health_silver')}
    WHERE service_name = :service_name
        AND timestamp >= date_sub(now(), INTERVAL {hours} HOURS)
    ORDER BY timestamp ASC
    """
    try:
        results = execute_query(query, {"service_name": service_name})
        return {"service_name": service_name, "window": window, "data": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{service_name}/operations")
async def get_service_operations(service_name: str, limit: int = Query(10, ge=1, le=100)):
    query = f"""
    SELECT 
        span_name as operation_name,
        COUNT(*) as call_count,
        AVG(duration_ms) as avg_duration_ms,
        MAX(duration_ms) as max_duration_ms,
        SUM(CASE WHEN status_code = 'ERROR' THEN 1 ELSE 0 END) as error_count
    FROM {get_table_name('traces_silver')}
    WHERE service_name = :service_name
        AND timestamp >= date_sub(now(), INTERVAL 24 HOURS)
    GROUP BY span_name
    ORDER BY call_count DESC
    LIMIT {limit}
    """
    try:
        results = execute_query(query, {"service_name": service_name})
        return {"service_name": service_name, "operations": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
