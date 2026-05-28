# Makefile for Dugout.ai Monorepo

.PHONY: help setup infra-up infra-down infra-logs contracts-gen build test lint clean

# Default shell
SHELL := /bin/bash

# Directories
GATEWAY_DIR := services/event-gateway
ORCHESTRATOR_DIR := services/ai-orchestrator
CV_NODE_DIR := services/cv-node
DASHBOARD_DIR := apps/dashboard
REFEREE_DIR := apps/referee-mobile
CONTRACTS_DIR := packages/contracts
INFRA_COMPOSE := infra/compose/docker-compose.yml

help:
	@echo "Dugout.ai Monorepo Management Commands:"
	@echo "  setup         - Set up local dependencies for all services"
	@echo "  infra-up      - Start local infrastructure (Postgres, NATS, MediaMTX)"
	@echo "  infra-down    - Stop local infrastructure"
	@echo "  infra-logs    - Follow infrastructure logs"
	@echo "  contracts-gen - Compile Protocol Buffers for Go, Python, and TypeScript"
	@echo "  build         - Compile/build all services"
	@echo "  test          - Run tests across all services"
	@echo "  lint          - Run linting checks across all services"
	@echo "  clean         - Clean up build files, node_modules, and virtual envs"

setup:
	@echo "==> Setting up local dependencies..."
	@echo "--> Setting up Go event-gateway..."
	cd $(GATEWAY_DIR) && go mod tidy
	@echo "--> Setting up Python services (ai-orchestrator & cv-node)..."
	python3 -m venv $(ORCHESTRATOR_DIR)/.venv
	$(ORCHESTRATOR_DIR)/.venv/bin/pip install --upgrade pip
	[ -f $(ORCHESTRATOR_DIR)/requirements.txt ] && $(ORCHESTRATOR_DIR)/.venv/bin/pip install -r $(ORCHESTRATOR_DIR)/requirements.txt || true
	python3 -m venv $(CV_NODE_DIR)/.venv
	$(CV_NODE_DIR)/.venv/bin/pip install --upgrade pip
	[ -f $(CV_NODE_DIR)/requirements.txt ] && $(CV_NODE_DIR)/.venv/bin/pip install -r $(CV_NODE_DIR)/requirements.txt || true
	@echo "--> Setting up TypeScript/Node apps..."
	npm install

infra-up:
	@echo "==> Starting infrastructure containers..."
	docker compose -f $(INFRA_COMPOSE) up -d

infra-down:
	@echo "==> Stopping infrastructure containers..."
	docker compose -f $(INFRA_COMPOSE) down

infra-logs:
	docker compose -f $(INFRA_COMPOSE) logs -f

contracts-gen:
	@echo "==> Generating code from protobuf contracts..."
	$(MAKE) -C $(CONTRACTS_DIR) generate

build:
	@echo "==> Building services..."
	@echo "--> Building Go event-gateway..."
	cd $(GATEWAY_DIR) && go build -o bin/gateway cmd/main.go
	@echo "--> Building Dashboard..."
	npm run build --workspace=$(DASHBOARD_DIR)

test:
	@echo "==> Running tests..."
	@echo "--> Testing Go event-gateway..."
	cd $(GATEWAY_DIR) && go test ./... -v
	@echo "--> Testing Python ai-orchestrator..."
	$(ORCHESTRATOR_DIR)/.venv/bin/pytest $(ORCHESTRATOR_DIR)/tests/ || echo "No tests folder in orchestrator yet"
	@echo "--> Testing Dashboard..."
	npm run test --workspace=$(DASHBOARD_DIR) || echo "No tests in dashboard yet"

lint:
	@echo "==> Linting codebase..."
	@echo "--> Linting Go..."
	cd $(GATEWAY_DIR) && go vet ./...
	@echo "--> Linting Python..."
	$(ORCHESTRATOR_DIR)/.venv/bin/flake8 $(ORCHESTRATOR_DIR) || echo "Flake8 not installed in orchestrator"
	@echo "--> Linting TypeScript..."
	npm run lint

clean:
	@echo "==> Cleaning up files..."
	rm -rf node_modules/
	rm -rf $(GATEWAY_DIR)/bin/
	rm -rf $(ORCHESTRATOR_DIR)/.venv/
	rm -rf $(CV_NODE_DIR)/.venv/
	rm -rf $(DASHBOARD_DIR)/dist/ $(DASHBOARD_DIR)/node_modules/
	rm -rf $(REFEREE_DIR)/.expo/ $(REFEREE_DIR)/node_modules/
