# Makefile for Databricks Observability Platform
# Quick commands for common operations

.PHONY: help validate deploy-dev deploy-staging deploy-prod run-loader clean diagnose

help:
	@echo "Databricks Observability Platform - Available Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make setup          - Install dependencies and configure environment"
	@echo "  make validate       - Validate bundle configuration"
	@echo ""
	@echo "Deployment:"
	@echo "  make deploy-dev     - Deploy to development environment"
	@echo "  make deploy-staging - Deploy to staging environment"
	@echo "  make deploy-prod    - Deploy to production environment"
	@echo ""
	@echo "Operations:"
	@echo "  make run-loader     - Run bronze data loader job (dev)"
	@echo "  make run-silver     - Run silver transformations job (dev)"
	@echo "  make run-quality    - Run data quality validation (dev)"
	@echo "  make logs           - View recent job logs"
	@echo ""
	@echo "Diagnostics:"
	@echo "  make diagnose           - Show diagnostic command help"
	@echo "  make diagnose-job       - Diagnose job by name (JOB=name)"
	@echo "  make diagnose-pipeline  - Diagnose pipeline by name (PIPELINE=name)"
	@echo "  make diagnose-table     - Check table health (TABLE=catalog.schema.table)"
	@echo "  make check-pipelines    - Check all pipeline statuses"
	@echo "  make check-jobs         - Check all job statuses"
	@echo "  make check-tables       - Check all table freshness"
	@echo ""
	@echo "Maintenance:"
	@echo "  make optimize       - Run table optimization (dev)"
	@echo "  make clean          - Clean deployment artifacts"
	@echo "  make destroy        - Destroy all resources (WARNING: dev only)"

setup:
	@echo "Setting up environment..."
	@pip install databricks-cli
	@if [ ! -f .env ]; then \
		cp .env.template .env; \
		echo "✓ Created .env file - please edit with your credentials"; \
	fi
	@echo "✓ Setup complete"

validate:
	@echo "Validating bundle configuration..."
	@databricks bundle validate -t dev
	@echo "✓ Validation successful"

deploy-dev:
	@echo "Deploying to dev environment..."
	@databricks bundle deploy -t dev
	@echo "✓ Deployment complete"
	@echo ""
	@echo "Next steps:"
	@echo "  make run-loader    - Load sample data"
	@echo "  make logs          - View job logs"

deploy-staging:
	@echo "Deploying to staging environment..."
	@databricks bundle deploy -t staging
	@echo "✓ Deployment complete"

deploy-prod:
	@echo "⚠️  WARNING: Deploying to PRODUCTION"
	@read -p "Are you sure? (yes/no): " confirm; \
	if [ "$$confirm" = "yes" ]; then \
		databricks bundle deploy -t prod; \
		echo "✓ Production deployment complete"; \
	else \
		echo "Cancelled"; \
	fi

run-loader:
	@echo "Running bronze data loader..."
	@databricks bundle run bronze_data_loader -t dev

run-silver:
	@echo "Running silver transformations..."
	@databricks bundle run silver_transformations -t dev

run-gold:
	@echo "Running gold aggregations..."
	@databricks bundle run gold_aggregations -t dev

run-quality:
	@echo "Running data quality validation..."
	@databricks bundle run data_quality_validation -t dev

optimize:
	@echo "Running table maintenance..."
	@databricks bundle run table_maintenance -t dev

logs:
	@echo "Fetching recent job logs..."
	@databricks bundle resources -t dev

clean:
	@echo "Cleaning deployment artifacts..."
	@rm -rf .bundle
	@rm -rf .databricks
	@echo "✓ Clean complete"

destroy:
	@echo "⚠️  WARNING: This will DELETE all resources in dev environment"
	@read -p "Are you sure? Type 'yes' to confirm: " confirm; \
	if [ "$$confirm" = "yes" ]; then \
		databricks bundle destroy -t dev --auto-approve; \
		echo "✓ Resources destroyed"; \
	else \
		echo "Cancelled"; \
	fi

# Development helpers
notebook-sync:
	@echo "Syncing notebooks to workspace..."
	@databricks sync ./src/notebooks /Workspace/Users/$(USER)/observability-poc

