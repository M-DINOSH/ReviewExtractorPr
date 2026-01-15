# Review Fetcher Microservice - Team Integration Guide

**Version**: 1.0.0 | **Status**: Production-Ready | **Last Updated**: January 15, 2026

---

## 🚀 Quick Start (5 minutes)

### Prerequisites
- Docker & Docker Compose installed
- Google OAuth2 access token (for real API mode)
- Basic understanding of REST APIs and Kafka

### Start the Service

```bash
cd review-fetcher-service

# Start all services
docker compose up -d

# Verify health
curl http://localhost:8084/api/v1/health
```

**Expected Response:**
```json
{
  "status": "healthy",
  "kafka_connected": true,
  "service": "review-fetcher-service"
}
```

### Access the UI

Open in browser: **http://localhost:8084/api/v1/reviews-viewer**

---

## 📋 Integration Overview

This is a **Kafka-based event-driven microservice** that fetches Google Business Profile reviews. It exposes HTTP REST APIs for job submission and Server-Sent Events (SSE) for real-time streaming.

### What It Does
1. ✅ Accepts Google OAuth2 tokens via REST API
2. ✅ Fetches accounts, locations, and reviews from Google Business Profile API
3. ✅ Processes data through Kafka topic pipeline
4. ✅ Streams nested aggregated results in real-time (SSE)
5. ✅ Supports both mock data (demo) and real Google APIs (production)

### Key Ports
- **8084** - Review Fetcher API & Web UI
- **9092** - Kafka (container internal)
- **8080** - Kafka UI (for debugging)
- **2181** - Zookeeper

---

## 🔌 API Reference

### 1. Create Stream Session (Production-Safe)

**Endpoint**: `POST /api/v1/stream-session`

**Purpose**: Get a session ID before opening SSE stream (token never in URL)

```bash
curl -X POST http://localhost:8084/api/v1/stream-session \
  -H "Content-Type: application/json" \
  -d '{
    "access_token": "ya29.YOUR_GOOGLE_OAUTH_TOKEN"
  }'
```

**Response** (201 Created):
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "expires_in_sec": 120
}
```

---

### 2. Stream Reviews (Server-Sent Events)

**Endpoint**: `GET /api/v1/stream/nested`

**Purpose**: Real-time streaming of accounts → locations → reviews

```bash
# Using EventSource in JavaScript (recommended)
const evtSource = new EventSource(
  "http://localhost:8084/api/v1/stream/nested?session_id=550e8400-e29b-41d4-a716-446655440000"
);

evtSource.addEventListener('job', (event) => {
  const data = JSON.parse(event.data);
  console.log('Job started:', data.job_id);
});

evtSource.addEventListener('nested', (event) => {
  const data = JSON.parse(event.data);
  console.log('Accounts:', data.accounts.length);
  console.log('Locations:', data.stats.locations);
  console.log('Reviews:', data.stats.reviews);
});

evtSource.addEventListener('done', () => {
  console.log('Stream complete');
  evtSource.close();
});
```

**Event Types**:
- `job` - Job created (contains `job_id`)
- `nested` - Accounts/locations/reviews update
- `done` - Stream complete

**Response Format** (nested event):
```json
{
  "job_id": "abc-123-def",
  "accounts": [
    {
      "account": {
        "account_id": "1",
        "account_display_name": "Restaurant Group A"
      },
      "locations": [
        {
          "location_id": "202",
          "location_title": "Main Branch",
          "reviews": [
            {
              "reviewer_name": "John Doe",
              "rating": 5,
              "comment": "Great service!",
              "review_created_time": "2026-01-15T10:00:00Z"
            }
          ]
        }
      ]
    }
  ],
  "stats": {
    "accounts": 10,
    "locations": 45,
    "reviews": 320
  },
  "joins_ok": {
    "account.account_id == location.google_account_id": true,
    "location.location_id == review.location_id": true
  }
}
```

---

### 3. Health Check

**Endpoint**: `GET /api/v1/health`

```bash
curl http://localhost:8084/api/v1/health
```

**Response**:
```json
{
  "status": "healthy",
  "service": "review-fetcher-service",
  "version": "1.0.0",
  "kafka_connected": true,
  "memory_used_percent": 0.0,
  "timestamp": "2026-01-15T14:30:00Z"
}
```

---

### 4. Web UI (Production Viewer)

**URL**: `http://localhost:8084/api/v1/reviews-viewer`

