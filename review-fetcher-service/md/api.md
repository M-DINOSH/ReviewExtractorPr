# Review Fetcher Service API Reference

Complete API documentation with curl examples for easy testing. This service fetches Google Business Profile reviews using OAuth tokens stored in the database.

## Base URLs
- **Service Root**: `http://localhost:8084`
- **Main API**: `http://localhost:8084/api/v1`
- **Token Management**: `http://localhost:8084/token-management`

---

## 🔄 Complete Workflow (Mock Mode)

### Step 1: Register OAuth Client & Get Token
### Step 2: Use Token to Fetch Reviews

---

## 📋 Review Fetcher API (`/api/v1`)

### 1. Health Check
**GET** `/api/v1/health`

Check if the service is running.

```bash
curl -X GET http://localhost:8084/api/v1/health
```

**Response (200 OK):**
```json
{
  "status": "healthy",
  "service": "review-fetcher-service",
  "version": "1.0.0",
  "kafka_connected": true,
  "memory_used_percent": 45.2,
  "timestamp": "2026-01-19T10:30:00Z"
}
```

---

### 2. Create Review Fetch Job
**POST** `/api/v1/review-fetch`

Start fetching reviews using an access token (from Token Management DB).

**Request Body:**
```json
{
  "access_token": "your-token-from-db"
}
```

**Curl Command:**
```bash
curl -X POST http://localhost:8084/api/v1/review-fetch \
  -H "Content-Type: application/json" \
  -d '{
    "access_token": "demo_token_12345"
  }'
```

**Response (202 Accepted):**
```json
{
  "job_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "queued",
  "message": "Job enqueued for processing"
}
```

---

### 3. Get Job Status
**GET** `/api/v1/status/{job_id}`

Check the progress of your review fetch job.

**Curl Command:**
```bash
curl -X GET http://localhost:8084/api/v1/status/a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

**Response (200 OK):**
```json
{
  "job_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "completed",
  "created_at": "2026-01-19T10:30:00Z",
  "accounts_fetched": 3,
  "locations_fetched": 25,
  "reviews_fetched": 487
}
```

---

### 4. Create Stream Session (Recommended for Production)
**POST** `/api/v1/stream-session`

Create a session to stream reviews without exposing token in URL.

**Request Body:**
```json
{
  "access_token": "your-token-from-db"
}
```

**Curl Command:**
```bash
curl -X POST http://localhost:8084/api/v1/stream-session \
  -H "Content-Type: application/json" \
  -d '{
    "access_token": "demo_token_12345"
  }'
```

**Response (201 Created):**
```json
{
  "session_id": "f9e8d7c6-b5a4-3210-9876-543210fedcba",
  "expires_in_sec": 120
}
```

---

### 5. Stream Reviews (SSE)
**GET** `/api/v1/stream/nested`

Stream reviews in real-time using Server-Sent Events.

**Using session_id (Recommended):**
```bash
curl -N http://localhost:8084/api/v1/stream/nested?session_id=f9e8d7c6-b5a4-3210-9876-543210fedcba
```

**Using job_id:**
```bash
curl -N http://localhost:8084/api/v1/stream/nested?job_id=a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

**With parameters:**
```bash
curl -N "http://localhost:8084/api/v1/stream/nested?session_id=f9e8d7c6-b5a4-3210-9876-543210fedcba&max_accounts=10&max_reviews_per_location=50"
```

**Query Parameters:**
- `session_id` or `job_id` (required, exactly one)
- `max_wait_sec` (default: 60, range: 5-600)
- `max_accounts` (default: 50, range: 1-500)
- `max_locations_total` (default: 2000, range: 1-10000)
- `max_reviews_per_location` (default: 200, range: 1-5000)
- `emit_interval_ms` (default: 250, range: 50-2000)
- `sample` (optional, defaults to true in mock mode)

