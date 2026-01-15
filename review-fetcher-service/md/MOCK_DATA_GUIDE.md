# Using Mock Data with Review Fetcher Service

This guide explains how to use mock data from the `jsom` folder to test the review-fetcher-service without calling the actual Google API.

## Overview

The review-fetcher-service now supports **two modes**:

1. **Mock Mode** (default): Uses data from JSON files in the `jsom` folder
2. **Production Mode**: Uses real Google Business Profile API

## Mock Data Files

The `jsom` folder contains three JSON files with test data:

- `accounts.json` - 130 mock Google Business Profile accounts
- `locations.json` - 500 mock business locations  
- `Reviews.json` - 710 mock customer reviews

This data simulates real Google API responses and flows through Kafka just like production data would.

## Configuration

### Enable Mock Mode

Mock mode is controlled by the `MOCK_GOOGLE_API` environment variable in your `.env` file:

```bash
# Use mock data (default)
MOCK_GOOGLE_API=true

# Use real Google API
MOCK_GOOGLE_API=false
```

You can also create a `.env` file from the example:

```bash
cp .env.example .env
```

## How It Works

### Data Flow

1. **API Request** → Submit a request to `/api/v1/review-fetch` with any access token
2. **Token Validation** → In mock mode, any token is accepted
3. **Account Fetching** → Returns 130 mock accounts from `accounts.json`
4. **Location Fetching** → Returns locations for each account from `locations.json`
5. **Review Fetching** → Returns reviews for each location from `Reviews.json`
6. **Kafka Streaming** → All data streams through Kafka topics:
   - `fetch-accounts` → Triggers account fetching
   - `fetch-locations` → Triggers location fetching  
   - `fetch-reviews` → Triggers review fetching
   - `reviews-raw` → Contains the final review data

### GoogleAPIClient Integration

The `GoogleAPIClient` class automatically detects mock mode and routes requests to the mock data service:

```python
from app.services.google_api import GoogleAPIClient

# Automatically uses mock mode if MOCK_GOOGLE_API=true
client = GoogleAPIClient()

# Token validation (always passes in mock mode)
await client.validate_token("any_token")

# Get accounts (returns 130 mock accounts)
accounts = await client.get_accounts("any_token")

# Get locations for an account
locations = await client.get_locations("accounts/10000000000000000001", "any_token")

# Get reviews for a location
reviews = await client.get_reviews("accounts/xxx", "locations/yyy", "any_token")
```

## Testing the Setup

Run the test script to verify mock data is loaded correctly:

```bash
python3 test_mock_data.py
```

Expected output:
```
🚀 Starting Review Fetcher Service Mock Data Tests

📊 Accounts loaded: 130
📍 Locations loaded: 500
⭐ Reviews loaded: 710

✅ All tests passed! Mock data is ready to stream via Kafka.
```

## Running the Service

### With Docker

```bash
# Build and start all services
docker-compose up --build

# Or in detached mode
docker-compose up -d --build
```

### Without Docker (Development)

```bash
# Install dependencies
pip3 install -r requirements.txt

# Run the service
python3 -m app.main
```

The service will start on `http://localhost:8000`

## Making Requests

### Submit a Review Fetch Job

```bash
curl -X POST http://localhost:8000/api/v1/review-fetch \
  -H "Content-Type: application/json" \
  -d '{"access_token": "mock_token_123"}'
```

Response:
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### Check Job Status

```bash
curl http://localhost:8000/api/v1/status/{job_id}
```

### Get Health Status

```bash
curl http://localhost:8000/api/v1/health
```

### View Metrics

```bash
curl http://localhost:8000/api/v1/metrics
```

### Get Reviews (Mock Mode Only)

```bash
curl http://localhost:8000/api/v1/reviews
```

This endpoint returns all reviews that have been published to the `reviews-raw` Kafka topic.

## Switching to Production Mode

When you're ready to use the real Google API:

1. **Get Google OAuth Token**: Obtain a valid Google OAuth 2.0 access token with Business Profile API access

2. **Update Configuration**:
   ```bash
   # .env file
   MOCK_GOOGLE_API=false
   ```

3. **Restart Service**:
   ```bash
   docker-compose restart
   ```

4. **Submit Real Token**:
   ```bash
   curl -X POST http://localhost:8000/api/v1/review-fetch \
     -H "Content-Type: application/json" \
     -d '{"access_token": "ya29.actual_google_token_here"}'
   ```

## Data Format

### Account Response Format

```json
{
  "accounts": [
    {
      "name": "accounts/10000000000000000001",
      "accountName": "ABC Restaurant Group",
      "type": "PERSONAL",
      "state": {
        "status": "VERIFIED"
      }
    }
  ]
}
```

### Location Response Format

```json
{
  "locations": [
    {
      "name": "accounts/xxx/locations/yyy",
      "locationName": "Taco Town - Ahmedabad",
      "primaryPhone": "+91-1234567890",
      "address": {
        "addressLines": ["123 Main St, City, State"]
      },
      "primaryCategory": {
        "displayName": "Restaurant"
      }
    }
  ]
}
```

### Review Response Format

```json
{
  "reviews": [
    {
      "reviewId": "ChdDSUhNMG9nS0VJQ0FnSUN1N3R3",
      "reviewer": {
        "displayName": "John Doe",
        "profilePhotoUrl": "https://..."
      },
      "starRating": "FOUR",
      "comment": "Great service!",
      "createTime": "2025-02-10T11:15:00Z",
      "reviewReply": {
        "comment": "Thank you!",
        "updateTime": "2025-02-10T13:00:00Z"
      }
    }
  ],
  "averageRating": 4.2,
  "totalReviewCount": 150
}
```

## Troubleshooting

### Mock Data Not Loading

Check the logs for errors:
```bash
docker-compose logs review-fetcher-service
```

Verify files exist:
```bash
ls -la jsom/
```

### No Reviews Returned

This is expected if the account/location mapping doesn't match. The mock data uses internal database IDs to link accounts → locations → reviews.

### Token Validation Fails

In mock mode, any token should be accepted. If validation fails:
1. Check `MOCK_GOOGLE_API=true` in `.env`
2. Restart the service
3. Check logs for configuration errors

## Benefits of Mock Mode

✅ **No API Quota Limits**: Test unlimited times without using Google API quota  
✅ **Faster Development**: No network latency or API rate limiting  
✅ **Consistent Data**: Same test data every time for reproducible tests  
✅ **Offline Development**: Work without internet connection  
✅ **Cost Savings**: No API usage costs during development  

## Next Steps

1. Test the complete flow with mock data
2. Integrate with the separation-service for sentiment analysis
3. When ready, switch to production mode with real Google API tokens
4. Monitor Kafka topics to see data streaming through the system

## Support

For issues or questions:
- Check the main [README.md](README.md) for architecture details
- Review [flow.md](flow.md) for data flow diagrams
- Check Docker logs: `docker-compose logs -f`
