.PHONY: install infra backend backend-demo backend-lan frontend test lint install-service uninstall-service service-logs ios ios-build tailscale-serve tailscale-status tailscale-stop

TAILSCALE_BIN ?= tailscale

install:
	cd backend && uv sync
	cd frontend && pnpm install

infra:
	docker compose up -d postgres redis

backend:
	cd backend && uv run uvicorn app.main:app --reload --port 8000

backend-demo:
	cd backend && MOCK_LLM=1 uv run uvicorn app.main:app --reload --port 8000

backend-lan:
	cd backend && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

frontend:
	cd frontend && pnpm dev

test:
	cd backend && uv run pytest

lint:
	cd backend && uv run ruff check .

install-service:
	bash deploy/launchd/install.sh

uninstall-service:
	bash deploy/launchd/uninstall.sh

service-logs:
	tail -f backend/data/logs/backend.out.log backend/data/logs/backend.err.log

ios:
	open ios/KaogongSchool.xcodeproj

ios-build:
	xcodebuild -project ios/KaogongSchool.xcodeproj -target KaogongSchool \
		-configuration Debug -sdk iphonesimulator \
		-destination 'generic/platform=iOS Simulator' \
		CODE_SIGNING_ALLOWED=NO build

tailscale-serve:
	$(TAILSCALE_BIN) serve --bg 8000
	$(TAILSCALE_BIN) serve status

tailscale-status:
	$(TAILSCALE_BIN) serve status

tailscale-stop:
	$(TAILSCALE_BIN) serve reset
