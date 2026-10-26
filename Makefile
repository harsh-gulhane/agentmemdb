.DEFAULT_GOAL := help
.PHONY: help install lint format typecheck test cov build check clean

help: ## Show available targets
	@awk 'BEGIN {FS = ":.*## "} /^[a-z-]+:.*## / {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install: ## Create .venv with the package (editable) and dev tools
	uv sync

lint: ## Lint and check formatting
	uv run ruff check .
	uv run ruff format --check .

format: ## Fix lint issues and format the code
	uv run ruff check --fix .
	uv run ruff format .

typecheck: ## Type-check with mypy (strict)
	uv run mypy

test: ## Run the test suite
	uv run pytest

cov: ## Run the tests with a coverage report
	uv run pytest --cov --cov-report=term-missing

build: ## Build the sdist and wheel, then validate them
	rm -rf dist
	uv build
	uv run twine check --strict dist/*

check: lint typecheck test ## Run everything CI runs

clean: ## Remove build artifacts and caches
	rm -rf build dist .coverage htmlcov .mypy_cache .pytest_cache .ruff_cache src/*.egg-info
