from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from app.database import execute_query, get_table_name

router = APIRouter()


@router.get("")
async def get_logs(
    service_name: Optional[str] = None,
    severity_text: Optional[str] = None,
    trace_id: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    where_clauses = []
    params = {}
    
    if service_name:
        where_clauses.append("service_name = :service_name")
        params["service_name"] = service_name
    
    if severity_text:
        where_clauses.append("severity_text = :severity_text")
        params["severity_text"] = severity_text
    
    if trace_id:
        where_clauses.append("trace_id = :trace_id")
        params["trace_id"] = trace_id
    
    where_clause = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""
    
    query = f"""
    SELECT 
        timestamp,
        service_name,
        severity_text,
        severity_number,
        body,
        trace_id,
        span_id,
        attributes
    FROM {get_table_name('logs_silver')}
    {where_clause}
    ORDER BY timestamp DESC
    LIMIT {limit} OFFSET {offset}
    """
    try:
        results = execute_query(query, params)
        return {"logs": results, "limit": limit, "offset": offset}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trace/{trace_id}")
async def get_logs_by_trace(trace_id: str):
    query = f"""
    SELECT 
        timestamp,
        service_name,
        severity_text,
        severity_number,
        body,
        trace_id,
        span_id,
        attributes
    FROM {get_table_name('logs_silver')}
    WHERE trace_id = :trace_id
    ORDER BY timestamp ASC
    """
    try:
        results = execute_query(query, {"trace_id": trace_id})
        return {"trace_id": trace_id, "logs": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