**Features**:
- Beautiful card-based UI
- Real-time streaming updates
- Live stats dashboard
- Star ratings and review details
- No token in URL (production-safe)

---

## 🔧 Configuration

### Environment Variables

Create a `.env` file in `review-fetcher-service/`:

```bash
# Data Source
MOCK_GOOGLE_API=true              # false = use real Google API

# Kafka
KAFKA_BOOTSTRAP_SERVERS=localhost:9092

# Rate Limiting
GOOGLE_REQUESTS_PER_SECOND=10
RATELIMIT_CAPACITY=100
RATELIMIT_REFILL=10

# Buffer
BUFFER_MAX_SIZE=10000

# Logging
LOG_LEVEL=INFO                    # DEBUG | INFO | WARNING | ERROR

# API
API_HOST=0.0.0.0
API_PORT=8000
```

### Switch to Real Google API

```bash
# Set environment variable
export MOCK_GOOGLE_API=false

# Restart service
docker compose restart review-fetcher
```

---

## 📊 Integration Patterns

### Pattern 1: Browser-Based Streaming (Recommended)

```html
<!DOCTYPE html>
<html>
<head>
    <title>Reviews Viewer</title>
</head>
<body>
    <input type="text" id="token" placeholder="Enter Google OAuth token">
    <button onclick="startStream()">Start Streaming</button>
    <div id="stats"></div>
    <div id="reviews"></div>

    <script>
        async function startStream() {
            const token = document.getElementById('token').value;
            
            // Step 1: Get session
            const sessionResp = await fetch(
                'http://localhost:8084/api/v1/stream-session',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ access_token: token })
                }
            );
            const { session_id } = await sessionResp.json();
            
            // Step 2: Connect to SSE
            const evtSource = new EventSource(
                `http://localhost:8084/api/v1/stream/nested?session_id=${session_id}`
            );
            
            evtSource.addEventListener('nested', (event) => {
                const data = JSON.parse(event.data);
                document.getElementById('stats').textContent = 
                    `Accounts: ${data.stats.accounts} | ` +
                    `Locations: ${data.stats.locations} | ` +
                    `Reviews: ${data.stats.reviews}`;
                    
                // Render accounts and reviews...
            });
        }
    </script>
</body>
</html>
```

---

### Pattern 2: Backend Service Integration (Node.js)

```javascript
const axios = require('axios');

async function fetchReviews(googleToken) {
    const baseUrl = 'http://localhost:8084/api/v1';
    
    // Step 1: Create session
    const sessionRes = await axios.post(`${baseUrl}/stream-session`, {
        access_token: googleToken
    });
    const sessionId = sessionRes.data.session_id;
    
    // Step 2: Stream results
    return new Promise((resolve, reject) => {
        const eventSource = new EventSource(
            `${baseUrl}/stream/nested?session_id=${sessionId}`
        );
        
        const results = [];
        
        eventSource.addEventListener('nested', (event) => {
            const data = JSON.parse(event.data);
            results.push(data);
        });
        
        eventSource.addEventListener('done', () => {
            eventSource.close();
            resolve(results);
        });
        
        eventSource.onerror = reject;
    });
}

// Usage
fetchReviews('ya29.YOUR_TOKEN')
    .then(results => console.log('Fetched', results.length, 'snapshots'))
    .catch(err => console.error('Stream error:', err));
```

---

### Pattern 3: Python Backend

```python
import requests
import json
from sseclient import SSEClient

