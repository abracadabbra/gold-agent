.PHONY: install dev test lint typecheck clean frontend-install frontend-test

# ── 后端 ──

install:
	pip install -e ".[dev]"

dev:
	uvicorn gold_agent.main:app --reload --host 0.0.0.0 --port 8001

test:
	pytest -v --tb=short

lint:
	ruff check src/ tests/

typecheck:
	mypy src/

format:
	ruff check src/ tests/ --fix

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -delete

# ── 前端 ──

frontend-install:
	cd frontend && npm ci

frontend-dev:
	cd frontend && npm run dev

frontend-test:
	cd frontend && npm test

frontend-lint:
	cd frontend && npx eslint src/

# ── Docker ──

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

docker-build:
	docker-compose build --no-cache

# ── 全量检查 ──

check: lint typecheck test frontend-test
