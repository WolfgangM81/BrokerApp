# BrokerApp developer entrypoints.
# `make help` to list targets.

SHELL := /bin/bash
.DEFAULT_GOAL := help

# ---------------------------------------------------------------------------
# Help
# ---------------------------------------------------------------------------

.PHONY: help
help: ## Show this help
	@awk 'BEGIN {FS = ":.*##"; printf "Targets:\n"} /^[a-zA-Z0-9_.-]+:.*##/ { printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

.PHONY: install
install: install-python install-node install-hooks ## Install all deps + pre-commit hooks

.PHONY: install-python
install-python: ## Install Python deps via uv
	uv sync --all-extras

.PHONY: install-node
install-node: ## Install Node deps via pnpm
	pnpm install

.PHONY: install-hooks
install-hooks: ## Install pre-commit hooks
	pre-commit install

# ---------------------------------------------------------------------------
# Local infrastructure (docker-compose)
# ---------------------------------------------------------------------------

.PHONY: up
up: ## Start local infra (TimescaleDB, Redis, MinIO, MLflow, MailHog)
	docker compose up -d

.PHONY: down
down: ## Stop local infra
	docker compose down

.PHONY: nuke
nuke: ## Stop local infra and DELETE all data volumes (destructive!)
	docker compose down -v

.PHONY: logs
logs: ## Tail logs from all local infra services
	docker compose logs -f

# ---------------------------------------------------------------------------
# Dev
# ---------------------------------------------------------------------------

.PHONY: dev
dev: ## Run api + web in dev mode (requires `make up` first)
	pnpm dev & uv run --package brokerapp-api uvicorn api.main:app --reload --port 8000

.PHONY: dev-api
dev-api: ## Run only the API in dev mode
	uv run --package brokerapp-api uvicorn api.main:app --reload --port 8000

.PHONY: dev-web
dev-web: ## Run only the web app in dev mode
	pnpm --filter @brokerapp/web dev

.PHONY: dev-worker
dev-worker: ## Run a Celery worker locally
	uv run --package brokerapp-ingest celery -A ingest.celery_app:celery_app worker --loglevel=INFO --concurrency=2

# ---------------------------------------------------------------------------
# Quality
# ---------------------------------------------------------------------------

.PHONY: lint
lint: lint-python lint-ts lint-helm ## Run all linters

.PHONY: lint-python
lint-python: ## Lint and type-check Python
	uv run ruff check .
	uv run ruff format --check .

.PHONY: lint-ts
lint-ts: ## Lint TypeScript
	pnpm -r run lint
	pnpm format:check

.PHONY: lint-helm
lint-helm: ## Lint Helm charts
	@for c in infra/helm/api infra/helm/web infra/helm/worker; do \
		echo ">>> helm lint $$c"; helm lint $$c || exit $$?; \
	done
	helm dependency update infra/helm/umbrella
	helm lint infra/helm/umbrella

.PHONY: format
format: ## Auto-format everything
	uv run ruff format .
	uv run ruff check --fix .
	pnpm format

.PHONY: test
test: test-python test-ts ## Run all tests

.PHONY: test-python
test-python: ## Run Python tests
	uv run --package brokerapp-api pytest apps/api
	uv run --package brokerapp-ingest pytest services/ingest

.PHONY: test-ts
test-ts: ## Run TypeScript tests
	pnpm -r run test

.PHONY: typecheck
typecheck: ## Type-check Python and TypeScript
	uv run mypy apps/api/src services/ingest/src
	pnpm -r run typecheck

# ---------------------------------------------------------------------------
# Helm helpers
# ---------------------------------------------------------------------------

.PHONY: helm-template
helm-template: ## Render the umbrella chart for inspection
	helm dependency update infra/helm/umbrella
	helm template brokerapp infra/helm/umbrella --namespace brokerapp

.PHONY: helm-deps
helm-deps: ## Update Helm sub-chart dependencies
	helm dependency update infra/helm/umbrella

# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

.PHONY: clean
clean: ## Remove caches and build artifacts (keeps volumes)
	rm -rf .venv .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov
	rm -rf node_modules apps/*/node_modules packages/*/node_modules
	rm -rf apps/web/.next apps/web/out
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
