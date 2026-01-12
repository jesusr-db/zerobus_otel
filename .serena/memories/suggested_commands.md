# Suggested Commands

## Setup & Validation
```bash
# Install dependencies and configure environment
make setup

# Validate bundle configuration before deployment
make validate
```

## Deployment Commands
```bash
# Deploy to development environment (default)
make deploy-dev

# Deploy to staging environment
make deploy-staging

# Deploy to production (with confirmation prompt)
make deploy-prod

# Using Databricks CLI directly
databricks bundle deploy -t dev
databricks bundle validate -t dev
```

## Operations Commands
```bash
# Run bronze data loader job (on-demand)
make run-loader
# Or: databricks bundle run bronze_data_loader -t dev

# Run silver transformations (every 5 min when scheduled)
make run-silver
# Or: databricks bundle run silver_transformations -t dev

# Run gold aggregations (hourly when scheduled)
make run-gold
# Or: databricks bundle run gold_aggregations -t dev

# Run data quality validation (daily when scheduled)
make run-quality
# Or: databricks bundle run data_quality_validation -t dev

# Run table maintenance (weekly when scheduled)
make optimize
# Or: databricks bundle run table_maintenance -t dev
```

## Monitoring & Debugging
```bash
# View recent job logs and resource status
make logs
# Or: databricks bundle resources -t dev

# Check bundle resources
databricks bundle resources -t dev
```

## Maintenance Commands
```bash
# Clean deployment artifacts (.bundle, .databricks)
make clean

# Destroy all resources in dev (DESTRUCTIVE - requires confirmation)
make destroy
# Or: databricks bundle destroy -t dev --auto-approve
```

## Development Helpers
```bash
# Format Python code with black
make fmt

# Lint Python code with pylint
make lint

# Run local tests (if pytest is set up)
make test-local

# Sync notebooks to workspace
make notebook-sync
```

## Git Workflow
```bash
# Check current status and branch
git status
git branch

# Create feature branch
git checkout -b feature/my-feature

# Commit changes
git add .
git commit -m "Description of changes"

# Push to remote
git push origin feature/my-feature
```

## Darwin/macOS Specific
Note: This project runs on Darwin (macOS), so standard Unix commands apply:
- `ls`: List files
- `cd`: Change directory
- `grep`: Search text
- `find`: Find files
- `cat`: Display file contents
- `tail`: View end of file (e.g., `tail -f logs/app.log`)
