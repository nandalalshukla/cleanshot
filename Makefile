# Common developer commands. Run `make help` for a list.
.PHONY: help setup worker app test lint format docker

help:
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-10s %s\n", $$1, $$2}'

setup: ## Install worker (venv) and app dependencies
	cd worker && python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
	cd app && npm install

worker: ## Run the worker with auto-reload on :8000
	cd worker && .venv/bin/uvicorn cleanshot_worker.main:create_app --factory --reload --host 0.0.0.0

app: ## Start the Expo dev server
	cd app && npx expo start

test: ## Run all tests
	cd worker && .venv/bin/pytest
	cd app && npm test -- --ci

lint: ## Lint and type-check everything
	cd worker && .venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/mypy cleanshot_worker
	cd app && npm run typecheck && npm run lint && npx prettier --check "src/**/*.{ts,tsx}"

format: ## Auto-format code
	cd worker && .venv/bin/ruff format . && .venv/bin/ruff check --fix .
	cd app && npm run format

docker: ## Build and start the worker in Docker
	docker compose up -d --build