**SSE Response Example:**
```
event: nested
data: {"accounts":[{"account_id":"123","account_name":"My Business","locations":[{"location_id":"456","location_name":"Main Store","reviews":[{"review_id":"789","rating":5,"text":"Great service!","reviewer_name":"John Doe"}]}]}],"stats":{"accounts":1,"locations":1,"reviews":1}}

event: nested
data: {"accounts":[...],"stats":{...}}

event: done
data: {}
```

---

### 6. Get Published Reviews (Mock Mode)
**GET** `/api/v1/reviews`

Get all reviews published to Kafka (mock mode only).

**Curl Command:**
```bash
curl -X GET "http://localhost:8084/api/v1/reviews?topic=reviews-raw"
```

**Response (200 OK):**
```json
{
  "topic": "reviews-raw",
  "total_reviews": 150,
  "reviews": [
    {
      "job_id": "abc123",
      "review_id": "review_001",
      "location_id": "456",
      "account_id": "123",
      "rating": 5,
      "text": "Excellent experience!",
      "reviewer_name": "Jane Smith",
      "created_at": "2026-01-19T10:30:00Z"
    }
  ],
  "timestamp": "2026-01-19T10:35:00Z"
}
```

---

### 7. Reviews Viewer Web UI
**GET** `/api/v1/reviews-viewer`

Open in browser: **http://localhost:8084/api/v1/reviews-viewer**

Beautiful web interface to view reviews with real-time updates.

---

### 8. Metrics
**GET** `/api/v1/metrics`

Get service operational metrics.

**Curl Command:**
```bash
curl -X GET http://localhost:8084/api/v1/metrics
```

**Response (200 OK):**
```json
{
  "deque": {
    "current_size": 15,
    "max_capacity": 10000,
    "total_pushed": 1250,
    "total_popped": 1235
  },
  "jobs_tracked": 42,
  "timestamp": "2026-01-19T10:35:00Z"
}
```

---

## 🔐 Token Management API (`/token-management`)

### 1. Register OAuth Client
**POST** `/token-management/clients`

Register a Google OAuth client with workspace details and store in database.

**Request Body:**
```json
{
  "client_id": "123456789-abcdefgh.apps.googleusercontent.com",
  "client_secret": "GOCSPX-your-secret-here",
  "redirect_uri": "http://localhost:8084/token-management/auth/callback",
  "branch_id": "branch-001",
  "workspace_email": "workspace@example.com",
  "workspace_name": "My Business Workspace"
}
```

**Curl Command:**
```bash
curl -X POST http://localhost:8084/token-management/clients \
  -H "Content-Type: application/json" \
  -d '{
    "client_id": "123456789-abcdefgh.apps.googleusercontent.com",
    "client_secret": "GOCSPX-your-secret-here",
    "redirect_uri": "http://localhost:8084/token-management/auth/callback",
    "branch_id": "branch-001",
    "workspace_email": "workspace@example.com",
    "workspace_name": "My Business Workspace"
  }'
```

**Response (201 Created):**
```json
{
  "success": true,
  "message": "Client registered successfully",
  "client_id": 1,
  "client_oauth_id": "123456789-abcdefgh.apps.googleusercontent.com",
  "branch_id": 1,
  "branch_identifier": "branch-001",
  "email": "workspace@example.com",
  "workspace_name": "My Business Workspace",
  "redirect_uri": "http://localhost:8084/token-management/auth/callback",
  "created_at": "2026-01-19T10:30:00Z"
}
```

---

### 2. Start OAuth Login Flow
**GET** `/token-management/oauth/login/{client_id}`

Redirects user to Google OAuth consent screen. After user authorizes, Google redirects back to callback URL with authorization code.

**Curl Command (or open in browser):**
```bash
# This will redirect to Google - use browser instead of curl
curl -L http://localhost:8084/token-management/oauth/login/1
```

**Browser URL:**
```
http://localhost:8084/token-management/oauth/login/1
```

**What happens:**
1. Redirects to Google OAuth consent screen
2. User authorizes access to Google Business Profile
3. Google redirects back to: `http://localhost:8084/token-management/auth/callback?code=...`

---

### 3. OAuth Callback (Automatic)
**GET** `/token-management/auth/callback`

