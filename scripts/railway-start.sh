#!/bin/bash
set -e

# Setup SSH key if provided
if [ -n "$GIT_SSH_KEY" ]; then
    mkdir -p ~/.ssh
    echo "$GIT_SSH_KEY" | base64 -d > ~/.ssh/id_ed25519
    chmod 600 ~/.ssh/id_ed25519
    ssh-keyscan github.com >> ~/.ssh/known_hosts 2>/dev/null
fi

# Clone or pull wiki content repo
if [ -n "$WIKI_REPO_URL" ]; then
    if [ ! -d "$WIKI_REPO_PATH/.git" ]; then
        echo "Cloning wiki content repository..."
        git clone "$WIKI_REPO_URL" "$WIKI_REPO_PATH"
    else
        echo "Pulling latest wiki content..."
        cd "$WIKI_REPO_PATH" && git pull --rebase || true
    fi
fi

# Change to src directory
cd /app/src

# Start Gunicorn
exec gunicorn core.wsgi \
    --bind 0.0.0.0:${PORT:-8000} \
    --workers 4 \
    --worker-class sync \
    --timeout 120 \
    --max-requests 1000 \
    --max-requests-jitter 50 \
    --access-logfile - \
    --error-logfile -
