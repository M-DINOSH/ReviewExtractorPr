# Architecture Overview

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      Review Extraction System                   │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                     Review Fetcher Service                      │
│  (review-fetcher-service on port 8001)                         │
│                                                                  │
│  - Fetch reviews from Google Business Profile API              │
│  - Process and store reviews                                    │
│  - Kafka producer for streaming reviews                        │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         │ 1. Request valid token
                         │ 2. Use token for API calls
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                 Token Generation Service                        │
│        (token-generation-service on port 8002)                 │
│                                                                  │
│  Components:                                                    │
│  ├── OAuth Manager                                              │
│  │   ├── Authorization URL generation                          │
│  │   ├── Code exchange                                          │
│  │   └── Token refresh                                          │
│  │                                                              │
│  ├── Client Manager                                             │
│  │   ├── Register OAuth clients                                │
│  │   ├── Manage credentials                                    │
│  │   └── Update configurations                                 │
│  │                                                              │
│  ├── Branch Manager                                             │
│  │   ├── Track business locations                              │
│  │   ├── Link to Google accounts                               │
│  │   └── Associate email managers                              │
│  │                                                              │
│  └── Token Manager                                              │
│      ├── Store tokens securely                                 │
│      ├── Auto-refresh before expiry                            │
│      └── Validation & revocation                               │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    PostgreSQL Database                          │
│  (token-postgres on port 5433)                                 │
│                                                                  │
│  Tables:                                                        │
│  ├── clients (OAuth credentials)                               │
│  ├── branches (Business locations)                             │
│  ├── tokens (Access/Refresh tokens)                            │
│  └── oauth_states (OAuth security)                             │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         │ (uses Google API)
                         ▼
         ┌───────────────────────────────┐
         │  Google Business Profile API  │
         │  (OAuth + Reviews endpoint)   │
         └───────────────────────────────┘
```

## Service Dependencies

```
review-fetcher-service
    ↓ (calls)
token-generation-service
    ↓ (uses)
postgres
    ↓ (connects to)
google-api
```

## Data Flow Diagram

### OAuth Flow

```
1. User/Admin
    │
    ├──> POST /clients (register Google OAuth creds)
    │       │
    │       └──> token-service stores in DB
    │
    ├──> GET /oauth/login/{client_id}
    │       │
    │       └──> Redirect to Google consent screen
    │
    ├──> Google asks user to authorize
    │
    ├──> Google redirects to /auth/callback with code
    │       │
    │       └──> token-service exchanges code for tokens
    │           └──> Stores in PostgreSQL
    │
    └──> OAuth complete! Tokens ready to use
```

### Token Validation Flow

```
review-fetcher-service
    │
    ├──> GET /tokens/validate/{client_id}
    │
    token-service
    │
    ├──> Check if token exists
    │    │
    │    ├─ NO  → Return error (need OAuth)
    │    │
    │    └─ YES → Check if expiring soon (< 5 min)
    │        │
    │        ├─ NO  → Return existing token ✓
    │        │
    │        └─ YES → Call Google to refresh
    │            │
    │            ├─ SUCCESS → Update DB, return new token ✓
    │            │
    │            └─ FAILED  → Mark invalid, return error
    │
    └──> review-fetcher uses token for API calls
```

### Branch Tracking Flow

```
Business with multiple locations:
├── Account ID: accounts/123456
│   ├── Location NYC:
│   │   └── location/111
│   │       └── Branch: branch-nyc-001
│   │           └── Email: nyc@company.com
│   │
│   └── Location LA:
│       └── location/222
│           └── Branch: branch-la-001
│               └── Email: la@company.com
│
All share same OAuth client (client_id=1)
Each branch has unique branch_id for tracking
```

## Container Architecture

```
┌──────────────────────────────────────────┐
│         Docker Network: app-network       │
│                                           │
│  ┌────────────────────────────────────┐  │
│  │  token-generation-service          │  │
│  │  Port: 8002                        │  │
│  │  Image: token-generation-service   │  │
│  │                                    │  │
│  │  ├── FastAPI app                  │  │
│  │  ├── Uvicorn server               │  │
│  │  └── Connection pool to postgres  │  │
│  └────────────────┬───────────────────┘  │
│                   │ (TCP)                 │
│                   │ Port 5432             │
│  ┌────────────────▼───────────────────┐  │
│  │  postgres (token-postgres)         │  │
│  │  Port: 5433 (on host)              │  │
│  │  Port: 5432 (internal)             │  │
│  │                                    │  │
│  │  ├── token_service_db             │  │
│  │  ├── clients table                │  │
│  │  ├── branches table               │  │
│  │  ├── tokens table                 │  │
│  │  └── oauth_states table           │  │
│  └────────────────────────────────────┘  │
│                                           │
└──────────────────────────────────────────┘
```

## API Endpoint Organization

```
Token Generation Service
├── General
│   ├── GET /                (Root)
│   └── GET /health          (Health check)
│
├── Clients (5 endpoints)
│   ├── POST   /clients
│   ├── GET    /clients
│   ├── GET    /clients/{id}
│   ├── PATCH  /clients/{id}
│   └── DELETE /clients/{id}
│
├── Branches (6 endpoints)
│   ├── POST   /branches
│   ├── GET    /branches
│   ├── GET    /branches/{id}
│   ├── GET    /branches/by-branch-id/{branch_id}
│   ├── PATCH  /branches/{id}
│   └── DELETE /branches/{id}
│
├── OAuth (3 endpoints)
│   ├── GET    /oauth/start/{client_id}
│   ├── GET    /oauth/login/{client_id}
│   └── GET    /auth/callback
│
├── Tokens (4 endpoints)
│   ├── GET    /tokens/validate/{client_id}
│   ├── POST   /tokens/refresh
│   ├── GET    /tokens/client/{client_id}
│   └── DELETE /tokens/{client_id}
│
└── Documentation
    ├── GET    /docs           (Swagger UI)
    └── GET    /redoc          (ReDoc)
