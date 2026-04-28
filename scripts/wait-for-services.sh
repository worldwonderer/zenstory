#!/bin/bash
# wait-for-services.sh - Wait for PostgreSQL and Redis to be ready
# Usage: ./scripts/wait-for-services.sh

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
POSTGRES_HOST="${POSTGRES_HOST:-localhost}"
POSTGRES_PORT="${POSTGRES_PORT:-5433}"
REDIS_HOST="${REDIS_HOST:-localhost}"
REDIS_PORT="${REDIS_PORT:-6380}"
TIMEOUT="${TIMEOUT:-60}"

# Function to print colored messages
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if PostgreSQL is ready
wait_for_postgres() {
    local count=0
    log_info "Waiting for PostgreSQL on ${POSTGRES_HOST}:${POSTGRES_PORT}..."

    while [ $count -lt $TIMEOUT ]; do
        if nc -z "$POSTGRES_HOST" "$POSTGRES_PORT" 2>/dev/null; then
            # Try to connect using pg_isready if available, otherwise just check port
            if command -v pg_isready >/dev/null 2>&1; then
                if pg_isready -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U test >/dev/null 2>&1; then
                    log_info "PostgreSQL is ready!"
                    return 0
                fi
            else
                # Just check if we can connect to the port
                log_info "PostgreSQL port is open!"
                return 0
            fi
        fi
        count=$((count + 1))
        sleep 1
    done

    log_error "Timeout waiting for PostgreSQL"
    return 1
}

# Function to check if Redis is ready
wait_for_redis() {
    local count=0
    log_info "Waiting for Redis on ${REDIS_HOST}:${REDIS_PORT}..."

    while [ $count -lt $TIMEOUT ]; do
        if nc -z "$REDIS_HOST" "$REDIS_PORT" 2>/dev/null; then
            # Try to ping Redis if redis-cli is available
            if command -v redis-cli >/dev/null 2>&1; then
                if redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" ping >/dev/null 2>&1; then
                    log_info "Redis is ready!"
                    return 0
                fi
            else
                # Just check if we can connect to the port
                log_info "Redis port is open!"
                return 0
            fi
        fi
        count=$((count + 1))
        sleep 1
    done

    log_error "Timeout waiting for Redis"
    return 1
}

# Main execution
main() {
    log_info "Starting service health checks..."

    # Wait for both services
    local postgres_ok=0
    local redis_ok=0

    # Run checks in parallel
    wait_for_postgres &
    local postgres_pid=$!

    wait_for_redis &
    local redis_pid=$!

    # Wait for background jobs
    if wait $postgres_pid; then
        postgres_ok=1
    fi

    if wait $redis_pid; then
        redis_ok=1
    fi

    # Report results
    if [ $postgres_ok -eq 1 ] && [ $redis_ok -eq 1 ]; then
        log_info "All services are ready!"
        return 0
    else
        log_error "Some services failed to start"
        return 1
    fi
}

# Run main function
main "$@"
