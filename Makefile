.PHONY: help install install-dev dev up down logs test lint format migrate backup clean

# Variables
PYTHON := python3.12
PIP := $(PYTHON) -m pip
DOCKER_COMPOSE := docker-compose
PROJECT_NAME := etsy-sevdesk-sync

# Colors for output
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[0;33m
RED := \033[0;31m
NC := \033[0m # No Color

##@ Help

help: ## Display this help message
	@echo "$(BLUE)$(PROJECT_NAME) - Makefile Commands$(NC)"
	@echo ""
	@awk 'BEGIN {FS = ":.*##"; printf "Usage:\n  make $(BLUE)<target>$(NC)\n"} /^[a-zA-Z_0-9-]+:.*?##/ { printf "  $(BLUE)%-20s$(NC) %s\n", $$1, $$2 } /^##@/ { printf "\n$(YELLOW)%s$(NC)\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

##@ Development

install: ## Install production dependencies
	@echo "$(GREEN)Installing production dependencies...$(NC)"
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt

install-dev: ## Install development dependencies
	@echo "$(GREEN)Installing development dependencies...$(NC)"
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements-dev.txt
	$(PIP) install -e .
	@echo "$(GREEN)Setting up pre-commit hooks...$(NC)"
	pre-commit install

dev: ## Start development environment
	@echo "$(GREEN)Starting development environment...$(NC)"
	@if [ ! -f .env ]; then \
		echo "$(YELLOW)Creating .env from .env.example...$(NC)"; \
		cp .env.example .env; \
		echo "$(RED)IMPORTANT: Edit .env and add your API credentials!$(NC)"; \
	fi
	$(DOCKER_COMPOSE) up -d postgres redis
	@echo "$(GREEN)Development environment ready!$(NC)"
	@echo "Run 'make migrate' to initialize database"
	@echo "Run 'uvicorn app.api.main:app --reload' to start API server"

##@ Docker

up: ## Start all services with Docker Compose
	@echo "$(GREEN)Starting all services...$(NC)"
	@if [ ! -f .env ]; then \
		echo "$(YELLOW)Creating .env from .env.example...$(NC)"; \
		cp .env.example .env; \
		echo "$(RED)IMPORTANT: Edit .env and add your API credentials!$(NC)"; \
		exit 1; \
	fi
	$(DOCKER_COMPOSE) up -d
	@echo "$(GREEN)Services started!$(NC)"
	@echo "API: http://localhost:8000"
	@echo "API Docs: http://localhost:8000/docs"

down: ## Stop all services
	@echo "$(YELLOW)Stopping all services...$(NC)"
	$(DOCKER_COMPOSE) down

restart: ## Restart all services
	@echo "$(YELLOW)Restarting services...$(NC)"
	$(DOCKER_COMPOSE) restart

logs: ## Tail logs from all services
	$(DOCKER_COMPOSE) logs -f

logs-api: ## Tail API logs
	$(DOCKER_COMPOSE) logs -f api

logs-worker: ## Tail Celery worker logs
	$(DOCKER_COMPOSE) logs -f worker

ps: ## Show running services
	$(DOCKER_COMPOSE) ps

##@ Database

migrate: ## Run database migrations
	@echo "$(GREEN)Running database migrations...$(NC)"
	alembic upgrade head

migration: ## Create new migration (usage: make migration message="description")
	@echo "$(GREEN)Creating new migration...$(NC)"
	@if [ -z "$(message)" ]; then \
		echo "$(RED)Error: message is required$(NC)"; \
		echo "Usage: make migration message=\"add users table\""; \
		exit 1; \
	fi
	alembic revision --autogenerate -m "$(message)"

downgrade: ## Downgrade database by 1 revision
	@echo "$(YELLOW)Downgrading database...$(NC)"
	alembic downgrade -1

db-reset: ## Reset database (WARNING: destroys all data)
	@echo "$(RED)WARNING: This will destroy all data!$(NC)"
	@read -p "Are you sure? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		alembic downgrade base; \
		alembic upgrade head; \
		echo "$(GREEN)Database reset complete$(NC)"; \
	else \
		echo "$(YELLOW)Aborted$(NC)"; \
	fi

##@ Testing

test: ## Run all tests
	@echo "$(GREEN)Running tests...$(NC)"
	pytest

test-unit: ## Run unit tests only
	@echo "$(GREEN)Running unit tests...$(NC)"
	pytest app/tests/unit -v

test-integration: ## Run integration tests only
	@echo "$(GREEN)Running integration tests...$(NC)"
	pytest app/tests/integration -v

test-cov: ## Run tests with coverage report
	@echo "$(GREEN)Running tests with coverage...$(NC)"
	pytest --cov=app --cov-report=html --cov-report=term
	@echo "$(GREEN)Coverage report generated in htmlcov/index.html$(NC)"

##@ Code Quality

lint: ## Run linters (ruff, mypy)
	@echo "$(GREEN)Running linters...$(NC)"
	ruff check app/
	mypy app/

format: ## Format code with black and isort
	@echo "$(GREEN)Formatting code...$(NC)"
	black app/
	isort app/
	@echo "$(GREEN)Code formatted!$(NC)"

format-check: ## Check code formatting without changing
	@echo "$(GREEN)Checking code formatting...$(NC)"
	black --check app/
	isort --check-only app/

pre-commit: ## Run pre-commit hooks on all files
	@echo "$(GREEN)Running pre-commit hooks...$(NC)"
	pre-commit run --all-files

##@ CLI Commands

sync-orders: ## Sync Etsy orders (usage: make sync-orders since=2025-01-01)
	@echo "$(GREEN)Syncing Etsy orders...$(NC)"
	$(PYTHON) -m app.jobs.cli sync:orders $(if $(since),--since $(since),)

sync-refunds: ## Sync Etsy refunds
	@echo "$(GREEN)Syncing Etsy refunds...$(NC)"
	$(PYTHON) -m app.jobs.cli sync:refunds $(if $(since),--since $(since),)

sync-fees: ## Sync Etsy fees (usage: make sync-fees period=2025-11)
	@echo "$(GREEN)Syncing Etsy fees...$(NC)"
	$(PYTHON) -m app.jobs.cli sync:fees $(if $(period),--period $(period),)

sync-payouts: ## Sync Etsy payouts
	@echo "$(GREEN)Syncing Etsy payouts...$(NC)"
	$(PYTHON) -m app.jobs.cli sync:payouts $(if $(since),--since $(since),)

backfill: ## Run full backfill of all data
	@echo "$(GREEN)Running full backfill...$(NC)"
	$(PYTHON) -m app.jobs.cli backfill:all

##@ Backup & Maintenance

backup: ## Create database backup
	@echo "$(GREEN)Creating database backup...$(NC)"
	@mkdir -p backups
	@TIMESTAMP=$$(date +%Y%m%d_%H%M%S); \
	$(DOCKER_COMPOSE) exec -T postgres pg_dump -U etsy_sync etsy_sevdesk > backups/backup_$$TIMESTAMP.sql
	@echo "$(GREEN)Backup created: backups/backup_$$TIMESTAMP.sql$(NC)"

restore: ## Restore database from backup (usage: make restore file=backup_20250109_120000.sql)
	@echo "$(YELLOW)Restoring database from backup...$(NC)"
	@if [ -z "$(file)" ]; then \
		echo "$(RED)Error: file is required$(NC)"; \
		echo "Usage: make restore file=backup_20250109_120000.sql"; \
		exit 1; \
	fi
	@if [ ! -f "backups/$(file)" ]; then \
		echo "$(RED)Error: backup file not found$(NC)"; \
		exit 1; \
	fi
	$(DOCKER_COMPOSE) exec -T postgres psql -U etsy_sync etsy_sevdesk < backups/$(file)
	@echo "$(GREEN)Database restored from backup$(NC)"

cleanup: ## Cleanup expired idempotency keys and old logs
	@echo "$(GREEN)Running cleanup tasks...$(NC)"
	$(PYTHON) -m app.jobs.cli maintenance:cleanup

##@ Build

build: ## Build Docker images
	@echo "$(GREEN)Building Docker images...$(NC)"
	$(DOCKER_COMPOSE) build

rebuild: ## Rebuild Docker images without cache
	@echo "$(GREEN)Rebuilding Docker images...$(NC)"
	$(DOCKER_COMPOSE) build --no-cache

##@ Cleanup

clean: ## Clean temporary files and caches
	@echo "$(YELLOW)Cleaning temporary files...$(NC)"
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -f .coverage 2>/dev/null || true
	rm -rf htmlcov/ 2>/dev/null || true
	rm -f test.db 2>/dev/null || true
	@echo "$(GREEN)Cleanup complete!$(NC)"

clean-all: clean down ## Clean everything including Docker volumes
	@echo "$(RED)Removing Docker volumes (all data will be lost)...$(NC)"
	@read -p "Are you sure? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		$(DOCKER_COMPOSE) down -v; \
		echo "$(GREEN)All cleaned up!$(NC)"; \
	else \
		echo "$(YELLOW)Aborted$(NC)"; \
	fi

##@ Monitoring

health: ## Check API health
	@echo "$(GREEN)Checking API health...$(NC)"
	@curl -f http://localhost:8000/health || echo "$(RED)API is not responding$(NC)"

status: ## Show system status
	@echo "$(BLUE)=== System Status ===$(NC)"
	@echo ""
	@echo "$(YELLOW)Docker Services:$(NC)"
	@$(DOCKER_COMPOSE) ps
	@echo ""
	@echo "$(YELLOW)Database:$(NC)"
	@alembic current 2>/dev/null || echo "Not initialized"
	@echo ""
	@echo "$(YELLOW)Environment:$(NC)"
	@if [ -f .env ]; then \
		echo "✓ .env file exists"; \
	else \
		echo "$(RED)✗ .env file missing$(NC)"; \
	fi
