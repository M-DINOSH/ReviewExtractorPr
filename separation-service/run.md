# 🚀 Running the Sentiment Analysis Service

This guide provides step-by-step instructions to run the separation-service microservice, which analyzes text reviews and classifies them as positive, negative, or neutral using VADER sentiment analysis.

## 📋 Prerequisites

- **Python 3.8+** installed
- **pip** package manager
- **Docker & Docker Compose** (optional, for containerized deployment)
- **curl** and **jq** (for testing, optional)

## ⚡ Quick Start (Recommended)

### Option 1: Using Make (Simplest)

```bash
# Navigate to the service directory
cd separation-service

# Install dependencies
make install

# Run the service
make run
```

### Option 2: Manual Python Setup

```bash
# Navigate to the service directory
cd separation-service

# Install dependencies
pip install -r requirements.txt

# Run the service
python run.py
```

The service will start on `http://localhost:8000`

## 🔧 Alternative Run Methods

### Using Docker Compose

```bash
# Build and run with Docker
make docker-build
make docker-run

# Or manually:
docker-compose up -d
```

### Development Mode

```bash
# Install development dependencies
pip install -r requirements-test.txt

# Run with auto-reload
export DEBUG=true
python run.py
```

## 🌐 API Endpoints

Once running, the service provides these endpoints:

### Health Check
```bash
GET http://localhost:8000/api/v1/health
```

### Readiness Check
```bash
GET http://localhost:8000/api/v1/ready
```

### Sentiment Analysis (Main Endpoint)
```bash
POST http://localhost:8000/api/v1/analyze
```

### API Documentation
```bash
# Interactive Swagger UI (development mode)
open http://localhost:8000/docs

# ReDoc documentation (development mode)
open http://localhost:8000/redoc
```

### Prometheus Metrics
```bash
GET http://localhost:8000/metrics
```

## 🧪 Testing the Service

### Using Make Commands

```bash
# Run all tests
make test

# Run tests with coverage
pytest tests/ -v --cov=sentiment_service
```

### Manual Testing with curl

```bash
# Test health endpoint
curl -s http://localhost:8000/api/v1/health | jq .

# Test readiness endpoint
curl -s http://localhost:8000/api/v1/ready | jq .

# Test sentiment analysis
curl -X POST http://localhost:8000/api/v1/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "reviews": [
      {
        "text": "This product is amazing! Highly recommend!",
        "id": "review_1"
      },
      {
        "text": "Terrible quality, complete waste of money.",
        "id": "review_2"
      },
      {
        "text": "It is okay, nothing special.",
        "id": "review_3"
      }
    ]
  }' | jq .
```

## 📊 Response Format

The `/api/v1/analyze` endpoint returns JSON with this structure:

```json
{
  "results": [
    {
      "id": "review_1",
      "text": "This product is amazing! Highly recommend!",
      "sentiment": "POSITIVE",
      "confidence": 0.8432
    },
    {
      "id": "review_2",
      "text": "Terrible quality, complete waste of money.",
      "sentiment": "NEGATIVE",
      "confidence": 0.7564
    },
    {
      "id": "review_3",
      "text": "It is okay, nothing special.",
      "sentiment": "NEUTRAL",
      "confidence": 0.0364
    }
  ],
  "total_processed": 3,
  "processing_time": 0.0021,
  "model_used": "vader"
}
```

## 🔌 Frontend Integration Example

### JavaScript/React Example
```javascript
const analyzeSentiment = async (reviews) => {
  try {
    const response = await fetch('http://localhost:8000/api/v1/analyze', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        reviews: reviews.map(review => ({
          text: review.text,
          id: review.id
        }))
      })
    });

    if (!response.ok) {
      throw new Error('Failed to analyze sentiment');
    }

    const data = await response.json();
    return data;
  } catch (error) {
    console.error('Error analyzing sentiment:', error);
    throw error;
  }
};

// Usage
const reviews = [
  { id: '1', text: 'Amazing product!' },
  { id: '2', text: 'Terrible service.' }
];

const results = await analyzeSentiment(reviews);
console.log(`Analyzed ${results.total_processed} reviews in ${results.processing_time}s`);
```

