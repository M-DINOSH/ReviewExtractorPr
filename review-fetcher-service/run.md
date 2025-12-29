# 🚀 Running the Google Reviews Fetcher Microservice

This guide provides step-by-step instructions to run the review-fetcher-service microservice, which fetches Google Business Profile reviews and serves them as JSON responses for frontend integration.

## 📋 Prerequisites

- **Docker & Docker Compose** installed and running
- **Git** (for cloning if needed)
- **curl** and **jq** (for testing, optional)

## ⚡ Quick Start (Recommended)

The easiest way to run the service is using the provided `run.sh` script:

```bash
# Navigate to the service directory
cd review-fetcher-service

# Make the script executable (first time only)
chmod +x run.sh

# Run with mock data (development mode)
./run.sh

# Or run with a custom access token
./run.sh "your_access_token_here"

# Or run with Google API mode (requires real OAuth token)
./run.sh "ya29.your_oauth_token" google
```

The script will:
- ✅ Check if Docker is running
- ✅ Stop any existing services
- ✅ Start PostgreSQL, Redis, and the API service
- ✅ Wait for services to be ready
- ✅ Test the API endpoints
- ✅ Display formatted results

## 🔧 Manual Setup (Alternative)

If you prefer manual control:

### Step 1: Start Services

```bash
# Start all services (PostgreSQL, Redis, API)
docker-compose --profile dev up -d

# Wait for services to initialize (about 30 seconds)
sleep 30
```

### Step 2: Verify Services

```bash
# Check if the service is healthy
curl http://localhost:8084/health

# Should return: {"status":"healthy","timestamp":"2025-12-29T...","version":"1.0.0"}
```

## 🌐 API Endpoints for Frontend Integration

Once running, the service provides these endpoints:

### Health Check
```bash
GET http://localhost:8084/health
```

### Fetch Reviews (Main Endpoint)
```bash
GET http://localhost:8084/sync/reviews?access_token=YOUR_TOKEN
```

### API Documentation
```bash
# Interactive Swagger UI
open http://localhost:8084/docs

# ReDoc documentation
open http://localhost:8084/redoc
```

## 🧪 Testing the Service

### Using the Test Script
```bash
# Run the automated test
bash test_microservice.sh
```

### Manual Testing with curl
```bash
# Test health endpoint
curl -s http://localhost:8084/health | jq .

# Test reviews endpoint with mock data
curl -s "http://localhost:8084/sync/reviews?access_token=test_token" | jq .

# Test with custom token
curl -s "http://localhost:8084/sync/reviews?access_token=your_custom_token" | jq .
```

## 📊 Response Format

The `/sync/reviews` endpoint returns JSON with this structure:

```json
{
  "account": {
    "account_id": "123456789",
    "account_display_name": "Business Name"
  },
  "locations": [
    {
      "location": {
        "location_id": "LOC001",
        "location_name": "Location Name",
        "address": {
          "address_lines": ["123 Main St"],
          "locality": "City",
          "administrative_area": "State",
          "postal_code": "12345",
          "region_code": "US"
        }
      },
      "reviews": [
        {
          "review_id": "REV001",
          "rating": 5,
          "comment": "Great service!",
          "create_time": "2025-01-01T10:00:00Z",
          "reviewer": {
            "display_name": "John Doe",
            "profile_photo_url": "https://..."
          }
        }
      ]
    }
  ]
}
```

## 🔌 Frontend Integration Example

### JavaScript/React Example
```javascript
const fetchReviews = async (accessToken) => {
  try {
    const response = await fetch('http://localhost:8084/sync/reviews?access_token=' + accessToken);
    if (!response.ok) {
      throw new Error('Failed to fetch reviews');
    }
    const data = await response.json();
    return data;
  } catch (error) {
    console.error('Error fetching reviews:', error);
    throw error;
  }
};

// Usage
const reviewsData = await fetchReviews('your_access_token');
console.log(`Fetched ${reviewsData.locations.length} locations with reviews`);
```

### Python Example
```python
import requests

def fetch_reviews(access_token):
    url = f"http://localhost:8084/sync/reviews?access_token={access_token}"
    response = requests.get(url)
    response.raise_for_status()
    return response.json()

# Usage
data = fetch_reviews("your_access_token")
print(f"Account: {data['account']['account_display_name']}")
```

## 🛑 Stopping the Service

```bash
# Stop all services
docker-compose down

# Or stop and remove volumes (clears data)
docker-compose down -v
```

## 📝 Useful Commands

```bash
# View service logs
docker-compose logs -f review-fetcher-dev

# View all logs
docker-compose logs

# Restart services
docker-compose restart

# Rebuild and restart
docker-compose up -d --build
```

## 🔍 Troubleshooting

### Service Won't Start
- Ensure Docker is running
- Check if ports 8084, 5432, 6379 are available
- Run `docker-compose logs` to see error messages

### API Returns Errors
- Verify the access_token parameter
- Check if using correct mode (mock vs google)
- Review logs: `docker-compose logs review-fetcher-dev`

### Port Conflicts
- Change ports in `docker-compose.yml` if needed
- Default ports: API (8084), PostgreSQL (5432), Redis (6379)

## 📚 Additional Resources

- [API Documentation](http://localhost:8084/docs) - Interactive API docs
- [README.md](./README.md) - Detailed service documentation
- [FRONTEND_INTEGRATION_GUIDE.md](./FRONTEND_INTEGRATION_GUIDE.md) - Frontend integration details
- [TEAM_INTEGRATION_GUIDE.md](./TEAM_INTEGRATION_GUIDE.md) - Team development guide

---

**🎯 Ready to integrate?** The service is now running and ready for frontend consumption!</content>
<parameter name="filePath">/Users/dinoshm/Desktop/applic/ReviewExtractorPr/review-fetcher-service/run.md