This endpoint is called automatically by Google after user authorization. It exchanges the code for access/refresh tokens and stores them in database.

**Query Parameters (from Google):**
- `code`: Authorization code from Google
- `state`: Optional state parameter

**Response (200 OK):**
```json
{
  "success": true,
  "message": "Token stored successfully",
  "client_id": "123456789-abcdefgh.apps.googleusercontent.com",
  "branch_id": "branch-001",
  "access_token": "ya29.a0AfH6SMBx...",
  "expires_at": "2026-01-19T11:30:00Z"
}
```

**Note:** Access token is now stored in database and ready to use!

---

### 4. Get Token by Branch ID
**GET** `/token-management/tokens/{branch_id}`

Retrieve the stored access token for a branch. Auto-refreshes if expiring soon.

**Curl Command:**
```bash
curl -X GET http://localhost:8084/token-management/tokens/branch-001
```

**Response (200 OK):**
```json
{
  "success": true,
  "message": "Token retrieved successfully",
  "client_id": 1,
  "branch_id": "branch-001",
  "access_token": "ya29.a0AfH6SMBx...",
  "refresh_token": "1//0gHQ...",
  "expires_at": "2026-01-19T11:30:00Z",
  "token_type": "Bearer"
}
```

---

### 5. Refresh Access Token
**POST** `/token-management/tokens/refresh`

Manually refresh an expired access token using the stored refresh token.

**Request Body:**
```json
{
  "client_id": 1
}
```

**Curl Command:**
```bash
curl -X POST http://localhost:8084/token-management/tokens/refresh \
  -H "Content-Type: application/json" \
  -d '{
    "client_id": 1
  }'
```

**Response (200 OK):**
```json
{
  "success": true,
  "message": "Token refreshed successfully",
  "client_id": 1,
  "branch_id": "branch-001",
  "access_token": "ya29.a0AfH6SMBx_NEW_TOKEN...",
  "refresh_token": "1//0gHQ...",
  "expires_at": "2026-01-19T12:30:00Z",
  "token_type": "Bearer"
}

```

---

## 🎯 Complete End-to-End Testing Flow

### Scenario: Register Client → Get OAuth Token → Fetch Reviews (Mock Mode)

#### Step 1: Register OAuth Client
```bash
curl -X POST http://localhost:8084/token-management/clients \
  -H "Content-Type: application/json" \
  -d '{
    "client_id": "123456789-test.apps.googleusercontent.com",
    "client_secret": "GOCSPX-test-secret",
    "redirect_uri": "http://localhost:8084/token-management/auth/callback",
    "branch_id": "test-branch-001",
    "workspace_email": "test@example.com",
    "workspace_name": "Test Workspace"
  }'
```
**Note the `client_id` (internal ID, e.g., 1) from response**

---

#### Step 2: OAuth Login (Browser)
Open in browser:
```
http://localhost:8084/token-management/oauth/login/1
```
- Authorize with Google
- Gets redirected to callback
- **Token is now stored in database!**

---

#### Step 3: Get Stored Token
```bash
curl -X GET http://localhost:8084/token-management/tokens/test-branch-001
```
**Save the `access_token` from response**

---

#### Step 4: Fetch Reviews Using Stored Token

**Option A: Direct Job Creation**
```bash
curl -X POST http://localhost:8084/api/v1/review-fetch \
  -H "Content-Type: application/json" \
  -d '{
    "access_token": "ya29.a0AfH6SMBx..."
  }'
```
**Note the `job_id` from response**

---

#### Step 5: Check Job Status
```bash
curl -X GET http://localhost:8084/api/v1/status/a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

---

#### Step 6: Get Reviews
```bash
curl -X GET http://localhost:8084/api/v1/reviews
```

---

**Option B: Stream Reviews in Real-Time**

Step 4B: Create Stream Session
```bash
curl -X POST http://localhost:8084/api/v1/stream-session \
  -H "Content-Type: application/json" \
  -d '{
    "access_token": "ya29.a0AfH6SMBx..."
  }'
