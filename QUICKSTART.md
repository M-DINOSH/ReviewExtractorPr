# Quick Start Guide - Review Fetcher Service

## 5-Minute Setup

### 1. Install Dependencies
```bash
cd review-fetcher-service
pip install -r requirements.txt
```

### 2. Run Service
```bash
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Output:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete
```

### 3. Test API

**Create a fetch job:**
```bash
curl -X POST http://localhost:8000/api/v1/review-fetch \
  -H "Content-Type: application/json" \
  -d '{"access_token": "ya29.test_token_123"}'
```

Response:
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "queued",
  "message": "Job enqueued for processing"
}
```

**Check health:**
```bash
curl http://localhost:8000/api/v1/health
```

**Get metrics:**
```bash
curl http://localhost:8000/api/v1/metrics
```

## Architecture Quick Reference

```
Client HTTP Request
        ↓
   API Gateway
        ↓
   Deque Buffer (burst smoothing)
        ↓
   Producer Loop (rate-limited)
        ↓
Kafka Topics:
  - fetch-accounts → Account Worker → fetch-locations
  - fetch-locations → Location Worker → fetch-reviews
  - fetch-reviews → Review Worker → reviews-raw (output)
        ↓
   reviews-dlq (errors)
```

## Key Features

| Feature | How It Works |
|---------|---|
| **Rate Limiting** | Token Bucket (10 tokens/sec) |
| **Retry** | Exponential backoff via heapq priority queue |
| **Deduplication** | Set-based O(1) lookup |
| **Error Handling** | DLQ for unrecoverable errors |
| **Async** | 100% non-blocking with asyncio |
| **Scalability** | Bounded deque smooths bursts |

## Environment Variables

```bash
# Default (works as-is)
MOCK_GOOGLE_API=true           # Use simulated API
LOG_LEVEL=INFO
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
DEQUE_MAX_SIZE=10000
RATELIMIT_REFILL_RATE=10.0
RETRY_MAX_RETRIES=3
```

## Example Workflow

### 1. Submit Job
```python
import asyncio
import httpx

async def submit_job():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/api/v1/review-fetch",
            json={"access_token": "ya29.test123"}
        )
        data = response.json()
        print(f"Job ID: {data['job_id']}")
        print(f"Status: {data['status']}")
        return data['job_id']

asyncio.run(submit_job())
```

### 2. Monitor Progress
```python
async def check_status(job_id):
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"http://localhost:8000/api/v1/status/{job_id}"
        )
        print(response.json())

asyncio.run(check_status("550e8400-..."))
```

### 3. Check Metrics
```python
async def get_metrics():
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "http://localhost:8000/api/v1/metrics"
        )
        metrics = response.json()
        print(f"Queue size: {metrics['deque']['current_size']}")
        print(f"Queue max: {metrics['deque']['max_size']}")

asyncio.run(get_metrics())
```

## Debugging

### View Logs
```bash
# Real-time logs
tail -f logs.txt

# Filter by level
grep "ERROR" logs.txt
```

### Check Deque Status
```bash
curl http://localhost:8000/api/v1/metrics | python -m json.tool
```

### Full Health Check
```bash
curl http://localhost:8000/api/v1/health | python -m json.tool
```

## Docker Deployment

### Build
```bash
docker build -t review-fetcher:1.0.0 .
```

### Run
```bash
docker run -p 8000:8000 review-fetcher:1.0.0
```

### With Docker Compose
```bash
docker-compose up -d
```

## Performance Expectations

- **API Response Time:** <10ms (immediate)
- **Job Processing:** ~1-3 seconds (accounts + locations + reviews)
- **Throughput:** 1000+ jobs/sec with 10K deque
- **Memory:** ~100MB per process
- **Rate Limit:** 10 tokens/sec (adjustable)

## Troubleshooting

### Service won't start
```bash
# Check port in use
lsof -i :8000

# Check Python version
python3 --version  # Must be 3.11+

# Check imports
python3 -m py_compile app/main.py
```

### 429 Errors (Too Many Requests)
- Deque is full (increase `DEQUE_MAX_SIZE`)
- Rate limiter is active (increase `RATELIMIT_REFILL_RATE`)

### Jobs not processing
- Check health: `curl http://localhost:8000/api/v1/health`
- Check logs for worker errors
- Verify `MOCK_GOOGLE_API=true` is set

### High memory usage
- Clear old jobs from tracking: restart service
- Reduce `DEQUE_MAX_SIZE` if not needed
- Check for review worker memory: review deduplication cache

## Next Steps

1. **Local Testing**
   - Run 100 concurrent requests
   - Monitor metrics
   - Verify no errors in logs

2. **Integration Testing**
   - Connect real Kafka broker
   - Set `MOCK_GOOGLE_API=false`
   - Add real Google API credentials

3. **Production Deployment**
   - Configure TLS for Kafka
   - Set up monitoring (Prometheus, ELK)
   - Configure alerting (PagerDuty)
   - Deploy to Kubernetes

## Documentation

- **Full Docs:** See [README.md](review-fetcher-service/README.md)
- **Architecture:** See [ARCHITECTURE.md](ARCHITECTURE.md)
- **API Docs:** Visit `http://localhost:8000/docs` (SwaggerUI)

## Support

For issues or questions:
1. Check logs: `cat logs.txt`
2. Review metrics: `curl http://localhost:8000/api/v1/metrics`
3. Check health: `curl http://localhost:8000/api/v1/health`
4. Read documentation

---

**Happy fetching! 🚀**
