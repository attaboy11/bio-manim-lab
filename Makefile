PY ?= python
RUN_TOPIC ?= "ATP synthase and oxidative phosphorylation"

.PHONY: help install dev test smoke run clean

help:
	@echo "make install   - install package (editable)"
	@echo "make dev       - install with dev + render extras"
	@echo "make test      - run pytest"
	@echo "make smoke     - run the ATP synthase vertical slice"
	@echo "make run       - same as smoke, override RUN_TOPIC=..."
	@echo "make clean     - remove outputs/ and __pycache__"

install:
	$(PY) -m pip install -e .

dev:
	$(PY) -m pip install -e ".[dev,render]"

test:
	$(PY) -m pytest -q

smoke:
	$(PY) -m biomanim run --topic $(RUN_TOPIC)

run: smoke

clean:
	rm -rf outputs/* .pytest_cache
	find . -type d -name __pycache__ -exec rm -rf {} +
