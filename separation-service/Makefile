# Makefile for Sentiment Analysis Service

.PHONY: help install run test clean docker-build docker-run docker-stop lint format

# Default target
help:
	@echo "Available commands:"
	@echo "  install      Install dependencies"
	@echo "  run          Run the service locally"
	@echo "  test         Run tests"
	@echo "  clean        Clean up generated files"
	@echo "  docker-build Build Docker image"
	@echo "  docker-run   Run service with Docker Compose"
	@echo "  docker-stop  Stop Docker services"
	@echo "  lint         Run linting"
	@echo "  format       Format code"

# Install dependencies
install:
	pip install -r requirements.txt
	pip install -r requirements-test.txt

# Run the service locally
run:
	python run.py

# Run tests
test:
	pytest tests/ -v --cov=sentiment_service --cov-report=html

# Clean up generated files
clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.pyd" -delete
	find . -type f -name ".coverage" -delete
	rm -rf htmlcov/
	rm -rf .pytest_cache/
	rm -f service.log service.pid

# Docker commands
docker-build:
	docker build -t sentiment-service .

docker-run:
	docker-compose up -d

docker-stop:
	docker-compose down

# Code quality
lint:
	flake8 src/ tests/ --max-line-length=100 --ignore=E203,W503
	mypy src/sentiment_service/ --ignore-missing-imports

format:
	black src/ tests/ --line-length=100
	isort src/ tests/

# Development setup
dev-setup: install
	pre-commit install

# Production deployment check
check-deploy:
	@echo "Checking deployment readiness..."
	@test -f .env || (echo "❌ .env file missing"; exit 1)
	@test -f requirements.txt || (echo "❌ requirements.txt missing"; exit 1)
	@echo "✅ Deployment check passed"