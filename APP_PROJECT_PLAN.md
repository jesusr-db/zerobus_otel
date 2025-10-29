# ZeroBus Observability App - Implementation Plan

## Overview

React frontend + FastAPI backend Databricks App for real-time observability of OpenTelemetry data.

**Data Source**: `jmr_demo.zerobus.*` tables (traces, logs, metrics, service_health)  
**Architecture**: FastAPI backend serves React SPA, queries Databricks SQL Warehouse  
**Reference**: https://apps-cookbook.dev/docs/fastapi/getting_started/create

---

## Phase 1: Project Setup

### Directory Structure
```
dashboard/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI app entrypoint
│   │   ├── config.py            # Config & env vars
│   │   ├── database.py          # Databricks SQL connector
│   │   └── routers/
│   │       ├── __init__.py
│   │       ├── services.py      # Service health endpoints
│   │       ├── traces.py        # Trace/span endpoints
│   │       ├── logs.py          # Log endpoints
│   │       └── metrics.py       # Metric endpoints
│   └── requirements.txt
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── index.html
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── api/                 # API client
│       ├── components/          # Reusable components
│       ├── pages/               # Page components
│       └── types/               # TypeScript types
└── app.yaml                     # Databricks App config
```

### Key Dependencies

**Backend (requirements.txt)**:
- fastapi
- uvicorn[standard]
- databricks-sql-connector
- pydantic
- python-dotenv

**Frontend (package.json)**:
- react + react-dom
- @mui/material + @emotion/react + @emotion/styled
- recharts
- reactflow
- @tanstack/react-query
- axios
- vite + @vitejs/plugin-react

---

## Phase 2: Backend API Development

### FastAPI Application Structure

**main.py** - App initialization with CORS, static file serving
```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from app.routers import services, traces, logs, metrics

app = FastAPI(title="ZeroBus Observability API")

# CORS for development
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"])

# API routes
app.include_router(services.router, prefix="/api/services", tags=["services"])
app.include_router(traces.router, prefix="/api/traces", tags=["traces"])
app.include_router(logs.router, prefix="/api/logs", tags=["logs"])
app.include_router(metrics.router, prefix="/api/metrics", tags=["metrics"])

# Serve React static files
app.mount("/", StaticFiles(directory="static", html=True), name="static")
```

**database.py** - Databricks SQL connection management
```python
from databricks import sql
import os

def get_connection():
    return sql.connect(
        server_hostname=os.getenv("DATABRICKS_SERVER_HOSTNAME"),
        http_path=os.getenv("DATABRICKS_HTTP_PATH"),
        access_token=os.getenv("DATABRICKS_TOKEN")
    )

def execute_query(query: str, params: dict = None):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query, params or {})
            return cursor.fetchall()
```

### API Endpoints

#### 1. Services Router (`/api/services`)

**GET /api/services**
- Query: `SELECT DISTINCT service_name FROM jmr_demo.zerobus.service_health_silver ORDER BY service_name`
- Returns: List of all service names

**GET /api/services/{service_name}**
- Query: Latest service health metrics from `service_health_silver`
- Returns: error_rate, latency_p50/p95/p99, request_count, timestamp

**GET /api/services/{service_name}/history**
- Query: Service health time series (last 24h) from `service_health_silver`
- Parameters: window (1h, 6h, 24h, 7d)
- Returns: Time series data for charts

#### 2. Traces Router (`/api/traces`)

**GET /api/traces**
- Query: Recent traces from `traces_silver` with service, operation, duration, status
- Parameters: service_name (filter), limit (default 100), offset (pagination)
- Returns: Trace list with basic metadata

**GET /api/traces/{trace_id}**
- Query: All spans for trace_id from `traces_silver`
- Returns: Complete trace with all spans, parent-child relationships

**GET /api/traces/dependencies**
- Query: Service-to-service calls from `service_dependencies_gold`
- Returns: Graph data (nodes: services, edges: calls with count/latency)

#### 3. Logs Router (`/api/logs`)