def fetch_reviews(google_token):
    base_url = 'http://localhost:8084/api/v1'
    
    # Step 1: Create session
    session_res = requests.post(
        f'{base_url}/stream-session',
        json={'access_token': google_token}
    )
    session_id = session_res.json()['session_id']
    
    # Step 2: Stream results
    stream_url = f'{base_url}/stream/nested?session_id={session_id}'
    client = SSEClient(stream_url)
    
    results = []
    for event in client:
        if event.event == 'nested':
            data = json.loads(event.data)
            results.append(data)
        elif event.event == 'done':
            break
    
    return results

# Usage
reviews = fetch_reviews('ya29.YOUR_TOKEN')
for snapshot in reviews:
    print(f"Accounts: {snapshot['stats']['accounts']}")
```

---

## ✅ Testing Checklist

- [ ] Service starts: `docker compose up -d`
- [ ] Health check passes: `curl http://localhost:8084/api/v1/health`
- [ ] Kafka is connected
- [ ] Web UI loads: `http://localhost:8084/api/v1/reviews-viewer`
- [ ] Can create session: `POST /api/v1/stream-session` returns `session_id`
- [ ] SSE stream works with demo token
- [ ] Reviews are nested correctly (account → location → review)
- [ ] `joins_ok` shows `true` for both joins
- [ ] Multiple requests produce different totals (if using mock/sampling)

---

## 🔒 Security Notes

### ✅ What We Do Right
- **Token Security**: OAuth tokens sent in POST body, never in URL
- **Session Isolation**: Each stream gets a unique `session_id` with TTL
- **No Sensitive Data in Logs**: Tokens are never logged
- **HTTPS Ready**: Runs behind any reverse proxy (nginx, Envoy, etc.)

### ⚠️ Recommendations
1. **Always use HTTPS** in production (reverse proxy with TLS)
2. **Rate limit by client IP** at the reverse proxy level
3. **Validate tokens** before passing to the service (optional, we validate too)
4. **Monitor Kafka topics** for sensitive data leaks
5. **Rotate Google API credentials** regularly
6. **Use environment variables** for secrets, not config files

---

## 🚨 Troubleshooting

### Issue: Kafka connection fails
```bash
# Check Kafka container
docker compose ps | grep kafka

# View Kafka logs
docker compose logs kafka
```

### Issue: No reviews in response
```bash
# Check if mock data is loaded
curl http://localhost:8084/api/v1/health

# Enable DEBUG logging
export LOG_LEVEL=DEBUG
docker compose restart review-fetcher
```

### Issue: SSE connection hangs
```bash
# Use shorter max_wait_sec
GET /api/v1/stream/nested?session_id=...&max_wait_sec=30
```

### Issue: Token validation fails
```bash
# Make sure token is valid for Google Business Profile API
# Test with mock mode first
export MOCK_GOOGLE_API=true
```

---

## 📞 Support & Documentation

### Key Documents
- **README.md** - Complete service overview
- **flow.md** - Message flow diagrams
- **run.md** - Deployment guide
- **md/DOCKER_GUIDE.md** - Container deployment
- **md/ARCHITECTURE_OVERVIEW.md** - System design

### API Documentation
- **Swagger UI**: `http://localhost:8084/docs`
- **ReDoc**: `http://localhost:8084/redoc`

### Kafka UI (Debugging)
- **URL**: `http://localhost:8080`
- **View**: Topics, messages, consumer groups

---

## 🎯 Next Steps for Your Team

1. **Read**: Start with `README.md` for overview
2. **Setup**: Run `docker compose up -d`
3. **Test**: Open `http://localhost:8084/api/v1/reviews-viewer`
4. **Integrate**: Choose integration pattern (browser/backend)
5. **Deploy**: Follow `run.md` for production deployment
6. **Monitor**: Use `/api/v1/health` endpoint for health checks

---

## 📋 Handoff Checklist

- [x] Service code is production-ready
- [x] All documentation is complete
- [x] Docker setup works
- [x] Web UI is functional
- [x] API endpoints are documented
- [x] Integration patterns provided
- [x] Security best practices documented
- [x] Troubleshooting guide included

**Status**: Ready for team integration! 🚀

---

*For questions or issues, refer to the README.md and flow.md in the project root.*
