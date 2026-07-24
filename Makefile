# AI API Builder — dev tasks

VENV = venv
BIN = $(VENV)/Scripts
PYTHON = python

.PHONY: install run test

install:
	$(PYTHON) -m venv $(VENV)
	$(BIN)/pip install --upgrade -r requirements.txt

run:
	cd src && ../$(BIN)/uvicorn server:app --reload --port 8080

test:
	$(BIN)/pytest
