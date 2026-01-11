# Docker Containerization Summary - Review Fetcher Service

## ✅ What's Been Dockerized

### 1. **Core Application Service**
- **Review Fetcher** (FastAPI)
  - Containerized with Python 3.11
  - Exposes HTTP API on port 8084
  - Includes health checks
  - Auto-reload volumes for development
  - Depends on Kafka being healthy before starting

### 2. **Message Infrastructure (Kafka Ecosystem)**
- **Zookeeper 7.5.0** (Coordination)
  - Port: 2181
  - Health checked before Kafka starts
  - Manages broker coordination and leadership

- **Kafka 7.5.0** (Message Broker)
  - Ports: 9092 (internal), 9094 (external)
  - Auto-creates topics on startup
  - Health checked via broker API
  - Waits for Zookeeper to be healthy
  - Auto-deletes messages after 24 hours
  - Topics auto-created:
    - `fetch-accounts` - Account fetch jobs
    - `fetch-locations` - Location fetch jobs
    - `fetch-reviews` - Review fetch jobs
    - `reviews-raw` - Processed reviews output
    - `reviews-dlq` - Dead Letter Queue for failures
    - `reviews-sentiment` - Sentiment analysis (optional)

- **Kafka UI (Monitoring)**
  - Port: 8080
  - Visual dashboard for monitoring topics and messages
  - Optional (can be disabled in production)

### 3. **Optional: Separation Service**
- **Sentiment Analysis Service**
  - Port: 8085
  - Reads from `reviews-raw` topic
  - Writes to `reviews-sentiment` topic
  - Optional for production

### 4. **Networking**
- **Bridge Network: review-network**
  - All containers connected on same network
  - Container-to-container communication by hostname
  - Example: Review Fetcher connects to `kafka:9092`

---

## 📋 Service Breakdown

| Service | Image | Port | Purpose | Dependencies |
|---------|-------|------|---------|--------------|
| **Zookeeper** | confluentinc/cp-zookeeper:7.5.0 | 2181 | Kafka coordination | None |
| **Kafka** | confluentinc/cp-kafka:7.5.0 | 9092/9094 | Message streaming | Zookeeper ✓ |
| **Kafka UI** | provectuslabs/kafka-ui | 8080 | Monitoring dashboard | Kafka ✓ |
| **Review Fetcher** | review-fetcher:local (built) | 8084 | Main API service | Kafka ✓ |
| **Separation Service** | separation-service:local (built) | 8085 | Sentiment analysis | Kafka ✓ |

---

## 🚀 Startup Sequence

```
START docker compose up
   │
   ├─→ Zookeeper starts (port 2181)
   │   └─ Waits for health check (10s)
   │
   ├─→ Kafka starts (port 9092/9094)
   │   ├─ Connects to Zookeeper
   │   ├─ Creates topics automatically
   │   └─ Waits for health check (10s)
   │
   ├─→ Kafka UI starts (port 8080)
   │   └─ Connects to Kafka
   │
   ├─→ Review Fetcher starts (port 8084)
   │   ├─ Waits for Kafka health check
   │   ├─ Mounts app code for hot-reload
   │   └─ Starts uvicorn server
   │
   └─→ Separation Service starts (port 8085)
       └─ Waits for Kafka health check
```

---

## 🔄 Data Flow in Containers

```
1. CLIENT submits fetch request
   ↓
2. REVIEW-FETCHER service
   - Validates token
   - Queues job in memory
   - Publishes to: fetch-accounts topic
   ↓
3. KAFKA stores message in topic
   ↓
4. WORKERS (in review-fetcher)
   - Account Worker reads fetch-accounts
   - Publishes to: fetch-locations
   - Location Worker reads fetch-locations
   - Publishes to: fetch-reviews
   - Review Worker reads fetch-reviews
   - Publishes to: reviews-raw
   ↓
5. SEPARATION-SERVICE (optional)
   - Reads reviews-raw
   - Analyzes sentiment
   - Publishes to: reviews-sentiment
   ↓
6. KAFKA-UI displays all topics and messages
```

---

## 💾 Volumes & Persistence

### Development Setup
```yaml
volumes:
  - ./app:/app/app          # Hot-reload code changes
```
**Effect:** Edit Python files locally → auto-reload in container

### Production Setup
```yaml
# (No code volumes)
# Add named volumes for Kafka persistence:
volumes:
  kafka-data:
    driver: local
```

---

## 📦 Environment Configuration

### Development (MOCK MODE)
```env
MOCK_GOOGLE_API=true                    # Fake reviews
KAFKA_BOOTSTRAP_SERVERS=kafka:9092      # Docker network
LOG_LEVEL=INFO                          # Verbose logging
```

