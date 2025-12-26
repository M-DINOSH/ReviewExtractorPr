# Architecture Structure  
## Google Business Profile Reviews Integration (SaaS)

This section describes the **complete SaaS architecture** for integrating Google Business Profile (GBP) Reviews, covering **high-level design**, **OAuth models**, **internal microservices**, **data flow**, and **scalability rationale**.

---

## 1️⃣ High-Level SaaS Architecture (Common for Both Models)

This is the **base architecture** and **never changes**, regardless of OAuth strategy.
┌──────────────────────┐
│   Client (Browser)   │
│  (Business Owner)    │
└──────────┬───────────┘
           │
           │ HTTPS
           ▼
┌────────────────────────────┐
│      SaaS Backend           │
│  (FastAPI Microservice)    │
│                            │
│  - OAuth Flow              │
│  - Token Management        │
│  - Client Isolation        │
│  - API Orchestration       │
└──────────┬─────────────────┘
           │
           │ OAuth / API Calls
           ▼
┌────────────────────────────┐
│ Google Business Profile     │
│ APIs (Google Cloud)         │
│                            │
│ - Accounts API              │
│ - Locations API             │
│ - Reviews API               │
└────────────────────────────┘


### Core Principle

- SaaS backend is the **single integration point**
- Clients never interact with Google APIs directly
- OAuth tokens and permissions are always backend-controlled

---

## 2️⃣ Centralized OAuth Architecture (Ideal, but Quota-Gated)

### 🔹 Concept

- One **Google Cloud Project**
- One **OAuth App**
- All clients authenticate using the **same Client ID & Secret**
- Tokens are stored **per client**
- Quota is **shared across all clients**

---

### 🔹 Architecture Diagram

                 ┌──────────────────────────┐
                 │ Google Cloud Project      │
                 │ (Owned by SaaS)           │
                 │                          │
                 │ - OAuth App              │
                 │ - GBP APIs               │
                 │ - Centralized Quota      │
                 └──────────┬───────────────┘
                            │
        OAuth Consent        │
                            │
┌──────────────┐    ┌────────▼────────┐    ┌──────────────┐
│ Client A     │───▶│                  │◀───│ Client B     │
│ (Business)   │    │   SaaS Backend   │    │ (Business)   │
└──────────────┘    │                  │    └──────────────┘
                     │ - Tokens per client
                     │ - Account isolation
                     │ - Review sync
                     └────────┬────────┘
                              │
                              ▼
                   Google Business Profile APIs

---

### 🔹 Characteristics

- Best possible user experience
- One-click onboarding
- No technical setup for clients
- Centralized quota shared by all customers

---

### 🔹 Why Google Often Rejects This Initially

- New SaaS product
- No production traffic history
- No proven data handling practices
- Google enforces strict internal trust checks

📌 Centralized OAuth usually requires **manual quota approval** from Google.

---

## 3️⃣ Decentralized (Client-Owned OAuth) Architecture  
### (Practical & Commonly Approved)

### 🔹 Concept

- Each client owns their **own Google Cloud Project**
- Each client creates:
  - OAuth Client ID
  - OAuth Client Secret
- SaaS uses **client-provided credentials**
- Quota belongs to the **client**, not the SaaS

---

### 🔹 Architecture Diagram

┌┌──────────────────────┐
│ Client A             │
│ Google Cloud Project │
│ - OAuth App          │
│ - GBP APIs           │
└──────────┬───────────┘
           │
           │ OAuth Tokens
           ▼
┌────────────────────────────┐
│        SaaS Backend        │
│                            │
│ - Stores client credentials│
│ - Manages tokens securely  │
│ - Calls Google APIs        │
└──────────┬─────────────────┘
           │
           ▼
 Google Business Profile APIs


┌──────────────────────┐
│ Client B             │
│ Google Cloud Project │
│ - OAuth App          │
│ - GBP APIs           │
└──────────┬───────────┘
           │
           ▼
        (Same SaaS Backend)

---

### 🔹 Characteristics

- No centralized quota dependency
- Easier Google approval
- Immediate usability
- More setup required from clients

📌 This model is **extremely common** for early-stage and B2B SaaS tools.

---

## 4️⃣ Internal SaaS Microservice Architecture (Production)

