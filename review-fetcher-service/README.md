# 🚀 Google Reviews Fetcher Microservice v2.0

> **Enterprise-Grade, SOLID Principles Microservice** with OOP design patterns, automatic scaling, and comprehensive monitoring for fetching Google Business Profile reviews.

[![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=for-the-badge&logo=docker&logoColor=white)](https://docker.com)
[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/postgresql-%23316192.svg?style=for-the-badge&logo=postgresql&logoColor=white)](https://postgresql.org)
[![Redis](https://img.shields.io/badge/redis-%23DD0031.svg?style=for-the-badge&logo=redis&logoColor=white)](https://redis.io)
[![SOLID](https://img.shields.io/badge/SOLID-Principles-blue?style=for-the-badge)](https://en.wikipedia.org/wiki/SOLID)
[![OOP](https://img.shields.io/badge/OOP-Design%20Patterns-green?style=for-the-badge)](https://en.wikipedia.org/wiki/Design_Patterns)

---

## 📋 Table of Contents

- [What is This?](#-what-is-this)
- [How It Works (The Flow)](#-how-it-works-the-flow)
- [Quick Start (5 Minutes)](#-quick-start-5-minutes)
- [Run Script](#-run-script)
- [Architecture Overview](#-architecture-overview)
- [OOP & SOLID Principles Architecture](#-oop--solid-principles-architecture)
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

The **Google Reviews Fetcher v2.0** is an enterprise-grade microservice that fetches, processes, and delivers Google Business Profile reviews directly as JSON responses. Built with **SOLID principles** and **OOP design patterns**, it supports both real Google API data and comprehensive mock data for development and testing.

### Key Features

- **🏛️ SOLID Architecture**: Single Responsibility, Open/Closed, Liskov Substitution, Interface Segregation, Dependency Inversion
- **🎯 Design Patterns**: Strategy, Observer, Command, Repository, Factory, Decorator patterns
- **⚡ Direct Response**: Single API call returns complete review data instantly
- **🎭 Dual Mode Support**: Switch between Google API and mock data seamlessly
- **📊 Complete Data**: Accounts, locations, and reviews in structured JSON
- **🏗️ Production Ready**: Docker containerization, health checks, error handling
- **🔄 Automatic Scaling**: Queue-based processing handles N concurrent users
- **📈 Performance Monitoring**: Real-time metrics, alerting, and observability
- **🛡️ Fault Tolerant**: Graceful error handling and fallback mechanisms
- **🔧 Modular Design**: Pluggable components, extensible architecture

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

### 🚀 Quick Run Script (Recommended)

The easiest way to get started is using the `run.sh` script that handles everything automatically:

```bash
# Make script executable (first time only)
chmod +x run.sh

# Run with mock data (development)
./run.sh

# Run with custom access token
./run.sh "your_access_token_here"

# Run with Google API mode
./run.sh "ya29.your_oauth_token" google

# Show help
./run.sh --help
```

**What the script does:**
- ✅ Stops any existing services
- ✅ Starts services in your chosen mode
- ✅ Waits for services to be ready
- ✅ Tests the API with your token
- ✅ Shows formatted results

**Modes:**
- **Mock**: Uses test data (130 accounts, 500 locations, 710 reviews)
- **Google**: Uses real Google Business Profile API (requires valid OAuth token)

---

### Manual Setup (Alternative)

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

## 🚀 Run Script

The `run.sh` script provides the easiest way to run and test your microservice with different modes and access tokens.

### Features

- **🎭 Dual Mode Support**: Switch between mock data and Google API modes
- **🔄 Automatic Setup**: Handles Docker orchestration and service management
- **🧪 Built-in Testing**: Tests API endpoints and displays results
- **🎨 Colored Output**: Clear status messages and formatted JSON responses
- **⚡ One-Command**: Single script for complete workflow

### Usage

```bash
# Make executable (first time only)
chmod +x run.sh

# Basic usage - mock mode with default token
./run.sh

# Custom access token (mock mode)
./run.sh "your_access_token_here"

# Google API mode (real data)
./run.sh "ya29.your_oauth_token" google

# Show help
./run.sh --help
```

### What It Does

1. **Service Management**
   - Stops any existing containers
   - Starts fresh services based on selected mode
   - Sets appropriate environment variables

2. **Health Checks**
   - Waits for services to be ready
   - Verifies API endpoints are responding

3. **API Testing**
   - Calls `/health` endpoint
   - Tests `/sync/reviews` with your access token
   - Displays formatted JSON response

4. **Results Display**
   - Shows account information
   - Lists locations with review counts
   - Displays sample reviews

### Mode Comparison

| Feature | Mock Mode | Google Mode |
|---------|-----------|-------------|
| **Data Source** | JSON files (130 accounts) | Google Business API |
| **Authentication** | Any token works | Valid OAuth token required |
| **Performance** | Instant response | Subject to API limits |
| **Use Case** | Development/Testing | Production |
| **Data Variety** | Random account selection | Real business data |

### Example Output

**Mock Mode:**
```bash
🚀 Google Reviews Fetcher Microservice
======================================
Access Token: test_token_123
Mode: mock

ℹ️  Starting services in mock mode...
✅ Services are ready!
ℹ️  Testing API with access token...

Health check: {"status":"healthy"}

Fetching reviews with token: test_token_123
Mode: mock

API Response:
{
  "account": {
    "account_display_name": "Nomad Nom Noms"
  },
  "locations": [
    {
      "location": {"location_name": "Vedic Plate - Varanasi"},
      "reviews": [...]
    }
  ]
}
✅ Microservice is running successfully!
```

**Google Mode:**
```bash
🚀 Google Reviews Fetcher Microservice
======================================
Access Token: ya29.token
Mode: google

ℹ️  Starting services in google mode...
✅ Services are ready!
ℹ️  Testing API with access token...

API Response: [Real Google Business data]
```

### Advanced Usage

```bash
# Development testing
./run.sh "dev_token_001" mock

# Production deployment testing
./run.sh "ya29.production_token" google

# CI/CD integration
./run.sh "$OAUTH_TOKEN" google

# Multiple test runs
for token in "token1" "token2" "token3"; do
  ./run.sh "$token" mock
done
```

### Troubleshooting

**Script not executable:**
```bash
chmod +x run.sh
```

**Docker not running:**
```bash
# Start Docker first
# Then run: ./run.sh
```

**Services fail to start:**
```bash
# Check logs
docker-compose logs review-fetcher-dev

# Clean restart
docker-compose down -v
./run.sh
```

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

## 🏛️ OOP & SOLID Principles Architecture

### Overview

The service has been refactored to follow **Object-Oriented Programming (OOP) principles** and **SOLID design patterns**, ensuring maximum scalability, modularity, and maintainability. This enterprise-grade architecture supports clean code practices and design pattern best practices.

### SOLID Principles Implementation

#### **1. Single Responsibility Principle (SRP)**
Each class has one reason to change:
- `SimpleSyncService` - Only handles sync operations
- `ReviewFetcherService` - Only manages service lifecycle
- `MetricsObserver` - Only handles metrics collection
- `SyncJobRepository` - Only handles database operations for sync jobs

#### **2. Open/Closed Principle (OCP)**
Classes are open for extension, closed for modification:
- **Strategy Pattern**: New sync strategies can be added without changing existing code
- **Observer Pattern**: New monitoring capabilities without modifying subjects
- **Decorator Pattern**: New cross-cutting concerns without changing decorated functions

#### **3. Liskov Substitution Principle (LSP)**
Subtypes are substitutable for their base types:
- `GoogleDataProvider` and `MockDataProvider` both implement `IDataProvider`
- All sync strategies implement `ISyncStrategy`
- All observers implement `IObserver`

#### **4. Interface Segregation Principle (ISP)**
Clients don't depend on interfaces they don't use:
- Separate interfaces: `IService`, `IDataProvider`, `ISyncService`, `IRepository`, etc.
- No bloated interfaces - each has specific, focused methods

#### **5. Dependency Inversion Principle (DIP)**
Depend on abstractions, not concretions:
- Services depend on `IDataProvider` interface, not concrete implementations
- Controllers depend on `ISyncService` abstractions
- All high-level modules depend on abstractions

### Design Patterns Implemented

#### **1. Strategy Pattern** (`app/strategies/`)
Multiple sync strategies for different scenarios:
```python
# Available strategies
SyncStrategy.SIMPLE     # Direct processing
SyncStrategy.BATCH      # Batched processing for large datasets
SyncStrategy.STREAMING  # Sequential processing
```

**Usage:**
```python
strategy = SyncStrategyFactory.create_strategy(SyncStrategy.BATCH, batch_size=20)
sync_service = SimpleSyncService(strategy=strategy)
```

#### **2. Observer Pattern** (`app/observers/`)
Event-driven monitoring and logging:
```python
# Concrete observers
metrics_observer = MetricsObserver()      # Performance metrics
logging_observer = LoggingObserver()      # Enhanced logging
alerting_observer = AlertingObserver()    # Error alerting
health_observer = HealthObserver()        # Health monitoring
```

**Benefits:**
- Decoupled monitoring system
- Extensible event handling
- Real-time observability

#### **3. Command Pattern** (`app/commands/`)
Encapsulated request handling:
```python
# Commands for different operations
sync_command = SyncReviewsCommand(sync_service, access_token)
health_command = HealthCheckCommand(services)

# Execute with history tracking
result = await command_invoker.execute_command(sync_command)
```

#### **4. Repository Pattern** (`app/repositories/`)
Data access abstraction:
```python
# Type-safe repositories
sync_job_repo = SyncJobRepository()
account_repo = AccountRepository()
location_repo = LocationRepository()
review_repo = ReviewRepository()
```

**Features:**
- Clean data access layer
- Database independence
- Testable data operations

#### **5. Factory Pattern** (`app/core/services.py`)
Dynamic service instantiation:
```python
# Service factory
service_factory = ServiceFactory()
service_factory.register_service("review_fetcher", ReviewFetcherService)
service = service_factory.create_service("review_fetcher")
```

#### **6. Decorator Pattern** (`app/decorators/`)
Cross-cutting concerns:
```python
@log_execution()
@rate_limit(requests_per_minute=60)
@monitor_performance(threshold_ms=5000)
@validate_input({"access_token": str})
@cache_result(ttl_seconds=300)
async def sync_reviews(access_token: str):
    # Function logic here
    pass
```

### Core Architecture Components

#### **Interfaces Layer** (`app/core/interfaces.py`)
Abstract base classes and protocols:
```python
class IService(Protocol):
    async def get_health(self) -> ServiceHealth: ...
    async def shutdown(self) -> None: ...

class IDataProvider(ABC):
    async def get_accounts(self, access_token: str) -> List[Dict]: ...
    async def get_locations(self, account_id: str) -> List[Dict]: ...
    async def get_reviews(self, location_id: str) -> List[Dict]: ...
```

#### **Services Layer** (`app/core/services.py`)
Core service implementations:
```python
class BaseService(IService):
    """Common service functionality"""

class DequeQueue(IQueue):
    """Thread-safe queue for scaling"""

class EventSubject(ISubject):
    """Observable subject for events"""
```

#### **Enhanced Main Service**
```python
class ReviewFetcherService(BaseService):
    """Main service with health monitoring and queue management"""

    def __init__(self):
        super().__init__("review-fetcher", "2.0.0")
        self.queue = request_queue
        self.command_invoker = command_invoker

    async def get_health(self) -> ServiceHealth:
        """Health status based on queue utilization"""
        # Dynamic health based on system state
        pass
```

### Scalability Features

#### **Queue-Based Processing**
- **Deque Implementation**: O(1) operations for request queuing
- **Automatic Scaling**: Handles N concurrent users
- **Rate Limiting**: Prevents API overload
- **Backpressure**: Queue size limits prevent memory issues

#### **Strategy-Based Sync**
- **Batch Processing**: Efficient for large datasets
- **Streaming Processing**: Memory-efficient for sequential operations
- **Simple Processing**: Direct response for small requests

#### **Observer-Based Monitoring**
- **Real-time Metrics**: Request counts, processing times, error rates
- **Health Monitoring**: Service status, queue utilization, performance
- **Alerting System**: Automatic notifications for critical issues

### Performance Optimizations

#### **Decorator-Based Enhancements**
- **Caching**: `@cache_result()` for repeated requests
- **Rate Limiting**: `@rate_limit()` prevents abuse
- **Performance Monitoring**: `@monitor_performance()` tracks slow operations
- **Retry Logic**: `@retry_on_failure()` handles transient failures

#### **Async Processing**
- **Background Tasks**: Non-blocking request processing
- **Concurrent Operations**: Multiple requests processed simultaneously
- **Resource Pooling**: Database connection pooling

### Code Quality & Maintainability

#### **Type Safety**
- **Protocol Classes**: Runtime type checking
- **Generic Types**: Type-safe repositories and services
- **Interface Contracts**: Clear API boundaries

#### **Error Handling**
- **Structured Exceptions**: Consistent error responses
- **Logging Integration**: Comprehensive observability
- **Graceful Degradation**: Service continues under partial failure

#### **Testing Support**
- **Dependency Injection**: Easy mocking for unit tests
- **Interface Abstraction**: Testable component boundaries
- **Factory Pattern**: Configurable test instances

### Advanced Scaling Architecture

#### **Deque-Based Queue System**
The service implements a sophisticated deque-based queue system for automatic scaling:

```python
# Thread-safe queue with configurable capacity
request_queue = DequeQueue(max_size=1000)

# O(1) enqueue/dequeue operations
await request_queue.append(request_data)  # Add to queue
request_data = request_queue.popleft()    # Process from queue
```

**Key Features:**
- **Thread-Safe Operations**: Concurrent access protection with asyncio.Lock
- **Configurable Capacity**: Prevents memory exhaustion under load
- **Health-Based Scaling**: Queue utilization affects service health status
- **Background Processing**: Dedicated worker processes queue at controlled rate

#### **Health-Aware Scaling**
The service health status dynamically adjusts based on queue utilization:

- **Healthy** (< 50% capacity): Normal operation
- **Warning** (50-80% capacity): Increased monitoring
- **Critical** (> 80% capacity): Service marked as unhealthy

#### **Rate Limiting & Backpressure**
- **Request Throttling**: Prevents API abuse with configurable limits
- **Queue Depth Monitoring**: Automatic alerts when approaching capacity
- **Graceful Degradation**: Service continues processing at reduced rate under load

#### **Concurrent User Handling**
- **N-User Scaling**: Queue system handles unlimited concurrent requests
- **Fair Processing**: FIFO (First-In-First-Out) request processing
- **Resource Pooling**: Database connections and external API calls are pooled

### Architecture Benefits

#### **Scalability**
- Queue-based request processing handles traffic spikes
- Strategy pattern allows performance tuning
- Observer pattern enables horizontal scaling

#### **Modularity**
- Pluggable components via interfaces
- Factory pattern for dynamic instantiation
- Decorator pattern for flexible composition

#### **Maintainability**
- Single responsibility per class
- Dependency inversion for loose coupling
- Clear separation of concerns

#### **Extensibility**
- Open/closed principle enables new features
- Strategy pattern for new algorithms
- Observer pattern for new monitoring

### Migration & Compatibility

The refactored architecture maintains **100% backward compatibility** with existing APIs while adding enterprise-grade features:

- **Same Endpoints**: `/sync/reviews`, `/health`, etc.
- **Same Response Formats**: JSON structure unchanged
- **Enhanced Internals**: Better performance and monitoring
- **Future-Proof**: Easy to extend and maintain

### Development Workflow

#### **Adding New Features**
```python
# 1. Define interface
class INewFeature(ABC):
    async def execute(self) -> Any: ...

# 2. Implement concrete class
class NewFeatureService(BaseService, INewFeature):
    async def execute(self) -> Any:
        # Implementation
        pass

# 3. Register with factory
service_factory.register_service("new_feature", NewFeatureService)

# 4. Use in application
new_service = service_factory.create_service("new_feature")
```

#### **Adding New Observers**
```python
class CustomObserver(BaseObserver):
    def __init__(self):
        super().__init__("custom")

    async def _handle_event(self, event: str, data: Dict[str, Any]):
        # Custom event handling
        pass

# Register observer
event_subject.attach(CustomObserver())
```

### Directory Structure

The refactored codebase follows a clean, modular architecture:

```
app/
├── core/                    # Core abstractions and services
│   ├── interfaces.py       # SOLID interfaces and protocols
│   └── services.py         # Core service implementations
├── commands/               # Command pattern implementations
│   └── __init__.py        # Command classes and invoker
├── strategies/             # Strategy pattern implementations
│   └── __init__.py        # Sync strategies and factory
├── observers/              # Observer pattern implementations
│   └── __init__.py        # Event observers and monitoring
├── decorators/             # Decorator pattern implementations
│   └── __init__.py        # Cross-cutting concerns
├── repositories/           # Repository pattern implementations
│   └── __init__.py        # Data access abstractions
├── services/               # Business logic services
│   ├── data_providers.py  # Data provider implementations
│   ├── simple_sync_service.py  # Sync service with strategies
│   └── ...                 # Other service implementations
├── models.py               # SQLAlchemy models
├── schemas.py              # Pydantic schemas
├── config.py               # Configuration management
├── database.py             # Database setup and connections
├── main.py                 # FastAPI application with patterns
└── utils/                  # Utility functions
```

### Key Architectural Files

| File | Pattern | Responsibility |
|------|---------|----------------|
| `core/interfaces.py` | Interfaces | Abstract contracts for all components |
| `core/services.py` | Factory/Service | Core service implementations and factory |
| `commands/__init__.py` | Command | Request handling and execution |
| `strategies/__init__.py` | Strategy | Sync algorithm implementations |
| `observers/__init__.py` | Observer | Event monitoring and alerting |
| `decorators/__init__.py` | Decorator | Cross-cutting concerns |
| `repositories/__init__.py` | Repository | Data access abstraction |
| `main.py` | Composition | Application composition and routing |

This comprehensive OOP and SOLID principles implementation transforms the service into an enterprise-grade, scalable, and maintainable microservice architecture! 🏆

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

### Production Scaling Configuration

For production deployments, configure the queue system for optimal performance:

```bash
# Queue Configuration
QUEUE_MAX_SIZE=1000      # Maximum queued requests
QUEUE_PROCESS_RATE=10    # Requests processed per second
HEALTH_WARNING_THRESHOLD=500  # Queue size for warning status
HEALTH_CRITICAL_THRESHOLD=800 # Queue size for critical status

# Rate Limiting
RATE_LIMIT_REQUESTS=100  # Requests per minute per IP
RATE_LIMIT_BURST=20      # Burst allowance

# Monitoring
METRICS_ENABLED=true     # Enable Prometheus metrics
ALERT_WEBHOOK_URL=https://your-monitoring-service.com/webhook
```

### Kubernetes Deployment

For enterprise deployments, use the provided Kubernetes manifests:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: review-fetcher
spec:
  replicas: 3  # Horizontal scaling
  template:
    spec:
      containers:
      - name: review-fetcher
        image: review-fetcher:latest
        env:
        - name: QUEUE_MAX_SIZE
          value: "2000"  # Larger queue for K8s
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "500m"
```

### Load Balancing

The service is stateless and can be deployed behind a load balancer:

```nginx
upstream review_fetcher {
    server review-fetcher-1:8084;
    server review-fetcher-2:8084;
    server review-fetcher-3:8084;
}

server {
    listen 80;
    location / {
        proxy_pass http://review_fetcher;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
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
| `QUEUE_MAX_SIZE` | `1000` | Maximum queued requests |
| `QUEUE_PROCESS_RATE` | `10` | Requests processed per second |
| `RATE_LIMIT_REQUESTS` | `100` | Requests per minute per IP |
| `METRICS_ENABLED` | `true` | Enable Prometheus metrics |

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

The service implements a comprehensive observer-based monitoring system with multiple specialized observers for different aspects of service health and performance.

### Observer-Based Monitoring System

The service uses the **Observer Pattern** to provide real-time monitoring through multiple specialized observers:

- **MetricsObserver**: Collects performance metrics, request counts, and response times
- **LoggingObserver**: Provides structured logging with correlation IDs and context
- **AlertingObserver**: Monitors for anomalies and sends alerts when thresholds are exceeded
- **HealthObserver**: Tracks service health status and dependency availability

### Health Endpoint

```bash
curl http://localhost:8084/health
# Returns comprehensive health status:
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00Z",
  "version": "1.0.0",
  "uptime": "2h 15m",
  "observers": {
    "metrics": "active",
    "logging": "active",
    "alerting": "active",
    "health": "active"
  },
  "dependencies": {
    "database": "healthy",
    "redis": "healthy",
    "google_api": "healthy"
  }
}
```

### Metrics Collection

Access real-time metrics via the metrics endpoint:

```bash
curl http://localhost:8084/metrics
# Returns Prometheus-compatible metrics:
# HELP review_sync_requests_total Total number of review sync requests
# TYPE review_sync_requests_total counter
# review_sync_requests_total 42
#
# HELP review_sync_duration_seconds Request duration in seconds
# TYPE review_sync_duration_seconds histogram
# review_sync_duration_seconds_bucket{le="0.1"} 5
# ...
```

### Service Logs

```bash
# View application logs with observer-enhanced logging
docker-compose logs -f review-fetcher

# View all service logs
docker-compose logs -f
```

### Alerting & Notifications

The AlertingObserver monitors for:
- High error rates (>5% of requests)
- Slow response times (>30 seconds)
- Queue depth exceeding thresholds
- Database connection issues
- External API failures

Alerts are logged and can be integrated with external monitoring systems.

### Docker Status

```bash
# Check container status
docker-compose ps

# Check resource usage
docker stats

# Monitor queue depth (via logs or metrics)
docker-compose logs review-fetcher | grep "queue_depth"
```

### Performance Monitoring

The service includes built-in performance monitoring with decorators that track:
- Request execution time
- Memory usage
- CPU utilization
- Queue processing efficiency
- Database query performance

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

### High Error Rates

```bash
# Check observer logs for alerts
docker-compose logs review-fetcher | grep "ALERT"

# Monitor queue status
curl http://localhost:8084/health | jq .queue_status

# Check dependency health
curl http://localhost:8084/health | jq .dependencies
```

### Performance Issues

```bash
# Check performance metrics
curl http://localhost:8084/metrics | grep "review_sync_duration"

# Monitor queue depth
docker-compose logs review-fetcher | grep "queue_size"

# Check resource usage
docker stats
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
