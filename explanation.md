# Review Fetcher Service - Complete Microservice Explanation

## 🎯 **What is the Review Fetcher Service?**

The **Review Fetcher Service** is a sophisticated, production-ready microservice built with FastAPI that fetches Google Business Profile reviews through OAuth authentication. It implements advanced software architecture patterns (SOLID principles, design patterns) and provides both synchronous and asynchronous review fetching capabilities.

**Core Purpose**: Fetch, process, and manage Google Business Profile reviews with enterprise-grade reliability, scalability, and monitoring.

---

## 🏗️ **Architecture Overview**

### **High-Level Architecture**
```
┌─────────────────────────────────────────────────────────────┐
│                    Review Fetcher Service                   │
│  ┌─────────────────────────────────────────────────────┐    │
│  │                FastAPI Application                 │    │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐    │    │
│  │  │  REST   │ │ WebSock │ │ Backgr  │ │ Health  │    │    │
│  │  │  APIs   │ │ et APIs │ │ ound    │ │ Checks  │    │    │
│  │  └─────────┘ └─────────┘ │ Tasks   │ └─────────┘    │    │
│  └──────────────────────────┼─────────────────────────┘    │
│  ┌──────────────────────────┼─────────────────────────┐    │
│  │      Business Logic      │     Data Access         │    │
│  │  ┌─────────┐ ┌─────────┐ │ ┌─────────┐ ┌─────────┐  │    │
│  │  │  Sync   │ │  Data   │ │ │  Repos  │ │  Models │  │    │
│  │  │ Service │ │ Provider│ │ │ itories │ │  (SQL)  │  │    │
│  │  └─────────┘ └─────────┘ │ └─────────┘ └─────────┘  │    │
│  └──────────────────────────┼─────────────────────────┘    │
│  ┌──────────────────────────┼─────────────────────────┐    │
│  │   Design Patterns        │   External Services     │    │
│  │  ┌─────────┐ ┌─────────┐ │ ┌─────────┐ ┌─────────┐  │    │
│  │  │Command │ │Observer │ │ │ Google  │ │ Kafka   │  │    │
│  │  │Pattern │ │Pattern  │ │ │  API    │ │Producer │  │    │
│  │  └─────────┘ └─────────┘ │ └─────────┘ └─────────┘  │    │
│  └──────────────────────────┼─────────────────────────┘    │
└─────────────────────────────┼──────────────────────────────┘
                              │
                 ┌────────────┴────────────┐
                 │    Infrastructure       │
                 │  ┌─────────┐ ┌─────────┐ │
                 │  │PostgreSQL│ │  Redis  │ │
                 │  │Database │ │  Cache  │ │
                 │  └─────────┘ └─────────┘ │
                 └─────────────────────────┘
```

---

## 📁 **Complete File Structure & Code Organization**

### **Root Directory Structure**
```
review-fetcher-service/
├── app/                          # Main application code
├── mock_data/                    # Test data for development
├── Dockerfile                    # Container configuration
├── docker-compose.yml           # Multi-container setup
├── requirements.txt             # Python dependencies
├── README.md                    # Documentation
├── flow.md                      # Architecture flow documentation
├── run.sh                       # Startup script
├── test_microservice.sh         # Testing script
└── .env.example                 # Environment configuration template
```

### **Main Application Directory (`app/`)**

#### **`main.py`** - FastAPI Application Entry Point
```python
# File: app/main.py
# Purpose: Main FastAPI application with SOLID principles and design patterns
# Key Components:
# - FastAPI app initialization
# - Request queue management for scaling
# - Background task processing
# - Observer pattern integration
# - Command pattern for request handling
# - Multiple API endpoints

# Core functionality:
app = FastAPI(title="Google Reviews Fetcher Service", version="2.0.0")

# Request queue for automatic scaling
request_queue = DequeQueue(max_size=1000)
PROCESSING_RATE = 10  # Requests per second

# Command invoker for handling requests
command_invoker = CommandInvoker()

# API Endpoints:
# 1. POST /sync - Background sync with job tracking
# 2. GET /job/{job_id} - Job status monitoring
# 3. GET /health - Enhanced health checks
# 4. GET /reviews - Get all reviews with pagination
# 5. GET /reviews/{job_id} - Get reviews by job
# 6. GET /sync/reviews - Simplified sync endpoint
```

#### **`config.py`** - Configuration Management
```python
# File: app/config.py
# Purpose: Environment-based configuration using Pydantic
# Key Settings:
class Settings(BaseSettings):
    database_url: str          # PostgreSQL connection
    redis_url: str            # Redis cache connection
    mock_mode: bool           # Enable mock data mode
    data_mode: str            # "google" or "mock"
    log_level: str            # Logging level
```

