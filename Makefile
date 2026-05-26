# Makefile — Medical Professionals Review

.PHONY: dev-setup run-backend run-gateway run-audit run-monitor run-search-service run-report-service run-payment-service run-worker run-frontend lint test \
        infra-init infra-validate infra-plan infra-apply infra-fmt \
        obs-validate \
        gitops-validate gitops-guard \
        opa-test connectors-test normalizers-test identity-test entity-linker-test search-test report-test worker-test payment-test frontend-test \
        help

ENV ?= dev

help:
	@echo "Medical Professionals Review — Make Targets"
	@echo ""
	@echo "  dev-setup            Install local development dependencies (idempotent)"
	@echo "  run-backend          Start the auth service dev server (Phase 1-F)"
	@echo "  run-gateway          Start the API gateway dev server (Phase 1-G)"
	@echo "  run-audit            Start the audit ledger service dev server (Phase 1-I)"
	@echo "  run-monitor          Start the source health monitor dev server (Phase 2-C)"
	@echo "  run-frontend         Start Next.js frontend dev server (Phase 2-K, port 3100)"
	@echo "  lint                 Run all linters (Python: black/flake8/mypy; TS: eslint/prettier)"
	@echo "  test                 Run all tests (pytest + jest)"
	@echo ""
	@echo "  infra-fmt            Check Terraform formatting (all modules)"
	@echo "  infra-validate       Validate Terraform syntax (all modules)"
	@echo "  infra-init ENV=dev   terragrunt run-all init for ENV"
	@echo "  infra-plan ENV=dev   terragrunt run-all plan for ENV"
	@echo "  infra-apply ENV=dev  terragrunt run-all apply for ENV (requires approval)"
	@echo ""
	@echo "  obs-validate         Validate observability configs (Phase 1-D, no cluster needed)"
	@echo ""
	@echo "  gitops-validate      Validate ArgoCD app-of-apps configs (Phase 1-E, no cluster needed)"
	@echo "  gitops-guard         Deploy-time PLACEHOLDER guard — blocks ArgoCD sync until Entry 003"
	@echo ""
	@echo "  opa-test             Run OPA policy unit tests (Phase 1-H, requires opa CLI)"
	@echo "  connectors-test      Run Source Connector Framework tests (Phase 2-A)"
	@echo "  normalizers-test     Run Normalization Layer tests (Phase 2-D)"
	@echo "  identity-test        Run Identity Resolution Engine tests (Phase 2-E)"
	@echo "  entity-linker-test   Run Entity Linking & Merge tests (Phase 2-F)"
	@echo "  search-test          Run Provider Search Service tests (Phase 2-G)"
	@echo ""
	@echo "  NOTE: infra-plan/apply require DECISIONS.md Entry 003 to be resolved."
	@echo "        All PLACEHOLDER values in environments/\$$ENV/env.hcl must be filled."

dev-setup:
	bash scripts/dev-setup.sh

run-backend:
	@echo "Starting auth service (Phase 1-F shell) on http://localhost:8000 ..."
	@echo "Try: curl localhost:8000/healthz  |  docs at /docs"
	PYTHONPATH=src uvicorn backend.auth_service.app:app --reload --port 8000

run-gateway:
	@echo "Starting API gateway (Phase 1-G shell) on http://localhost:8080 ..."
	@echo "Try: curl localhost:8080/healthz  |  docs at /docs"
	PYTHONPATH=src uvicorn backend.api_gateway.app:app --reload --port 8080

run-audit:
	@echo "Starting audit ledger service (Phase 1-I shell) on http://localhost:8001 ..."
	@echo "Try: curl localhost:8001/healthz  |  docs at /docs"
	PYTHONPATH=src uvicorn backend.audit_service.app:app --reload --port 8001

