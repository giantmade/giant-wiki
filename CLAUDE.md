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
| web | 9050 | Django runserver |
| worker | - | Celery worker |
| cache | 9052 | Redis (Celery broker) |

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

## Performance Optimizations

### Sidebar Cache Warming

The sidebar uses a two-tier caching strategy in Redis for fast access:

- **Page titles cache:** Maps page paths to frontmatter titles (raw data)
- **Structure cache:** Pre-built category hierarchy with sorted items (99% of work done)
- **Startup:** Both caches warmed via `warm_sidebar_cache` Celery task
- **TTL:** 30 minutes (configurable via `SIDEBAR_CACHE_TTL`)
- **Git sync:** Caches re-warmed automatically after pulling changes
- **Performance:** ~5-10ms per request (structure cache hit) vs ~7000ms (cold)

Implementation: `src/wiki/services/sidebar.py` (two cache keys) and `src/wiki/tasks.py` (cache warming).

## Task Monitoring

The wiki includes a web UI for monitoring Celery background tasks at `/tasks/`.

### URL Structure

| URL | Description |
|-----|-------------|
| `/tasks/` | List all tasks (paginated, 30 per page) |
| `/tasks/<task_id>/` | Task detail with logs and audit trail |
| `/tasks/<task_id>/status/` | JSON endpoint for status polling |
| `/tasks/<task_id>/cancel/` | Cancel a running task (POST) |

### Features

- **Tasks List:** Paginated table showing all tasks with status, type, name, creation time, and duration
- **Status Badges:** Color-coded badges (queued, in_progress, success, completed_with_errors, failed, cancelled)
- **Detail View:** Real-time task monitoring with auto-refresh, logs, progress tracking, and audit trail
- **Navigation:** Accessible via sidebar footer link (History | Tasks)

### Implementation

- Views: `src/core/views.py` (tasks_list, task_detail, task_status_json, task_cancel)
- Templates: `src/core/templates/core/tasks_list.html`, `src/core/templates/core/task_detail.html`
- Models: Task and TaskAuditTrail in `src/core/models.py`
- Task dispatcher: `dispatch_task()` function for launching Celery tasks with tracking

## Deployment

Deployed to Railway with Tailscale forwarder for private access:

- `railway-web.toml` - Web service config
- `railway-worker.toml` - Worker service config
- Private access via Tailscale network only
