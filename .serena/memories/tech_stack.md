# Technology Stack

## Data Platform
- **Platform**: Databricks (Unity Catalog enabled)
- **Storage**: Delta Lake (ACID transactions, time travel)
- **Compute**: Serverless SQL Warehouse + Serverless Compute
- **Orchestration**: Databricks Workflows & Delta Live Tables (DLT)
- **IaC**: Databricks Asset Bundles (YAML configuration)

## Development
- **Language**: Python 3.11 (PySpark)
- **Framework**: Apache Spark (distributed processing)
- **Notebooks**: Databricks notebooks (.py format with magic commands)

## CI/CD
- **Version Control**: Git
- **CI/CD**: GitHub Actions
- **Deployment**: Databricks CLI (`databricks bundle deploy`)

## Monitoring & Alerting
- **Dashboards**: Lakeview (Databricks SQL Analytics)
- **Alerting**: HTTP Webhook
- **Visualization**: Plotly (planned for Streamlit app)

## Data Sources
- **Collection**: OpenTelemetry (OTEL) Collector Gateway
- **Signals**: Traces, Metrics, Logs
- **Sample Services**: frontend, cart, ad, currency, product-catalog, payment, etc.

## Tools & Utilities
- **Databricks CLI**: Project deployment and management
- **Make**: Command automation (see Makefile)
- **SQL**: Data quality validation and maintenance

## Environments
- **dev**: Development & testing (single-node serverless, continuous pipelines)
- **staging**: Pre-production validation (small serverless)
- **prod**: Production workloads (medium serverless with autoscale)

All environments use Unity Catalog for governance and serverless compute for cost optimization.
