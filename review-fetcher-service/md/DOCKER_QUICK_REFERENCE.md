# Docker Quick Reference - Review Fetcher Service

## What's Containerized

```
┌─────────────────────────────────────────────────┐
│        DOCKER COMPOSE SERVICES                   │
└─────────────────────────────────────────────────┘

INFRASTRUCTURE:
├─ zookeeper:2181 (CP ZK 7.5.0)
│  └─ Kafka coordination & leader election
│
├─ kafka:9092 (CP Kafka 7.5.0)
│  └─ Message broker
│  └─ Auto-creates topics
│  └─ 24hr retention
│
└─ kafka-ui:8080 (Provectus UI)
   └─ Web dashboard for monitoring

APPLICATIONS:
├─ review-fetcher:8084
│  └─ FastAPI service
│  └─ Health checks via /health
│  └─ Hot-reload volumes (dev)
│
└─ separation-service:8085 (optional)
   └─ Sentiment analysis
   └─ Reads from reviews-raw

NETWORK:
└─ review-network (bridge)
   └─ All containers connected
```

---

## Essential Commands

### Start Everything
```bash
docker compose up --build
```

### Start with Development Profile
```bash
docker compose --profile dev up --build
```

### Start Lightweight (No External Kafka)
```bash
docker compose --profile dev-lite up --build
```

Notes:
- This profile uses the service's in-memory Kafka implementation (`MOCK_KAFKA=true`).
- Kafka UI and broker ports will not be available in this mode.

### View Logs
```bash
docker compose logs -f                    # All services
docker compose logs -f review-fetcher     # Specific service
docker compose logs -f kafka | head -50   # First 50 lines
```

### Stop Services
```bash
docker compose down                       # Stop all
docker compose down -v                    # Stop + remove volumes
docker compose down --rmi all -v          # Remove everything
```

### Check Status
```bash
docker compose ps                         # List all containers
docker compose ps --services              # List service names
```

---

## Port Reference

| What | Port | URL |
|------|------|-----|
| Review Fetcher API | 8084 | http://localhost:8084 |
| Kafka Broker | 9094 | localhost:9094 |
| Zookeeper | 2181 | localhost:2181 |
| Kafka UI | 8080 | http://localhost:8080 |
| Separation Service | 8085 | http://localhost:8085 |

---

## Key Environment Variables

```env
# Review Fetcher
MOCK_GOOGLE_API=true/false                # Use fake or real API
MOCK_KAFKA=true/false                     # true=in-memory Kafka (no broker), false=real Kafka
KAFKA_BOOTSTRAP_SERVERS=kafka:9092        # Always "kafka", not localhost
LOG_LEVEL=INFO/DEBUG/WARNING/ERROR        # Logging verbosity

# Kafka
KAFKA_AUTO_CREATE_TOPICS_ENABLE=true      # Auto-create topics
KAFKA_LOG_RETENTION_HOURS=24              # Keep messages for 24h

# Rate Limiting
RATELIMIT_TOKEN_BUCKET_CAPACITY=100       # Burst tokens
RATELIMIT_REFILL_RATE=10.0                # Tokens/second

# Retry Policy
RETRY_MAX_RETRIES=3                       # Attempt 3 times
RETRY_INITIAL_BACKOFF_MS=100              # Start wait
RETRY_MAX_BACKOFF_MS=10000                # Max wait
```

---

## Kafka Topics (Auto-Created)

```
Input Topics (from Review Fetcher):
├─ fetch-accounts         ← Account jobs
├─ fetch-locations        ← Location jobs
└─ fetch-reviews          ← Review jobs

Output Topics:
├─ reviews-raw            ← Processed reviews
├─ reviews-sentiment      ← From separation-service
└─ reviews-dlq            ← Dead Letter Queue (failed jobs)
```

---

## Health Checks

```bash
# Review Fetcher
curl http://localhost:8084/health

# Kafka UI
curl http://localhost:8080

# Kafka Broker
docker compose exec kafka kafka-broker-api-versions.sh --bootstrap-server localhost:9092
```

---

## Troubleshooting

### "zookeeper is unhealthy"
→ Wait 10 seconds, Zookeeper takes time to start

### "Cannot connect to kafka:9092"
→ Use container hostname "kafka", not "localhost"

### "Port already in use"
→ Change port mapping: `"8084:8000"` → `"9084:8000"`

### "Service not found"
→ Services have profiles, use: `docker compose --profile dev up`

### "Hot-reload not working"
→ Check volumes are mounted: `./app:/app/app`

---

## Development Workflow

```bash
# 1. Start services
docker compose up --build

# 2. Edit code locally (changes auto-reload)
vim app/api.py

# 3. Test API
curl -X POST http://localhost:8084/api/v1/review-fetch \
  -H "Content-Type: application/json" \
  -d '{"access_token": "ya29.test", "account_id": "123"}'

# 4. Check Kafka UI
open http://localhost:8080

# 5. View logs
docker compose logs -f review-fetcher

# 6. Stop when done
docker compose down
```

---

## Production Checklist

- [ ] Set `MOCK_GOOGLE_API=false`
- [ ] Update `KAFKA_BOOTSTRAP_SERVERS` to real brokers
- [ ] Change `LOG_LEVEL` to WARNING
- [ ] Remove Kafka UI from compose
- [ ] Add persistent volumes for Kafka
- [ ] Enable SSL/TLS for Kafka
- [ ] Set resource limits (memory, CPU)
- [ ] Use external network (not bridge)
- [ ] Enable container restart policies
- [ ] Setup monitoring/alerting

---

## Network Details

**Container Hostnames (internal):**
- `zookeeper` → Zookeeper service
- `kafka` → Kafka service
- `review-fetcher` → Review Fetcher service
- `separation-service` → Separation service

**From host machine:**
- Use `localhost:9094` for Kafka (not 9092)
- Use `localhost:8084` for Review Fetcher

---

## File Locations

```
review-fetcher-service/
├── docker-compose.yml          ← Services definition
├── Dockerfile                  ← Build image
├── DOCKER_GUIDE.md            ← This detailed guide
├── README.md                  ← Service documentation
├── app/                       ← Application code
│   ├── main.py               ← FastAPI app
│   ├── api.py                ← HTTP endpoints
│   ├── kafka_producer.py     ← Kafka publishing
│   └── kafka_consumers/      ← Worker implementations
└── requirements.txt           ← Python dependencies
```

---

## See Also

- **DOCKER_GUIDE.md** - Detailed containerization guide
- **README.md** - Service documentation with API reference
- **CLEANUP.md** - What was removed/cleaned up