### Python Example
```python
import requests

def analyze_sentiment(reviews):
    url = "http://localhost:8000/api/v1/analyze"
    payload = {
        "reviews": [
            {"text": review["text"], "id": review["id"]}
            for review in reviews
        ]
    }

    response = requests.post(url, json=payload)
    response.raise_for_status()
    return response.json()

# Usage
reviews = [
    {"id": "1", "text": "This is fantastic!"},
    {"id": "2", "text": "Not good at all."}
]

result = analyze_sentiment(reviews)
print(f"Processed {result['total_processed']} reviews")
for res in result['results']:
    print(f"{res['id']}: {res['sentiment']} ({res['confidence']:.2f})")
```

## ⚙️ Configuration

### Environment Variables

Create a `.env` file or set environment variables:

```bash
# Server settings
HOST=0.0.0.0
PORT=8000

# Rate limiting
RATE_LIMIT_REQUESTS_PER_MINUTE=100

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json

# Development
DEBUG=false

# Metrics
METRICS_ENABLED=true
```

### Rate Limiting

The service includes built-in rate limiting:
- Default: 100 requests per minute per IP
- Configurable via `RATE_LIMIT_REQUESTS_PER_MINUTE`
- Returns HTTP 429 when exceeded

## 🛑 Stopping the Service

### Local Python Process
```bash
# Find and stop the process
ps aux | grep "python run.py"
kill <PID>

# Or use Ctrl+C in the terminal where it's running
```

### Docker Compose
```bash
# Stop services
make docker-stop

# Or manually
docker-compose down
```

## 📝 Useful Commands

```bash
# Development workflow
make install          # Install dependencies
make run             # Run service locally
make test            # Run tests
make lint            # Check code quality
make format          # Format code

# Docker workflow
make docker-build    # Build Docker image
make docker-run      # Run with Docker Compose
make docker-stop     # Stop Docker services

# Code quality
make format          # Format code with black
make lint            # Lint with flake8

# Cleanup
make clean           # Remove cache files and logs
```

## 🔍 Troubleshooting

### Service Won't Start
- Check Python version: `python --version` (requires 3.8+)
- Verify dependencies: `pip list | grep fastapi`
- Check port availability: `lsof -i :8000`
- Review logs for error messages

### API Returns Errors
- Verify JSON format in POST requests
- Check rate limiting (429 errors)
- Ensure reviews array is not empty
- Maximum 1000 reviews per request

### Performance Issues
- Service processes ~1000 reviews/second
- Check system resources (CPU, memory)
- Review batch size (smaller batches may be faster for large volumes)

### Docker Issues
- Ensure Docker daemon is running
- Check container logs: `docker-compose logs`
- Verify port mapping: `docker ps`

## 📚 Additional Resources

- [API Documentation](http://localhost:8000/docs) - Interactive API docs (dev mode)
- [README.md](./README.md) - Detailed service documentation
- [flow.md](./flow.md) - Service processing flow explanation
- [Makefile](./Makefile) - All available commands

## 🔄 Integration with Review Fetcher

The sentiment service is designed to work with the review-fetcher-service:

```bash
# 1. Start review-fetcher-service
cd ../review-fetcher-service
./run.sh

# 2. Start sentiment service
cd ../separation-service
make run

# 3. Fetch reviews and analyze sentiment
curl "http://localhost:8084/sync/reviews?access_token=test_token" | \
  jq '.locations[].reviews[] | {text: .comment, id: .review_id}' | \
  curl -X POST http://localhost:8000/api/v1/analyze \
    -H "Content-Type: application/json" \
    -d @-
```

---

**🎯 Ready to analyze sentiments?** The service is now running and ready for text classification!</content>
<parameter name="filePath">/Users/dinoshm/Desktop/applic/ReviewExtractorPr/separation-service/run.md