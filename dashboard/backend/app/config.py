from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    databricks_server_hostname: str
    databricks_http_path: str
    databricks_token: Optional[str] = None
    catalog_name: str = "jmr_demo"
    schema_name: str = "zerobus"
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
