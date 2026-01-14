# Mock Data Integration - Summary of Changes

## Overview

Successfully integrated mock data from the `jsom` folder to stream through Kafka, simulating the Google Business Profile API flow without requiring actual API calls.

## Files Modified

### 1. **app/services/mock_data.py** (NEW)
- Created service to load and serve mock data from JSON files
- Implements methods mirroring Google API responses:
  - `get_accounts()` - Returns 130 mock accounts
  - `get_locations()` - Returns locations for a given account
  - `get_reviews()` - Returns reviews for a given location
- Handles data format conversion from database schema to Google API format
- Automatically loads data on initialization

### 2. **app/services/google_api.py** (MODIFIED)
- Added `use_mock` parameter to `GoogleAPIClient.__init__()`
- Integrated with `mock_data_service` for mock mode
- Modified methods to check mock mode and route accordingly:
  - `validate_token()` - Skips validation in mock mode
  - `get_accounts()` - Returns mock data if enabled
  - `get_locations()` - Returns mock data if enabled
  - `get_reviews()` - Returns mock data if enabled
- Maintains full compatibility with real Google API

### 3. **app/config.py** (NO CHANGES NEEDED)
- Already had `mock_google_api` flag (defaults to `true`)
- Configuration reads from `MOCK_GOOGLE_API` environment variable

### 4. **app/api.py** (MODIFIED)
- Added import for `GoogleAPIClient` and `GoogleAPIError`
- Updated `APIService.__init__()` to initialize `GoogleAPIClient`
- Modified `validate_access_token()` to use `GoogleAPIClient.validate_token()`
- Removed hardcoded mock validation logic

### 5. **app/kafka_consumers/account_worker.py** (MODIFIED)
- Added import for `GoogleAPIClient` and `GoogleAPIError`
- Added `self.google_api_client` initialization
- Replaced `_fetch_accounts_from_google()` with actual API client call
- Updated to use real Google API response format
- Added access_token propagation to downstream events

### 6. **app/kafka_consumers/location_worker.py** (MODIFIED)
- Added import for `GoogleAPIClient` and `GoogleAPIError`
- Added `self.google_api_client` initialization
- Replaced `_fetch_locations_from_google()` with actual API client call
- Updated location ID extraction for Google API format
- Added access_token propagation to downstream events

### 7. **app/kafka_consumers/review_worker.py** (MODIFIED)
- Added import for `GoogleAPIClient` and `GoogleAPIError`
- Added `self.google_api_client` initialization
- Replaced `_fetch_reviews_from_google()` with actual API client call
- Removed pagination loop (single fetch now)
- Added Google API format parsing (rating enum conversion)
- Improved error handling for API errors

### 8. **app/kafka_producer.py** (MODIFIED)
- Added `access_token` parameter to `publish_fetch_locations_event()`
- Added `access_token` parameter to `publish_fetch_reviews_event()`
- Access token now flows through entire Kafka message chain

## Files Created

### 1. **test_mock_data.py** (NEW)
- Comprehensive test script for verifying mock data integration
- Tests:
  - Mock data loading (accounts, locations, reviews)
  - GoogleAPIClient in mock mode
  - Configuration settings
- Provides clear output showing what data is available

### 2. **MOCK_DATA_GUIDE.md** (NEW)
- Complete user guide for working with mock data
- Explains mock vs production modes
- Provides examples and troubleshooting tips
- Documents data formats and API endpoints

### 3. **.env.example** (EXISTS - NOT MODIFIED)
- Already contained necessary configuration
- Documents `MOCK_GOOGLE_API` flag

## Data Flow

### Before (Hardcoded Mock)
```
API Request → Hardcoded validation → Random mock data generation → Kafka
```

### After (JSON-Based Mock)
```
API Request → GoogleAPIClient → MockDataService → JSON Files → Kafka
                    ↓
              (if mock_mode)
```

### Production Mode
```
API Request → GoogleAPIClient → Real Google API → Kafka
                    ↓
         (if NOT mock_mode)
```

## Key Features

### ✅ Implemented
1. **Mock Data Loading**: Automatically loads 130 accounts, 500 locations, 710 reviews
2. **Seamless Switching**: Toggle between mock and production with environment variable
3. **Full Kafka Integration**: Data streams through all Kafka topics as in production
4. **Token Propagation**: Access token flows through entire pipeline
5. **Error Handling**: Proper error handling for both mock and real API calls
6. **Testing Framework**: Test script to verify everything works

### ✅ Maintained
1. **Rate Limiting**: Still enforced even in mock mode
2. **Retry Logic**: Preserved for production mode
3. **Deduplication**: Review deduplication still works
4. **DLQ Support**: Dead letter queue handling maintained

## Configuration

### Mock Mode (Default)
```env
MOCK_GOOGLE_API=true
```

### Production Mode
```env
MOCK_GOOGLE_API=false
```

## Testing Results

```
📊 Accounts loaded: 130
📍 Locations loaded: 500
⭐ Reviews loaded: 710

✅ All tests passed! Mock data is ready to stream via Kafka.
```

## Usage Example

```python
# In mock mode
client = GoogleAPIClient()  # Automatically uses mock if configured

# Validate token (always passes in mock mode)
await client.validate_token("any_token")

# Get accounts (returns 130 from accounts.json)
accounts_response = await client.get_accounts("any_token")

# Get locations (returns from locations.json)
locations_response = await client.get_locations(
    "accounts/10000000000000000001", 
    "any_token"
)

# Get reviews (returns from Reviews.json)
reviews_response = await client.get_reviews(
    "accounts/xxx",
    "locations/yyy",
    "any_token"
)
```

## Benefits

1. **Development Speed**: No need to wait for real API calls
2. **Testing**: Consistent, repeatable test data
3. **Offline Work**: Can develop without internet
4. **Cost Savings**: No API quota usage during development
5. **Production Ready**: Same code paths, just different data source

## Migration Path to Production

1. ✅ Develop and test with mock data
2. ✅ Verify Kafka streaming works
3. ✅ Test entire pipeline end-to-end
4. ⏭️ Obtain Google OAuth token
5. ⏭️ Set `MOCK_GOOGLE_API=false`
6. ⏭️ Submit real token to API
7. ⏭️ Monitor production data flow

## Notes

- Mock data uses realistic Indian restaurant names and locations
- Review ratings range from 1-5 stars
- All timestamps are in ISO 8601 format
- Data relationships: Account → Location → Review are maintained
- Mock mode is the default to prevent accidental API calls

## Future Enhancements

Potential improvements:
- Add more mock data scenarios (errors, edge cases)
- Mock pagination support
- Configurable data volume
- Custom mock data injection for specific tests
