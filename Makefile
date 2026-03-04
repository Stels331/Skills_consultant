PYTHON ?= python3
WORKSPACE_ID ?= case_20260228_001

.PHONY: test create-workspace validate-workspace run-typization run-smoke clean-workspace

test:
	$(PYTHON) -m unittest discover -s tests -p 'test_*.py'

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
