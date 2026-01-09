# Giant Wiki

Internal documentation wiki with Git-based storage, deployed privately via Tailscale.

## Features

- **Git-based storage** - Wiki pages stored as markdown files in a Git repository
- **Full-text search** - SQLite FTS5 for fast, ephemeral search index
- **Background sync** - Celery tasks sync changes to Git remote
- **Mermaid diagrams** - Support for flowcharts, sequence diagrams, and other visualizations
- **Teams notifications** - Optional notifications to Microsoft Teams when pages are created, edited, moved, or deleted
- **Private access** - Tailscale boundary, no authentication required
- **Modern UI** - Tailwind CSS with Giant Tool Design System

## Quick Start

```bash
# Initial setup
make install

# Start development server
make server

# Run tests
make test
```

## Development

See [CLAUDE.md](CLAUDE.md) for detailed project documentation.

### Key Commands

| Command | Purpose |
|---------|---------|
| `make server` | Start all services |
| `make test` | Run tests |
| `make format` | Lint and format code |
| `make logs` | Follow service logs |

## Deployment

Deployed to Railway with Tailscale forwarder:

1. Configure `WIKI_REPO_URL` pointing to content repository
2. Set `GIT_SSH_KEY` (base64-encoded) for Git authentication
3. (Optional) Configure `TEAMS_NOTIFICATION_WEBHOOK` for Teams notifications
4. (Optional) Set `SITE_URL` base URL for notification links
5. Deploy web and worker services

Access via Tailscale network only.
