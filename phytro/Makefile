# PhyTro shortcuts.  Run every command from the  phytro/  folder  (the one containing this Makefile).
# Type  make  (or  make help) to list them.
OWNER ?= robby
TF    := terraform -chdir=infra
PY    := .venv/bin/python
TABLE  = $$($(TF) output -raw table_name)

.DEFAULT_GOAL := help
.PHONY: help setup test knowledge state infra outputs web seed seed-missing backup restore dev logs destroy

help:               ## list commands
	@grep -E '^[a-z-]+:.*## ' Makefile | awk -F':.*## ' '{printf "  make %-14s %s\n", $$1, $$2}'

setup:              ## one-time: Python venv (.venv) + frontend packages
	python3 -m venv .venv
	.venv/bin/pip install -q -r backend/requirements-dev.txt -r knowledge/requirements.txt
	cd frontend && npm install --no-audit --no-fund

test:               ## run the unit tests (no AWS needed)
	cd backend && ../$(PY) -m pytest -v

knowledge:          ## download the regulatory documents + rebuild the search index
	$(PY) knowledge/fetch_sources.py; $(PY) knowledge/build_index.py

state:              ## one-time per AWS account: create the Terraform state bucket + infra/backend.hcl
	./scripts/bootstrap_state.sh $(OWNER)

infra:              ## create/update AWS resources (shows the plan, asks for 'yes')
	$(TF) init -input=false -backend-config=backend.hcl
	$(TF) apply -var owner=$(OWNER)

outputs:            ## print app URL, API URL, table name, dashboard link ...
	$(TF) output

web:                ## build the React app and publish it (S3 + CloudFront)
	cd frontend && npm run build
	aws s3 sync frontend/dist s3://$$($(TF) output -raw web_bucket) --delete --exclude config.json
	aws cloudfront create-invalidation --distribution-id $$($(TF) output -raw cloudfront_id) --paths "/*" >/dev/null
	@echo "Open: $$($(TF) output -raw app_url)   (allow ~1 minute for the CDN refresh)"

seed:               ## pre-load every store x aisle from Open Food Facts (~20 min)
	TABLE_NAME=$(TABLE) $(PY) scripts/seed_catalog.py

seed-missing:       ## retry only the store/aisle lists that failed or are empty
	TABLE_NAME=$(TABLE) $(PY) scripts/seed_catalog.py --only-missing

backup:             ## save seeded aisles to catalog-backup.json  (TABLE=... to override)
	$(PY) scripts/catalog_backup.py dump catalog-backup.json --table $(TABLE)

restore:            ## load catalog-backup.json into the current table
	$(PY) scripts/catalog_backup.py load catalog-backup.json --table $(TABLE)

dev:                ## run the web app on http://localhost:5173 against the deployed API
	aws s3 cp s3://$$($(TF) output -raw web_bucket)/config.json frontend/public/config.json
	cd frontend && npm run dev

logs:               ## last 15 min of the AI agent worker logs
	aws logs tail /aws/lambda/phytro-$(OWNER)-worker --since 15m

destroy:            ## delete ALL AWS resources of this deployment (end of course)
	$(TF) destroy -var owner=$(OWNER)
