from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from app.routers import services, traces, logs, metrics

app = FastAPI(
    title="ZeroBus Observability API",
    description="Real-time observability API for OpenTelemetry data",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(services.router, prefix="/api/services", tags=["services"])
app.include_router(traces.router, prefix="/api/traces", tags=["traces"])
app.include_router(logs.router, prefix="/api/logs", tags=["logs"])
app.include_router(metrics.router, prefix="/api/metrics", tags=["metrics"])


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


static_dir = os.path.join(os.path.dirname(__file__), "..", "static")
if os.path.exists(static_dir):
    app.mount("/assets", StaticFiles(directory=os.path.join(static_dir, "assets")), name="assets")
    
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        file_path = os.path.join(static_dir, full_path)
        if os.path.exists(file_path) and os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(static_dir, "index.html"))