```

## Database Relationships

```
clients (1) ───────────┬─────────── (Many) branches
   │                   │
   │                   └─── branch_id (unique)
   │                   └─── branch_name
   │                   └─── account_id
   │                   └─── location_id
   │                   └─── email
   │
   └──────────────────┬─────────── (Many) tokens
                      │
                      └─── access_token
                      └─── refresh_token
                      └─── expires_at
                      └─── is_valid
                      
clients (1) ───────────┬─────────── (Many) oauth_states
                      │
                      └─── state (CSRF token)
                      └─── expires_at
                      └─── is_used
```

## Deployment Architecture (Docker Compose)

```
┌─────────────────────────────────────────────────────────┐
│            Docker Compose Network                       │
│                                                          │
│  ┌──────────────────────┐    ┌──────────────────────┐  │
│  │ token-service        │    │ postgres             │  │
│  │ - Port 8002:8002     │    │ - Port 5433:5432     │  │
│  │ - Healthcheck ✓      │    │ - Volume persistence │  │
│  │ - Auto restart       │    │ - Healthcheck ✓      │  │
│  │ - Depends on DB      │◄───│ - Data preserved     │  │
│  └──────────────────────┘    └──────────────────────┘  │
│                                                          │
│  On startup:                                            │
│  1. PostgreSQL starts                                  │
│  2. token-service waits for DB (depends_on)           │
│  3. Alembic migrations run                            │
│  4. Service starts listening on 8002                  │
└─────────────────────────────────────────────────────────┘
```

## Production Deployment Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    Load Balancer / Nginx                     │
│                     (Handles TLS, Caching)                   │
└──────────────────┬───────────────────────────────────────────┘
                   │
       ┌───────────┼───────────┐
       │           │           │
       ▼           ▼           ▼
   Instance 1  Instance 2  Instance 3
   Port 8002   Port 8002   Port 8002
   
   (All point to same PostgreSQL database)
   
       │           │           │
       └───────────┼───────────┘
                   │
       ┌───────────▼────────────┐
       │   PostgreSQL Database  │
       │   (External / RDS)     │
       │   Read Replicas        │
       │   Automated Backups    │
       └────────────────────────┘
```

## Security Layers

```
┌─────────────────────────────────────────┐
│        Incoming Request                 │
└──────────────────┬──────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────┐
│     TLS/HTTPS Layer (Production)        │
└──────────────────┬──────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────┐
│      Firewall / Rate Limiting           │
└──────────────────┬──────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────┐
│    CORS Validation                      │
└──────────────────┬──────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────┐
│   Request Validation (Pydantic)         │
└──────────────────┬──────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────┐
│   OAuth State Validation (CSRF)         │
└──────────────────┬──────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────┐
│   Token Expiry Validation               │
└──────────────────┬──────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────┐
│   Database Parameterized Queries        │
└──────────────────┬──────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────┐
│        Database with User Perms         │
└─────────────────────────────────────────┘
```

## Scaling Strategy

```
Vertical Scaling (More powerful server):
├── Increase DB pool size: DB_POOL_SIZE=50
├── Increase workers: WORKERS=8
└── Increase server resources (CPU, RAM)

Horizontal Scaling (More servers):
├── Multiple instances behind load balancer
├── All connecting to same PostgreSQL
├── Stateless design (no in-memory state)
├── Connection pooling handles concurrency
└── Easy to scale to N instances

Database Scaling:
├── Read replicas for query distribution
├── Master-slave replication
├── Connection pooling (10-50 connections)
└── Automated backups
```

## Monitoring Architecture

```
┌──────────────────────────────────────────┐
│      Token Generation Service            │
│                                           │
│  ├── Application Logs                   │
│  │   └── stdout → Container Logs        │
│  │                                       │
│  ├── Health Endpoint                    │
│  │   └── GET /health every 30s          │
│  │                                       │
│  └── Metrics (future)                   │
│      └── Prometheus compatible          │
└──────────────────┬──────────────────────┘
                   │
       ┌───────────┼───────────┐
       │           │           │
       ▼           ▼           ▼
   Docker Logs  Health      Metrics
   (ELK Stack)  Monitor    (Prometheus)
       │           │           │
       └───────────┼───────────┘
                   │
                   ▼
            ┌──────────────┐
            │   Alerts     │
            │   (PagerDuty)│
            └──────────────┘
```

---

This architecture provides:
- ✅ Scalability (horizontal and vertical)
- ✅ High availability (stateless design)
- ✅ Security (multiple validation layers)
- ✅ Monitoring (health checks, logs)
- ✅ Reliability (database persistence)
- ✅ Flexibility (Docker/Kubernetes ready)
