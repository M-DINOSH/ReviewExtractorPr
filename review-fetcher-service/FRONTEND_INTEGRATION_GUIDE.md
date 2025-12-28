# 🎯 Google Reviews Fetcher - Frontend Integration Guide

## Overview

The Google Reviews Fetcher microservice provides a seamless way to integrate Google Business Profile reviews into your frontend applications. It supports both **mock mode** (for development/testing) and **production mode** (real Google API calls) with identical APIs.

## 🏗️ Architecture Overview

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Frontend      │────│  Microservice    │────│ Google API /    │
│   (React/Vue)   │    │  (FastAPI)       │    │ Mock Data       │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌─────────────────┐
                       │   Database      │
                       │   (PostgreSQL)  │
                       └─────────────────┘
```

## 🔄 Production Flow

### 1. **Authentication & Token Management**
```javascript
// Frontend gets OAuth token from Google
const googleToken = await getGoogleOAuthToken();

// Send to your backend/microservice
const response = await fetch('/api/reviews/sync', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    access_token: googleToken,
    client_id: 'your_client_id'
  })
});
```

### 2. **Microservice Processing**
```mermaid
graph TD
    A[Frontend Request] --> B[FastAPI Endpoint]
    B --> C{Data Mode?}
    C -->|Mock| D[MockDataProvider]
    C -->|Google| E[GoogleDataProvider]
    D --> F[Load JSON Data]
    E --> G[Call Google API]
    F --> H[Process & Return]
    G --> H
    H --> I[Return JSON Response]
```

### 3. **Data Flow**
```
Frontend Request
    ↓
Access Token Validation
    ↓
Account Discovery (Google API / Mock)
    ↓
Location Fetching (per account)
    ↓
Review Fetching (per location)
    ↓
Data Aggregation & Response
    ↓