┌┌────────────────────────────────────┐
│ API Gateway / Load Balancer         │
└──────────┬─────────────────────────┘
           │
           ▼
┌────────────────────────────────────┐
│ FastAPI Review Service              │
│                                    │
│ Routers                             │
│ - /oauth/login                      │
│ - /oauth/callback                   │
│ - /clients/{id}/accounts            │
│ - /clients/{id}/locations           │
│ - /clients/{id}/reviews             │
│                                    │
│ Services                            │
│ - OAuth Service                     │
│ - Token Refresh Service             │
│ - Google API Service                │
│                                    │
│ Security                            │
│ - Token encryption                  │
│ - Client isolation                  │
└──────────┬─────────────────────────┘
           │
           ▼
┌────────────────────────────────────┐
│ PostgreSQL                          │
│                                    │
│ Tables                              │
│ - clients                           │
│ - google_oauth_accounts             │
│ - google_locations                  │
│ - google_reviews (optional cache)  │
└────────────────────────────────────┘


## 5️⃣ Data Flow (Accounts → Locations → Reviews)

OAuth Token
↓
GET /accounts
↓
Account ID
↓
GET /accounts/{accountId}/locations
↓
Location IDs
↓
GET /accounts/{accountId}/locations/{locationId}/reviews

markdown
Copy code

📌 Reviews **cannot** be accessed without first resolving:
- Business Account
- Business Location

---

## 6️⃣ Why This Architecture Scales to N Users

- Stateless FastAPI services
- Tokens stored per client (DB-backed)
- No in-memory session dependency
- Async HTTP calls (`httpx`)
- Ready for background workers (Celery / Temporal / queues)
- Horizontal scaling supported

---

## 7️⃣ OAuth Models – Detailed Comparison

### Centralized OAuth

#### How It Works (Flow)

1. Client signs up on SaaS
2. Client clicks **“Connect Google Business Profile”**
3. SaaS redirects to Google OAuth (SaaS Client ID)
4. Client grants consent
5. Tokens stored per client
6. SaaS fetches:
   - Accounts
   - Locations
   - Reviews

#### Characteristics

- One Google Cloud project
- One OAuth app
- Tokens isolated per client
- Shared quota

#### Pros

- Best user experience
- Zero setup for clients
- Professional SaaS feel

#### Cons

- Google quota approval mandatory
- Rejection blocks new onboarding
- Riskier for early-stage products

#### Ideal Use Case

- Mature SaaS
- Public website & privacy policy
- Production customers
- Non-technical users

Examples:
- Review monitoring platforms
- Reputation management tools
- Enterprise SaaS

---

### Decentralized OAuth

#### How It Works (Flow)

1. Client follows onboarding guide
2. Client creates Google Cloud project
3. Client generates Client ID & Secret
4. Client enters credentials into SaaS
5. SaaS performs OAuth using client credentials
6. Tokens and quota belong to the client

#### Characteristics

- One Google Cloud project per client
- OAuth credentials owned by clients
- Quota isolated per client

#### Pros

- No centralized quota dependency
- Easier Google acceptance
- Immediate go-live
- Lower SaaS risk

#### Cons

- More setup steps
- Requires strong documentation
- Less friendly for non-technical users

#### Ideal Use Case

- Early-stage SaaS
- Agencies & enterprises
- Internal tools
- Proof-of-concept platforms

---

## 8️⃣ Architecture Comparison

| Aspect | Centralized OAuth | Decentralized OAuth |
|------|------------------|--------------------|
| Google Cloud Project | One (SaaS-owned) | One per client |
| OAuth App | Single | Multiple |
| Client Setup | Minimal | Required |
| Quota Ownership | SaaS | Client |
| Google Approval | Mandatory | Often unnecessary |
| Scalability | High (after approval) | High (naturally isolated) |
| User Experience | Excellent | Moderate |
| Time to Market | Slow | Fast |
| Risk to SaaS | Higher | Lower |

---

## 9️⃣ Final Key Takeaway

- **Centralized OAuth** is the **long-term ideal**
- **Decentralized OAuth** is the **practical early-stage solution**

✅ A well-designed SaaS supports **both**, starting decentralized and transitioning to centralized once Google approval is obtained.

This is exactly how **mature, production-grade SaaS platforms are built**.