test-local:
	@echo "Running local tests..."
	@python -m pytest tests/

fmt:
	@echo "Formatting Python code..."
	@black src/
	@echo "✓ Code formatted"

lint:
	@echo "Linting Python code..."
	@pylint src/
	@echo "✓ Linting complete"

# Diagnostic helpers
diagnose:
	@echo "Databricks Diagnostics CLI Helper"
	@echo ""
	@echo "Quick diagnostic commands using Databricks CLI"
	@echo ""
	@echo "Usage Examples:"
	@echo "  make diagnose-job JOB=gold_aggregations        - Diagnose specific job"
	@echo "  make diagnose-pipeline PIPELINE=silver_stream - Diagnose specific pipeline"
	@echo "  make diagnose-table TABLE=jmr_demo.zerobus.traces_silver - Check table health"
	@echo ""
	@echo "Environment Variables:"
	@echo "  PROFILE     - Databricks CLI profile (default: DEFAULT)"
	@echo "  CATALOG     - Default catalog (default: jmr_demo)"
	@echo "  SCHEMA      - Default schema (default: zerobus_sdp for dev)"
	@echo ""
	@echo "For comprehensive troubleshooting workflows, see:"
	@echo "  - claudedocs/databricks_cli_reference.md"
	@echo "  - claudedocs/databricks_troubleshooting_guide.md"
	@echo "  - claudedocs/databricks_common_errors.md"

PROFILE ?= DEFAULT
CATALOG ?= jmr_demo
SCHEMA ?= zerobus_sdp

diagnose-job:
	@if [ -z "$(JOB)" ]; then \
		echo "Error: JOB parameter required"; \
		echo "Usage: make diagnose-job JOB=job_name"; \
		exit 1; \
	fi
	@echo "Diagnosing job: $(JOB)"
	@echo ""
	@echo "=== Finding Job ==="
	@JOB_JSON=$$(databricks jobs list --profile $(PROFILE) --output json | \
		jq ".jobs[] | select(.settings.name | contains(\"$(JOB)\"))"); \
	if [ -z "$$JOB_JSON" ]; then \
		echo "❌ Job not found: $(JOB)"; \
		echo "Available jobs:"; \
		databricks jobs list --profile $(PROFILE) | head -20; \
		exit 1; \
	fi; \
	JOB_ID=$$(echo "$$JOB_JSON" | jq -r ".job_id"); \
	echo "✓ Found job ID: $$JOB_ID"; \
	echo ""; \
	echo "=== Recent Runs (Last 5) ==="; \
	databricks jobs runs list --job-id $$JOB_ID --limit 5 --profile $(PROFILE) --output json | \
		jq -r ".runs[] | \"\(.run_id)\t\(.state.result_state // \"RUNNING\")\t\(.start_time / 1000 | strftime(\"%Y-%m-%d %H:%M:%S\"))\"" | \
		column -t -s$$'\t' -N "RUN_ID,STATE,START_TIME"; \
	echo ""; \
	echo "=== Latest Failed Run Details ==="; \
	FAILED_RUN=$$(databricks jobs runs list --job-id $$JOB_ID --limit 10 --profile $(PROFILE) --output json | \
		jq -r ".runs[] | select(.state.result_state==\"FAILED\") | .run_id" | head -1); \
	if [ -n "$$FAILED_RUN" ]; then \
		echo "Getting error details for run: $$FAILED_RUN"; \
		databricks jobs runs get-output --run-id $$FAILED_RUN --profile $(PROFILE) --output json | \
			jq -r ".error // \"No error message available\""; \
	else \
		echo "No failed runs found in last 10 runs"; \
	fi; \
	echo ""; \
	echo "For detailed investigation, run:"; \
	echo "  databricks jobs runs get-output --run-id <run_id> --profile $(PROFILE)"

