.PHONY: dev dev-backend dev-frontend dev-supabase test test-backend test-frontend lint format migrate seed reset logs help

# Default
help:
	@echo "CareerOS — tilgængelige kommandoer:"
	@echo ""
	@echo "  make dev              Start backend + frontend (Docker)"
	@echo "  make dev-backend      Start kun backend (hot reload)"
	@echo "  make dev-frontend     Start kun frontend"
	@echo "  make dev-supabase     Start lokal Supabase"
	@echo ""
	@echo "  make test             Kør alle tests"
	@echo "  make test-backend     Kør kun backend tests"
	@echo "  make test-frontend    TypeCheck + lint frontend"
	@echo ""
	@echo "  make lint             Lint backend (ruff) + frontend (eslint)"
	@echo "  make format           Formatér backend (ruff format)"
	@echo ""
	@echo "  make migrate          Anvend nye migrations"
	@echo "  make seed             Kør seed.sql"
	@echo "  make reset            Nulstil og genopbyg database"
	@echo ""
	@echo "  make logs             Vis Docker logs"
	@echo "  make build            Byg Docker images"
	@echo "  make down             Stop alle containers"

dev:
	docker compose up

dev-backend:
	cd backend && uvicorn app.main:app --reload --port 8000

dev-frontend:
	cd frontend && npm run dev

dev-supabase:
	supabase start

build:
	docker compose build

down:
	docker compose down

logs:
	docker compose logs -f

test: test-backend test-frontend

test-backend:
	cd backend && python -m pytest tests/ -v --cov=app --cov-report=term-missing

test-frontend:
	cd frontend && npm run typecheck && npm run lint

lint:
	cd backend && ruff check app/
	cd frontend && npm run lint

format:
	cd backend && ruff format app/ && ruff check --fix app/

migrate:
	supabase db push

seed:
	supabase db reset --local

reset:
	supabase db reset

install:
	cd backend && pip install -e ".[dev]"
	cd frontend && npm install

# Opret ny migration
new-migration:
	@read -p "Migration navn (fx add_user_settings): " name; \
	num=$$(ls supabase/migrations/*.sql 2>/dev/null | wc -l); \
	num=$$((num + 1)); \
	printf -v padded "%05d" $$num; \
	touch "supabase/migrations/$${padded}_$${name}.sql"; \
	echo "Oprettet: supabase/migrations/$${padded}_$${name}.sql"
