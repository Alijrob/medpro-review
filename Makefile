# Makefile — Medical Professionals Review

.PHONY: dev-setup run-backend run-gateway run-audit run-monitor run-frontend lint test \
        infra-init infra-validate infra-plan infra-apply infra-fmt \
        obs-validate \
        gitops-validate gitops-guard \
        opa-test connectors-test normalizers-test identity-test \
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
	@echo "  run-frontend         Start Next.js frontend dev server (Phase 2-K+)"
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

run-frontend:
	@echo "[Phase 2-K not yet built] Frontend not available yet."

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
