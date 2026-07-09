.PHONY: install test preview playground deploy lint

install:
	agents-cli install

test:
	uv run pytest tests/ -q

preview:
	uv run uvicorn app.preview.server:app --reload --port 8080

playground:
	agents-cli playground

deploy:
	agents-cli deploy

lint:
	agents-cli lint