run-monitor:
	@echo "Starting source health monitor (Phase 2-C shell) on http://localhost:8002 ..."
	@echo "Try: curl localhost:8002/healthz  |  docs at /docs"
	PYTHONPATH=src uvicorn backend.source_health_monitor.app:app --reload --port 8002

run-search-service:
	@echo "Starting provider search service (Phase 2-G shell) on http://localhost:8003 ..."
	@echo "Try: curl localhost:8003/healthz  |  docs at /docs"
	@echo "     curl 'localhost:8003/v1/providers/search?q=Smith&state=CA'"
	PYTHONPATH=src uvicorn backend.search_service.app:app --reload --port 8003

run-frontend:
	@echo "Starting Next.js frontend (Phase 2-K) on http://localhost:3100 ..."
	@echo "Copy src/frontend/.env.local.example to src/frontend/.env.local and fill in Auth0 credentials first."
	cd src/frontend && npm run dev

lint:
	cd src/backend && poetry run black --check . && poetry run flake8 . && poetry run mypy . 2>/dev/null || \
		echo "[No backend source yet] lint will activate when src/backend/ is populated."

test:
	PYTHONPATH=src poetry run pytest tests/ -v

infra-fmt:
	@echo "Checking Terraform formatting..."
	@find src/infrastructure/modules -name "*.tf" | xargs terraform fmt -check -diff
	@echo "All .tf files are correctly formatted."

