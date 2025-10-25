# Makefile for Databricks Observability Platform
# Quick commands for common operations

.PHONY: help validate deploy-dev deploy-staging deploy-prod run-loader clean

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
