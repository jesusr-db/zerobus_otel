# Task Completion Checklist

## Before Making Changes
1. ✅ Check git status and ensure you're on the correct branch
2. ✅ Review current project status in PROJECT_PLAN.md
3. ✅ Validate bundle configuration if modifying YAML files

## During Development
1. ✅ Follow existing code patterns and naming conventions
2. ✅ Add logging statements for operational visibility
3. ✅ Use parameterized dbutils.widgets for notebook flexibility
4. ✅ Specify checkpoint locations for streaming operations
5. ✅ Include markdown documentation cells in notebooks

## After Code Changes
1. ✅ **Format code**: Run `make fmt` (black formatter)
2. ✅ **Lint code**: Run `make lint` (pylint)
3. ✅ **Validate bundle**: Run `make validate` if YAML configs changed
4. ✅ **Test locally**: Deploy to dev with `make deploy-dev`
5. ✅ **Run job**: Test the modified job/pipeline
6. ✅ **Check logs**: Use `make logs` to verify execution

## Data Quality Checks
1. ✅ Verify output table schemas match expectations
2. ✅ Check for null values in critical columns
3. ✅ Validate row counts and data freshness
4. ✅ Run data quality notebooks if available

## Before Committing
1. ✅ Review changes with `git diff`
2. ✅ Ensure no sensitive data (tokens, passwords) in code
3. ✅ Update PROJECT_PLAN.md if task status changes
4. ✅ Update README.md if user-facing changes
5. ✅ Write descriptive commit message

## Commit Message Format
```
<type>: <short description>

<optional detailed description>

Co-Authored-By: Claude <noreply@anthropic.com>
```

Types: feat, fix, refactor, docs, test, chore

## Deployment Checklist
1. ✅ Deploy to dev first: `make deploy-dev`
2. ✅ Test end-to-end functionality
3. ✅ Review job run results in Databricks UI
4. ✅ Only promote to staging/prod after dev validation

## CI/CD Notes
- Push to `develop` branch → Auto-deploy to dev
- Push to `main` branch → Auto-deploy to staging
- Production deploys require manual workflow trigger with approval

## When Task is Complete
1. ✅ Mark corresponding todo in PROJECT_PLAN.md as complete
2. ✅ Document any architectural decisions or changes
3. ✅ Update relevant documentation (README, QUICKSTART, etc.)
4. ✅ Create pull request if using feature branch workflow
