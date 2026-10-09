.PHONY: install migrate dev createsuperuser archive shell env-setup

env-setup:
	@if [ ! -f .env ]; then cp .env.template .env && echo "Created .env from .env.template — edit it with your values."; else echo ".env already exists."; fi

install: env-setup
	uv sync

migrate:
	uv run python manage.py migrate

dev: migrate
	uv run gunicorn hub.wsgi:application --workers 3 --bind 0.0.0.0:8000 --reload

createsuperuser:
	uv run python manage.py createsuperuser

archive:
	uv run python manage.py archive_expired

shell:
	uv run python manage.py shell

check:
	uv run python manage.py check

makemigrations:
	uv run python manage.py makemigrations

wait-for-db:
	./scripts/wait-for-db.sh