# Docker Orchestration Guide - Review Fetcher Service

## What Gets Containerized

### 1. **Core Application Services**

#### Review Fetcher Service
- **Port:** 8084 → 8000 (internal)
- **Image:** review-fetcher:local
- **Dependencies:** Kafka (healthy)
- **Function:** Accepts fetch jobs, manages queue, publishes to Kafka topics
- **Health Check:** `GET /health` endpoint
- **Volumes:** Mounts app code for development (hot-reload)

#### Separation Service (Optional)
- **Port:** 8085 → 5000
- **Image:** separation-service:local
- **Function:** Sentiment analysis on reviews from Kafka
- **Input Topic:** `reviews-raw` (from review-fetcher)
- **Output Topic:** `reviews-sentiment`

---

### 2. **Message Queue - Kafka Ecosystem**

#### Zookeeper
- **Port:** 2181
- **Image:** confluentinc/cp-zookeeper:7.5.0
- **Purpose:** Coordinates Kafka broker, manages leader election
- **Why:** Kafka requires Zookeeper for distributed consensus
- **Health Check:** Checks TCP port 2181 connectivity

#### Kafka Broker
- **Ports:** 
  - 9092 (internal container communication)
  - 9094 (host machine access)
- **Image:** confluentinc/cp-kafka:7.5.0
- **Purpose:** Message streaming, topic management, partition handling
- **Topics Auto-Created:**
  - `fetch-accounts` - Account fetch jobs
  - `fetch-locations` - Location fetch jobs
  - `fetch-reviews` - Review fetch jobs
  - `reviews-raw` - Processed reviews output
  - `reviews-dlq` - Dead Letter Queue for failed jobs
  - `reviews-sentiment` - Sentiment analysis results (if separation-service enabled)
- **Health Check:** Validates broker API availability

#### Kafka UI (Optional)
- **Port:** 8080
- **Image:** provectuslabs/kafka-ui
- **Purpose:** Visual monitoring and debugging of Kafka topics
- **Features:**
  - View all topics and messages
  - Monitor consumer groups
  - Inspect topic partitions
  - Browse message history

---

## Container Architecture

```
┌─────────────────────────────────────────────────────┐
│                 Docker Network                      │
│            (review-network bridge)                  │
└─────────────────────────────────────────────────────┘
                      │
     ┌────────────────┼────────────────┐
     │                │                │
     ▼                ▼                ▼
┌──────────┐  ┌──────────────┐  ┌──────────────┐
│ Review   │  │   Kafka      │  │  Separation  │
│ Fetcher  │  │  Ecosystem   │  │   Service    │
│ (8084)   │  │  (9092)      │  │   (8085)     │
└──────────┘  └──────────────┘  └──────────────┘
                  │        │
                  ▼        ▼
             ┌────────────────┐
             │   Zookeeper    │
             │    (2181)      │
             └────────────────┘

Optional:
┌──────────────┐
│  Kafka UI    │
│  (8080)      │
└──────────────┘
```

---

## Startup Commands

### Development (All Services)
```bash
# Start all services including Kafka, Zookeeper, UI
docker compose up --build

# Or with profile flag
docker compose --profile dev up --build
```

**What starts:**
- Zookeeper (2181) - checks health
- Kafka (9092/9094) - waits for Zookeeper, checks health
- Kafka UI (8080) - optional monitoring
- Review Fetcher (8084) - waits for Kafka health check
- Separation Service (8085) - optional, waits for Kafka

**Expected output:**
```
zookeeper        | Created broker: host.docker.internal:9092
kafka            | [Broker] Successfully started
kafka-ui         | Listening on port 8080
review-fetcher   | Uvicorn running on http://0.0.0.0:8000
```

### Lightweight (No External Kafka/Zookeeper)
```bash
# Only review-fetcher with mock Kafka
docker compose --profile dev-lite up --build
```

Useful for testing without full infrastructure.

Notes:
- This mode uses the service's in-memory Kafka implementation (`MOCK_KAFKA=true`).
- Kafka UI won't be available, and there is no broker to inspect.

### Production
```bash
# Excludes UI and optional services
docker compose --profile prod up -d
```

---

## Port Mapping

| Service | Internal Port | Host Port | Protocol | Purpose |
|---------|---|---|---|---|
| Review Fetcher | 8000 | 8084 | HTTP | API endpoints |
| Kafka | 9092 | 9094 | TCP | Broker connections |
| Zookeeper | 2181 | 2181 | TCP | Coordination |
| Kafka UI | 8080 | 8080 | HTTP | Web dashboard |
| Separation Service | 5000 | 8085 | HTTP | Sentiment API |

---

## Environment Variables

### Review Fetcher Service

```env
# Logging
LOG_LEVEL=INFO                          # DEBUG, INFO, WARNING, ERROR
ENVIRONMENT=development                 # development, staging, production

# Feature Flags
MOCK_GOOGLE_API=true                    # true=fake data, false=real Google API

# Kafka (IMPORTANT: Use container name, not localhost)
KAFKA_BOOTSTRAP_SERVERS=kafka:9092      # "kafka" = container hostname
KAFKA_CONSUMER_GROUP=review-fetcher-service

# Rate Limiting
RATELIMIT_TOKEN_BUCKET_CAPACITY=100     # Max burst tokens
RATELIMIT_REFILL_RATE=10.0              # Tokens/second

# Retry Policy
RETRY_MAX_RETRIES=3                     # Max retry attempts
RETRY_INITIAL_BACKOFF_MS=100            # First wait time (ms)
RETRY_MAX_BACKOFF_MS=10000              # Max wait time (ms)
RETRY_BACKOFF_MULTIPLIER=2.0            # Exponential multiplier

# Queue Configuration
DEQUE_MAX_SIZE=10000                    # Max jobs in queue
DEQUE_BURST_CHECK_INTERVAL_SEC=0.1      # Check interval (seconds)

# API Server
API_HOST=0.0.0.0                        # Listen on all interfaces
API_PORT=8000                           # Internal port
API_WORKERS=4                           # Uvicorn workers
```

