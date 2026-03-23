PYTHON ?= python3
WORKSPACE_ID ?= case_20260228_001

.PHONY: test db-bootstrap db-upgrade db-downgrade db-current-revision import-legacy-workspace create-workspace validate-workspace run-typization run-smoke clean-workspace sprint-init sprint-status sprint-prepare-codex sprint-start-codex sprint-build-codex-bundle sprint-build-acceptance-bundle sprint-advance

test:
	$(PYTHON) -m unittest discover -s tests -p 'test_*.py'

db-bootstrap:
	$(PYTHON) scripts/db_bootstrap.py upgrade

db-upgrade:
	$(PYTHON) scripts/db_bootstrap.py upgrade

db-downgrade:
	$(PYTHON) scripts/db_bootstrap.py downgrade

db-current-revision:
	$(PYTHON) scripts/db_bootstrap.py current

import-legacy-workspace:
	@echo "usage: $(PYTHON) scripts/import_legacy_workspace.py <workspace_root> --organization-id <org_id> --created-by-user-id <user_id>"

create-workspace:
	$(PYTHON) scripts/workspace_cli.py --project-root . create --workspace-id $(WORKSPACE_ID)

validate-workspace:
	$(PYTHON) scripts/validate_workspace.py $(WORKSPACE_ID)

run-typization:
	$(PYTHON) scripts/run_typization.py $(WORKSPACE_ID)

run-smoke:
	$(PYTHON) scripts/workspace_cli.py --project-root . create --workspace-id $(WORKSPACE_ID)
	$(PYTHON) scripts/workspace_cli.py --project-root . load $(WORKSPACE_ID)
	$(PYTHON) scripts/workspace_cli.py --project-root . set-state $(WORKSPACE_ID) ACTIVE --reason "smoke-start"
	$(PYTHON) scripts/workspace_cli.py --project-root . checkpoint $(WORKSPACE_ID) --reason "smoke-checkpoint" --structural
	$(PYTHON) scripts/run_typization.py $(WORKSPACE_ID)
	$(PYTHON) scripts/validate_workspace.py $(WORKSPACE_ID)
	$(PYTHON) -m unittest discover -s tests -p 'test_*.py'

clean-workspace:
	rm -rf cases/$(WORKSPACE_ID)

sprint-init:
	$(PYTHON) scripts/run_sprint_loop.py init

sprint-status:
	$(PYTHON) scripts/run_sprint_loop.py status

sprint-prepare-codex:
	$(PYTHON) scripts/run_sprint_loop.py prepare-codex

sprint-start-codex:
	$(PYTHON) scripts/run_sprint_loop.py start-codex

sprint-build-codex-bundle:
	$(PYTHON) scripts/run_sprint_loop.py build-bundle --agent codex

sprint-build-acceptance-bundle:
	$(PYTHON) scripts/run_sprint_loop.py build-bundle --agent acceptance

sprint-advance:
	$(PYTHON) scripts/run_sprint_loop.py advance
