# ZeroBus Observability Dashboard

React + FastAPI application for real-time observability of OpenTelemetry data in Databricks.

## Architecture

- **Backend**: FastAPI serving API endpoints and static files
- **Frontend**: React + TypeScript with Material-UI, Recharts, React Flow
- **Data Source**: Databricks SQL Warehouse querying `jmr_demo.zerobus.*` tables
- **Deployment**: Databricks App

## Project Structure

```
dashboard/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app
│   │   ├── config.py            # Configuration
│   │   ├── database.py          # Databricks SQL connector
│   │   └── routers/             # API endpoints
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── api/                 # API client
│   │   ├── components/          # React components
│   │   ├── pages/               # Page components
│   │   └── types/               # TypeScript types
│   ├── package.json
│   └── vite.config.ts
└── app.yaml                     # Databricks App config
```

## Local Development

### Prerequisites
- Python 3.11+
- Node.js 18+
- Databricks workspace access
- SQL Warehouse ID: 5067b513037fbf07

### Backend Setup

```bash
cd dashboard/backend
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install -r requirements.txt

# Set environment variables
export DATABRICKS_SERVER_HOSTNAME="your-workspace.cloud.databricks.com"
export DATABRICKS_HTTP_PATH="/sql/1.0/warehouses/5067b513037fbf07"
export DATABRICKS_TOKEN="your-token"

# Run backend
uvicorn app.main:app --reload --port 8000
```

Backend will be available at http://localhost:8000

### Frontend Setup

```bash
cd dashboard/frontend
npm install
npm run dev
```

Frontend dev server will be available at http://localhost:5173 with API proxy to backend.

## Building for Production

```bash
# Build frontend (outputs to backend/static/)
cd dashboard/frontend
npm run build

# Verify static files
ls -la ../backend/static/

# Test production build locally
cd ../backend
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Deployment to Databricks

### Deploy via Databricks CLI

```bash
cd dashboard
databricks apps deploy . --app-name zerobus-observability
```

### Monitor App

```bash
# View logs
databricks apps logs zerobus-observability

# Check status
databricks apps get zerobus-observability
```

## Features

### Dashboard
- System overview with aggregate metrics
- Service health summary table
- Auto-refresh every 30 seconds

### Services
- List all services with health indicators
- Click service → Service detail page
- Health badges: ✅ Healthy | ⚠️ Degraded | ❌ Critical

### Service Detail
- Current metrics (error rate, latency, request count)
- 24-hour time series charts
- Top operations by call count
- Auto-refresh every 30-60 seconds

### Dependency Map
- Interactive service dependency graph
- Node colors indicate health (green/yellow/red)
- Edge thickness = call volume
- Animated edges for critical services
- Auto-refresh every 30 seconds

### Traces
- List recent traces with filtering
- Click trace → Trace detail with spans
- Status indicators (OK/ERROR)
- Service filtering dropdown

### Logs
- Log viewer with filtering (service, severity)
- Trace correlation (click trace_id → view trace)
- Severity color coding
- Auto-refresh every 30 seconds

## API Endpoints

### Services
- `GET /api/services` - List all services
- `GET /api/services/{name}` - Get service health
- `GET /api/services/{name}/history?window=24h` - Get time series
- `GET /api/services/{name}/operations` - Get top operations

### Traces
- `GET /api/traces` - List traces
- `GET /api/traces/{trace_id}` - Get trace spans
- `GET /api/traces/dependencies/graph` - Get dependency graph

### Logs
- `GET /api/logs` - List logs with filters
- `GET /api/logs/trace/{trace_id}` - Get logs by trace

### Metrics
- `GET /api/metrics/{service_name}` - Get metrics for service
- `GET /api/metrics/{service_name}/names` - Get available metric names

## Configuration

### Environment Variables (app.yaml)
- `DATABRICKS_SERVER_HOSTNAME` - Workspace hostname
- `DATABRICKS_HTTP_PATH` - SQL Warehouse HTTP path
- `DATABRICKS_TOKEN` - Access token from secrets

### Data Sources
All data from `jmr_demo.zerobus` schema:
- `traces_silver` - Trace spans
- `logs_silver` - Log entries
- `metrics_silver` - Metrics
- `service_health_silver` - Service health computed metrics
- `service_dependencies_gold` - Service call graph

## Troubleshooting

### Backend Issues
- Check SQL Warehouse is running
- Verify access token has permissions
- Check table/schema names in queries

### Frontend Issues
- Clear browser cache
- Check API proxy configuration in vite.config.ts
- Verify static files built correctly

### Deployment Issues
- Check app.yaml syntax
- Verify secret `app.token` exists
- Check warehouse permissions in resources section