#### **`database.py`** - Database Connection Management
```python
# File: app/database.py
# Purpose: SQLAlchemy async database setup with connection pooling
# Key Features:
# - Async engine with connection pooling
# - Optimized for high concurrency
# - Connection recycling and timeout management

engine = create_async_engine(
    settings.database_url,
    pool_size=20,          # 20 persistent connections
    max_overflow=30,       # 30 additional connections
    pool_timeout=60,       # 60 second timeout
    pool_recycle=3600,     # Recycle every hour
)
```

#### **`models.py`** - Database Models (SQLAlchemy)
```python
# File: app/models.py
# Purpose: SQLAlchemy ORM models for database tables
# Tables:

class SyncJob(Base):           # Tracks sync operations
    id: Primary Key
    client_id: String
    status: String (pending/running/completed/failed)
    current_step: String
    step_status: JSON          # Detailed step tracking
    access_token: Text         # OAuth token storage
    created_at/updated_at: DateTime

class Account(Base):           # Google Business accounts
    id: String (Google account ID)
    name: String
    client_id: String
    sync_job_id: Foreign Key

class Location(Base):          # Business locations
    id: String (Google location ID)
    account_id: Foreign Key
    name: String
    address: Text
    client_id: String
    sync_job_id: Foreign Key

class Review(Base):            # Customer reviews
    id: String (Google review ID)
    location_id: Foreign Key
    account_id: Foreign Key
    rating: Integer (1-5)
    comment: Text
    reviewer_name: String
    create_time: DateTime
    client_id: String
    sync_job_id: Foreign Key
```

#### **`schemas.py`** - API Data Models (Pydantic)
```python
# File: app/schemas.py
# Purpose: Pydantic models for API request/response validation
# Key Schemas:

class SyncRequest(BaseModel):          # POST /sync input
    access_token: str
    client_id: Optional[str]
    request_id: Optional[str]
    correlation_id: Optional[str]

class SyncResponse(BaseModel):         # POST /sync output
    job_id: int
    status: str
    message: str

class JobStatusResponse(BaseModel):    # GET /job/{id} output
    job_id: int
    status: str
    current_step: str
    step_status: Dict[str, Any]
    created_at: datetime

class ReviewResponse(BaseModel):       # Review data structure
    id: str
    location_id: str
    account_id: str
    rating: Optional[int]
    comment: Optional[str]
    reviewer_name: Optional[str]
    create_time: Optional[datetime]
```

### **Services Directory (`app/services/`)**

#### **`data_providers.py`** - Data Provider Pattern Implementation
```python
# File: app/services/data_providers.py
# Purpose: Abstract data source interface for Google API vs Mock data
# Design Pattern: Strategy Pattern + Abstract Factory

class DataProvider(ABC):               # Abstract interface
    @abstractmethod
    async def get_accounts(self, access_token: str): pass
    @abstractmethod
    async def get_locations(self, account_id: str): pass
    @abstractmethod
    async def get_reviews(self, location_id: str): pass

class GoogleDataProvider(DataProvider):    # Real Google API
    def __init__(self, google_api_client):
        self.google_api_client = google_api_client

class MockDataProvider(DataProvider):      # Mock data for testing
    def __init__(self, mock_data_path: str = None):
        # Loads JSON files: accounts.json, locations.json, reviews.json
        self._load_data()
        self._build_indexes()  # Efficient lookup indexes

def get_data_provider(data_mode: str) -> DataProvider:
    """Factory function for data provider selection"""
    if data_mode == "mock":
        return MockDataProvider()
    elif data_mode == "google":
        return GoogleDataProvider(google_api_client)
```

#### **`sync_service.py`** - Core Sync Business Logic
```python
# File: app/services/sync_service.py
# Purpose: Implements the 5-step continuous sync flow
# Key Features:
# - Retry mechanisms with Tenacity
# - Step-by-step progress tracking
# - Error handling and recovery
# - Database persistence

class SyncService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # 5-Step Continuous Flow:
    # 1. Token Validation
    # 2. Accounts Fetch
    # 3. Locations Fetch
    # 4. Reviews Fetch
    # 5. Kafka Publish

    async def start_sync_flow(self, access_token, client_id, sync_job_id):
        # Step 1: Token validation with retry
        await self._step_token_validation(access_token, sync_job_id)

        # Step 2: Fetch accounts and store in DB
        await self._step_accounts_fetch(access_token, client_id, sync_job_id)

        # Step 3: Fetch locations for all accounts
        await self._step_locations_fetch(access_token, client_id, sync_job_id)

        # Step 4: Fetch reviews for all locations
        await self._step_reviews_fetch(access_token, client_id, sync_job_id)

        # Step 5: Publish to Kafka
        await self._step_kafka_publish(sync_job_id)
```

