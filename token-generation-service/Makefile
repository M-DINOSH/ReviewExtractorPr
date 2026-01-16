# Makefile for Token Generation Service

.PHONY: help install dev up down logs clean migrate test

help:
	@echo "Token Generation Service - Available Commands:"
	@echo "  make install    - Install dependencies"
	@echo "  make dev        - Run development server"
	@echo "  make up         - Start Docker containers"
	@echo "  make down       - Stop Docker containers"
	@echo "  make logs       - View service logs"
	@echo "  make migrate    - Run database migrations"
	@echo "  make clean      - Clean up containers and volumes"
	@echo "  make test       - Run tests"

install:
	pip install -r requirements.txt

dev:
	uvicorn src.token_service.api.main:app --reload --port 8002

up:
	docker-compose up -d
	@echo "Service starting... Wait a few seconds then check http://localhost:8002/health"

down:
	docker-compose down

logs:
	docker-compose logs -f token-service

migrate:
	alembic upgrade head

clean:
	docker-compose down -v
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

test:
	pytest tests/ -v
