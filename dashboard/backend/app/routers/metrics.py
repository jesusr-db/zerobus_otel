from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from app.database import execute_query, get_table_name

router = APIRouter()


@router.get("/{service_name}")
async def get_service_metrics(
    service_name: str,
    metric_name: Optional[str] = None,
    window: str = Query("1h", regex="^(1h|6h|24h|7d)$")
):
    hours_map = {"1h": 1, "6h": 6, "24h": 24, "7d": 168}
    hours = hours_map[window]
    
    where_clauses = ["service_name = :service_name"]
    params = {"service_name": service_name}
    
    if metric_name:
        where_clauses.append("metric_name = :metric_name")
        params["metric_name"] = metric_name
    
    where_clause = " AND ".join(where_clauses)
    
    query = f"""
    SELECT 
        service_name,
        metric_name,
        metric_type,
        value,
        unit,
        timestamp,
        attributes
    FROM {get_table_name('metrics_silver')}
    WHERE {where_clause}
        AND timestamp >= date_sub(now(), INTERVAL {hours} HOURS)
    ORDER BY timestamp ASC
    """
    try:
        results = execute_query(query, params)
        return {"service_name": service_name, "window": window, "metrics": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{service_name}/names")
async def get_metric_names(service_name: str):
    query = f"""
    SELECT DISTINCT metric_name
    FROM {get_table_name('metrics_silver')}
    WHERE service_name = :service_name
    ORDER BY metric_name
    """
    try:
        results = execute_query(query, {"service_name": service_name})
        return {"service_name": service_name, "metric_names": [r["metric_name"] for r in results]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
