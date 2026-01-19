# Makefile for Review Fetcher Service

.PHONY: help build up down logs clean db-migrate db-upgrade db-downgrade db-current db-history test test-integration

help:
	@echo "Available commands:"
	@echo "  make build        - Build Docker images"
	@echo "  make up           - Start all services"
	@echo "  make down         - Stop all services"
	@echo "  make logs         - View logs"
	@echo "  make clean        - Remove containers and volumes"
	@echo "  make db-migrate   - Generate token management DB migration"
	@echo "  make db-upgrade   - Run pending migrations"
	@echo "  make db-downgrade - Rollback last migration"
	@echo "  make db-current   - Show current migration version"
	@echo "  make db-history   - Show migration history"
	@echo "  make test         - Run tests"

# Docker commands
build:
	docker-compose build

up:
	docker-compose up -d

down:
	docker-compose down

logs:
	docker-compose logs -f

clean:
	docker-compose down -v
	rm -rf __pycache__ app/__pycache__

# Database migrations - Unified token management DB
db-migrate:
	alembic -c alembic_tokens.ini revision --autogenerate -m "$(msg)"

db-upgrade:
	alembic -c alembic_tokens.ini upgrade head

db-downgrade:
	alembic -c alembic_tokens.ini downgrade -1

db-current:
	alembic -c alembic_tokens.ini current

db-history:
	alembic -c alembic_tokens.ini history

# Tests
test:
	python3.11 -m pytest tests/ -v

test-integration:
	python3.11 test_token_integration.py