**GET /api/logs**
- Query: Recent logs from `logs_silver`
- Parameters: service_name, severity_text, time_range, limit
- Returns: Log entries with timestamp, severity, body, trace_id

**GET /api/logs/trace/{trace_id}**
- Query: Logs correlated to trace_id
- Returns: Logs matching trace_id

#### 4. Metrics Router (`/api/metrics`)

**GET /api/metrics/{service_name}**
- Query: Metrics for service from `metrics_silver`
- Parameters: metric_name, time_range
- Returns: Metric time series data

---

## Phase 3: Frontend Development

### Page Components

#### 1. Dashboard (`pages/Dashboard.tsx`)
- System overview: total services, total requests, avg error rate, avg latency
- Service health summary table (all services with latest metrics)
- Recent anomalies (from `anomaly_baselines_gold`)
- Quick links to services, dependency map, traces

#### 2. Services List (`pages/Services.tsx`)
- Table with all services + health indicators
- Columns: Service Name, Error Rate, P95 Latency, Request Count, Status (✅/⚠️/❌)
- Click → Navigate to Service Detail

#### 3. Service Detail (`pages/ServiceDetail.tsx`)
- Service health charts (error rate, latency percentiles, request count over time)
- Recent traces for service
- Recent logs for service
- Top operations (by count, by latency)

#### 4. Dependency Map (`pages/DependencyMap.tsx`)
- React Flow graph visualization
- Nodes: Services with health color coding (green/yellow/red)
- Edges: Service calls with thickness = call count, color = health
- Click node → Show service health panel
- Click edge → Show call details (count, latency, error rate)
- Live updates via polling

#### 5. Traces (`pages/Traces.tsx`)
- Trace search/filter UI
- Trace list with duration, status, service, operation
- Click trace → Trace detail with waterfall view
- Span timeline visualization

#### 6. Logs (`pages/Logs.tsx`)
- Log viewer with filtering (service, severity, time range)
- Real-time log streaming (polling)
- Trace correlation (click trace_id → view trace)

### Component Architecture

**API Client (`api/client.ts`)**
```typescript
import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
});

export const servicesApi = {
  getAll: () => api.get('/services'),
  getDetail: (name: string) => api.get(`/services/${name}`),
  getHistory: (name: string, window: string) => api.get(`/services/${name}/history`, { params: { window } }),
};

export const tracesApi = {
  getAll: (params: any) => api.get('/traces', { params }),
  getDetail: (traceId: string) => api.get(`/traces/${traceId}`),
  getDependencies: () => api.get('/traces/dependencies'),
};

// ... similar for logs, metrics
```

**Reusable Components**
- `ServiceHealthBadge`: Color-coded health indicator (✅/⚠️/❌)
- `LatencyChart`: Recharts line chart for latency time series
- `ErrorRateChart`: Recharts area chart for error rates
- `TraceWaterfall`: Span timeline with parent-child visualization
- `LogViewer`: Virtualized log list with syntax highlighting
- `DependencyGraph`: React Flow wrapper with custom nodes/edges

---

## Phase 4: Visualization & Real-time Updates

### Dependency Map Implementation

**React Flow Setup**
```typescript
import ReactFlow, { Node, Edge } from 'reactflow';

// Node: Service with health color
const nodes: Node[] = services.map(svc => ({
  id: svc.service_name,
  data: { 
    label: svc.service_name, 
    health: svc.error_rate > 5 ? 'error' : svc.error_rate > 1 ? 'warning' : 'success',
    errorRate: svc.error_rate,
    latency: svc.latency_p95_ms,
  },
  position: { x: 0, y: 0 }, // auto-layout with dagre
  type: 'serviceNode', // custom node component
}));

// Edge: Service call
const edges: Edge[] = dependencies.map(dep => ({
  id: `${dep.source_service}-${dep.target_service}`,
  source: dep.source_service,
  target: dep.target_service,
  label: `${dep.call_count} calls`,
  style: { strokeWidth: Math.min(dep.call_count / 100, 10) },
  animated: dep.error_rate > 5,
}));
```

