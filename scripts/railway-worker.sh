#!/bin/bash
set -e

echo "=== Railway Worker Script ==="
echo "Current directory: $(pwd)"

# Setup SSH key if provided
if [ -n "$GIT_SSH_KEY" ]; then
    echo "Setting up SSH key..."
    mkdir -p ~/.ssh
    echo "$GIT_SSH_KEY" | base64 -d > ~/.ssh/id_rsa
    chmod 600 ~/.ssh/id_rsa
    ssh-keyscan github.com >> ~/.ssh/known_hosts 2>/dev/null
fi

# Clone or pull wiki content repo (worker needs it for tasks)
if [ -n "$WIKI_REPO_URL" ]; then
    if [ ! -d "$WIKI_REPO_PATH/.git" ]; then
        echo "Cloning wiki content repository..."
        if [ -n "$WIKI_REPO_BRANCH" ]; then
            git clone --branch "$WIKI_REPO_BRANCH" "$WIKI_REPO_URL" "$WIKI_REPO_PATH" || echo "Warning: Failed to clone repository"
        else
            git clone "$WIKI_REPO_URL" "$WIKI_REPO_PATH" || echo "Warning: Failed to clone repository"
        fi
    else
        echo "Pulling latest wiki content..."
        cd "$WIKI_REPO_PATH" && git pull --rebase || true
    fi
else
    echo "No WIKI_REPO_URL configured, skipping git clone"
fi

cd /app/src

echo "Working directory: $(pwd)"
echo "Starting Celery worker with beat scheduler..."

# -B flag runs beat scheduler embedded in the worker
exec celery -A core worker -B \
    --loglevel=info \
    --concurrency=4 \
    --without-gossip \
    --without-mingle \
    --without-heartbeat
