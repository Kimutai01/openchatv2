start_services:
	docker compose up -d --force-recreate

stop_services:
	docker compose down
build:
	docker compose up --build -d
migrate:
	docker compose exec chat python manage.py migrate

makemigrations:
	docker compose exec chat python manage.py makemigrations

django_shell:
	docker compose exec chat python manage.py shell

container_shell:
	docker compose run chat sh

collectstatic:
	docker compose exec chat python manage.py collectstatic

	