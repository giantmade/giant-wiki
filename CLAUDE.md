# Giant Wiki

Internal documentation wiki with Git-based storage.

## Tech Stack

- Django 6.0 / Python 3.13
- Git-based content storage (markdown files)
- SQLite FTS5 for search (ephemeral, rebuilt on writes)
- Celery + Redis for background Git sync
- Tailwind CSS (Giant Tool Design System)
- No authentication (Tailscale boundary)

## Docker Services

| Service | Port | Purpose |
|---------|------|---------|
| web | 8000 | Django runserver |
| worker | - | Celery worker |
| cache | 6379 | Redis (Celery broker) |

## Development Commands

Always use Makefile commands:

| Command | Purpose |
|---------|---------|
| `make install` | Build images, create .env |
| `make server` | Start all services (foreground) |
| `make up` | Start services (background) |
| `make down` | Stop services |
| `make test` | Run pytest (parallel) |
| `make test-fast` | Run affected tests only (testmon) |
| `make cov` | Tests with coverage report |
| `make format` | Run ruff check + format |
| `make shell` | Django shell |
| `make logs` | Follow all logs |
| `make ps` | Show service status |
| `make rebuild-search` | Rebuild FTS index |
| `make sync-git` | Sync with Git remote |
| `make clone-content` | Clone wiki content repo for dev |

## Project Structure

```
giant-wiki/
├── src/                      # Django application code
│   ├── core/                 # Django project settings
│   │   ├── management/
│   │   │   └── commands/     # rebuild_search, sync_git
│   │   ├── templates/        # Base template, wiki templates
│   │   ├── settings.py
│   │   ├── celery.py
│   │   └── urls.py
│   ├── wiki/                 # Wiki app
│   │   ├── services/         # git_storage.py, search.py
│   │   ├── tasks.py          # Celery tasks
│   │   └── views.py
│   ├── conftest.py
│   └── manage.py
├── var/                      # Runtime data (gitignored)
│   ├── data/                 # SQLite databases
│   ├── logs/                 # Application logs
│   ├── repo/                 # Wiki content Git repo
│   └── static/               # Collected static files
├── scripts/                  # Startup scripts
├── docker-compose.yml
├── dev.Dockerfile
├── Makefile
├── pyproject.toml
└── uv.lock
```

## Wiki Content Storage

Wiki pages are stored as markdown files in a Git repository:

```
pages/
  index.md
  Sidebar.md
  <path>.md
attachments/
  <page-path>/
    file.png
```

- Local development: `var/repo/` (initialized as empty local git repo)
- With real data: Set `WIKI_REPO_URL` in `.env`, run `make clone-content`
- Production: Cloned from `WIKI_REPO_URL` environment variable

## Environment Variables

| Variable | Description |
|----------|-------------|
| `SECRET_KEY` | Django secret key |
| `DEBUG` | Enable debug mode |
| `SITE_TITLE` | Wiki title |
| `WIKI_REPO_URL` | Git repo URL for content |
| `WIKI_REPO_PATH` | Local path for repo |
| `WIKI_REPO_BRANCH` | Git branch to use (optional, defaults to repo default) |
| `CELERY_BROKER_URL` | Redis URL for Celery |
| `GIT_SSH_KEY` | Base64-encoded SSH key (production) |

## Deployment

Deployed to Railway with Tailscale forwarder for private access:

- `railway-web.toml` - Web service config
- `railway-worker.toml` - Worker service config
- Private access via Tailscale network only
