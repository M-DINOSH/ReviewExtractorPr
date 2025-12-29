# Review Fetcher Service - Complete Flow Documentation

## Overview

The **Review Fetcher Service** is a high-performance microservice built with FastAPI that fetches Google Business Profile reviews through OAuth authentication. It implements a sophisticated dual-mode architecture supporting both production Google API calls and mock data for development/testing.

## Architecture & Tech Stack

### Core Technologies
- **FastAPI**: Async web framework for high-performance API endpoints
- **SQLAlchemy (Async)**: Asynchronous database ORM for PostgreSQL operations
- **PostgreSQL**: Primary database for job tracking and data persistence
- **Redis**: Caching layer and potential message queuing
- **Google Business Profile API**: External data source for real business reviews
- **Kafka**: Message streaming for downstream processing (sentiment analysis, etc.)
- **Docker**: Containerization for consistent deployment
- **AsyncIO**: Python's asynchronous programming for concurrent I/O operations
- **Structlog**: Structured JSON logging for production monitoring
- **Pydantic**: Runtime data validation and serialization
- **Tenacity**: Retry mechanisms for resilient API calls

### Design Patterns
- **Data Provider Pattern**: Clean abstraction for Google vs Mock data sources
- **Background Tasks**: FastAPI's async background processing for long-running operations
- **Repository Pattern**: Database operations abstracted through services
- **Factory Pattern**: Dynamic provider instantiation based on configuration

## System Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   FastAPI App   │────│  Background Task │────│   Sync Service  │
│   (main.py)     │    │   (tasks.py)     │    │ (sync_service.py)│
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                        │                       │
         │                        │                       │
         ▼                        ▼                       ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Data Provider │────│   Google API     │────│   PostgreSQL    │
│ (data_providers)│    │   Client         │    │   Database      │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                        │                       │
         │                        ▼                       │
         │              ┌──────────────────┐              │
         └──────────────│     Kafka        │──────────────┘
                        │   Producer      │
                        └──────────────────┘
```

## Data Flow Architecture

### 1. API Request Entry Point
```python
# app/main.py - FastAPI endpoint
@app.post("/sync-reviews")
async def sync_reviews(request: SyncRequest, background_tasks: BackgroundTasks):
    # 1. Create database job record
    sync_job = SyncJob(client_id=request.client_id, access_token=request.access_token)
    db.add(sync_job)
    await db.commit()

    # 2. Enqueue background task
    background_tasks.add_task(sync_reviews_task, request.access_token, request.client_id, sync_job.id)

    # 3. Return immediate response with job ID
    return {"job_id": sync_job.id, "status": "accepted"}
```

### 2. Background Task Processing
```python
# app/workers/tasks.py - Background task execution
async def sync_reviews_task(access_token: str, client_id: str, sync_job_id: int):
    async with async_session() as db:
        service = SyncService(db)
        await service.start_sync_flow(access_token, client_id, sync_job_id)
```

### 3. Continuous Sync Flow
The service implements a **5-step continuous flow** with automatic progression:

#### Step 1: Token Validation
```python
async def _step_token_validation(self, access_token: str, sync_job_id: int):
    await google_api_client.validate_token(access_token)
    await self._update_step_status(sync_job_id, "token_validation", "completed")
```

#### Step 2: Accounts Fetch
```python
async def _step_accounts_fetch(self, access_token: str, client_id: str, sync_job_id: int):
    accounts_data = await google_api_client.get_accounts(access_token)
    # Store accounts in database with unique IDs
    for account in accounts:
        account_obj = Account(id=unique_id, name=account["accountName"], ...)
        self.db.add(account_obj)
```

#### Step 3: Locations Fetch
```python
async def _step_locations_fetch(self, access_token: str, client_id: str, sync_job_id: int):
    # For each account, fetch locations
    for account_id in account_ids:
        locations_data = await google_api_client.get_locations(account_id, access_token)
        # Store locations in database
```

#### Step 4: Reviews Fetch
```python
async def _step_reviews_fetch(self, access_token: str, client_id: str, sync_job_id: int):
    # For each location, fetch reviews
    for location_id, account_id in location_data:
        reviews_data = await google_api_client.get_reviews(account_id, location_id, access_token)
        # Store reviews in database with rating conversion
```

#### Step 5: Kafka Publish
```python
async def _step_kafka_publish(self, sync_job_id: int):
    # Get all reviews and publish to Kafka
    for review in review_data:
        message = ReviewMessage(...)
        kafka_producer.send_review(message.dict())
```

## Dual-Mode Architecture

### Configuration
```python
# app/config.py
class Settings(BaseSettings):
    data_mode: str = os.getenv("DATA_MODE", "google")  # "google" or "mock"
    mock_mode: bool = os.getenv("MOCK_MODE", "false").lower() == "true"
