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

### Frontmatter Metadata

Pages support YAML frontmatter for metadata:

```yaml
---
title: "Page Title"
author: "Alice"
last_updated: 2026-01-06 16:56:00.736849
---
```

**System-Managed Fields:**
- `last_updated` - Automatically set on every save (format: `YYYY-MM-DD HH:MM:SS.ffffff`)
- Only updated when content or user metadata actually changes
- Not editable by users (excluded from edit form)

**User-Editable Fields:**
- All other fields are user-defined and editable
- Types auto-detected for form rendering (string, number, date, datetime, boolean, list)
- `title` field is special - shown in page header, not in properties panel

Implementation: `src/wiki/services/git_storage.py` (SYSTEM_MANAGED_FIELDS constant)

## Page Features

### CRUD Operations

All wiki pages have CRUD buttons in the header for page management:

**Create New Pages:**
- "New Page" button opens modal dialog
- Enter page path (e.g., "guides/setup" or "teams/engineering")
- Client-side validation prevents invalid paths (.., absolute paths)
- Redirects to edit page for new content

**Delete Pages:**
- "Delete" button with confirmation dialog
- Removes page file from Git repository
- Removes from search index
- Invalidates sidebar and widget caches
- Leaves attachments orphaned (safer for recovery)
- Commits with message "Delete: {page_path}"

**Move/Rename Pages:**
- "Move" button opens modal dialog
- Shows current path and accepts new path input
- Moves page file and attachments directory automatically
- Updates search index (removes old, adds new)
- Invalidates caches
- Commits with message "Move: {old} -> {new}"
- Note: Wikilinks in other pages are NOT automatically updated

**Archive Pages:**
- "Archive" button opens confirmation modal
- Automatically moves page to `archive/{original_path}`
- Moves attachments with page
- Updates search index (removes old, adds new)
- Invalidates caches
- Commits with message "Archive: {page_path}"
- Prevents double-archiving (pages already in archive/)
- Note: Archived pages remain accessible and visible in sidebar

**Button Styling:**
- All buttons use subtle gray backgrounds (`bg-gray-100 hover:bg-gray-200`)
- Differentiated by text and icon colors: blue (New), gray (Move), green (Edit), amber (Archive), red (Delete)
- Maintains accessibility with proper focus rings

**Button Order:** [New Page] [Move] [Edit] [Archive] [Delete]

**Implementation:**
- Views: `delete()`, `move()`, `archive()` in `src/wiki/views.py`
- Service methods: `delete_page()`, `move_page()` in `src/wiki/services/git_storage.py`
- URL patterns: `/wiki/<path>/delete/`, `/wiki/<path>/move/`, `/wiki/<path>/archive/`
- Template: `src/core/templates/wiki/page.html` (Alpine.js modals)

### GitHub Source Link

Each wiki page displays a "View source" link in the footer that links to the original markdown file on GitHub.

- **Configuration:** Set `WIKI_REPO_URL` to enable (automatically detected from environment)
- **Supported formats:** Both SSH (`git@github.com:org/repo.git`) and HTTPS (`https://github.com/org/repo.git`)
- **Branch:** Uses `WIKI_REPO_BRANCH` if set, otherwise defaults to `main`
- **Location:** Footer below main content card
- **Implementation:** `get_github_source_url()` in `src/wiki/services/git_storage.py`

### Index Page Widgets

The index page (`/wiki/index/`) displays two dashboard widgets below the main content:

**Recently Updated Widget:**
- Shows 8 most recently changed pages
- Clock icon with green links
- Sorted by `last_updated` frontmatter or file modification time

**Needs Review Widget:**
- Shows pages approaching stale status (270-365 days old)
- Warning triangle icon with amber styling
- Helps identify content that may need updating

**Performance:**
- Widgets load only on index page (zero impact on other pages)
- Redis caching with 30-minute TTL
- Caches pre-warmed on startup and after Git sync
- Invalidated on page edits

**Implementation:**
- Data service: `src/wiki/services/widgets.py`
- Batch data fetching: `get_pages_with_dates()` in `src/wiki/services/git_storage.py`
- Template: `src/core/templates/wiki/page.html` (conditional rendering)
- Cache warming: `src/wiki/tasks.py` (warm_sidebar_cache task)

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
| `TEAMS_NOTIFICATION_WEBHOOK` | Teams webhook URL for notifications (optional) |
| `SITE_URL` | Base URL for wiki (required for Teams notifications) |

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

## Teams Notifications

The wiki can send notifications to Microsoft Teams when pages are created, edited, moved, or deleted.

### Configuration

| Variable | Description |
|----------|-------------|
| `TEAMS_NOTIFICATION_WEBHOOK` | Microsoft Teams webhook URL (optional) |
| `SITE_URL` | Base URL for constructing page links (required if using notifications) |

### Notification Types

- **Create**: "New page created: [Page Title]" with link to page
- **Edit**: "Page updated: [Page Title]" with link to page
- **Delete**: "Page deleted: [Page Title]" (no link)
- **Move**: "Page moved: [Page Title]" with link to new location
- **Archive**: "Page archived: [Page Title]" with link to archived location

### Implementation

- Notifications sent asynchronously via Celery task `wiki.send_teams_notification`
- Page operations never fail if notification webhook fails
- Errors logged to task logs but marked as "completed_with_errors"
- Notifications skipped silently if `TEAMS_NOTIFICATION_WEBHOOK` not configured

### Message Format

Uses Microsoft Teams Adaptive Cards v1.2:
- Simple card with title and "View Page" button
- Generic messages without user attribution
- 10-second timeout for webhook requests

### Error Handling

All errors are gracefully handled:
- Webhook not configured: Skip silently
- Invalid `SITE_URL`: Log error, complete task with errors
- Webhook timeout: Log warning, complete task with errors
- Connection error: Log warning, complete task with errors
- HTTP 4xx/5xx: Log warning, complete task with errors

Notifications are fire-and-forget - errors never block page operations.

## Deployment

Deployed to Railway with Tailscale forwarder for private access:

- `railway-web.toml` - Web service config
- `railway-worker.toml` - Worker service config
- Private access via Tailscale network only
