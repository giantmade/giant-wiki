#!/bin/bash
set -e

# Setup SSH key if provided
if [ -n "$GIT_SSH_KEY" ]; then
    mkdir -p ~/.ssh
    echo "$GIT_SSH_KEY" | base64 -d > ~/.ssh/id_rsa
    chmod 600 ~/.ssh/id_rsa
    ssh-keyscan github.com >> ~/.ssh/known_hosts 2>/dev/null
fi

# Change to src directory
cd /app/src

# Start Celery worker
exec uv run celery -A core worker -l INFO --concurrency=2
