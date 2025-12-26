#!/bin/bash
set -e

# Setup SSH key if provided
if [ -n "$GIT_SSH_KEY" ]; then
    mkdir -p ~/.ssh
    echo "$GIT_SSH_KEY" | base64 -d > ~/.ssh/id_ed25519
    chmod 600 ~/.ssh/id_ed25519
    ssh-keyscan github.com >> ~/.ssh/known_hosts 2>/dev/null
fi

# Change to src directory
cd /app/src

# Start Celery worker with embedded beat scheduler
exec celery -A core worker -B \
    --loglevel=INFO \
    --concurrency=4 \
    --without-gossip \
    --without-mingle \
    --without-heartbeat
