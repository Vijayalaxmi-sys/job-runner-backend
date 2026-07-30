.PHONY: up down logs psql test reset

## Boot Postgres, run migrations, start the API and 3 workers.
up:
	docker compose up --build -d --scale worker=3
	@echo "api  -> http://localhost:8000/health"
	@echo "logs -> make logs"

down:
	docker compose down -v

logs:
	docker compose logs -f api worker

psql:
	docker compose exec db psql -U app -d app

## Run your test suite inside the api container.
test:
	docker compose exec api pytest -q

reset: down up
