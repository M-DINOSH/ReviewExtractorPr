# 🚀 Google Reviews Fetcher Microservice

> **Simplified, Production-Ready Service** for fetching Google Business Profile reviews with direct JSON responses and mock data support.

[![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=for-the-badge&logo=docker&logoColor=white)](https://docker.com)
[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/postgresql-%23316192.svg?style=for-the-badge&logo=postgresql&logoColor=white)](https://postgresql.org)
[![Redis](https://img.shields.io/badge/redis-%23DD0031.svg?style=for-the-badge&logo=redis&logoColor=white)](https://redis.io)

---

## 📋 Table of Contents

- [What is This?](#-what-is-this)
- [How It Works (The Flow)](#-how-it-works-the-flow)
- [Quick Start (5 Minutes)](#-quick-start-5-minutes)
- [Architecture Overview](#-architecture-overview)
- [API Documentation](#-api-documentation)
- [Data Modes](#-data-modes)
- [Integration Examples](#-integration-examples)
- [Deployment Options](#-deployment-options)
- [Configuration](#-configuration)
- [Monitoring & Health Checks](#-monitoring--health-checks)
- [Troubleshooting](#-troubleshooting)
- [Development](#-development)

---

## 🤔 What is This?

The **Google Reviews Fetcher** is a streamlined microservice that fetches, processes, and delivers Google Business Profile reviews directly as JSON responses. It's designed for simplicity and reliability, supporting both real Google API data and comprehensive mock data for development and testing.

### Key Features

- **⚡ Direct Response**: Single API call returns complete review data instantly
- **🎭 Dual Mode Support**: Switch between Google API and mock data seamlessly
- **📊 Complete Data**: Accounts, locations, and reviews in structured JSON
- **🏗️ Production Ready**: Docker containerization, health checks, error handling
- **🔄 Random Selection**: Mock mode provides varied test data across requests
- **🛡️ Fault Tolerant**: Graceful error handling and fallback mechanisms

### Use Cases

- **Frontend Integration**: Direct API calls from web/mobile apps
- **Business Intelligence**: Aggregate reviews across multiple locations
- **Development Testing**: Mock data for reliable testing and demos
- **Analytics Platforms**: Feed review data to dashboards and reports
- **Marketing Tools**: Track sentiment and review trends

---

## 🔄 How It Works (The Flow)

### The Simplified Direct Response Workflow

```
1. Frontend Request
        ↓
2. GET /sync/reviews?access_token=YOUR_TOKEN
        ↓
3. 🎯 Automatic Processing Starts
        ↓
   ┌─────────────────┐
   │ Data Mode Check │ ← Check DATA_MODE setting
   └─────────────────┘
           ↓
   ┌─────────────────┐
   │ Provider Setup  │ ← Google API or Mock Data
   └─────────────────┘
           ↓
   ┌─────────────────┐
   │ Accounts Fetch  │ ← Get business accounts
   └─────────────────┘
           ↓
   ┌─────────────────┐
   │ Locations Fetch │ ← Get all locations
   └─────────────────┘
           ↓
   ┌─────────────────┐
   │ Reviews Fetch   │ ← Get all reviews
   └─────────────────┘
           ↓
4. Combined JSON Response
```

### What Happens Automatically

1. **Mode Detection**: Service checks `DATA_MODE` environment variable
2. **Provider Selection**: Chooses Google API or Mock data provider
3. **Account Discovery**: Fetches business accounts (Google) or selects random account (Mock)
4. **Location Mapping**: Gets all business locations for the selected account
5. **Review Collection**: Fetches all reviews for each location
6. **Data Combination**: Structures account, locations, and reviews into JSON response

### Real-World Example

```bash
# Frontend makes simple GET request
curl "http://localhost:8084/sync/reviews?access_token=test_token_123"

# Service automatically:
# 1. Detects DATA_MODE=mock ✓
# 2. Selects MockDataProvider ✓
# 3. Picks random account (e.g., "Amber Arch Catering") ✓
# 4. Fetches 9 locations for that account ✓
# 5. Collects 36 reviews across locations ✓
# 6. Returns combined JSON instantly ✓

# Response structure:
{
  "account": {
    "account_id": "123456789",
    "account_display_name": "Amber Arch Catering"
  },
  "locations": [
    {
      "location": {
        "location_id": "LOC001",
        "location_name": "Urban Kitchen",
        "address": {...}
      },
      "reviews": [
        {
          "review_id": "REV001",
          "rating": 5,
          "comment": "Amazing food!",
          "reviewer": {...}
        }
      ]
    }
  ]
}
```

---

## ⚡ Quick Start (5 Minutes)

### Prerequisites

- **Docker & Docker Compose** (install from [docker.com](https://docker.com))
- **Git** (install from [git-scm.com](https://git-scm.com))

### Step 1: Clone & Navigate

```bash
git clone <your-repo-url>
cd review-fetcher-service
```

### Step 2: Start Everything

```bash
# Start all services (PostgreSQL, Redis, API)
docker-compose --profile dev up -d

# Wait 30 seconds for services to be ready
sleep 30
```

### Step 3: Verify It's Working

```bash
# Check service health
curl http://localhost:8084/health
# Should return: {"status": "healthy"}
```

### Step 4: Run the Test Script

```bash
# Run comprehensive test (shows full flow)
bash test_microservice.sh

# This will:
# - Test multiple access tokens
# - Show random account selection
# - Display fetched reviews
# - Demonstrate the complete workflow
```

### Step 5: Try the API

```bash
# Get reviews with any access token (mock mode)
curl "http://localhost:8084/sync/reviews?access_token=test_token_123"

# Try different tokens for different accounts
curl "http://localhost:8084/sync/reviews?access_token=different_token_456"
```

**🎉 You're Done!** The service is running and ready to fetch Google reviews.

---

## 🏗️ Architecture Overview

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                    Load Balancer (Optional)                 │
└─────────────────────┬───────────────────────────────────────┘
                      │
           ┌──────────▼──────────┐
           │  FastAPI Service    │ ← Single instance (simplified)
           │  (Port 8084)        │
           └──────────┬──────────┘
                      │
           ┌──────────▼──────────┐
           │ Data Provider       │ ← Google API or Mock Data
           │ (Pluggable Interface)│
           └──────────┬──────────┘
                      │
     ┌────────────────┼────────────────┐
     │                │                │
┌────▼────┐      ┌────▼────┐      ┌────▼────┐
│PostgreSQL│      │ Redis  │      │ Mock Data │
│Database  │      │ Cache  │      │ Volume    │
│(Port 5432)│      │(Port 6379)│    │(JSON files)│
└─────────┘      └─────────┘      └─────────┘
```

### Technology Stack

| Component | Technology | Purpose | Scaling |
|-----------|------------|---------|---------|
| **API** | FastAPI (Python) | REST endpoints, async processing | Single instance (dev) |
| **Database** | PostgreSQL | Data persistence (future use) | Connection pooling |
| **Cache** | Redis | API response caching (future use) | Single instance (dev) |
| **Mock Data** | JSON Files | Test data with relationships | Static files |
| **Container** | Docker | Packaging, deployment | Resource limits |
| **Orchestration** | Docker Compose | Service coordination | Scaling commands |

### Data Flow Architecture

```
Request Flow:
GET /sync/reviews → FastAPI → Data Provider → Google API / Mock Data → JSON Response

Data Sources:
Google APIs → Validation → Normalization → JSON Response
Mock JSON Files → Random Selection → Relationship Mapping → JSON Response

Response Flow:
Combined JSON ← Data Provider ← FastAPI ← Frontend
```

### Key Design Principles

- **Simplicity First**: Direct responses eliminate complexity
- **Provider Pattern**: Clean abstraction for data sources
- **Mode Switching**: Environment variable controls data source
- **Mock Data Quality**: Realistic test data with proper relationships
- **Error Resilience**: Graceful handling of API failures

---

## 📚 API Documentation

### Base URL
```
Development: http://localhost:8084
Production: https://your-domain.com/api/v1
```

### Authentication
Currently: No authentication required (access tokens passed as query parameters)

### Endpoints

#### 1. Sync Reviews (Main Endpoint)
**GET** `/sync/reviews`

Fetches and returns complete review data directly as JSON.

**Query Parameters:**
- `access_token` (required): OAuth access token or test token

**Response (Success):**
```json
{
  "account": {
    "account_id": "string",
    "account_display_name": "string",
    "type": "BUSINESS",
    "role": "OWNER",
    "state": {
      "status": "VERIFIED"
    }
  },
  "locations": [
    {
      "location": {
        "location_id": "string",
        "location_name": "string",
        "address": {
          "locality": "string",
          "region_code": "string",
          "postal_code": "string",
          "address_lines": ["string"]
        },
        "latlng": {
          "latitude": 0.0,
          "longitude": 0.0
        }
      },
      "reviews": [
        {
          "review_id": "string",
          "rating": 5,
          "comment": "string",
          "create_time": "2024-01-01T00:00:00Z",
          "update_time": "2024-01-01T00:00:00Z",
          "reviewer": {
            "display_name": "string",
            "profile_photo_url": "string"
          }
        }
      ]
    }
  ]
}
```

**Response (Error):**
```json
{
  "detail": "Error message describing what went wrong"
}
```

#### 2. Health Check
**GET** `/health`

Returns service health status.

**Response:**
```json
{
  "status": "healthy"
}
```

---

## 🎭 Data Modes

The service supports two data modes, controlled by the `DATA_MODE` environment variable.

### Google API Mode (`DATA_MODE=google`)

- **Purpose**: Production use with real Google Business Profile data
- **Requirements**: Valid OAuth access tokens from Google
- **Data Source**: Google Business Profile API
- **Rate Limits**: Subject to Google's API quotas and limits
- **Authentication**: Requires proper OAuth flow implementation

### Mock Data Mode (`DATA_MODE=mock`)

- **Purpose**: Development, testing, and demonstrations
- **Requirements**: Any access token (ignored, tokens just trigger different random accounts)
- **Data Source**: Pre-loaded JSON files with realistic test data
- **Content**: 130 accounts, 500 locations, 710 reviews with proper relationships
- **Behavior**: Each request returns a randomly selected account with its locations and reviews

### Switching Between Modes

```bash
# Set environment variable
export DATA_MODE=mock  # or "google"

# Restart service
docker-compose --profile dev down
docker-compose --profile dev up -d
```

### Mock Data Structure

The mock data includes:
- **130 Business Accounts**: Various restaurant and service businesses
- **500 Locations**: Distributed across different cities and regions
- **710 Reviews**: Realistic ratings (1-5 stars) and comments
- **Proper Relationships**: Accounts → Locations → Reviews hierarchy maintained
- **Random Selection**: Different access tokens return different accounts

---

## 🔗 Integration Examples

### JavaScript/React Frontend

```javascript
// Simple fetch integration
async function fetchReviews(accessToken) {
  const response = await fetch(
    `http://localhost:8084/sync/reviews?access_token=${accessToken}`
  );
  const data = await response.json();
  return data;
}

// Usage
const reviewsData = await fetchReviews('your_oauth_token');
console.log('Account:', reviewsData.account.account_display_name);
console.log('Locations:', reviewsData.locations.length);
console.log('Total Reviews:', reviewsData.locations.reduce(
  (sum, loc) => sum + loc.reviews.length, 0
));
```

### Python Backend Integration

```python
import requests

def get_reviews(access_token):
    url = f"http://localhost:8084/sync/reviews"
    params = {"access_token": access_token}
    response = requests.get(url, params=params)
    return response.json()

# Usage
data = get_reviews("your_token")
print(f"Business: {data['account']['account_display_name']}")
for location in data['locations']:
    print(f"Location: {location['location']['location_name']}")
    print(f"Reviews: {len(location['reviews'])}")
```

### cURL Testing

```bash
# Basic request
curl "http://localhost:8084/sync/reviews?access_token=test_123"

# Pretty print JSON
curl "http://localhost:8084/sync/reviews?access_token=test_123" | jq '.'

# Extract specific data
curl "http://localhost:8084/sync/reviews?access_token=test_123" | jq '.account.account_display_name'

# Count locations and reviews
curl "http://localhost:8084/sync/reviews?access_token=test_123" | jq '.locations | length, (.locations | map(.reviews | length) | add)'
```

---

## 🚀 Deployment Options

### Development (Docker Compose)

```bash
# Start development stack
docker-compose --profile dev up -d

# View logs
docker-compose logs -f review-fetcher

# Stop services
docker-compose down
```

### Production (Docker)

```bash
# Build production image
docker build -t review-fetcher:latest .

# Run with environment variables
docker run -d \
  --name review-fetcher \
  -p 8084:8084 \
  -e DATA_MODE=google \
  -e DATABASE_URL="postgresql+asyncpg://..." \
  -e REDIS_URL="redis://..." \
  review-fetcher:latest
```

### Environment Variables

```bash
# Data Mode
DATA_MODE=google          # "google" or "mock"

# Database (required for future features)
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/reviews

# Redis (required for future features)
REDIS_URL=redis://localhost:6379

# Logging
LOG_LEVEL=INFO           # DEBUG, INFO, WARNING, ERROR
```

---

## ⚙️ Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATA_MODE` | `google` | Data source: "google" or "mock" |
| `DATABASE_URL` | `postgresql+asyncpg://...` | PostgreSQL connection string |
| `REDIS_URL` | `redis://localhost:6379` | Redis connection string |
| `LOG_LEVEL` | `INFO` | Logging level |

### Docker Compose Profiles

- **dev**: Development stack with mock data volume
- **prod**: Production-ready configuration

### Mock Data Volume

The mock data is mounted as a Docker volume:
```
volumes:
  - ./mock_data:/app/mock_data:ro
```

---

## 📊 Monitoring & Health Checks

### Health Endpoint

```bash
curl http://localhost:8084/health
# Returns: {"status": "healthy"}
```

### Service Logs

```bash
# View application logs
docker-compose logs -f review-fetcher

# View all service logs
docker-compose logs -f
```

### Docker Status

```bash
# Check container status
docker-compose ps

# Check resource usage
docker stats
```

---

## 🔧 Troubleshooting

### Service Won't Start

```bash
# Check Docker status
docker-compose ps

# View startup logs
docker-compose logs review-fetcher

# Restart service
docker-compose restart review-fetcher
```

### API Returns Errors

```bash
# Test health endpoint
curl http://localhost:8084/health

# Test with mock data
curl "http://localhost:8084/sync/reviews?access_token=test"

# Check logs for errors
docker-compose logs -f review-fetcher
```

### Mock Data Issues

```bash
# Verify mock data volume is mounted
docker-compose exec review-fetcher ls -la /app/mock_data/

# Check file permissions
docker-compose exec review-fetcher cat /app/mock_data/accounts.json | head -5
```

### Common Issues

1. **Port 8084 already in use**: Change port in docker-compose.yml
2. **Mock data not loading**: Check volume mount and file permissions
3. **Database connection failed**: Verify PostgreSQL is running
4. **Memory issues**: Increase Docker memory allocation

---

## 💻 Development

### Local Development Setup

```bash
# Clone repository
git clone <repo-url>
cd review-fetcher-service

# Install dependencies (if running outside Docker)
pip install -r requirements.txt

# Run tests
python -m pytest

# Start development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8084
```

### Project Structure

```
review-fetcher-service/
├── app/
│   ├── main.py              # FastAPI application
│   ├── config.py            # Environment configuration
│   ├── models.py            # Database models
│   ├── schemas.py           # API schemas
│   └── services/
│       ├── data_providers.py    # Data provider interface
│       ├── simple_sync_service.py # Main sync logic
│       └── google_api.py         # Google API client
├── mock_data/               # Test data files
├── docker-compose.yml       # Container orchestration
├── Dockerfile              # Container definition
└── requirements.txt        # Python dependencies
```

### Adding New Features

1. **New Data Provider**: Implement `DataProvider` interface
2. **New Endpoint**: Add route in `main.py`
3. **New Model**: Define in `models.py` and `schemas.py`
4. **Configuration**: Add to `config.py` with environment variable

### Testing

```bash
# Run the test script
bash test_microservice.sh

# Manual API testing
curl "http://localhost:8084/sync/reviews?access_token=test"

# Check API documentation
open http://localhost:8084/docs
```

---

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

---

**🎉 Happy Reviewing!** Your Google Reviews Fetcher is ready to serve review data to your applications.
                      │