### Kafka Configuration

```env
KAFKA_BROKER_ID=1                       # Unique broker ID
KAFKA_ZOOKEEPER_CONNECT=zookeeper:2181  # Zookeeper coordination
KAFKA_ADVERTISED_LISTENERS=...          # Internal and external listeners
KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR=1
KAFKA_AUTO_CREATE_TOPICS_ENABLE=true    # Auto-create topics
KAFKA_LOG_RETENTION_HOURS=24            # Message retention period
```

---

## Health Checks

Each service has health checks that Docker monitors:

### Review Fetcher
```
Endpoint: GET /health
Command:  curl -f http://localhost:8000/health
Interval: 10 seconds
Timeout:  5 seconds
Retries:  3 before unhealthy
```

Response:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2025-01-07T12:34:56Z"
}
```

### Kafka
```
Command:  kafka-broker-api-versions.sh --bootstrap-server localhost:9092
Interval: 10 seconds
Checks:   Broker API is responding
```

### Zookeeper
```
Command:  echo stat | nc localhost 2181
Interval: 10 seconds
Checks:   Zookeeper is accepting connections
```

---

## How Services Communicate

### Review Fetcher → Kafka
```
1. Review Fetcher connects to: kafka:9092 (container network)
2. Publishes jobs to topics:
   - fetch-accounts
   - fetch-locations
   - fetch-reviews
3. Reads messages from Kafka topics as responses
```

### Kafka Internal
```
1. Kafka uses Zookeeper (zookeeper:2181) for:
   - Broker registration
   - Topic management
   - Leader election
2. Zookeeper persists state internally
```

### Separation Service → Kafka
```
1. Reads from: reviews-raw topic
2. Processes sentiment analysis
3. Writes to: reviews-sentiment topic
```

---

## Volumes & Persistence

### App Code Mount (Development)
```yaml
volumes:
  - ./app:/app/app
```
**Purpose:** Allows hot-reload during development
**Use Case:** Edit code locally, changes reflected in container immediately

### Kafka Data (Implicit)
```
Kafka stores messages internally in container
Data lost when container stops (dev mode)
Use named volumes for persistence in production
```

---

## Docker Compose Profiles

### Dev Profile
```bash
docker compose --profile dev up
```
Includes:
- Zookeeper
- Kafka
- Kafka UI
- Review Fetcher
- Separation Service (optional)

### Dev-Lite Profile
```bash
docker compose --profile dev-lite up
```
Includes:
- Only Review Fetcher
- Mock Kafka (no real broker)
- Faster startup, no dependencies

### Prod Profile
```bash
docker compose --profile prod up
```
Includes:
- Zookeeper
- Kafka
- Review Fetcher
- Excludes: Kafka UI, Separation Service
- No hot-reload volumes

---

## Networking

### Bridge Network: review-network
- All services connected via single bridge network
- Services communicate by container hostname
- Example: `kafka:9092` resolves to Kafka container IP

### Port Binding
```
Container Port 8000 → Host Port 8084
(Review Fetcher)
```

---

## Logs

### View All Logs
```bash
docker compose logs -f
```

### View Specific Service
```bash
docker compose logs -f review-fetcher
docker compose logs -f kafka
docker compose logs -f zookeeper
```

### Filter Logs
```bash
docker compose logs review-fetcher | grep ERROR
docker compose logs kafka | grep "Successfully"
```

---

## Stopping Services

```bash
# Graceful stop (gives services time to cleanup)
docker compose down

# Stop and remove volumes (WARNING: deletes data)
docker compose down -v

# Stop and remove everything (images, containers, volumes)
docker compose down --rmi all -v
```

---

## Troubleshooting

### Kafka not starting
```
Error: "zookeeper is unhealthy"
Solution: Zookeeper takes ~5-10s to start, wait longer or check:
  docker compose logs zookeeper
```

### Review Fetcher can't connect to Kafka
```
Error: "Cannot connect to kafka:9092"
Solution: Use container hostname "kafka", not "localhost"
  KAFKA_BOOTSTRAP_SERVERS=kafka:9092  ✅
  KAFKA_BOOTSTRAP_SERVERS=localhost:9092  ❌
```

### Port already in use
```
Error: "Port 8084 is already allocated"
Solution: Change port mapping in docker-compose.yml:
  ports:
    - "8084:8000"  # Change first number
```

### Services won't start with profiles
```
Error: "service not found"
Solution: Add profile to service definition:
  profiles:
    - dev
Then use: docker compose --profile dev up
```

---

## Next Steps

1. **Start services:**
   ```bash
   docker compose up --build
   ```

2. **Test health endpoints:**
   ```bash
   curl http://localhost:8084/health
   curl http://localhost:8080  # Kafka UI
   ```

3. **Submit a fetch job:**
   ```bash
   curl -X POST http://localhost:8084/api/v1/review-fetch \
     -H "Content-Type: application/json" \
     -d '{"access_token": "ya29.test", "account_id": "123"}'
   ```

4. **Monitor Kafka topics:**
   - Open http://localhost:8080 (Kafka UI)
   - View messages in `fetch-accounts`, `reviews-raw`, etc.

5. **For production:**
   - Update `MOCK_GOOGLE_API=false`
   - Update `KAFKA_BOOTSTRAP_SERVERS` to real Kafka brokers
   - Remove Kafka UI from docker-compose
   - Use persistent volumes for Kafka data
