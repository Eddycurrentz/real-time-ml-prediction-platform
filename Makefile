.PHONY: up down build-api

up:
	docker compose up -d postgres kafka api

down:
	docker compose down -v

build-api:
	docker compose build api
