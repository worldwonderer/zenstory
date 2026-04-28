# Local CI with act

This guide explains how to run GitHub Actions workflows locally using `act`.

## Prerequisites

- **Docker Desktop** must be installed and running
  - Download from: https://www.docker.com/products/docker-desktop
  - Ensure Docker is running before executing `act` commands
- **act** CLI tool (see installation below)

## Installation

### macOS
```bash
brew install act
```

### Linux
```bash
curl https://raw.githubusercontent.com/nektos/act/master/install.sh | sudo bash
```

### Windows
```powershell
choco install act-cli
```

## Configuration

The project includes a `.actrc` file that configures act with:
- **Platform**: `node:20-bookworm` for `ubuntu-latest` runners
- **Environment**: Loads variables from `.env.test`
- **Architecture**: `linux/amd64` for compatibility on Apple Silicon Macs

## Usage

### Run All Workflows
```bash
act
```
Executes all jobs in all workflow files.

### Run Specific Job
```bash
act -j backend-test
```
Runs only the `backend-test` job from any workflow.

### Run Specific Workflow
```bash
act .github/workflows/backend-ci.yml
```
Executes all jobs in the specified workflow file.

### Dry Run (Preview)
```bash
act -n
```
Shows what would be executed without actually running anything.

### List Available Jobs
```bash
act -l
```
Displays all jobs across all workflows.

### Run with Specific Event
```bash
act pull_request
act push
act workflow_dispatch
```
Simulates a specific GitHub event trigger.

## Service Containers

When running workflows locally with `act`, service containers (PostgreSQL, Redis) defined in the workflow will be automatically started. These run in Docker containers alongside the job containers.

The workflows are configured with:
- **PostgreSQL**: Available at `localhost:5432`
- **Redis**: Available at `localhost:6379`

## Common Commands

### Backend Tests Only
```bash
act -j backend-test
```

### Frontend Tests Only
```bash
act -j frontend-test
```

### Full CI Pipeline
```bash
act
```

### Debug Mode
```bash
act -v
```
Runs with verbose output for troubleshooting.

## Troubleshooting

### Docker Not Running
**Error**: `Cannot connect to the Docker daemon`

**Solution**: Start Docker Desktop and wait for it to fully initialize.

### Architecture Issues (Apple Silicon)
**Error**: `no matching manifest for linux/arm64/v8`

**Solution**: The `.actrc` includes `--container-architecture linux/amd64` to use x86_64 emulation. If issues persist:
```bash
act --container-architecture linux/amd64
```

### Missing Environment Variables
**Error**: Environment variable errors or missing secrets

**Solution**: Ensure `.env.test` exists in the project root with required test variables:
```bash
cp apps/server/.env.example .env.test
```

### Service Container Failures
**Error**: Database connection errors

**Solution**:
1. Check if Docker has sufficient resources (Memory: 4GB+, CPUs: 2+)
2. Verify service containers are healthy:
   ```bash
   docker ps
   ```
3. Review service logs:
   ```bash
   docker logs <container-id>
   ```

### Permission Errors
**Error**: Permission denied when running act

**Solution**: Ensure your user is in the docker group (Linux):
```bash
sudo usermod -aG docker $USER
```
Log out and back in for changes to take effect.

### Workflow Syntax Errors
**Error**: YAML parsing errors

**Solution**: Validate workflow syntax:
```bash
actionlint .github/workflows/backend-ci.yml
```
Install actionlint: `brew install actionlint`

## Performance Tips

1. **Reuse Containers**: act caches Docker images. First run is slow, subsequent runs are faster.

2. **Resource Allocation**: In Docker Desktop preferences, allocate:
   - Memory: 4GB+
   - CPUs: 2+
   - Disk: 64GB+

3. **Selective Testing**: Use `-j` to run only the jobs you need:
   ```bash
   act -j backend-test  # Faster than running all jobs
   ```

## Differences from GitHub Actions

There are some differences when running locally:

1. **Secrets**: Not available unless explicitly provided via `--secret-file`
2. **GitHub Context**: Some GitHub-specific environment variables may not be set
3. **Runner Performance**: Local Docker containers may differ from GitHub-hosted runners
4. **Network**: Service containers accessible at `localhost` instead of service names

## Additional Resources

- [act Documentation](https://github.com/nektos/act)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Docker Desktop Download](https://www.docker.com/products/docker-desktop)

## Support

For issues specific to this project's CI configuration, check:
- `.github/workflows/` for workflow definitions
- `.env.test` for test environment variables
- Project documentation in `CLAUDE.md`
