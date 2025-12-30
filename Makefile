.PHONY: install server build up down restart logs logs-web logs-worker ps
.PHONY: test test-fast cov format shell clean clone-content

# Helper to auto-start Docker if needed
define ensure_docker_running
	@if ! docker compose ps web 2>/dev/null | grep -q "Up"; then \
		echo "Starting Docker services..."; \
		docker compose up -d --wait; \
	fi
endef

# =============================================================================
# SETUP & LIFECYCLE
# =============================================================================

install:
	@echo "Building Docker images..."
	docker compose build
	@if [ ! -f .env ]; then \
		echo "Creating .env file from .env.example..."; \
		cp .env.example .env; \
		echo "Remember to configure your .env file"; \
	fi
	@mkdir -p var/data var/logs var/repo var/static var/media

server:
	@echo "Starting Docker services..."
	docker compose up

build:
	@echo "Building Docker images..."
	docker compose build

up:
	@echo "Starting Docker services in background..."
	docker compose up -d

down:
	@echo "Stopping Docker services..."
	docker compose down

restart:
	@echo "Restarting Docker services..."
	docker compose restart web worker

clean:
	@echo "Stopping Docker containers..."
	docker compose down --remove-orphans
	@echo "Cleaning runtime data..."
	rm -rf var/data/* var/logs/* var/static/*
	@echo "Done. Run 'make install' to rebuild."

# =============================================================================
# TESTING
# =============================================================================

test:
	@echo "Running tests..."
	$(call ensure_docker_running)
	docker compose exec web uv run pytest -n auto

test-fast:
	@echo "Running affected tests (testmon)..."
	$(call ensure_docker_running)
	docker compose exec web uv run pytest --testmon -q

cov:
	@echo "Running tests with coverage..."
	$(call ensure_docker_running)
	docker compose exec web uv run pytest -n auto --cov --cov-report=term-missing --cov-report=html

# =============================================================================
# CODE QUALITY
# =============================================================================

format:
	@echo "Formatting code..."
	$(call ensure_docker_running)
	docker compose exec web uv run ruff check --fix .
	docker compose exec web uv run ruff format .

# =============================================================================
# DJANGO OPERATIONS
# =============================================================================

shell:
	@echo "Opening Django shell..."
	$(call ensure_docker_running)
	docker compose exec web uv run python manage.py shell

collectstatic:
	@echo "Collecting static files..."
	$(call ensure_docker_running)
	docker compose exec web uv run python manage.py collectstatic --noinput

# =============================================================================
# WIKI OPERATIONS
# =============================================================================

clone-content:
	@if [ -d var/repo ]; then \
		echo "Removing existing var/repo (may need Docker for permissions)..."; \
		rm -rf var/repo 2>/dev/null || docker run --rm -v "$(PWD)/var:/var" alpine rm -rf /var/repo; \
	fi
	@if [ -z "$(WIKI_REPO_URL)" ]; then \
		if [ -f .env ]; then \
			WIKI_REPO_URL=$$(grep -E '^WIKI_REPO_URL=' .env | cut -d'=' -f2-); \
		fi; \
		if [ -z "$$WIKI_REPO_URL" ]; then \
			echo "Error: WIKI_REPO_URL not set. Either:"; \
			echo "  1. Set WIKI_REPO_URL in .env"; \
			echo "  2. Run: make clone-content WIKI_REPO_URL=git@github.com:org/repo.git"; \
			exit 1; \
		fi; \
		echo "Cloning wiki content from $$WIKI_REPO_URL..."; \
		git clone "$$WIKI_REPO_URL" var/repo; \
	else \
		echo "Cloning wiki content from $(WIKI_REPO_URL)..."; \
		git clone "$(WIKI_REPO_URL)" var/repo; \
	fi
	@echo "Done. Run 'make restart' to reload."

rebuild-search:
	@echo "Rebuilding search index..."
	$(call ensure_docker_running)
	docker compose exec web uv run python manage.py rebuild_search

sync-git:
	@echo "Syncing with Git remote..."
	$(call ensure_docker_running)
	docker compose exec web uv run python manage.py sync_git

# =============================================================================
# LOGGING & STATUS
# =============================================================================

logs:
	@echo "Following logs for all services..."
	docker compose logs -f web worker

logs-web:
	@echo "Following web service logs..."
	docker compose logs -f web

logs-worker:
	@echo "Following worker logs..."
	docker compose logs -f worker

ps:
	@echo "Docker services status:"
	docker compose ps
