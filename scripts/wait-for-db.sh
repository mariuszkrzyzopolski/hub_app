#!/usr/bin/env bash
# Wait for PostgreSQL to be ready
set -e

host="${DB_HOST:-localhost}"
port="${DB_PORT:-5432}"
timeout="${DB_TIMEOUT:-30}"

echo "Waiting for PostgreSQL at $host:$port..."

for i in $(seq 1 $timeout); do
    if nc -z "$host" "$port" 2>/dev/null; then
        echo "PostgreSQL is ready!"
        exit 0
    fi
    sleep 1
done

echo "Timeout: PostgreSQL did not become ready within ${timeout}s"
exit 1