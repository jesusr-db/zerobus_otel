# Code Style & Conventions

## Python Style
- **Format**: PEP 8 compliant
- **Formatter**: black (mentioned in Makefile)
- **Linter**: pylint (mentioned in Makefile)
- **Imports**: Standard library → Third-party → PySpark
  ```python
  import logging
  from pyspark.sql import SparkSession
  from pyspark.sql.functions import *
  from pyspark.sql.types import *
  ```

## Databricks Notebooks
- **Format**: Python files with magic commands (`# MAGIC %md`)
- **Structure**:
  1. Title and description (markdown)
  2. Setup section (imports, logging)
  3. Parameters section (dbutils.widgets)
  4. Processing logic (well-commented sections)
  5. Output (writeStream or write operations)

## Naming Conventions
- **Tables**: `{layer}_{entity}` (e.g., `traces_silver`, `service_health_gold`)
- **Notebooks**: `{number}_{description}.py` (e.g., `01_flatten_traces.py`)
- **Variables**: snake_case (e.g., `catalog_name`, `bronze_table`)
- **Functions**: snake_case (e.g., `compute_service_health()`)
- **Constants**: UPPER_SNAKE_CASE (if any)

## Documentation
- **Docstrings**: Not heavily used in notebooks (markdown cells serve this purpose)
- **Comments**: Inline comments for complex logic
- **Markdown**: Extensive use of markdown cells for documentation

## Configuration
- **Parameters**: Passed via dbutils.widgets in notebooks
- **Environment**: Managed via Databricks Asset Bundle variables
- **Secrets**: Via .env file (never committed)

## Logging
- **Standard**: Python logging module
- **Level**: INFO for operational messages
- **Format**: Basic configuration with logger names

## PySpark Patterns
- **Streaming**: Use `readStream` and `writeStream` for continuous processing
- **Checkpointing**: Always specify checkpoint locations for streaming
- **Column Operations**: Use PySpark functions (col(), when(), lit(), etc.)
- **Transformations**: Chain transformations with `.withColumn()` for clarity

## Asset Bundle Configuration
- **Format**: YAML
- **Variables**: Use `${var.variable_name}` for substitution
- **Resources**: Organized in separate files (jobs.yml, pipelines.yml, schemas.yml)
- **Environments**: Target-specific overrides in `targets:` section