diagnose-pipeline:
	@if [ -z "$(PIPELINE)" ]; then \
		echo "Error: PIPELINE parameter required"; \
		echo "Usage: make diagnose-pipeline PIPELINE=pipeline_name"; \
		exit 1; \
	fi
	@echo "Diagnosing pipeline: $(PIPELINE)"
	@echo ""
	@echo "=== Finding Pipeline ==="
	@PIPELINE_JSON=$$(databricks pipelines list --profile $(PROFILE) --output json | \
		jq ".statuses[] | select(.name | contains(\"$(PIPELINE)\"))"); \
	if [ -z "$$PIPELINE_JSON" ]; then \
		echo "❌ Pipeline not found: $(PIPELINE)"; \
		echo "Available pipelines:"; \
		databricks pipelines list --profile $(PROFILE) | head -20; \
		exit 1; \
	fi; \
	PIPELINE_ID=$$(echo "$$PIPELINE_JSON" | jq -r ".pipeline_id"); \
	echo "✓ Found pipeline ID: $$PIPELINE_ID"; \
	echo ""; \
	echo "=== Pipeline Status ==="; \
	databricks pipelines get --pipeline-id $$PIPELINE_ID --profile $(PROFILE) --output json | \
		jq "{state: .state, health: .health, latest_update: .latest_updates[0].state}"; \
	echo ""; \
	echo "=== Recent Updates (Last 5) ==="; \
	databricks pipelines list-updates --pipeline-id $$PIPELINE_ID --max-results 5 --profile $(PROFILE) --output json | \
		jq -r ".updates[] | \"\(.update_id)\t\(.state)\t\(.update_info.start_time / 1000 | strftime(\"%Y-%m-%d %H:%M:%S\"))\"" | \
		column -t -s$$'\t' -N "UPDATE_ID,STATE,START_TIME" || true; \
	echo ""; \
	echo "=== Recent Error Events ==="; \
	databricks api GET /api/2.0/pipelines/$$PIPELINE_ID/events --profile $(PROFILE) | \
		jq -r ".events[] | select(.level==\"ERROR\") | \"\(.timestamp)\t\(.message)\"" | \
		head -10 | column -t -s$$'\t' -N "TIMESTAMP,ERROR_MESSAGE" || echo "No recent errors"; \
	echo ""; \
	echo "For detailed investigation, run:"; \
	echo "  databricks api GET /api/2.0/pipelines/$$PIPELINE_ID/events --profile $(PROFILE) | jq '.events[] | select(.level==\"ERROR\")'"

diagnose-table:
	@if [ -z "$(TABLE)" ]; then \
		echo "Error: TABLE parameter required"; \
		echo "Usage: make diagnose-table TABLE=catalog.schema.table"; \
		exit 1; \
	fi
	@echo "Diagnosing table: $(TABLE)"
	@echo ""
	@echo "=== Table Existence ==="
	@if databricks sql --query "SELECT 1 FROM $(TABLE) LIMIT 1" --profile $(PROFILE) > /dev/null 2>&1; then \
		echo "✓ Table exists and is accessible"; \
	else \
		echo "❌ Cannot access table - check name and permissions"; \
		exit 1; \
	fi
	@echo ""
	@echo "=== Table Schema ==="
	@databricks sql --query "DESCRIBE $(TABLE)" --profile $(PROFILE) | head -20
	@echo ""
	@echo "=== Row Count & Freshness ==="
	@TABLE_PARTS=$$(echo "$(TABLE)" | tr '.' '\n'); \
	CATALOG=$$(echo "$$TABLE_PARTS" | sed -n '1p'); \
	SCHEMA=$$(echo "$$TABLE_PARTS" | sed -n '2p'); \
	TABLE_NAME=$$(echo "$$TABLE_PARTS" | sed -n '3p'); \
	TIMESTAMP_COL=$$(databricks sql --query "DESCRIBE $(TABLE)" --profile $(PROFILE) | \
		grep -E "timestamp|time|date" | head -1 | awk '{print $$1}'); \
	if [ -n "$$TIMESTAMP_COL" ]; then \
		echo "Using timestamp column: $$TIMESTAMP_COL"; \
		databricks sql --query "SELECT COUNT(*) as row_count, MAX($$TIMESTAMP_COL) as latest_record FROM $(TABLE)" --profile $(PROFILE); \
	else \
		databricks sql --query "SELECT COUNT(*) as row_count FROM $(TABLE)" --profile $(PROFILE); \
	fi
	@echo ""
	@echo "=== Null Checks (First 5 Columns) ==="
	@COLS=$$(databricks sql --query "DESCRIBE $(TABLE)" --profile $(PROFILE) | \
		awk 'NR>1 && NR<=6 {print $$1}' | tr '\n' ',' | sed 's/,$$//'); \
	if [ -n "$$COLS" ]; then \
		NULL_QUERY="SELECT "; \
		for col in $$(echo $$COLS | tr ',' '\n'); do \
			NULL_QUERY="$$NULL_QUERY SUM(CASE WHEN $$col IS NULL THEN 1 ELSE 0 END) as $${col}_nulls,"; \
		done; \
		NULL_QUERY=$$(echo "$$NULL_QUERY" | sed 's/,$$//'); \
		NULL_QUERY="$$NULL_QUERY FROM $(TABLE)"; \
		databricks sql --query "$$NULL_QUERY" --profile $(PROFILE); \
	fi
	@echo ""
	@echo "For detailed analysis, run:"
	@echo "  databricks sql --query \"DESCRIBE EXTENDED $(TABLE)\" --profile $(PROFILE)"
	@echo "  databricks sql --query \"SHOW TBLPROPERTIES $(TABLE)\" --profile $(PROFILE)"