#### **`simple_sync_service.py`** - Simplified Sync Service
```python
# File: app/services/simple_sync_service.py
# Purpose: Lightweight sync service for direct JSON responses
# Use Case: Quick API responses without database persistence
# Returns: {"account": {...}, "locations": [{"location": {...}, "reviews": [...]}]}
```

#### **`google_api.py`** - Google Business Profile API Client
```python
# File: app/services/google_api.py
# Purpose: HTTP client for Google Business Profile API
# Methods:
# - validate_token()
# - get_accounts()
# - get_locations()
# - get_reviews()
```

#### **`kafka_producer.py`** - Message Queue Integration
```python
# File: app/services/kafka_producer.py
# Purpose: Publish review data to Kafka for downstream processing
# Message Format: ReviewMessage (review_id, location_id, account_id, rating, comment, etc.)
```

### **Workers Directory (`app/workers/`)**

#### **`tasks.py`** - Background Task Processing
```python
# File: app/workers/tasks.py
# Purpose: Celery-like background task execution for FastAPI
# Key Function:

async def sync_reviews_task(access_token: str, client_id: str, sync_job_id: int):
    """Execute the continuous sync flow automatically"""
    async with async_session() as db:
        service = SyncService(db)
        await service.start_sync_flow(access_token, client_id, sync_job_id)
```

### **Core Architecture (`app/core/`)**

#### **`interfaces.py`** - SOLID Principles Interfaces
```python
# File: app/core/interfaces.py
# Purpose: Define contracts for dependency injection and polymorphism
# Key Interfaces:

class IService(Protocol):              # Service health and lifecycle
class IDataProvider(ABC):             # Data source abstraction
class ISyncService(ABC):              # Sync operations
class IRepository(ABC):               # Data access abstraction
class ICache(ABC):                    # Caching abstraction
class IObserver(ABC):                 # Observer pattern
class ICommand(ABC):                  # Command pattern
```

#### **`services.py`** - Core Service Implementations
```python
# File: app/core/services.py
# Purpose: Base service classes and shared utilities
# Key Components:

class BaseService(IService):          # Base service with health monitoring
class DequeQueue:                     # Thread-safe request queue
class EventSubject:                   # Observer pattern subject
service_factory: ServiceFactory       # Service registration and discovery
```

### **Design Patterns Implementation**

#### **`commands/__init__.py`** - Command Pattern
```python
# File: app/commands/__init__.py
# Purpose: Encapsulate requests as objects for queuing and execution
# Commands:

class SyncReviewsCommand(BaseCommand):    # Execute sync operation
class HealthCheckCommand(BaseCommand):    # Health check execution
class CommandInvoker:                     # Command execution manager
```

#### **`observers/__init__.py`** - Observer Pattern
```python
# File: app/observers/__init__.py
# Purpose: Event-driven monitoring and alerting
# Observers:

class MetricsObserver(BaseObserver):      # Collect performance metrics
class LoggingObserver(BaseObserver):      # Enhanced structured logging
class AlertingObserver(BaseObserver):     # Alert on errors/critical events
class HealthObserver(BaseObserver):       # Health status monitoring
```

#### **`strategies/__init__.py`** - Strategy Pattern
```python
# File: app/strategies/__init__.py
# Purpose: Pluggable sync strategies
# Strategies:

class SimpleSyncStrategy(ISyncStrategy):  # Direct processing
class BatchSyncStrategy(ISyncStrategy):   # Batch processing
class StreamingSyncStrategy(ISyncStrategy): # Streaming processing

class SyncStrategyFactory:                # Strategy creation factory
```

#### **`repositories/__init__.py`** - Repository Pattern
```python
# File: app/repositories/__init__.py
# Purpose: Data access abstraction layer
# Repositories:

class BaseRepository(IRepository):         # Generic CRUD operations
class SyncJobRepository(BaseRepository):  # SyncJob specific operations
class AccountRepository(BaseRepository):  # Account specific operations
class LocationRepository(BaseRepository): # Location specific operations
class ReviewRepository(BaseRepository):   # Review specific operations
```

