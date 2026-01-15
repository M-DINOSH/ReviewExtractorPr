# Deployment & Operations Checklist

## Pre-Deployment

### Code & Configuration
- [ ] Clone repository
- [ ] Review `INTEGRATION_GUIDE.md`
- [ ] Check `docker-compose.yml` for your environment
- [ ] Set environment variables (`.env` file)
- [ ] Verify `MOCK_GOOGLE_API` setting (true for demo, false for production)

### Dependencies
- [ ] Docker installed (`docker --version`)
- [ ] Docker Compose installed (`docker-compose --version`)
- [ ] Ports 8084, 9092, 8080, 2181 are available
- [ ] Google OAuth2 credentials prepared (for real API mode)

---

## Deployment

### Local / Development

```bash
cd review-fetcher-service
docker compose up -d --build
docker compose ps
```

### Staging / Production (Docker)

```bash
# Set production environment
export MOCK_GOOGLE_API=false
export LOG_LEVEL=WARNING

# Pull latest
docker pull review-fetcher:latest

# Deploy
docker compose -f docker-compose.yml up -d
```

### Behind Reverse Proxy (Nginx Example)

```nginx
upstream review_fetcher {
    server localhost:8084;
}

server {
    listen 443 ssl http2;
    server_name api.reviews.yourdomain.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    location / {
        proxy_pass http://review_fetcher;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # SSE support
        proxy_buffering off;
        proxy_cache off;
        proxy_set_header Connection "";
        chunked_transfer_encoding on;
    }
}
```

---

## Post-Deployment Verification

### 1. Health Check
```bash
curl -s http://localhost:8084/api/v1/health | jq .
# Expected: status: "healthy", kafka_connected: true
```

### 2. API Documentation
Open in browser: `http://localhost:8084/docs`
- [ ] Swagger UI loads
- [ ] All endpoints visible

### 3. Web UI Test
Open in browser: `http://localhost:8084/api/v1/reviews-viewer`
- [ ] Page loads
- [ ] Can enter token
- [ ] Can start fetch
- [ ] Stats update in real-time

### 4. Kafka Health
```bash
# Check Kafka is running
docker compose ps | grep kafka

# View Kafka UI
open http://localhost:8080
```

### 5. API Test
```bash
# Create session
curl -X POST http://localhost:8084/api/v1/stream-session \
  -H "Content-Type: application/json" \
  -d '{"access_token":"test_token"}'

# Should return: { "session_id": "...", "expires_in_sec": 120 }
```

---

## Monitoring & Observability

### Logs
```bash
# View service logs
docker compose logs -f review-fetcher

# View Kafka logs
docker compose logs -f kafka

# Check specific error
docker compose logs review-fetcher | grep ERROR
```

### Metrics
```bash
# Health endpoint
curl http://localhost:8084/api/v1/health

# Response includes:
# - status
# - kafka_connected
# - memory_used_percent
# - service version
# - timestamp
```

### Kafka Debugging
- **Kafka UI**: `http://localhost:8080`
- **Topics to monitor**:
  - `fetch-accounts`
  - `fetch-locations`
  - `fetch-reviews`
  - `reviews-raw`

---

## Scaling & Performance

### For Small Scale (< 100 jobs/day)
- Single instance of `review-fetcher`
- Single Kafka broker
- In-memory buffer (10K jobs max)

### For Medium Scale (100-1000 jobs/day)
- 2-3 instances of `review-fetcher` behind load balancer
- Single Kafka broker with replication
- Monitor buffer size
- Add rate limiting at reverse proxy

### For Large Scale (> 1000 jobs/day)
- Horizontal scaling of `review-fetcher` instances
- Kafka cluster (3+ brokers)
- Message queue (Redis/RabbitMQ) for job buffering
- Separate Kafka consumers for processing
- Database persistence for job history

### Configuration Tuning
```bash
# Increase job capacity
BUFFER_MAX_SIZE=50000

# Rate limiting
GOOGLE_REQUESTS_PER_SECOND=20
RATELIMIT_CAPACITY=500

# Kafka batch size
KAFKA_BATCH_SIZE=100
```

---

## Backup & Recovery

### Backup Strategy
- **Code**: Git repository (already done)
- **Mock Data**: `jsom/` JSON files (checked in)
- **Configuration**: `.env` file (keep secure, don't commit)
- **Kafka Data**: ephemeral (recreate if needed)

### Recovery Steps
```bash
# Stop service
docker compose down

# Remove data
docker volume rm review-fetcher-service_kafka-data

# Restart
docker compose up -d
```

---

## Maintenance

### Regular Tasks
- [ ] **Daily**: Check health endpoint
- [ ] **Weekly**: Review logs for errors
- [ ] **Monthly**: Update Docker images
- [ ] **Quarterly**: Review and update dependencies

### Upgrade Path
```bash
# Check for updates
docker compose pull

# Restart with new images
docker compose restart

# Verify health
curl http://localhost:8084/api/v1/health
```

### Database Migrations (if added later)
```bash
# Coming soon: persistent storage for job history
# Will include migration guide
```

---

## Incident Response

### Service Down
1. Check logs: `docker compose logs review-fetcher | tail -50`
2. Check health: `curl http://localhost:8084/api/v1/health`
3. Restart: `docker compose restart review-fetcher`
4. Verify: `curl http://localhost:8084/api/v1/health`

### Kafka Connection Failed
1. Check Kafka: `docker compose ps | grep kafka`
2. Restart Kafka: `docker compose restart kafka`
3. Verify connection: Check logs for `kafka_connected`

### High Error Rate
1. Check logs for patterns
2. Verify Google API credentials
3. Check rate limits not exceeded
4. Review Kafka topics for stuck messages

### Memory Issues
```bash
# Check memory usage
curl http://localhost:8084/api/v1/health | jq .memory_used_percent

# If > 80%, restart service
docker compose restart review-fetcher
```

---

## Security Hardening

### Firewall Rules
```bash
# Allow only from trusted IPs
sudo ufw allow from 10.0.0.0/8 to any port 8084
```

### Credentials Management
```bash
# Store secrets in environment, not in code
export GOOGLE_API_KEY="..."
export KAFKA_PASSWORD="..."

# Use .env (never commit)
# Use secrets manager in production
```

### Audit & Compliance
- [ ] Log all token requests (anonymized)
- [ ] Monitor for suspicious activity
- [ ] Encrypt data in transit (HTTPS)
- [ ] Encrypt Kafka topics (optional)

---

## Rollback Plan

If issues occur after deployment:

```bash
# Rollback to previous version
docker compose down
git checkout previous-stable-commit
docker compose up -d --build
```

---

## Handoff Verification

Team lead should:
- [ ] Successfully start the service
- [ ] Access the web UI
- [ ] Run a test stream
- [ ] Understand the API
- [ ] Know how to troubleshoot
- [ ] Have access to documentation

**Sign-off Date**: _______________
**Team Lead**: _______________
**Notes**: 

---

*For detailed information, see INTEGRATION_GUIDE.md and README.md*
