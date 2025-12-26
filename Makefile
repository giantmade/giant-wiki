.PHONY: install server build up down restart logs logs-web logs-worker ps
.PHONY: test test-fast cov format shell clean

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
