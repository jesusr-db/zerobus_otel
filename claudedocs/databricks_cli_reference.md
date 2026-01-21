# Databricks CLI Reference for Troubleshooting

Comprehensive reference guide for using Databricks CLI to gather schemas, metadata, error logs, and troubleshoot pipelines.

## Table of Contents
1. [Authentication & Setup](#authentication--setup)
2. [Job Operations](#job-operations)
3. [Schema Inspection](#schema-inspection)
4. [Pipeline Operations](#pipeline-operations)
5. [Workspace & File Operations](#workspace--file-operations)
6. [Catalog & Schema Operations](#catalog--schema-operations)
7. [Cluster & Warehouse Operations](#cluster--warehouse-operations)

---

## Authentication & Setup

### Configure CLI with Token
```bash
# Interactive configuration
databricks configure --token

# Set specific profile
databricks configure --token --profile <profile-name>

# Environment variables (alternative)
export DATABRICKS_HOST="https://your-workspace.cloud.databricks.com"
export DATABRICKS_TOKEN="your-token-here"
```

### Test Connectivity
```bash
# List workspaces (validates auth)
databricks workspace ls /

# Get current user info
databricks api GET /api/2.0/preview/scim/v2/Me
```

### Profile Management
```bash
# List configured profiles
cat ~/.databrickscfg

# Use specific profile for command
databricks jobs list --profile production
```

---

## Job Operations

### List and Search Jobs
```bash
# List all jobs
databricks jobs list

# List with JSON output
databricks jobs list --output json

# Search for specific job
databricks jobs list | grep "job_name"

# Get job ID from name
databricks jobs list --output json | jq '.jobs[] | select(.settings.name=="job_name") | .job_id'
```

### Job Details
```bash
# Get job configuration
databricks jobs get --job-id <job-id>

# Get job details with JSON output
databricks jobs get --job-id <job-id> --output json

# Extract specific fields
databricks jobs get --job-id <job-id> --output json | jq '.settings.tasks'
```

### Job Runs
```bash
# List recent runs for a job
databricks jobs runs list --job-id <job-id> --limit 10

# Get all runs (paginated)
databricks jobs runs list --job-id <job-id> --limit 100

# Filter failed runs
databricks jobs runs list --job-id <job-id> --output json | \
  jq '.runs[] | select(.state.result_state=="FAILED")'

# Get most recent run
databricks jobs runs list --job-id <job-id> --limit 1 --output json | jq '.runs[0]'
```

### Run Details and Logs
```bash
# Get detailed run information
databricks jobs runs get --run-id <run-id>

# Get run output (includes error messages)
databricks jobs runs get-output --run-id <run-id>

# Extract error message
databricks jobs runs get-output --run-id <run-id> --output json | \
  jq -r '.error // "No error"'

# Get task-level details
databricks jobs runs get --run-id <run-id> --output json | \
  jq '.tasks[] | {task_key: .task_key, state: .state}'
```

### Trigger Job Run
```bash
# Run job now
databricks jobs run-now --job-id <job-id>

# Run with parameters
databricks jobs run-now --job-id <job-id> --python-params '["param1", "param2"]'
```

---

## Schema Inspection

### Table Schema via SQL
```bash
# Describe table
databricks sql --query "DESCRIBE EXTENDED catalog.schema.table"

# Show CREATE TABLE statement
databricks sql --query "SHOW CREATE TABLE catalog.schema.table"

# Get table properties
databricks sql --query "SHOW TBLPROPERTIES catalog.schema.table"

# List columns with types
databricks sql --query "DESCRIBE catalog.schema.table"

# Execute on specific warehouse
databricks sql --query "DESCRIBE catalog.schema.table" --warehouse-id <warehouse-id>
```

### Table Schema via Unity Catalog API
```bash
# Get full table details
databricks api GET /api/2.1/unity-catalog/tables/catalog.schema.table

# Extract schema definition
databricks api GET /api/2.1/unity-catalog/tables/catalog.schema.table | \
  jq '.columns[] | {name: .name, type: .type_name, nullable: .nullable}'

# Get table properties
databricks api GET /api/2.1/unity-catalog/tables/catalog.schema.table | \
  jq '.properties'

# Check table type (managed, external, view)
databricks api GET /api/2.1/unity-catalog/tables/catalog.schema.table | \
  jq '{name: .name, type: .table_type, storage_location: .storage_location}'
```

### Compare Schemas
```bash
# Get schema of two tables for comparison
databricks sql --query "DESCRIBE catalog.schema.table1" > schema1.txt
databricks sql --query "DESCRIBE catalog.schema.table2" > schema2.txt
diff schema1.txt schema2.txt

# Programmatic comparison
diff <(databricks api GET /api/2.1/unity-catalog/tables/catalog.schema.table1 | jq -S '.columns') \
     <(databricks api GET /api/2.1/unity-catalog/tables/catalog.schema.table2 | jq -S '.columns')
```

### Table Statistics
```bash
# Get row count
databricks sql --query "SELECT COUNT(*) as row_count FROM catalog.schema.table"

# Get table size
databricks sql --query "DESCRIBE DETAIL catalog.schema.table" | grep sizeInBytes

# Check data freshness
databricks sql --query "SELECT MAX(timestamp_column) as latest_data FROM catalog.schema.table"

# Table history (Delta tables)
databricks sql --query "DESCRIBE HISTORY catalog.schema.table LIMIT 10"
```

---

## Pipeline Operations

### List Pipelines
```bash
# List all pipelines
databricks pipelines list

# List with JSON output
databricks pipelines list --output json

# Find pipeline by name
databricks pipelines list --output json | jq '.statuses[] | select(.name=="pipeline_name")'

# Get pipeline ID from name
databricks pipelines list --output json | jq -r '.statuses[] | select(.name=="pipeline_name") | .pipeline_id'
```

### Pipeline Details
```bash
# Get pipeline configuration
databricks pipelines get --pipeline-id <pipeline-id>

# Get full details with JSON
databricks pipelines get --pipeline-id <pipeline-id> --output json

# Extract specific configuration
databricks pipelines get --pipeline-id <pipeline-id> --output json | \
  jq '.spec | {target: .target, storage: .storage, configuration: .configuration}'
```

### Pipeline Updates
```bash
# List pipeline updates
databricks pipelines list-updates --pipeline-id <pipeline-id>

# Get latest update
databricks pipelines list-updates --pipeline-id <pipeline-id> --max-results 1

# Get specific update details
databricks pipelines get-update --pipeline-id <pipeline-id> --update-id <update-id>

# Check update state
databricks pipelines get-update --pipeline-id <pipeline-id> --update-id <update-id> --output json | \
  jq '.update.state'
```

### Pipeline Event Logs
```bash
# Get all events
databricks api GET /api/2.0/pipelines/<pipeline-id>/events

# Filter ERROR events
databricks api GET /api/2.0/pipelines/<pipeline-id>/events | \
  jq '.events[] | select(.level=="ERROR")'

# Filter by event type
databricks api GET /api/2.0/pipelines/<pipeline-id>/events | \
  jq '.events[] | select(.event_type=="flow_progress")'

# Get recent errors with details
databricks api GET /api/2.0/pipelines/<pipeline-id>/events | \
  jq '.events[] | select(.level=="ERROR") | {timestamp: .timestamp, message: .message, details: .details}'

# Get events for specific update
databricks api GET /api/2.0/pipelines/<pipeline-id>/events?max_results=100 | \
  jq --arg update_id "<update-id>" '.events[] | select(.origin.update_id==$update_id)'
```

### Pipeline Control
```bash
# Start pipeline update
databricks pipelines start-update --pipeline-id <pipeline-id>

# Stop pipeline
databricks pipelines stop --pipeline-id <pipeline-id>

# Reset pipeline (WARNING: destructive)
databricks pipelines reset --pipeline-id <pipeline-id>
```

---

## Workspace & File Operations

### Workspace Navigation
```bash
# List workspace root
databricks workspace ls /

# List specific directory
databricks workspace ls /Workspace/path/to/directory

# Recursive list
databricks workspace ls -r /Workspace/path

# List with details
databricks workspace ls -l /Workspace/path
```

### Notebook Operations
```bash
# Export notebook (Python format)
databricks workspace export /Workspace/path/to/notebook.py --format SOURCE

# Export as HTML
databricks workspace export /Workspace/path/to/notebook.py --format HTML -o notebook.html

# Export as Jupyter
databricks workspace export /Workspace/path/to/notebook.py --format JUPYTER -o notebook.ipynb

# Check notebook language
databricks workspace export /Workspace/path/to/notebook.py --format SOURCE | head -1
```

### DBFS Operations
```bash
# List DBFS root
databricks fs ls dbfs:/

# List specific path
databricks fs ls dbfs:/path/to/directory

# Recursive list
databricks fs ls -r dbfs:/path/to/directory

# Check file size
databricks fs ls -l dbfs:/path/to/file

# Read file contents
databricks fs cat dbfs:/path/to/file

# Download file
databricks fs cp dbfs:/path/to/file ./local-file

# Check if path exists
databricks fs ls dbfs:/path/to/check 2>&1 | grep -q "does not exist" && echo "Not found" || echo "Exists"
```

### Checkpoint Management
```bash
# List checkpoint directory
databricks fs ls dbfs:/checkpoint/pipeline_name/

# Check commits directory
databricks fs ls dbfs:/checkpoint/pipeline_name/commits/

# List offsets
databricks fs ls dbfs:/checkpoint/pipeline_name/offsets/

# Read checkpoint metadata
databricks fs cat dbfs:/checkpoint/pipeline_name/metadata

# Check checkpoint size
databricks fs ls -r dbfs:/checkpoint/pipeline_name/ | wc -l

# Delete checkpoint (WARNING: causes full reprocessing)
databricks fs rm -r dbfs:/checkpoint/pipeline_name/
```

---

## Catalog & Schema Operations

### List Catalogs
```bash
# List all catalogs
databricks api GET /api/2.1/unity-catalog/catalogs

# Extract catalog names
databricks api GET /api/2.1/unity-catalog/catalogs | jq -r '.catalogs[].name'

# Get catalog details
databricks api GET /api/2.1/unity-catalog/catalogs/<catalog-name>

# Check catalog properties
databricks api GET /api/2.1/unity-catalog/catalogs/<catalog-name> | jq '.properties'
```

### List Schemas
```bash
# List schemas in catalog
databricks api GET /api/2.1/unity-catalog/schemas?catalog_name=<catalog>

# Extract schema names
databricks api GET /api/2.1/unity-catalog/schemas?catalog_name=<catalog> | \
  jq -r '.schemas[].name'

# Get schema details
databricks api GET /api/2.1/unity-catalog/schemas/<catalog>.<schema>

# Via SQL
databricks sql --query "SHOW SCHEMAS IN <catalog>"
```

### List Tables
```bash
# List tables in schema
databricks api GET /api/2.1/unity-catalog/tables?catalog_name=<catalog>&schema_name=<schema>

# Extract table names
databricks api GET /api/2.1/unity-catalog/tables?catalog_name=<catalog>&schema_name=<schema> | \
  jq -r '.tables[].name'

# Via SQL
databricks sql --query "SHOW TABLES IN <catalog>.<schema>"

# Search for table by pattern
databricks sql --query "SHOW TABLES IN <catalog>.<schema> LIKE '*pattern*'"
```

### Table Details
```bash
# Get full table information
databricks api GET /api/2.1/unity-catalog/tables/<catalog>.<schema>.<table>

# Check table owner
databricks api GET /api/2.1/unity-catalog/tables/<catalog>.<schema>.<table> | jq -r '.owner'

# Check table creation time
databricks api GET /api/2.1/unity-catalog/tables/<catalog>.<schema>.<table> | \
  jq -r '.created_at'

# Get table comment
databricks api GET /api/2.1/unity-catalog/tables/<catalog>.<schema>.<table> | jq -r '.comment'
```

---

## Cluster & Warehouse Operations

### SQL Warehouses
```bash
# List SQL warehouses
databricks sql warehouses list

# List with JSON output
databricks sql warehouses list --output json

# Get warehouse details
databricks sql warehouses get --id <warehouse-id>

# Check warehouse state
databricks sql warehouses get --id <warehouse-id> --output json | jq -r '.state'

# Start warehouse
databricks sql warehouses start --id <warehouse-id>

# Stop warehouse
databricks sql warehouses stop --id <warehouse-id>
```

### Compute Clusters
```bash
# List clusters
databricks clusters list

# List with JSON
databricks clusters list --output json

# Get cluster details
databricks clusters get --cluster-id <cluster-id>

# Check cluster state
databricks clusters get --cluster-id <cluster-id> --output json | jq -r '.state'

# Get cluster events (logs)
databricks clusters events --cluster-id <cluster-id>

# Filter errors from cluster events
databricks clusters events --cluster-id <cluster-id> --output json | \
  jq '.events[] | select(.type=="ERROR")'
```

---

## Advanced Troubleshooting Patterns

### Chaining Commands with jq
```bash
# Get job ID, then latest run, then error message
JOB_ID=$(databricks jobs list --output json | jq -r '.jobs[] | select(.settings.name=="job_name") | .job_id')
RUN_ID=$(databricks jobs runs list --job-id $JOB_ID --limit 1 --output json | jq -r '.runs[0].run_id')
databricks jobs runs get-output --run-id $RUN_ID --output json | jq -r '.error'

# Get pipeline ID, then latest update, then event errors
PIPELINE_ID=$(databricks pipelines list --output json | jq -r '.statuses[] | select(.name=="pipeline_name") | .pipeline_id')
databricks api GET /api/2.0/pipelines/$PIPELINE_ID/events | jq '.events[] | select(.level=="ERROR")'
```

### Parallel Diagnostics
```bash
# Check multiple tables simultaneously
for table in table1 table2 table3; do
  databricks sql --query "SELECT COUNT(*) as count FROM catalog.schema.$table" &
done
wait

# Get status of multiple jobs
for job_id in 123 456 789; do
  databricks jobs get --job-id $job_id --output json | jq '{job_id: .job_id, status: .state}' &
done
wait
```

### Error Pattern Extraction
```bash
# Extract unique error types from job runs
databricks jobs runs list --job-id <job-id> --limit 50 --output json | \
  jq -r '.runs[] | select(.state.result_state=="FAILED") | .state.state_message' | \
  sort | uniq -c

# Find common error patterns in pipeline events
databricks api GET /api/2.0/pipelines/<pipeline-id>/events | \
  jq -r '.events[] | select(.level=="ERROR") | .message' | \
  sort | uniq -c | sort -rn
```

---

## Tips and Best Practices

### Performance
- Use `--output json` with `jq` for structured parsing instead of grep/awk
- Cache frequently used IDs (job_id, pipeline_id) in shell variables
- Use `--limit` parameter to reduce API response size
- Leverage parallel execution with `&` and `wait` for independent queries

### Safety
- Always verify catalog/schema/table names before destructive operations
- Test queries on sample data before running on production tables
- Use `--dry-run` flag when available
- Back up checkpoint locations before deletion

### Debugging
- Add `--debug` flag to see API requests: `databricks jobs list --debug`
- Check command exit codes: `$?` after each command
- Use `jq -r` for raw output (no quotes) when piping to other commands
- Save diagnostic output to files for later analysis

### API Rate Limits
- Be mindful of API rate limits when scripting
- Add delays with `sleep` between rapid-fire requests
- Use bulk APIs when available (e.g., batch job status checks)
- Consider caching frequently accessed metadata