### Production (REAL MODE)
```env
MOCK_GOOGLE_API=false                   # Real Google API
KAFKA_BOOTSTRAP_SERVERS=kafka-prod:9092 # Real Kafka cluster
LOG_LEVEL=WARNING                       # Less logging
```

---

## 🔧 Key Configuration Files

### docker-compose.yml (159 lines)
- Defines 5 services
- Health checks for each service
- Dependency ordering
- Port mappings
- Environment variables
- Volume mounts
- Network configuration
- Profiles for different scenarios

### Dockerfile
- Python 3.11-slim base
- Sets PYTHONPATH=/app
- Installs dependencies
- Exposes port 8000
- Runs uvicorn

---

## 🎯 Usage Scenarios

### Development (All Services)
```bash
docker compose up --build
# Starts: Zookeeper, Kafka, Kafka-UI, Review-Fetcher, Separation-Service
# Use: Testing, development, local debugging
```

### Development Lightweight
```bash
docker compose --profile dev-lite up
# Starts: Only Review-Fetcher with mock Kafka
# Use: Quick testing without infrastructure
```

### Production
```bash
docker compose --profile prod up -d
# Starts: Zookeeper, Kafka, Review-Fetcher (no UI, no separation)
# Use: Deployment to servers
```

---

## 🔗 Key Networking Points

### Container-to-Container (Internal)
```
review-fetcher → kafka:9092      ✓
review-fetcher → zookeeper:2181  ✓
separation-service → kafka:9092  ✓
kafka → zookeeper:2181           ✓
```

### Host-to-Container (External)
```
localhost:8084 → review-fetcher:8000
localhost:9094 → kafka:9092
localhost:8080 → kafka-ui:8080
localhost:2181 → zookeeper:2181
```

**Important:** From containers, use `kafka:9092` not `localhost:9092`

---

## 📊 Ports Summary

| Port | Service | Access | Protocol |
|------|---------|--------|----------|
| 2181 | Zookeeper | localhost:2181 | TCP |
| 9092 | Kafka (internal) | kafka:9092 | TCP |
| 9094 | Kafka (external) | localhost:9094 | TCP |
| 8080 | Kafka UI | http://localhost:8080 | HTTP |
| 8084 | Review Fetcher | http://localhost:8084 | HTTP |
| 8085 | Separation Service | http://localhost:8085 | HTTP |

---

## ✅ Health Checks

```
Service              Check Method                          Interval  Timeout
─────────────────────────────────────────────────────────────────────────
Zookeeper            echo stat | nc localhost 2181         10s       5s
Kafka                kafka-broker-api-versions.sh          10s       5s
Review Fetcher       curl /health endpoint                 10s       5s
Separation Service   curl /health endpoint                 10s       5s
Kafka UI             (no health check)                     -         -
```

---

## 🚦 Dependency Graph

```
START
  │
  ├─ Zookeeper (no deps)
  │
  ├─ Kafka (depends on Zookeeper ✓)
  │
  ├─ Kafka-UI (depends on Kafka ✓)
  │
  ├─ Review-Fetcher (depends on Kafka ✓)
  │
  └─ Separation-Service (depends on Kafka ✓)
```

All services wait for their dependencies to be "healthy" before starting.

---

## 📝 Documentation Files Created

1. **DOCKER_GUIDE.md** (433 lines)
   - Comprehensive containerization guide
   - Architecture diagrams
   - Environment variable explanations
   - Troubleshooting guide
   - Production best practices

2. **DOCKER_QUICK_REFERENCE.md** (241 lines)
   - Quick command reference
   - Port mapping cheat sheet
   - Essential environment variables
   - Common troubleshooting
   - Development workflow

3. **docker-compose.yml** (159 lines)
   - Fully configured multi-service setup
   - Health checks for all services
   - Proper dependency ordering
   - Environment variables
   - Profiles for dev/prod

---

## 🎓 Getting Started

### Start All Services
```bash
cd review-fetcher-service
docker compose up --build
```

### Test Service Health
```bash
# Review Fetcher
curl http://localhost:8084/health

# Kafka UI
open http://localhost:8080
```

### Submit a Job
```bash
curl -X POST http://localhost:8084/api/v1/review-fetch \
  -H "Content-Type: application/json" \
  -d '{
    "access_token": "ya29.test_token",
    "account_id": "123456"
  }'
```

### Monitor Kafka
```
1. Open http://localhost:8080 (Kafka UI)
2. View topics: fetch-accounts, fetch-locations, fetch-reviews, reviews-raw
3. Monitor messages in real-time
4. Check consumer groups
```

### Stop Services
```bash
docker compose down              # Stop and remove
docker compose down -v           # Also remove volumes
```

---

## 📚 Related Documentation

- **README.md** - Service API and features
- **DOCKER_GUIDE.md** - Detailed containerization guide
- **DOCKER_QUICK_REFERENCE.md** - Quick reference card
- **CLEANUP.md** - What was cleaned up