#### **`decorators/__init__.py`** - Decorator Pattern
```python
# File: app/decorators/__init__.py
# Purpose: Cross-cutting concerns (logging, caching, rate limiting)
# Decorators:

@log_execution()                          # Function execution logging
@rate_limit(requests_per_minute=60)       # Rate limiting
@monitor_performance(threshold_ms=5000)  # Performance monitoring
@validate_input({...})                    # Input validation
@cache_result(ttl_seconds=300)            # Result caching
```

### **Mock Data Directory (`mock_data/`)**

#### **`accounts.json`** - Mock Business Accounts
```json
[
  {
    "id": 1,
    "account_id": 1,
    "client_id": 1,
    "google_account_name": "accounts/10000000000000000001",
    "account_display_name": "ABC Restaurant Group",
    "created_at": "2025-01-20T12:46:00Z",
    "updated_at": "2025-01-20T12:46:00Z"
  }
  // ... more accounts
]
```

#### **`locations.json`** - Mock Business Locations
```json
[
  {
    "id": 1,
    "location_id": 1,
    "account_id": 1,
    "location_name": "Downtown Branch",
    "address": "123 Main St, City, State",
    "google_location_name": "locations/10000000000000000001"
  }
  // ... more locations
]
```

#### **`reviews.json`** - Mock Customer Reviews
```json
[
  {
    "id": 1,
    "review_id": "r1",
    "location_id": 1,
    "account_id": 1,
    "rating": 5,
    "comment": "Amazing service and great food!",
    "reviewer_name": "John Doe",
    "create_time": "2025-01-15T14:30:00Z"
  }
  // ... more reviews
]
```

---

## 🔄 **How All Components Work Together**

### **1. Request Flow (Simplified Sync)**
```
User Request → FastAPI Endpoint → Command Pattern → Strategy Pattern → Data Provider → Response
```

### **2. Background Sync Flow**
```
POST /sync → Background Task → Sync Service → 5-Step Flow → Database → Kafka → Completion
```

### **3. Data Flow Architecture**
```
Google API / Mock Data → Data Provider → Sync Service → Database Models → Kafka Producer → Downstream Services
```

### **4. Monitoring & Observability**
```
All Components → Observer Pattern → Metrics/Logging/Alerting → Health Checks → Monitoring Dashboard
```

### **5. Design Patterns Integration**
```
Command Pattern → Strategy Pattern → Repository Pattern → Observer Pattern → Decorator Pattern
```

---

## 🎯 **Key Features & Capabilities**

### **Dual-Mode Operation**
- **Google Mode**: Real Google Business Profile API integration
- **Mock Mode**: JSON file-based testing and development
- **Seamless Switching**: Environment variable configuration

### **Advanced Sync Flow**
- **5-Step Process**: Token → Accounts → Locations → Reviews → Kafka
- **Progress Tracking**: Real-time step status monitoring
- **Retry Mechanisms**: Tenacity-based resilient API calls
- **Error Recovery**: Comprehensive error handling and logging

### **Scalability Features**
- **Request Queue**: Automatic scaling with controlled processing rate
- **Async Processing**: Non-blocking I/O operations
- **Connection Pooling**: Optimized database connections
- **Background Tasks**: Long-running operations don't block API

### **Enterprise Monitoring**
- **Structured Logging**: JSON-formatted logs with correlation IDs
- **Health Checks**: Multi-level service health monitoring
- **Metrics Collection**: Performance and usage metrics
- **Observer Pattern**: Event-driven monitoring and alerting

### **API Endpoints**
1. **POST /sync** - Start background sync job
2. **GET /job/{job_id}** - Monitor sync progress
3. **GET /sync/reviews** - Direct JSON response sync
4. **GET /reviews** - Paginated review retrieval
5. **GET /health** - Service health status

---

## 🛠️ **Technology Stack**

### **Core Framework**
- **FastAPI**: High-performance async web framework
- **Python 3.11+**: Modern Python with async/await support
- **Uvicorn**: ASGI server for FastAPI

### **Database & Caching**
- **PostgreSQL**: Primary data storage with async SQLAlchemy
- **Redis**: Caching and session management
- **SQLAlchemy 2.0**: Modern async ORM

### **External Integrations**
- **Google Business Profile API**: Review data source
- **Kafka**: Message streaming for downstream processing
- **OAuth 2.0**: Authentication and authorization

### **Quality & Monitoring**
- **Pydantic**: Data validation and serialization
- **Structlog**: Structured JSON logging
- **Tenacity**: Retry mechanisms and resilience
- **Prometheus**: Metrics collection (optional)

