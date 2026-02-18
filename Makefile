PY=python3
PIP=pip3

.PHONY: help setup run test clean doctor

help:
	@echo ""
	@echo "Commands:"
	@echo "  make setup   - install dependencies"
	@echo "  make run     - start the dev server"
	@echo "  make test    - run 5 smoke tests against /iso"
	@echo "  make doctor  - check environment & key"
	@echo "  make clean   - remove generated PDFs"
	@echo ""

setup:
	$(PIP) install -r requirements.txt

doctor:
	@echo "Python: $$($(PY) --version)"
	@if [ -z "$$OPENAI_API_KEY" ]; then echo "OPENAI_API_KEY: NOT SET ❌"; exit 1; else echo "OPENAI_API_KEY: SET ✅"; fi

run:
	./scripts/dev.sh

test:
	$(PY) ./scripts/smoke_test.py

clean:
	rm -f ISO_Report_*.pdf ISO_Lead_Report.pdf 2>/dev/null || true
	@echo "Cleaned PDFs."
