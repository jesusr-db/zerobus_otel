from databricks import sql
from typing import List, Dict, Any, Optional
from contextlib import contextmanager
from app.config import settings
import os


@contextmanager
def get_connection():
    token = os.getenv('DATABRICKS_TOKEN') or settings.databricks_token
    
    conn = sql.connect(
        server_hostname=settings.databricks_server_hostname,
        http_path=settings.databricks_http_path,
        access_token=token
    )
    try:
        yield conn
    finally:
        conn.close()


def execute_query(query: str, parameters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query, parameters or {})
            columns = [desc[0] for desc in cursor.description]
            results = cursor.fetchall()
            return [dict(zip(columns, row)) for row in results]


def get_table_name(table: str) -> str:
    return f"{settings.catalog_name}.{settings.schema_name}.{table}"