### **Design Patterns**
- **SOLID Principles**: Interface segregation, dependency inversion
- **Command Pattern**: Request encapsulation
- **Observer Pattern**: Event-driven architecture
- **Strategy Pattern**: Pluggable algorithms
- **Repository Pattern**: Data access abstraction
- **Decorator Pattern**: Cross-cutting concerns

---

## 🚀 **Deployment & Configuration**

### **Environment Variables**
```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/reviews

# External Services
REDIS_URL=redis://localhost:6379
KAFKA_BOOTSTRAP_SERVERS=localhost:9092

# Mode Configuration
DATA_MODE=google  # or "mock"
MOCK_MODE=false

# Application
LOG_LEVEL=INFO
HOST=0.0.0.0
PORT=8000
```

### **Docker Deployment**
```yaml
# docker-compose.yml
version: '3.8'
services:
  review-fetcher:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATA_MODE=mock
    depends_on:
      - postgres
      - redis
      - kafka
```

### **Production Considerations**
- **Load Balancing**: Multiple service instances
- **Database Indexing**: Optimized query performance
- **Rate Limiting**: API quota management
- **Monitoring**: Comprehensive observability setup
- **Security**: OAuth token management and validation

---

## 📊 **Data Processing Flow**

### **Input Processing**
1. **OAuth Token Validation**: Verify Google API access
2. **Account Discovery**: Fetch all accessible business accounts
3. **Location Enumeration**: Get all locations for each account
4. **Review Collection**: Fetch reviews for each location
5. **Data Transformation**: Convert to internal data models

### **Data Storage**
1. **SyncJob Creation**: Track overall operation status
2. **Account Persistence**: Store business account information
3. **Location Storage**: Save location details with relationships
4. **Review Archival**: Store review data with foreign keys
5. **Status Updates**: Real-time progress tracking

### **Data Output**
1. **Kafka Publishing**: Stream reviews to message queue
2. **API Responses**: Return processed data to clients
3. **Health Metrics**: Provide operational visibility
4. **Logging**: Structured event logging

---

## 🔍 **Understanding the Current State**

### **What Makes This Microservice Special**

1. **Enterprise-Grade Architecture**: Implements advanced design patterns rarely seen in microservices
2. **Dual-Mode Operation**: Seamless switching between production and testing environments
3. **Comprehensive Monitoring**: Built-in observability with multiple monitoring patterns
4. **Scalable Design**: Request queuing, connection pooling, and async processing
5. **Resilient Operations**: Retry mechanisms, error recovery, and graceful degradation

### **Current Capabilities**

- ✅ **Google Business Profile Integration**: Real API data fetching
- ✅ **Mock Data Testing**: Complete test environment
- ✅ **Background Processing**: Non-blocking long-running operations
- ✅ **Real-time Monitoring**: Job status and health tracking
- ✅ **Message Queue Integration**: Kafka publishing for downstream processing
- ✅ **Database Persistence**: Full data archival with relationships
- ✅ **API Rate Limiting**: Controlled request processing
- ✅ **Structured Logging**: Production-ready logging infrastructure

### **How to Use This Microservice**

1. **Start the Service**:
   ```bash
   # For mock mode (testing)
   export DATA_MODE=mock
   python -m uvicorn app.main:app --reload

   # For Google API mode (production)
   export DATA_MODE=google
   export DATABASE_URL=postgresql+asyncpg://...
   python -m uvicorn app.main:app
   ```

2. **Test the API**:
   ```bash
   # Health check
   curl http://localhost:8000/health

   # Simple sync (returns JSON directly)
   curl "http://localhost:8000/sync/reviews?access_token=mock_token"

   # Background sync (returns job ID)
   curl -X POST "http://localhost:8000/sync" \
        -H "Content-Type: application/json" \
        -d '{"access_token": "your_oauth_token"}'

   # Check job status
   curl "http://localhost:8000/job/1"
   ```

3. **Monitor Operations**:
   - Check logs for structured JSON output
   - Monitor health endpoints for service status
   - Track job progress through status API
   - Observe metrics collection

### **Key Insights for Understanding**

1. **Modular Design**: Each component has a single responsibility
2. **Testability**: Mock data provider enables comprehensive testing
3. **Scalability**: Async processing and queuing handle high loads
4. **Reliability**: Retry mechanisms and error handling ensure robustness
5. **Maintainability**: Clean architecture with clear separation of concerns
6. **Observability**: Multiple monitoring patterns provide full visibility

This microservice represents a sophisticated implementation of modern software architecture principles applied to a real-world business problem: fetching and processing Google Business Profile reviews at scale.</content>
<parameter name="filePath">/Users/dinoshm/Desktop/applic/ReviewExtractorPr/explanation.md