```

### Data Provider Abstraction
```python
# app/services/data_providers.py
class DataProvider(ABC):
    @abstractmethod
    async def get_accounts(self, access_token: str): pass
    @abstractmethod
    async def get_locations(self, account_id: str): pass
    @abstractmethod
    async def get_reviews(self, location_id: str): pass

def get_data_provider(data_mode: str, google_api_client=None) -> DataProvider:
    if data_mode == "mock":
        return MockDataProvider()
    elif data_mode == "google":
        return GoogleDataProvider(google_api_client)
```

### Google Mode vs Mock Mode

#### Google Mode
- Real Google Business Profile API calls
- OAuth token validation
- Production data from Google servers
- Rate limiting and quota management
- Real account/location/review data

#### Mock Mode
- JSON file-based data simulation
- Random account selection (1-40 range)
- Pre-defined test data
- No API rate limits
- Deterministic testing scenarios

## Database Schema

### SyncJob Table
```sql
CREATE TABLE sync_jobs (
    id SERIAL PRIMARY KEY,
    client_id VARCHAR NOT NULL,
    status VARCHAR DEFAULT 'pending',
    current_step VARCHAR DEFAULT 'token_validation',
    step_status JSONB DEFAULT '{}',
    access_token TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE
);
```

### Account Table
```sql
CREATE TABLE accounts (
    id VARCHAR PRIMARY KEY,
    name VARCHAR,
    client_id VARCHAR NOT NULL,
    sync_job_id INTEGER REFERENCES sync_jobs(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### Location Table
```sql
CREATE TABLE locations (
    id VARCHAR PRIMARY KEY,
    account_id VARCHAR REFERENCES accounts(id),
    name VARCHAR,
    address TEXT,
    client_id VARCHAR NOT NULL,
    sync_job_id INTEGER REFERENCES sync_jobs(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### Review Table
```sql
CREATE TABLE reviews (
    id VARCHAR PRIMARY KEY,
    location_id VARCHAR REFERENCES locations(id),
    account_id VARCHAR REFERENCES accounts(id),
    rating INTEGER,
    comment TEXT,
    reviewer_name VARCHAR,
    create_time TIMESTAMP WITH TIME ZONE,
    client_id VARCHAR NOT NULL,
    sync_job_id INTEGER REFERENCES sync_jobs(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

## API Endpoints

### POST /sync-reviews
**Purpose**: Initiate review synchronization job
**Request**:
```json
{
  "client_id": "client123",
  "access_token": "ya29.abc123..."
}
```
**Response**:
```json
{
  "job_id": 123,
  "status": "accepted"
}
```

### GET /job-status/{job_id}
**Purpose**: Get real-time job status and progress
**Response**:
```json
{
  "job_id": 123,
  "status": "running",
  "current_step": "reviews_fetch",
  "step_status": {
    "token_validation": {"status": "completed", "timestamp": "2024-01-01T10:00:00Z"},
    "accounts_fetch": {"status": "completed", "timestamp": "2024-01-01T10:00:05Z"},
    "locations_fetch": {"status": "completed", "timestamp": "2024-01-01T10:00:10Z"},
    "reviews_fetch": {"status": "running", "timestamp": "2024-01-01T10:00:15Z"}
  },
  "created_at": "2024-01-01T10:00:00Z",
  "updated_at": "2024-01-01T10:00:15Z"
}
```

### POST /sync-reviews-simple
**Purpose**: Simplified sync returning JSON data directly
**Request**:
```json
{
  "access_token": "ya29.abc123..."
}
```
**Response**:
```json
{
  "account": {
    "account_id": 1,
    "account_display_name": "Test Business"
  },
  "locations": [
    {
      "location": {
        "location_id": 1,
        "location_name": "Main Store",
        "address": "123 Main St"
      },
      "reviews": [
        {
          "review_id": "r1",
          "rating": 5,
          "comment": "Great service!",
          "reviewer_name": "John Doe",
          "create_time": "2024-01-01T12:00:00Z"
        }
      ]
    }
  ]
}
```

## Error Handling & Resilience

### Retry Mechanisms
- **Tenacity Library**: Exponential backoff retry for API calls
- **Step-level Retries**: Each sync step has independent retry logic
- **Configurable Retry Counts**: Default 3 retries per step

### Error Scenarios
1. **Token Validation Failure**: Invalid or expired OAuth token
2. **API Rate Limiting**: Google API quota exceeded
3. **Network Issues**: Connection timeouts or DNS failures
4. **Data Parsing Errors**: Unexpected API response format
5. **Database Connection Issues**: PostgreSQL connectivity problems

### Status Tracking
- **Job-level Status**: Overall job state (pending/running/completed/failed)
- **Step-level Status**: Individual step progress with timestamps
- **Error Messages**: Detailed error information for debugging

## Kafka Integration

### Message Schema
```python
class ReviewMessage(BaseModel):
    review_id: str
    location_id: str
    account_id: str
    rating: int
    comment: str
    reviewer_name: str
    create_time: str
    source: str = "google"
    ingestion_timestamp: str
    sync_job_id: int
```

### Publishing Flow
1. Fetch all reviews from database for completed job
2. Transform each review into ReviewMessage format
3. Publish to Kafka topic with proper partitioning
4. Track publish success/failure counts

## Configuration & Environment

### Environment Variables
```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/reviews

# Redis
REDIS_URL=redis://localhost:6379

# Mode Configuration
DATA_MODE=google  # or "mock"
MOCK_MODE=false   # legacy, use DATA_MODE

# Logging
LOG_LEVEL=INFO

# Google API (if applicable)
GOOGLE_CLIENT_ID=your_client_id
GOOGLE_CLIENT_SECRET=your_client_secret
```

### Docker Configuration
```yaml
version: '3.8'
services:
  review-fetcher:
    build: .
    environment:
      - DATA_MODE=mock  # Switch to 'google' for production
      - DATABASE_URL=postgresql+asyncpg://user:password@db:5432/reviews
      - REDIS_URL=redis://redis:6379
    depends_on:
      - db
      - redis
```

## Development & Testing

### Mock Data Structure
```
mock_data/
├── accounts.json     # Business accounts data
├── locations.json    # Location information
└── reviews.json      # Review data with ratings/comments
```

### Testing Strategy
1. **Unit Tests**: Individual service method testing
2. **Integration Tests**: Full API endpoint testing
3. **Mock Mode Testing**: Deterministic testing with mock data
4. **Load Testing**: Concurrent request handling validation

### Switching Between Modes
```bash
# Development with mock data
export DATA_MODE=mock
python main.py

# Production with Google API
export DATA_MODE=google
export GOOGLE_CLIENT_ID=...
export GOOGLE_CLIENT_SECRET=...
python main.py
```

## Monitoring & Observability

### Structured Logging
- **Request Correlation**: Track requests across service boundaries
- **Step Timing**: Measure performance of each sync step
- **Error Context**: Detailed error information with stack traces
- **Business Metrics**: Review counts, account counts, processing times

### Health Checks
- **Database Connectivity**: PostgreSQL connection validation
- **Redis Connectivity**: Cache/message queue availability
- **Google API Health**: Token validation and basic API calls
- **Kafka Connectivity**: Message publishing capability

## Performance Considerations

### Async Processing Benefits
- **Concurrent API Calls**: Multiple Google API requests simultaneously
- **Non-blocking I/O**: Database operations don't block request handling
- **Background Processing**: Long-running sync jobs don't tie up web workers

### Scalability Features
- **Horizontal Scaling**: Multiple service instances with shared database
- **Background Queues**: Redis-backed task queuing for high throughput
- **Database Indexing**: Optimized queries for job status and data retrieval

### Resource Management
- **Connection Pooling**: SQLAlchemy async connection management
- **Memory Efficient**: Streaming processing for large datasets
- **Rate Limiting**: Respect Google API quotas and limits

## Deployment & Operations

### Docker Deployment
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Production Checklist
- [ ] Environment variables configured
- [ ] Database migrations applied
- [ ] Google OAuth credentials set
- [ ] Kafka brokers accessible
- [ ] Redis cache available
- [ ] Mock data files present (for testing)
- [ ] Health check endpoints responding
- [ ] Logging configured for production
- [ ] Monitoring dashboards set up

## Future Enhancements

### Potential Improvements
1. **Webhook Integration**: Real-time review notifications from Google
2. **Incremental Sync**: Only fetch new/changed reviews
3. **Multi-region Support**: Global deployment with data locality
4. **Advanced Filtering**: Date ranges, rating filters, location filters
5. **Analytics Dashboard**: Review trends and business insights
6. **Machine Learning**: Automated review categorization and insights

### Scalability Roadmap
1. **Message Queue**: Replace background tasks with Redis/RabbitMQ
2. **Microservices Split**: Separate sync service from API service
3. **Event Sourcing**: Complete audit trail of all operations
4. **Caching Layer**: Redis caching for frequently accessed data
5. **Load Balancing**: Nginx/Traefik for request distribution

---

## Quick Start Guide

1. **Clone Repository**
   ```bash
   git clone <repository-url>
   cd review-fetcher-service
   ```

2. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment**
   ```bash
   export DATA_MODE=mock  # For testing
   export DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/reviews
   ```

4. **Run Database Migrations**
   ```bash
   # Using Alembic or manual SQL
   python -c "from app.database import create_tables; create_tables()"
   ```

5. **Start Service**
   ```bash
   uvicorn app.main:app --reload
   ```

6. **Test Endpoint**
   ```bash
   curl -X POST "http://localhost:8000/sync-reviews-simple" \
        -H "Content-Type: application/json" \
        -d '{"access_token": "mock_token"}'
   ```

This documentation provides a comprehensive overview of the Review Fetcher Service architecture, implementation details, and operational procedures.</content>
<parameter name="filePath">/Users/dinoshm/Desktop/applic/ReviewExtractorPr/flow.md