### Live Updates Strategy

**Polling with React Query**
```typescript
import { useQuery } from '@tanstack/react-query';

// Auto-refresh every 30 seconds
const { data: services } = useQuery({
  queryKey: ['services'],
  queryFn: () => servicesApi.getAll(),
  refetchInterval: 30000,
});
```

**Real-time Indicators**
- Green dot: healthy (error_rate < 1%)
- Yellow dot: degraded (1% <= error_rate < 5%)
- Red dot: critical (error_rate >= 5%)
- Pulsing animation for active anomalies

---

## Phase 5: Databricks App Configuration

### app.yaml Structure
```yaml
command:
  - uvicorn
  - app.main:app
  - --host
  - "0.0.0.0"
  - --port
  - "8000"

resources:
  - name: warehouse
    sql_warehouse:
      id: 5067b513037fbf07
      permission: CAN_USE

env:
  - name: DATABRICKS_SERVER_HOSTNAME
    value: {{workspace.host}}
  - name: DATABRICKS_HTTP_PATH
    value: /sql/1.0/warehouses/5067b513037fbf07
  - name: DATABRICKS_TOKEN
    value: {{secrets.app.token}}
```

### Build Process

**React Build Script (frontend/package.json)**
```json
{
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview"
  }
}
```

**Vite Config (frontend/vite.config.ts)**
```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: '../backend/static',
    emptyOutDir: true,
  }
})
```

**Deployment Flow**
1. Build frontend: `cd frontend && npm run build` → outputs to `backend/static/`
2. Package backend: Backend serves FastAPI routes + static files
3. Deploy: `databricks apps deploy dashboard --app-name zerobus-observability`

---

## Phase 6: Testing & Deployment

### Local Development

**Terminal 1 - Backend**
```bash
cd dashboard/backend
export DATABRICKS_SERVER_HOSTNAME="..."
export DATABRICKS_HTTP_PATH="/sql/1.0/warehouses/5067b513037fbf07"
export DATABRICKS_TOKEN="..."
uvicorn app.main:app --reload --port 8000
```

**Terminal 2 - Frontend**
```bash
cd dashboard/frontend
npm run dev  # Vite dev server on port 5173, proxies /api to backend
```

### Testing Checklist

**Backend API**
- [ ] All endpoints return valid JSON
- [ ] Query parameters work correctly
- [ ] Error handling (invalid service names, trace IDs)
- [ ] Performance (queries complete < 5s)

**Frontend**
- [ ] All pages load without errors
- [ ] Charts render with real data
- [ ] Dependency map displays correctly
- [ ] Real-time updates work (polling)
- [ ] Navigation between pages works

**Integration**
- [ ] API calls succeed from frontend
- [ ] Data displays correctly in UI
- [ ] Error states handled gracefully
- [ ] Loading states show appropriately

### Deployment to Databricks

**Steps**
1. Build frontend: `cd frontend && npm run build`
2. Verify static files: `ls -la backend/static/`
3. Deploy app: `databricks apps deploy dashboard --app-name zerobus-observability`
4. Test in workspace: Click app URL → Verify all pages work
5. Monitor logs: `databricks apps logs zerobus-observability`

**Post-Deployment Validation**
- [ ] App accessible via Databricks workspace URL
- [ ] All API endpoints respond correctly
- [ ] Warehouse permissions configured
- [ ] Authentication works (token from secrets)
- [ ] Static files served correctly

---

## Success Criteria

✅ **Functional**
- View service health for all services
- Interactive dependency map with live health indicators
- Trace viewer with waterfall visualization
- Log viewer with trace correlation
- Real-time updates via polling

✅ **Performance**
- Page load < 3s
- API responses < 5s
- Smooth animations and interactions

✅ **Quality**
- TypeScript type safety
- Error handling throughout
- Loading states for async operations
- Responsive design (desktop-first)

✅ **Deployment**
- Deployed as Databricks App
- Accessible to authorized users
- Logs and monitoring configured