infra-validate:
	@echo "Validating Terraform modules..."
	@for module in src/infrastructure/modules/*/; do \
		echo "  -> $$module"; \
		cd $$module && terraform init -backend=false -input=false -no-color > /dev/null && \
		terraform validate -no-color && cd - > /dev/null; \
	done
	@echo "All modules validated."

infra-init:
	@echo "Initializing Terragrunt for ENV=$(ENV)..."
	@if grep -r "PLACEHOLDER" src/infrastructure/environments/$(ENV)/env.hcl > /dev/null 2>&1; then \
		echo "ERROR: PLACEHOLDER values found in environments/$(ENV)/env.hcl"; \
		echo "Resolve DECISIONS.md Entry 003 before running infra-init."; \
		exit 1; \
	fi
	cd src/infrastructure/environments/$(ENV) && terragrunt run-all init

infra-plan:
	@echo "Planning Terragrunt for ENV=$(ENV)..."
	@if grep -r "PLACEHOLDER" src/infrastructure/environments/$(ENV)/env.hcl > /dev/null 2>&1; then \
		echo "ERROR: PLACEHOLDER values found in environments/$(ENV)/env.hcl"; \
		echo "Resolve DECISIONS.md Entry 003 before running infra-plan."; \
		exit 1; \
	fi
	cd src/infrastructure/environments/$(ENV) && terragrunt run-all plan

infra-apply:
	@echo "Applying Terragrunt for ENV=$(ENV)..."
	@if grep -r "PLACEHOLDER" src/infrastructure/environments/$(ENV)/env.hcl > /dev/null 2>&1; then \
		echo "ERROR: PLACEHOLDER values found in environments/$(ENV)/env.hcl"; \
		echo "Resolve DECISIONS.md Entry 003 before running infra-apply."; \
		exit 1; \
	fi
	cd src/infrastructure/environments/$(ENV) && terragrunt run-all apply

obs-validate:
	@echo "Validating observability configs (Phase 1-D)..."
	PYTHONPATH=src poetry run pytest tests/observability/ -v 2>/dev/null || \
		PYTHONPATH=src pytest tests/observability/ -v

gitops-validate:
	@echo "Validating GitOps / ArgoCD configs (Phase 1-E)..."
	PYTHONPATH=src poetry run pytest tests/gitops/ -v 2>/dev/null || \
		PYTHONPATH=src pytest tests/gitops/ -v

gitops-guard:
	@bash scripts/gitops-guard.sh

opa-test:
	@echo "Validating + testing OPA policy bundle (Phase 1-H)..."
	opa check src/policy
	opa test src/policy -v

connectors-test:
	@echo "Testing the Source Connector Framework (Phase 2-A)..."
	PYTHONPATH=src poetry run pytest tests/connectors/ -v 2>/dev/null || \
		PYTHONPATH=src pytest tests/connectors/ -v

normalizers-test:
	@echo "Testing the Normalization Layer (Phase 2-D, C11)..."
	PYTHONPATH=src poetry run pytest tests/normalizers/ -v 2>/dev/null || \
		PYTHONPATH=src pytest tests/normalizers/ -v

identity-test:
	@echo "Testing the Identity Resolution Engine (Phase 2-E, C12)..."
	PYTHONPATH=src poetry run pytest tests/identity/ -v 2>/dev/null || \
		PYTHONPATH=src pytest tests/identity/ -v

entity-linker-test:
	@echo "Testing the Entity Linking & Merge Engine (Phase 2-F, C13)..."
	PYTHONPATH=src poetry run pytest tests/entity_linker/ -v 2>/dev/null || \
		PYTHONPATH=src pytest tests/entity_linker/ -v

search-test:
	@echo "Testing the Provider Search Service (Phase 2-G, C14)..."
	PYTHONPATH=src poetry run pytest tests/search/ tests/backend/test_search_service.py -v 2>/dev/null || \
		PYTHONPATH=src pytest tests/search/ tests/backend/test_search_service.py -v

report-test:
	@echo "Testing the Report Generation Library (Phase 2-H, C17)..."
	PYTHONPATH=src poetry run pytest tests/report/ tests/backend/test_report_service.py -v 2>/dev/null || \
		PYTHONPATH=src pytest tests/report/ tests/backend/test_report_service.py -v

worker-test:
	@echo "Testing the Temporal Worker activities (Phase 2-H, C15)..."
	PYTHONPATH=src poetry run pytest tests/workers/ -v 2>/dev/null || \
		PYTHONPATH=src pytest tests/workers/ -v

run-report-service:
	@echo "Starting report service (Phase 2-H shell) on http://localhost:8004 ..."
	@echo "Try: curl localhost:8004/healthz  |  docs at /docs"
	@echo "     curl -X POST localhost:8004/v1/reports/from-profile -H 'Content-Type: application/json' -d '{\"profile\": {...}}'"
	PYTHONPATH=src poetry run uvicorn backend.report_service.app:app --host 0.0.0.0 --port 8004 --reload 2>/dev/null || \
		PYTHONPATH=src uvicorn backend.report_service.app:app --host 0.0.0.0 --port 8004 --reload

run-payment-service:
	@echo "Starting payment service (Phase 2-J) on http://localhost:8005 ..."
	@echo "Try: curl localhost:8005/healthz  |  docs at /docs"
	@echo "     curl -X POST localhost:8005/v1/payments/checkout -H 'Content-Type: application/json' -d '{...}'"
	PYTHONPATH=src poetry run uvicorn backend.payment_service.app:app --host 0.0.0.0 --port 8005 --reload 2>/dev/null || \
		PYTHONPATH=src uvicorn backend.payment_service.app:app --host 0.0.0.0 --port 8005 --reload

run-worker:
	@echo "Starting Temporal worker (Phase 2-H, C15) -- requires WORKER_TEMPORAL_ADDRESS to be set..."
	PYTHONPATH=src poetry run python -m workers.worker 2>/dev/null || \
		PYTHONPATH=src python3 -m workers.worker

payment-test:
	PYTHONPATH=src poetry run pytest tests/backend/test_payment_service.py tests/data/test_migrations.py \
		-m "not integration" -v 2>/dev/null || \
		PYTHONPATH=src pytest tests/backend/test_payment_service.py tests/data/test_migrations.py \
		-m "not integration" -v

frontend-test:
	@echo "Running frontend tests (Jest + React Testing Library) -- Phase 2-K..."
	cd src/frontend && npm test