check-pipelines:
	@echo "=== All Pipeline Statuses ==="
	@databricks pipelines list --profile $(PROFILE) --output json | \
		jq -r ".statuses[] | \"\(.name)\t\(.state)\t\(.health // \"N/A\")\"" | \
		column -t -s$$'\t' -N "PIPELINE,STATE,HEALTH"
	@echo ""
	@echo "For detailed pipeline investigation:"
	@echo "  make diagnose-pipeline PIPELINE=<pipeline_name>"

check-jobs:
	@echo "=== All Job Statuses (Last Run) ==="
	@JOB_LIST=$$(databricks jobs list --profile $(PROFILE) --output json | \
		jq -r ".jobs[] | \"\(.job_id)\t\(.settings.name)\""); \
	echo "$$JOB_LIST" | while IFS=$$'\t' read -r job_id job_name; do \
		LAST_RUN=$$(databricks jobs runs list --job-id $$job_id --limit 1 --profile $(PROFILE) --output json 2>/dev/null | \
			jq -r ".runs[0] | \"\(.state.result_state // \"NEVER_RUN\")\t\(.start_time / 1000 | strftime(\"%Y-%m-%d %H:%M\"))\"" 2>/dev/null || echo "N/A\tN/A"); \
		echo "$$job_name\t$$LAST_RUN"; \
	done | column -t -s$$'\t' -N "JOB_NAME,LAST_STATE,LAST_RUN"
	@echo ""
	@echo "For detailed job investigation:"
	@echo "  make diagnose-job JOB=<job_name>"

check-tables:
	@echo "=== Silver Table Freshness ==="
	@echo "Checking tables in $(CATALOG).$(SCHEMA)..."
	@echo ""
	@for table in traces_silver logs_silver metrics_silver service_health_silver; do \
		FULL_TABLE="$(CATALOG).$(SCHEMA).$$table"; \
		if databricks sql --query "SELECT 1 FROM $$FULL_TABLE LIMIT 1" --profile $(PROFILE) > /dev/null 2>&1; then \
			echo "Table: $$table"; \
			TIMESTAMP_COL=$$(databricks sql --query "DESCRIBE $$FULL_TABLE" --profile $(PROFILE) | \
				grep -E "timestamp|time" | head -1 | awk '{print $$1}'); \
			if [ -n "$$TIMESTAMP_COL" ]; then \
				databricks sql --query "SELECT COUNT(*) as rows, MAX($$TIMESTAMP_COL) as latest FROM $$FULL_TABLE" --profile $(PROFILE); \
			else \
				databricks sql --query "SELECT COUNT(*) as rows FROM $$FULL_TABLE" --profile $(PROFILE); \
			fi; \
			echo ""; \
		else \
			echo "⚠️  Table $$table not accessible"; \
			echo ""; \
		fi; \
	done
	@echo "For detailed table investigation:"
	@echo "  make diagnose-table TABLE=catalog.schema.table"
