# GitHub Utilities

Unified GitHub CLI operations for CI workflows and PR management.

## gh-utils.sh - Unified GitHub Operations

### Usage

```bash
./scripts/github/gh-utils.sh <command> [args]
```

### Commands

| Command        | Description                              |
|----------------|------------------------------------------|
| `logs <run-id>`| Fetch CI logs for a specific run         |
| `watch`        | Watch CI status for current branch       |
| `pr <title>`   | Create PR and watch CI                   |
| `help`         | Show help message                        |

### Examples

```bash
# Watch CI for current branch
./scripts/github/gh-utils.sh watch

# Fetch logs for run ID 1234567890
./scripts/github/gh-utils.sh logs 1234567890

# Get run ID from current branch
gh run list --branch $(git branch --show-current)

# Create PR and automatically watch CI
./scripts/github/gh-utils.sh pr "Fix authentication bug"
```

### Prerequisites

- GitHub CLI (`gh`) installed and authenticated
- Repository with GitHub Actions enabled

### Common Workflows

#### Create PR and Monitor CI

```bash
# One-liner to create PR and watch
./scripts/github/gh-utils.sh pr "Add new feature"
```

#### Debug Failed CI Run

```bash
# List recent runs
gh run list --branch $(git branch --show-current)

# Fetch detailed logs
./scripts/github/gh-utils.sh logs <run-id>
```

#### Monitor CI Without Creating PR

```bash
# Watch the latest CI run for current branch
./scripts/github/gh-utils.sh watch
```

### GitHub CLI Tips

```bash
# Check authentication status
gh auth status

# View PR list
gh pr list

# View workflow runs
gh run list

# Download artifacts from a run
gh run download <run-id>
```
