# Project Structure & Architecture  
## Google Business Profile Reviews Integration (FastAPI SaaS)

This document explains the **project structure**, **technology choices**, **file responsibilities**, and the **end-to-end OAuth → API workflow** used to integrate Google Business Profile (GBP) Reviews into a SaaS backend.

---

## 📁 Project Structure

app/
├── main.py
├── oauth.py
├── config.py
├── gbp_api.py # (or google_gbp.py / google_gpb.py)
├── database.py
├── models.py
.env
requirements.txt

yaml
Copy code

This structure cleanly separates **configuration**, **OAuth**, **API logic**, and **data persistence**, which is essential for scaling from PoC → production SaaS.

---

## 🧰 Tech Stack Overview (Why These Choices)

### 1️⃣ FastAPI (Backend Framework)

**Why FastAPI?**

You need a backend server that can:

- Expose HTTP endpoints (`/login`, `/accounts`, etc.)
- Receive Google’s OAuth callback (`/auth/callback`)
- Call Google APIs securely from the backend
- Scale horizontally for SaaS workloads

**FastAPI advantages:**
- Async-first (perfect with `httpx`)
- High performance
- Clean routing and dependency injection
- Production-ready

---

### 2️⃣ Authlib (OAuth Client Library)

**Why Authlib?**

OAuth is complex and security-sensitive. Authlib handles:

- Building Google OAuth redirect URLs
- CSRF protection (`state` validation)
- Exchanging authorization code → tokens
- Safely parsing token responses

Without Authlib, OAuth logic becomes error-prone and insecure.

---

### 3️⃣ Starlette `SessionMiddleware` (Cookie-Based Session)

**Why sessions are needed?**

OAuth requires maintaining state between:

1. Redirect to Google (`/login`)
2. Callback from Google (`/auth/callback`)

`SessionMiddleware` stores a secure session cookie in the browser so the backend can correlate requests.

⚠️ **PoC:** Storing tokens in session is acceptable  
✅ **Production SaaS:** Tokens must be stored in DB per client

---

### 4️⃣ httpx (Async HTTP Client)

**Why httpx?**

You must call Google’s REST APIs from Python.

Advantages:
- Async support (`AsyncClient`)
- Clean and modern API
- Excellent compatibility with FastAPI

---

### 5️⃣ SQLAlchemy + SQLite (Data Persistence)

**Why a database is required for SaaS?**

You eventually need to store:

- SaaS clients
- OAuth refresh tokens
- Business locations
- Reviews (optional cache)

**SQLite** is enough for PoC.  
**PostgreSQL** can replace it later without architecture changes.

---

## 📄 File-by-File Explanation

---

## ✅ `config.py`

### Responsibility
Centralized configuration and environment variable loading.

### Why This File Exists
- Secrets should never be hard-coded
- All OAuth-related config must live in one place
- Easier debugging and maintenance

### What It Does
- Loads `.env`
- Exposes constants such as:
  - `GOOGLE_CLIENT_ID`
  - `GOOGLE_CLIENT_SECRET`
  - `GOOGLE_REDIRECT_URI`
  - `GOOGLE_OAUTH_SCOPE`

### What Breaks If This Is Wrong
- `redirect_uri_mismatch`
- OAuth flow fails to start
- Token exchange fails

---

## ✅ `oauth.py`

### Responsibility
Defines and registers the **Google OAuth client**.

### Why This File Exists
- OAuth configuration should not be scattered across routes
- Enables reuse of a single `oauth.google` client

### What It Does
- Registers Google OAuth provider using:
  - `client_id`
  - `client_secret`
  - Google OAuth metadata (`server_metadata_url`)
  - Required scopes (`business.manage`)

### Key Concept
This file represents **“Google OAuth connection settings”**.

### Common Mistakes
- Missing required scopes
- Wrong redirect URI passed during login
- Not using `server_metadata_url`

---

## ✅ `main.py`

