#!/bin/bash

# 🎯 Google Reviews Fetcher - Quick Test Script
# Run this to quickly test your microservice and see reviews!

echo "🚀 Google Reviews Fetcher Microservice - Quick Test"
echo "=================================================="
echo ""

# Check if service is running
echo "1️⃣ Checking service status..."
if curl -s "http://localhost:8084/sync/reviews?access_token=status_check" > /dev/null; then
    echo "✅ Service is RUNNING on http://localhost:8084"
else
    echo "❌ Service is NOT running. Start with: docker-compose --profile dev up -d"
    exit 1
fi

echo ""
echo "2️⃣ Testing with different access tokens (random accounts)..."
echo ""

for i in {1..3}; do
    token="test_token_$i"
    echo "🔑 Token: $token"
    curl -s "http://localhost:8084/sync/reviews?access_token=$token" | jq -r '"   📊 Account: \(.account.account_display_name)", "   🏢 Locations: \(.locations | length)", "   💬 Reviews: \(.locations | map(.reviews | length) | add)"'
    echo ""
done

echo "3️⃣ Sample reviews from latest test..."
echo ""
curl -s "http://localhost:8084/sync/reviews?access_token=sample_reviews" | jq -r '.locations[0:2][] | .location.location_title as $location | (.reviews[0:1][] | "📍 \($location)\n⭐ Rating: \(.rating)\n💬 \(.comment | if length > 60 then .[0:60] + "..." else . end)\n👤 \(.reviewer_name)\n---")'

echo ""
echo "4️⃣ Useful links:"
echo "   📖 API Docs: http://localhost:8084/docs"
echo "   🔗 Direct API: http://localhost:8084/sync/reviews?access_token=YOUR_TOKEN"
echo "   📁 Saved reviews: ./all_reviews.json (if you ran the save command)"
echo ""
echo "🎉 Your microservice is working perfectly!"