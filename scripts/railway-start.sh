#!/bin/bash

echo "=== Railway Start Script ==="
echo "Current directory: $(pwd)"
echo "PORT: ${PORT:-8000}"

# Configure Git identity for commits
git config --global user.email "wiki@giantmade.com"
git config --global user.name "Giant Wiki"
echo "Configured Git identity"

# Setup SSH key if provided
if [ -n "$GIT_SSH_KEY" ]; then
    echo "Setting up SSH key..."
    mkdir -p ~/.ssh
    echo "$GIT_SSH_KEY" | base64 -d > ~/.ssh/id_rsa || echo "Warning: Failed to decode SSH key"
    chmod 600 ~/.ssh/id_rsa || true
    ssh-keyscan github.com >> ~/.ssh/known_hosts 2>/dev/null || echo "Warning: Failed to scan SSH keys"
fi

# Clone or pull wiki content repo
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

# Find src directory
if [ -d "/app/src" ]; then
    cd /app/src
elif [ -d "src" ]; then
    cd src
else
    echo "ERROR: Cannot find src directory!"
    exit 1
fi

echo "Working directory: $(pwd)"

# Start Gunicorn
exec gunicorn core.wsgi:application \
    --bind 0.0.0.0:${PORT:-8000} \
    --workers 4 \
    --worker-class sync \
    --timeout 120 \
    --max-requests 1000 \
    --max-requests-jitter 50 \
    --access-logfile - \
    --error-logfile - \
    --capture-output \
    --log-level info
