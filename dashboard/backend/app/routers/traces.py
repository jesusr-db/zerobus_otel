from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from app.database import execute_query, get_table_name

router = APIRouter()


@router.get("")
async def get_traces(
    service_name: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    where_clause = "WHERE service_name = :service_name" if service_name else ""
    params = {"service_name": service_name} if service_name else {}
    
    query = f"""
    SELECT 
        trace_id,
        service_name,
        span_name as operation_name,
        duration_ms,
        status_code,
        timestamp
    FROM {get_table_name('traces_silver')}
    {where_clause}
    ORDER BY timestamp DESC
    LIMIT {limit} OFFSET {offset}
    """
    try:
        results = execute_query(query, params)
        return {"traces": results, "limit": limit, "offset": offset}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{trace_id}")
async def get_trace_detail(trace_id: str):
    query = f"""
    SELECT 
        trace_id,
        span_id,
        parent_span_id,
        service_name,
        span_name,
        span_kind,
        start_timestamp,
        end_timestamp,
        duration_ms,
        status_code,
        status_message,
        attributes
    FROM {get_table_name('traces_silver')}
    WHERE trace_id = :trace_id
    ORDER BY start_timestamp ASC
    """
    try:
        results = execute_query(query, {"trace_id": trace_id})
        if not results:
            raise HTTPException(status_code=404, detail=f"Trace {trace_id} not found")
        return {"trace_id": trace_id, "spans": results}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dependencies/graph")
async def get_dependencies():
    query = f"""
    SELECT 
        source_service,
        target_service,
        call_count,
        avg_latency_ms,
        error_count,
        error_rate
    FROM {get_table_name('service_dependencies_gold')}
    WHERE window_start >= date_sub(now(), INTERVAL 1 HOUR)
    """
    try:
        results = execute_query(query)
        
        services = set()
        for row in results:
            services.add(row["source_service"])
            services.add(row["target_service"])
        
        service_health_query = f"""
        SELECT 
            service_name,
            error_rate,
            latency_p95_ms,
            request_count
        FROM {get_table_name('service_health_silver')}
        WHERE service_name IN ({','.join([f"'{s}'" for s in services])})
        ORDER BY timestamp DESC
        """
        
        health_results = execute_query(service_health_query)
        health_by_service = {r["service_name"]: r for r in health_results}
        
        nodes = [
            {
                "id": service,
                "label": service,
                "error_rate": health_by_service.get(service, {}).get("error_rate", 0),
                "latency_p95": health_by_service.get(service, {}).get("latency_p95_ms", 0),
                "request_count": health_by_service.get(service, {}).get("request_count", 0),
            }
            for service in services
        ]
        
        edges = [
            {
                "source": row["source_service"],
                "target": row["target_service"],
                "call_count": row["call_count"],
                "avg_latency_ms": row["avg_latency_ms"],
                "error_count": row["error_count"],
                "error_rate": row["error_rate"],
            }
            for row in results
        ]
        
        return {"nodes": nodes, "edges": edges}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