Frontend Receives Complete Dataset
```

## 🚀 API Endpoints

### **GET /sync/reviews** (Simplified Flow)
**Purpose:** Direct JSON response with all reviews
**Use Case:** Frontend needs immediate data without polling

```javascript
// Frontend integration
const fetchReviews = async (accessToken) => {
  const response = await fetch('/api/reviews/sync/reviews', {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${accessToken}`,
      'Content-Type': 'application/json'
    }
  });

  if (!response.ok) {
    throw new Error('Failed to fetch reviews');
  }

  const data = await response.json();
  return data;
};

// Usage
const reviewsData = await fetchReviews(userToken);
console.log(reviewsData.account.account_display_name);
console.log(`${reviewsData.locations.length} locations`);
console.log(`${reviewsData.locations.reduce((sum, loc) => sum + loc.reviews.length, 0)} total reviews`);
```

**Response Format:**
```json
{
  "account": {
    "account_id": 15,
    "account_display_name": "Urban Spice Hub"
  },
  "locations": [
    {
      "location": {
        "location_id": 123,
        "location_title": "Restaurant Name - City",
        "address": "123 Main St, City, State"
      },
      "reviews": [
        {
          "rating": 5,
          "comment": "Amazing food and service!",
          "reviewer_name": "John Doe",
          "review_created_time": "2025-01-15T10:30:00Z",
          "review_id": "ChdDSUhNMG9nS0VJQ0FnSUN1N3R3"
        }
      ]
    }
  ]
}
```

### **POST /sync** (Background Processing)
**Purpose:** Long-running sync with job tracking
**Use Case:** Large datasets, progress tracking needed

```javascript
// Start sync job
const startSync = async (accessToken, clientId) => {
  const response = await fetch('/api/reviews/sync', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      access_token: accessToken,
      client_id: clientId,
      request_id: 'unique_request_id'
    })
  });

  const job = await response.json();
  return job.job_id; // "sync_job_123"
};

// Poll for completion
const pollJobStatus = async (jobId) => {
  const response = await fetch(`/api/reviews/job/${jobId}`);
  return await response.json();
};
```

## ⚙️ Configuration & Environment

### **Environment Variables**
```bash
# Production Mode
DATA_MODE=google
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret

# Development Mode
DATA_MODE=mock

# Database
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/reviews

# Caching & Messaging
REDIS_URL=redis://localhost:6379
KAFKA_BOOTSTRAP_SERVERS=kafka:9092
```

### **Mode Switching**
```javascript
// Frontend can detect mode via response headers or config endpoint
const isMockMode = process.env.NODE_ENV === 'development';

// Or check via API
const config = await fetch('/api/config');
const { data_mode } = await config.json();
```

## 🔐 Security Considerations

### **Token Handling**
```javascript
// Never expose tokens in frontend code
// Always use HTTPS
// Implement token refresh logic

const secureFetchReviews = async () => {
  // Get fresh token from your backend
  const tokenResponse = await fetch('/api/auth/token');
  const { access_token } = await tokenResponse.json();

  return await fetch('/api/reviews/sync/reviews', {
    headers: {
      'Authorization': `Bearer ${access_token}`
    }
  });
};
```

### **CORS Configuration**
```javascript
// For development
const corsOptions = {
  origin: ["http://localhost:3000", "http://localhost:8080"],
  credentials: true
};

// For production
const corsOptions = {
  origin: ["https://yourdomain.com"],
  credentials: true
};
```

## 🎨 Frontend Integration Examples

### **React Component**
```jsx
import React, { useState, useEffect } from 'react';

const ReviewsDashboard = () => {
  const [reviewsData, setReviewsData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchReviews();
  }, []);

  const fetchReviews = async () => {
    try {
      setLoading(true);
      const response = await fetch('/api/reviews/sync/reviews?access_token=user_token');
      if (!response.ok) throw new Error('Failed to fetch reviews');

      const data = await response.json();
      setReviewsData(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <div>Loading reviews...</div>;
  if (error) return <div>Error: {error}</div>;
  if (!reviewsData) return null;

  return (
    <div className="reviews-dashboard">
      <h1>{reviewsData.account.account_display_name}</h1>
      <p>{reviewsData.locations.length} locations</p>

      {reviewsData.locations.map((location, idx) => (
        <div key={idx} className="location">
          <h3>{location.location.location_title}</h3>
          <div className="reviews">
            {location.reviews.map((review, reviewIdx) => (
              <div key={reviewIdx} className="review">
                <div className="rating">{'⭐'.repeat(review.rating)}</div>
                <p>{review.comment}</p>
                <small>- {review.reviewer_name}</small>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
};

export default ReviewsDashboard;
```

### **Vue.js Component**
```vue
<template>
  <div class="reviews-container">
    <div v-if="loading">Loading reviews...</div>
    <div v-else-if="error">{{ error }}</div>
    <div v-else-if="reviewsData">
      <h1>{{ reviewsData.account.account_display_name }}</h1>
      <p>{{ reviewsData.locations.length }} locations</p>

      <div v-for="(location, idx) in reviewsData.locations" :key="idx">
        <h3>{{ location.location.location_title }}</h3>
        <div class="reviews">
          <div v-for="(review, reviewIdx) in location.reviews" :key="reviewIdx" class="review">
            <div class="rating">{{ '⭐'.repeat(review.rating) }}</div>
            <p>{{ review.comment }}</p>
            <small>- {{ review.reviewer_name }}</small>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'ReviewsDashboard',
  data() {
    return {
      reviewsData: null,
      loading: true,
      error: null
    }
  },
  async mounted() {
    await this.fetchReviews();
  },
  methods: {
    async fetchReviews() {
      try {
        this.loading = true;
        const response = await fetch('/api/reviews/sync/reviews?access_token=user_token');
        if (!response.ok) throw new Error('Failed to fetch reviews');

        this.reviewsData = await response.json();
      } catch (err) {
        this.error = err.message;
      } finally {
        this.loading = false;
      }
    }
  }
}
</script>
```

### **Vanilla JavaScript**
```javascript
class ReviewsManager {
  constructor(apiBaseUrl) {
    this.apiBaseUrl = apiBaseUrl;
  }

  async fetchReviews(accessToken) {
    const response = await fetch(`${this.apiBaseUrl}/sync/reviews?access_token=${accessToken}`);
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    return await response.json();
  }

  renderReviews(data, containerElement) {
    containerElement.innerHTML = `
      <h1>${data.account.account_display_name}</h1>
      <p>${data.locations.length} locations</p>
      ${data.locations.map(location => `
        <div class="location">
          <h3>${location.location.location_title}</h3>
          <div class="reviews">
            ${location.reviews.map(review => `
              <div class="review">
                <div class="rating">${'⭐'.repeat(review.rating)}</div>
                <p>${review.comment}</p>
                <small>- ${review.reviewer_name}</small>
              </div>
            `).join('')}
          </div>
        </div>
      `).join('')}
    `;
  }

  async displayReviews(accessToken, containerId) {
    const container = document.getElementById(containerId);
    container.innerHTML = '<div>Loading...</div>';

    try {
      const data = await this.fetchReviews(accessToken);
      this.renderReviews(data, container);
    } catch (error) {
      container.innerHTML = `<div>Error: ${error.message}</div>`;
    }
  }
}

// Usage
const reviewsManager = new ReviewsManager('/api/reviews');
reviewsManager.displayReviews('user_access_token', 'reviews-container');
```

## 🚀 Deployment & Scaling

### **Docker Deployment**
```yaml
# docker-compose.prod.yml
version: '3.8'
services:
  review-fetcher:
    image: your-registry/review-fetcher:latest
    environment:
      - DATA_MODE=google
      - DATABASE_URL=postgresql+asyncpg://user:pass@db:5432/reviews
      - REDIS_URL=redis://redis:6379
    deploy:
      replicas: 3
      resources:
        limits:
          cpus: '1.0'
          memory: 1G
```

### **Load Balancing**
```nginx
# nginx.conf
upstream review_api {
    server review-fetcher-1:8000;
    server review-fetcher-2:8000;
    server review-fetcher-3:8000;
}

server {
    listen 80;
    server_name api.yourdomain.com;

    location /api/reviews/ {
        proxy_pass http://review_api;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## 📊 Monitoring & Analytics

### **Health Checks**
```javascript
// Frontend health monitoring
const checkServiceHealth = async () => {
  try {
    const response = await fetch('/api/reviews/health');
    return response.ok;
  } catch {
    return false;
  }
};
```

### **Error Tracking**
```javascript
// Implement error boundaries
class ErrorBoundary extends React.Component {
  componentDidCatch(error, errorInfo) {
    // Log to your error tracking service
    logError(error, {
      component: 'ReviewsDashboard',
      errorInfo,
      userAgent: navigator.userAgent
    });
  }
}
```

## 🔧 Troubleshooting

### **Common Issues**

**1. CORS Errors**
```javascript
// Ensure CORS is properly configured
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://yourdomain.com"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
```

**2. Token Expiration**
```javascript
// Implement token refresh
const refreshToken = async () => {
  const response = await fetch('/api/auth/refresh');
  const { access_token } = await response.json();
  return access_token;
};
```

**3. Rate Limiting**
```javascript
// Handle rate limit errors
if (response.status === 429) {
  const retryAfter = response.headers.get('Retry-After');
  setTimeout(() => fetchReviews(), retryAfter * 1000);
}
```

## 📈 Performance Optimization

### **Caching Strategy**
```javascript
// Implement client-side caching
const cache = new Map();

const getCachedReviews = async (token) => {
  const cacheKey = `reviews_${token}`;

  if (cache.has(cacheKey)) {
    const { data, timestamp } = cache.get(cacheKey);
    if (Date.now() - timestamp < 300000) { // 5 minutes
      return data;
    }
  }

  const data = await fetchReviews(token);
  cache.set(cacheKey, { data, timestamp: Date.now() });
  return data;
};
```

### **Lazy Loading**
```javascript
// Load reviews on demand
const loadMoreReviews = async (locationId, page = 1) => {
  const response = await fetch(`/api/reviews/location/${locationId}?page=${page}`);
  return await response.json();
};
```

## 🎯 Best Practices

### **Frontend Integration**
1. **Always handle loading states** - Show spinners/loaders
2. **Implement error boundaries** - Graceful error handling
3. **Cache appropriately** - Don't refetch unnecessarily
4. **Optimize for mobile** - Responsive design
5. **Accessibility** - Screen reader support

### **API Usage**
1. **Use appropriate endpoints** - `/sync/reviews` for immediate data
2. **Handle rate limits** - Implement exponential backoff
3. **Validate tokens** - Check expiration before requests
4. **Monitor usage** - Track API calls and performance

### **Security**
1. **HTTPS only** - Never use HTTP in production
2. **Token rotation** - Implement refresh tokens
3. **Input validation** - Validate all inputs
4. **CORS policy** - Restrict to allowed origins

## 📚 Additional Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Google Business Profile API](https://developers.google.com/my-business/reference/rest)
- [OAuth 2.0 Best Practices](https://tools.ietf.org/html/rfc6749)
- [CORS Specification](https://fetch.spec.whatwg.org/#cors-protocol)

---

**🎉 Ready to integrate?** Your microservice provides a robust, scalable solution for Google Reviews integration with seamless mode switching between development and production environments!</content>
<parameter name="filePath">/Users/dinoshm/Desktop/applic/ReviewExtractorPr/review-fetcher-service/FRONTEND_INTEGRATION_GUIDE.md