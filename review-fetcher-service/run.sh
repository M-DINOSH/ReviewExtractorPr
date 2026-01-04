#!/bin/bash

# 🚀 Google Reviews Fetcher - Production Run Script
# Usage: ./run.sh [access_token]
# Requires valid Google OAuth token starting with 'ya29'

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
ACCESS_TOKEN=${1:-""}
SERVICE_NAME="review-fetcher-dev"

# Function to print colored output
print_status() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

# Function to check if Docker is running
check_docker() {
    if ! docker info >/dev/null 2>&1; then
        print_error "Docker is not running. Please start Docker first."
        exit 1
    fi
}

# Function to validate access token
validate_token() {
    if [ -z "$ACCESS_TOKEN" ]; then
        print_error "Access token is required. Usage: ./run.sh 'ya29.your_oauth_token'"
        print_info "Get your OAuth token from Google Cloud Console with Business Profile API access"
        exit 1
    fi

    if [[ ! $ACCESS_TOKEN == ya29.* ]]; then
        print_error "Invalid token format. Token must start with 'ya29.' (Google OAuth token)"
        print_info "Get a proper OAuth token from Google Cloud Console"
        exit 1
    fi
}

# Function to stop existing services
stop_services() {
    print_info "Stopping any existing services..."
    docker-compose down >/dev/null 2>&1 || true
}

# Function to start services in Google API mode
start_services() {
    print_info "Starting services in Google API production mode..."

    # Set Google API mode
    export DATA_MODE=google

    docker-compose --profile dev up -d
}

# Function to wait for services to be ready
wait_for_services() {
    print_info "Waiting for services to be ready..."
    local max_attempts=30
    local attempt=1

    while [ $attempt -le $max_attempts ]; do
        if curl -s http://localhost:8084/health >/dev/null 2>&1; then
            print_status "Services are ready!"
            return 0
        fi

        echo -n "."
        sleep 2
        ((attempt++))
    done

    print_error "Services failed to start within 60 seconds"
    docker-compose logs review-fetcher-dev
    exit 1
}

# Function to test the API
test_api() {
    print_info "Testing API with access token..."

    # Test health endpoint
    echo "Health check:"
    curl -s http://localhost:8084/health | jq . || curl -s http://localhost:8084/health

    echo ""
    echo "Fetching reviews with token: $ACCESS_TOKEN"
    echo "Mode: $MODE"
    echo ""

    # Test the main API endpoint
    local response=$(curl -s "http://localhost:8084/sync/reviews?access_token=$ACCESS_TOKEN")

    # Pretty print the response
    echo "API Response:"
    echo "$response" | jq . 2>/dev/null || echo "$response"

    echo ""
    print_status "API test completed!"
}

# Function to show usage information
show_usage() {
    echo "🚀 Google Reviews Fetcher - Production Run Script"
    echo ""
    echo "Usage:"
    echo "  ./run.sh [access_token]"
    echo ""
    echo "Arguments:"
    echo "  access_token    OAuth access token (required, must start with 'ya29.')"
    echo ""
    echo "Examples:"
    echo "  ./run.sh 'ya29.your_oauth_token_here'    # Run with Google API"
    echo ""
    echo "Requirements:"
    echo "  • Valid Google OAuth token with Business Profile API access"
    echo "  • Google Cloud Console project with Business Profile API enabled"
    echo "  • Business owner consent for GBP data access"
    echo ""
    echo "API Endpoints:"
    echo "  Health:    http://localhost:8084/health"
    echo "  Reviews:   http://localhost:8084/sync/reviews?access_token=YOUR_TOKEN"
    echo "  Docs:      http://localhost:8084/docs"
}

# Main script logic
main() {
    # Check if help is requested first, before any other processing
    if [ "$1" = "--help" ] || [ "$1" = "-h" ] || [ "$1" = "help" ]; then
        show_usage
        exit 0
    fi

    echo "🚀 Google Reviews Fetcher - Production Microservice"
    echo "=================================================="
    echo "Access Token: ${ACCESS_TOKEN:0:20}..."
    echo ""

    # Validate access token
    validate_token

    # Check Docker
    check_docker

    # Stop existing services
    stop_services

    # Start services
    start_services

    # Wait for readiness
    wait_for_services

    # Test the API
    test_api

    echo ""
    print_status "Production microservice is running successfully!"
    echo ""
    print_info "Useful commands:"
    echo "  • View logs: docker-compose logs -f review-fetcher-dev"
    echo "  • Stop service: docker-compose down"
    echo "  • API Docs: http://localhost:8084/docs"
    echo "  • Test script: bash test_microservice.sh"
}

# Run main function with all arguments
main "$@"