### Responsibility
Application entry point — routes and orchestration.
All HTTP requests enter through this file.

---

### `/login`

**Purpose**
- Starts OAuth flow
- Redirects user to Google consent screen

**Why It Exists**
- OAuth must happen in a browser
- User must explicitly grant permission

⚠️ OAuth cannot be tested with `curl` (cookies + redirects required).

---

### `/auth/callback`

**Purpose**
- Receives `?code=` and `?state=` from Google
- Authlib exchanges authorization code → tokens
- Token is stored in session (PoC)

**Why It Exists**
This is the **OAuth handshake completion point**.

---

### `/accounts`

**Purpose**
- Reads OAuth token from session
- Calls:
GET https://mybusinessaccountmanagement.googleapis.com/v1/accounts

yaml
Copy code

**Why**
- A user may control multiple business accounts

---

### `/locations/{account_name}`

**Purpose**
- Uses account name like `accounts/123`
- Calls:
GET https://mybusinessbusinessinformation.googleapis.com/v1/accounts/123/locations

yaml
Copy code

**Why**
- Businesses can have multiple locations/stores

---

### `/reviews/{location_name}`

**Purpose**
- Uses location name like `accounts/123/locations/456`
- Calls:
GET https://mybusiness.googleapis.com/v1/accounts/123/locations/456/reviews

markdown
Copy code

**Why**
- Reviews live under **locations**, not accounts

---

### Common Failures in `main.py`
- Redirect URI mismatch
- Missing session (calling APIs before login)
- Zero quota (Google approval pending)
- Wrong Reviews API version (`v1` vs `v4`)

---

## ✅ `gbp_api.py`  
*(or `google_gbp.py` / `google_gpb.py`)*

### Responsibility
Google Business Profile API client wrapper.

### Why This File Exists
- Keeps API logic separate from routes
- Improves readability and testability
- Enables reuse in background jobs

### What It Does
- Builds Authorization headers
- Contains helper functions:
- `get_accounts(token)`
- `get_locations(token, account_name)`
- `get_reviews(token, location_name)`

### Why This Matters for SaaS
Later reused by:
- Background sync workers
- Cron jobs
- Review polling services

---

## ✅ `database.py`

### Responsibility
Database connection and session factory.

### Why This File Exists
- Centralizes DB setup
- Avoids engine duplication
- Standardizes DB access

### What It Does
- Creates SQLAlchemy engine
- Defines `SessionLocal`
- Declares `Base` for models

---

## ✅ `models.py`

### Responsibility
Database schema for SaaS scalability.

### Why This File Exists
Session-based token storage does **not scale**.

### Tables Typically Defined
- `Client`
- SaaS customers
- `GoogleOAuthAccount`
- Refresh tokens per client
- `GoogleLocation`
- Locations linked to clients
- *(Optional)* `GoogleReview`
- Cached reviews

### What This Enables
- Multi-tenant support
- Background syncing
- Recovery after server restarts
- Auditability and compliance

---

## 🔗 How All Files Work Together (One Line Each)

- `config.py` → loads secrets & config
- `oauth.py` → prepares Google OAuth client
- `main.py` → routes + OAuth flow
- `gbp_api.py` → calls Google APIs
- `database.py` → DB connection
- `models.py` → SaaS data schema

---

## 🔄 End-to-End Workflow (Code Perspective)

1. User hits `/login`
2. `main.py` calls `oauth.google.authorize_redirect`
3. Google redirects to `/auth/callback`
4. `oauth.py` exchanges code → token
5. Token stored in session (PoC)
6. `/accounts` calls Google Account API
7. User selects account → `/locations/{account}`
8. User selects location → `/reviews/{location}`

---

## ✅ Final Takeaway

This structure is:

- Clean
- Secure
- OAuth-compliant
- Production-scalable

It supports:
- PoC experimentation
- Multi-tenant SaaS growth
- Migration from session-based auth → DB-backed auth

This is **exactly how professional Google-integrated SaaS backends are built**.