# BEAI local commands. Run from the repository root.
# Node and npm are pinned to the same install. The default PATH on this
# machine can point `node` and `npm` at different Node versions.

NVM_BIN ?= /home/ubuntu/.nvm/versions/node/v22.23.3/bin
export PATH := $(NVM_BIN):$(CURDIR)/.venv/bin:$(PATH)

.PHONY: setup test migrate backend

setup:
	/usr/bin/python3 -m venv .venv
	.venv/bin/python -m pip install -U pip
	.venv/bin/python -m pip install -e ".[dev]"

test:
	.venv/bin/python -m pytest

migrate:
	.venv/bin/python -m alembic -c backend/alembic.ini upgrade head

backend:
	mkdir -p .logs data
	$(MAKE) migrate
	.venv/bin/uvicorn backend.app.main:app --host 127.0.0.1 --port 8731
