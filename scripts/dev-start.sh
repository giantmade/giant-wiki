#!/bin/bash
set -e

# Setup SSH key if provided
if [ -n "$GIT_SSH_KEY" ]; then
    mkdir -p ~/.ssh
    echo "$GIT_SSH_KEY" | base64 -d > ~/.ssh/id_rsa
    chmod 600 ~/.ssh/id_rsa
    ssh-keyscan github.com >> ~/.ssh/known_hosts 2>/dev/null
fi

# Clone or pull wiki content repo
if [ -n "$WIKI_REPO_URL" ]; then
    if [ ! -d "$WIKI_REPO_PATH/.git" ]; then
        echo "Cloning wiki content repository..."
        if [ -n "$WIKI_REPO_BRANCH" ]; then
            git clone --branch "$WIKI_REPO_BRANCH" "$WIKI_REPO_URL" "$WIKI_REPO_PATH"
        else
            git clone "$WIKI_REPO_URL" "$WIKI_REPO_PATH"
        fi
    else
        echo "Pulling latest wiki content..."
        cd "$WIKI_REPO_PATH" && git pull --rebase || true
    fi
fi

# Change to src directory
cd /app/src

# Start Django dev server
exec uv run python manage.py runserver 0.0.0.0:8000
