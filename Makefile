.PHONY: help setup dev test lint web docker-build docker-run feeds ingest

help:
	@grep -E '^[a-z-]+:.*?##' $(MAKEFILE_LIST) | sed 's/:.*##/\t/'

setup:  ## create the server venv and install dependencies
	cd server && uv venv --python 3.12 .venv && uv pip install -e ".[dev]"

dev:  ## run the API locally on :8099 with the dev database
	cd server && NEWSFIN_DB=./data/dev.db .venv/bin/python -m uvicorn newsfin.api:app \
		--host 0.0.0.0 --port 8099 --reload

test:  ## run the backend and Flutter test suites
	cd server && .venv/bin/python -m pytest -q
	cd app && flutter test

lint:  ## ruff + flutter analyze
	cd server && .venv/bin/ruff check newsfin/ tests/
	cd app && flutter analyze

feeds:  ## check every registered feed is still alive
	cd server && .venv/bin/python -m newsfin.validate_feeds

ingest:  ## run one full fetch/cluster/score pass against the dev database
	cd server && NEWSFIN_DB=./data/dev.db .venv/bin/python -c \
		"import asyncio, logging; logging.basicConfig(level=logging.INFO); \
		 from newsfin.pipeline import refresh; print(asyncio.run(refresh()))"

web:  ## rebuild the Flutter web bundle into server/static (commit the result)
	cd app && flutter build web --release --dart-define=FLUTTER_WEB_CANVASKIT_URL=/canvaskit/
	rm -rf server/static && cp -r app/build/web server/static
	@# Written after the build on purpose: it is absent from the service
	@# worker's resource manifest, so the worker never caches it and the
	@# client always sees the truth about what the server is serving.
	@printf '{"id":"%s"}\n' "$$(date -u +%Y%m%dT%H%M%SZ)" > server/static/build-id.json
	@echo "build id: $$(cat server/static/build-id.json)"

docker-build:  ## build the deployment image
	docker build -t newsfin:local .

docker-run:  ## run the image locally on :8099
	docker run --rm -p 8099:8099 -v newsfin-data:/data --name newsfin newsfin:local
