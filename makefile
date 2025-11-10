# Constants
# ==============================================================================

COLOR_BLUE=\033[0;34m
COLOR_NONE=\033[0m

PYTHON_VERSION=python3.13

PROJECT_NAME=cost_explorer

SENTINEL_FILE_DEPS=.make-sentinel.deps

# Proxy certificates
export SSL_CERT_FILE=/etc/ssl/cert.pem

TEST_FILE=tests/cost_explorer/test_console.py

# Targets
# ==============================================================================

# Help
# ======================================

help:
	@grep -E '^[0-9a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| sort \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "$(COLOR_BLUE)%s|$(COLOR_NONE)%s\n", $$1, $$2}' \
		| column -t -s '|'

# Clean
# ======================================

.PHONY: stop
stop: ## Stop any running processes
	@echo 'Stopping processes'
	@uv run dmypy stop || true

.PHONY: clean
clean: stop ## Remove all artefacts
	@echo 'Cleaning application'

.PHONY: clean-all
clean-all: clean ## Remove all artefacts and dependencies
	@echo 'Cleaning dependencies'
	@rm -rf dist/ htmlcov/
	@rm -f $(SENTINEL_FILE_DEPS)
	@rm -rf .venv

# Dependencies
# ======================================

$(SENTINEL_FILE_DEPS): pyproject.toml
	@echo 'Setting Python version to $(PYTHON_VERSION)'
	@uv python pin $(PYTHON_VERSION)
	@echo 'Fetching dependencies'
	export REQUESTS_CA_BUNDLE=$(SSL_CERT_FILE) \
		&& uv sync --all-extras
	@touch .make-sentinel.deps

deps: $(SENTINEL_FILE_DEPS) ## Install dependencies

.PHONY: deps-lock
deps-lock:
	@echo 'Locking uv file'
	@uv lock

.PHONY: deps-scan
deps-scan: deps
	@echo 'Scanning dependencies for security vulnerabilities'
	@uv run pip-audit -r <(uv export --format requirements-txt --all-extras)

.PHONY: deps-update
deps-update: clean-all ## Update dependency versions
	@echo 'Updating dependencies'
	@uv sync --upgrade --all-extras

.PHONY: deps-add
deps-add: ## Add a dependency (use DEP=foo to specify the dependency)
	@uv add $(DEP)

.PHONY: deps-remove
deps-remove: ## Remove a dependency (use DEP=foo to specify the dependency)
	@uv remove $(DEP)

# Running
# ======================================

run: deps ## Run the app
	@echo 'Running application'
	@export REQUESTS_CA_BUNDLE=$(SSL_CERT_FILE) \
		&& uv run run-app
	@echo

test-single-file: deps ## Run a single test file with coverage
	@echo 'Running test $(TEST_FILE)'
	@uv run coverage run --source=src -m pytest $(TEST_FILE)
	@uv run coverage html

test: deps ## Run the tests
	@echo 'Running tests'
	@uv run pytest --cov
	@uv run coverage html
	@echo

check: deps ## Check the code
	@echo 'Running linter'
	@uv run ruff check
	@echo
	@echo 'Running static type checks'
	@uv run dmypy run -- src tests
	@echo

fix: format deps ## Fix formatting and minor style issues
	@echo 'Fixing problems'
	@uv run ruff check --fix
	@echo

format: deps ## Format the code
	@echo 'Formatting code'
	@uv run isort src tests
	@uv run black src tests
	@echo

build: format test check ## Build the code
	@echo 'Building artefacts'
	@uv build
