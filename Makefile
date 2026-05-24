# Makefile — Medical Professionals Review
# All targets are stubs until the relevant phase builds the underlying service.

.PHONY: dev-setup run-backend run-frontend lint test infra-plan infra-apply help

help:
	@echo "Medical Professionals Review — Make Targets"
	@echo ""
	@echo "  dev-setup      Install local development dependencies (idempotent)"
	@echo "  run-backend    Start FastAPI backend dev server (Phase 1-F+)"
	@echo "  run-frontend   Start Next.js frontend dev server (Phase 2-K+)"
	@echo "  lint           Run all linters (Python: black/flake8/mypy; TS: eslint/prettier)"
	@echo "  test           Run all tests (pytest + jest)"
	@echo "  infra-plan     Terraform/Terragrunt plan (Phase 1-B+)"
	@echo "  infra-apply    Terraform/Terragrunt apply (Phase 1-B+, requires approval)"

dev-setup:
	bash scripts/dev-setup.sh

run-backend:
	@echo "[Phase 1-F not yet built] Backend service not available yet."
	@echo "This target will launch: uvicorn src.backend.api_gateway.main:app --reload"

run-frontend:
	@echo "[Phase 2-K not yet built] Frontend not available yet."
	@echo "This target will launch: cd src/frontend && npm run dev"

lint:
	@echo "[No source yet] Lint targets will activate when src/ is populated."
	@# Future: cd src/backend && poetry run black --check . && poetry run flake8 . && poetry run mypy .
	@# Future: cd src/frontend && npm run lint

test:
	@echo "[No source yet] Test targets will activate when src/ is populated."
	@# Future: cd src/backend && poetry run pytest
	@# Future: cd src/frontend && npm test

infra-plan:
	@echo "[Phase 1-B not yet built] Infrastructure IaC not available yet."
	@# Future: cd src/infrastructure && terragrunt run-all plan

infra-apply:
	@echo "[Phase 1-B not yet built] Infrastructure IaC not available yet."
	@# Future: cd src/infrastructure && terragrunt run-all apply
