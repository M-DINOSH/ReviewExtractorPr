# 🔄 Sentiment Analysis Service - Flow

## Overview

The Sentiment Analysis Service is a microservice that classifies text reviews as **POSITIVE**, **NEGATIVE**, or **NEUTRAL** using the VADER (Valence Aware Dictionary and sEntiment Reasoner) sentiment analysis model. It's designed for high-performance batch processing of reviews with built-in rate limiting, monitoring, and production-ready features.

## 🏗️ Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Client        │────│  FastAPI Service │────│   VADER Model   │
│   (Frontend)    │    │  (Async)         │    │   (Pre-trained) │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌─────────────────┐
                       │   Response      │
                       │   (JSON)        │
                       └─────────────────┘
```

## 🔄 Processing Flow

### 1. **Request Reception**
```
Client Request (POST /api/v1/analyze)
    ↓
Rate Limiting Check (100 requests/minute default)
    ↓
Input Validation (JSON schema, max 1000 reviews)
    ↓
Batch Processing Queue
```

### 2. **Sentiment Analysis Pipeline**
```
Input Reviews
    ↓
├── Review 1: "Amazing product!"
├── Review 2: "Terrible quality..."
└── Review N: "It's okay"
    ↓
VADER Analysis (per review)
    ↓
├── Compound Score: +0.8432 → POSITIVE
├── Compound Score: -0.7564 → NEGATIVE
└── Compound Score: +0.0123 → NEUTRAL
    ↓
Confidence Calculation
    ↓
Response Assembly
```

### 3. **VADER Analysis Details**
```
Text Input: "This product is amazing! Highly recommend!"
    ↓
VADER Processing:
├── Positive words: amazing (+3.0), highly (+1.0), recommend (+1.0)
├── Negative words: none
├── Neutral words: this, product, is
├── Punctuation: ! (amplifies sentiment)
    ↓
Compound Score: +0.8432 (ranges from -1 to +1)
    ↓
Classification:
├── ≥ +0.05 → POSITIVE
├── ≤ -0.05 → NEGATIVE
└── -0.05 to +0.05 → NEUTRAL
    ↓
Confidence: min(|compound_score|, 1.0) = 0.8432
```

## 📊 Data Flow Example

### Input Request
```json
{
  "reviews": [
    {
      "text": "This restaurant has amazing food and great service!",
      "id": "review_123"
    },
    {
      "text": "The wait time was too long and food was cold.",
      "id": "review_124"
    },
    {
      "text": "It's an average place, nothing special.",
      "id": "review_125"
    }
  ]
}
```

### Processing Steps
```
1. Input Validation ✓
   ├── Check JSON structure
   ├── Validate review objects
   └── Ensure text and id fields

2. Rate Limiting Check ✓
   ├── Check client IP against limits
   └── Allow/deny based on configuration

3. Sentiment Analysis ✓
   ├── Initialize VADER analyzer
   ├── Process each review text
   └── Calculate compound scores

4. Classification ✓
   ├── Review 123: +0.8476 → POSITIVE (confidence: 0.8476)
   ├── Review 124: -0.6249 → NEGATIVE (confidence: 0.6249)
   └── Review 125: -0.0364 → NEUTRAL (confidence: 0.0364)

5. Response Assembly ✓
   ├── Structure results array
   ├── Add metadata (processing time, total count)
   └── Format JSON response
```

### Output Response
```json
{
  "results": [
    {
      "id": "review_123",
      "text": "This restaurant has amazing food and great service!",
      "sentiment": "POSITIVE",
      "confidence": 0.8476
    },
    {
      "id": "review_124",
      "text": "The wait time was too long and food was cold.",
      "sentiment": "NEGATIVE",
      "confidence": 0.6249
    },
    {
      "id": "review_125",
      "text": "It's an average place, nothing special.",
      "sentiment": "NEUTRAL",
      "confidence": 0.0364
    }
  ],
  "total_processed": 3,
  "processing_time": 0.0021,
  "model_used": "vader"
}
```

## ⚡ Performance Characteristics

### Single Review Processing
```
Input → VADER Analysis → Classification → Output
   ↓         ↓              ↓            ↓
~0.001s   ~0.0008s       ~0.0001s     ~0.0001s
```

### Batch Processing
```
100 Reviews → Parallel Processing → Results Array
     ↓              ↓                ↓
 ~0.08-0.12s     Linear scaling    JSON Response
```

### Rate Limiting
```
Client Requests → Token Bucket → Allow/Deny
     ↓               ↓            ↓
Per IP/Minute    100 req/min     429 Response
```

## 🔧 Configuration Flow

### Environment Variables
```
.env File → Settings Class → Application Config
    ↓            ↓              ↓
HOST=0.0.0.0  → host="0.0.0.0" → FastAPI Host
PORT=8000     → port=8000      → FastAPI Port
RATE_LIMIT=100→ rate_limit=100 → Requests/Minute
```

### Service Initialization
```
Config Load → Logging Setup → FastAPI App → Middleware → Routes
    ↓            ↓              ↓            ↓          ↓
Environment   JSON/Console    Lifespan     CORS       /analyze
Variables     Format          Manager      Rate Limit  /health
```

## 🛡️ Error Handling Flow

### Input Validation Errors
```
Invalid JSON → 400 Bad Request
    ↓
Missing Fields → 400 Bad Request
    ↓
Empty Reviews → 400 Bad Request
    ↓
Too Many Reviews → 400 Bad Request
```

### Rate Limiting
```
Exceeded Limit → 429 Too Many Requests
    ↓
Retry-After Header → Client Backoff
```

### System Errors
```
Service Unavailable → 503 Service Unavailable
    ↓
Internal Error → 500 Internal Server Error
    ↓
Logged & Monitored → Alert System
```

## 📈 Monitoring & Metrics

### Health Checks
```
/health → System Status
    ↓
/ready → Service Readiness
    ↓
/metrics → Prometheus Data
```

### Logging Flow
```
Request → Processing → Response → Log Entry
    ↓         ↓          ↓         ↓
Timestamp  Duration   Status    JSON Format
IP Address Results    Code      Structured
```

## 🔄 Integration Flow

### With Review Fetcher Service
```
Review Fetcher → Reviews Data → Sentiment Service → Enriched Data
     ↓              ↓                ↓              ↓
Google API      JSON Response    POST /analyze    Sentiment Scores
Mock Data       Locations        Batch Process    Frontend Display
```

### Frontend Integration
```
User Request → API Gateway → Sentiment Service → Database
    ↓              ↓                ↓              ↓
Fetch Reviews  Route Request   Analyze Batch    Store Results
Display UI     Load Balance    Rate Limit       Cache Scores
```

---

**🎯 Key Benefits:**
- **Fast Processing**: ~0.001s per review
- **Batch Efficient**: Linear scaling with input size
- **Production Ready**: Rate limiting, monitoring, health checks
- **Accurate Classification**: VADER model trained on social media text
- **Easy Integration**: RESTful API with JSON responses</content>
<parameter name="filePath">/Users/dinoshm/Desktop/applic/ReviewExtractorPr/separation-service/flow.md