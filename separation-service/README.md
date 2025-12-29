# Sentiment Analysis Service

A scalable, production-ready microservice for classifying text reviews as positive, negative, or neutral using VADER sentiment analysis.

## Features

- **FastAPI Framework**: High-performance async web framework
- **VADER Sentiment Analysis**: Pre-trained model for social media text
- **Batch Processing**: Analyze multiple reviews in a single request
- **Rate Limiting**: Configurable request limits per minute
- **Health Checks**: Service health and readiness endpoints
- **Structured Logging**: JSON-formatted logs for production monitoring
- **Prometheus Metrics**: Built-in monitoring and alerting support
- **CORS Support**: Cross-origin resource sharing enabled
- **OpenAPI Documentation**: Interactive API docs at `/docs`

## Quick Start

### Prerequisites

- Python 3.8+
- pip

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd separation-service
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the service:
```bash
python run.py
```

The service will start on `http://localhost:8000`

## API Usage

### Analyze Sentiment

**Endpoint:** `POST /api/v1/analyze`

**Request:**
```json
{
  "reviews": [
    {
      "text": "This product is amazing! Highly recommend!",
      "id": "review_1"
    },
    {
      "text": "Terrible quality, complete waste of money.",
      "id": "review_2"
    }
  ]
}
```

**Response:**
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
    }
  ],
  "total_processed": 2,
  "processing_time": 0.0012,
  "model_used": "vader"
}
```

### Health Check

**Endpoint:** `GET /api/v1/health`

**Response:**
```json
{
  "status": "healthy",
  "service": "Sentiment Analysis Service",
  "version": "1.0.0",
  "timestamp": "2025-12-29T10:48:03Z",
  "uptime": 1766985711.412
}
```

## Development

### Prerequisites

- Python 3.8+
- pip
- Docker (optional)

### Setup

1. **Clone and install:**
```bash
git clone <repository-url>
cd separation-service
make install
```

2. **Run tests:**
```bash
make test
```

3. **Run locally:**
```bash
make run
```

### Testing

Run the comprehensive test suite:
```bash
pytest tests/ -v --cov=sentiment_service
```

### Code Quality

```bash
# Format code
make format

# Lint code
make lint

# Run pre-commit hooks
pre-commit run --all-files
```

## Deployment

### Docker Compose

```bash
# Build and run
make docker-build
make docker-run

# Stop services
make docker-stop
```

### Production Deployment

1. **Environment setup:**
```bash
cp .env.example .env
# Edit .env with production values
```

2. **Deploy:**
```bash
docker-compose -f docker-compose.yml up -d
```

3. **Health check:**
```bash
curl http://localhost:8000/api/v1/health
```

## Configuration

Configure the service using environment variables or `.env` file:

| Variable | Default | Description |
|----------|---------|-------------|
| `HOST` | `0.0.0.0` | Server host |
| `PORT` | `8000` | Server port |
| `RATE_LIMIT_REQUESTS_PER_MINUTE` | `100` | Rate limit per minute |
| `LOG_LEVEL` | `INFO` | Logging level |
| `LOG_FORMAT` | `json` | Log format (json/text) |
| `DEBUG` | `false` | Debug mode |
| `METRICS_ENABLED` | `true` | Enable Prometheus metrics |

## Architecture

```
sentiment_service/
├── api/           # FastAPI routes and main app
├── core/          # Configuration and logging
├── models/        # Pydantic schemas
└── services/      # Business logic (sentiment analysis)
```

## Performance

- **Single Review**: ~0.001 seconds
- **Batch Processing**: Scales linearly with input size
- **Rate Limiting**: Configurable per-minute limits
- **Memory Efficient**: Minimal memory footprint
- **Concurrent Requests**: Handles multiple simultaneous requests

## Production Deployment

### Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY src/ ./src/
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

CMD ["python", "src/sentiment_service/api/main.py"]
```

### Kubernetes

The service is designed to be deployed on Kubernetes with:
- Horizontal Pod Autoscaling (HPA)
- ConfigMaps for configuration
- Readiness and liveness probes
- Resource limits and requests

## Monitoring

- **Health Endpoint**: `/api/v1/health`
- **Readiness Endpoint**: `/api/v1/ready`
- **Metrics Endpoint**: `/metrics` (Prometheus)
- **Structured Logs**: JSON format for log aggregation
- **Performance Metrics**: Request latency, throughput, error rates

## API Documentation

When running in debug mode, visit `http://localhost:8000/docs` for interactive API documentation.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Write tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## License

MIT License