```
**Note the `session_id` from response**

Step 5B: Stream Reviews
```bash
curl -N http://localhost:8084/api/v1/stream/nested?session_id=f9e8d7c6-b5a4-3210-9876-543210fedcba
```

---

## 📝 Quick Test Commands (Mock Mode)

### Test with demo token (no OAuth needed):
```bash
# 1. Create session
SESSION_RESPONSE=$(curl -s -X POST http://localhost:8084/api/v1/stream-session \
  -H "Content-Type: application/json" \
  -d '{"access_token": "demo_token_12345"}')

SESSION_ID=$(echo $SESSION_RESPONSE | grep -o '"session_id":"[^"]*"' | cut -d'"' -f4)

# 2. Stream reviews
curl -N "http://localhost:8084/api/v1/stream/nested?session_id=$SESSION_ID"
```

### Simple fetch job:
```bash
# Create job
JOB_RESPONSE=$(curl -s -X POST http://localhost:8084/api/v1/review-fetch \
  -H "Content-Type: application/json" \
  -d '{"access_token": "demo_token_12345"}')

JOB_ID=$(echo $JOB_RESPONSE | grep -o '"job_id":"[^"]*"' | cut -d'"' -f4)

# Wait a bit
sleep 3

# Check status
curl -X GET "http://localhost:8084/api/v1/status/$JOB_ID"

# Get all reviews
curl -X GET http://localhost:8084/api/v1/reviews
```

---

## 🌐 Demo Endpoints (Development/Testing)

### Demo HTML Page
```bash
# Open in browser
open http://localhost:8084/demo
```

### Static Mock Data
```bash
# Get demo accounts
curl -X GET http://localhost:8084/api/v1/demo/accounts?limit=10

# Get demo locations
curl -X GET "http://localhost:8084/api/v1/demo/locations?limit=25&google_account_id=1"

# Get demo reviews
curl -X GET "http://localhost:8084/api/v1/demo/reviews?limit=50&location_id=1"
```

### Demo Nested Output (POST)
```bash
curl -X POST http://localhost:8084/api/v1/demo/nested \
  -H "Content-Type: application/json" \
  -d '{
    "access_token": "demo_token",
    "max_wait_sec": 30,
    "max_locations": 10,
    "max_reviews_per_location": 25
  }'
```

### Demo Streams (SSE)
```bash
# Stream accounts
curl -N "http://localhost:8084/api/v1/demo/stream/accounts?max_items=10"

# Stream locations
curl -N "http://localhost:8084/api/v1/demo/stream/locations?max_items=25"

# Stream reviews
curl -N "http://localhost:8084/api/v1/demo/stream/reviews?max_items=50"

# Stream nested (accounts → locations → reviews)
curl -N "http://localhost:8084/api/v1/demo/stream/nested?max_locations=10&max_reviews_per_location=25"
```

---

## 🔧 Environment Configuration

### Mock Mode (Default)
```bash
export MOCK_GOOGLE_API=true
```
- Uses mock data from `jsom/` folder
- Any token passes validation
- No real Google API calls

### Real Google API Mode
```bash
export MOCK_GOOGLE_API=false
```
- Makes real calls to Google Business Profile API
- Requires valid OAuth tokens
- Rate limited by Google

---

## ⚠️ Important Notes

1. **Authentication in Mock Mode**: Any non-empty token is accepted (e.g., `"demo_token_12345"`)

2. **Token Storage Flow**:
   - Register client → OAuth login → Token stored in DB → Use token to fetch reviews

3. **Streaming vs Polling**:
   - Streaming (`/stream/nested`): Real-time SSE updates
   - Polling (`/status/{job_id}` + `/reviews`): Check periodically

4. **Session Security**: Use `session_id` flow to avoid exposing tokens in URLs

5. **Rate Limits** (Real Mode):
   - Google Business Profile API: 1000 requests/day, 10/second
   - Service enforces token bucket rate limiting

6. **SSE Curl Note**: Use `-N` flag with curl for Server-Sent Events to disable buffering

---
