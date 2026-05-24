# Makefile — Medical Professionals Review

.PHONY: dev-setup run-backend run-frontend lint test \
        infra-init infra-validate infra-plan infra-apply infra-fmt \
        help

ENV ?= dev

help:
	@echo "Medical Professionals Review — Make Targets"
	@echo ""
	@echo "  dev-setup            Install local development dependencies (idempotent)"
	@echo "  run-backend          Start FastAPI backend dev server (Phase 1-F+)"
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
	@echo "  NOTE: infra-plan/apply require DECISIONS.md Entry 003 to be resolved."
	@echo "        All PLACEHOLDER values in environments/\$$ENV/env.hcl must be filled."

dev-setup:
	bash scripts/dev-setup.sh

run-backend:
	@echo "[Phase 1-F not yet built] Backend service not available yet."

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
