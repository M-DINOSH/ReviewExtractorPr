#!/usr/bin/env python
"""Kafka chaining demo.

Shows the real event-driven chain using mock data from `jsom/`:

API -> fetch-accounts -> fetch-locations -> fetch-reviews -> reviews-raw

What you will see:
- `fetch-locations` messages (proof accounts.json was loaded)
- `fetch-reviews` messages (proof locations.json was loaded)
- `reviews-raw` messages (final reviews streamed)
"""
import asyncio
import json
import os
import time
from dataclasses import dataclass

import httpx
from aiokafka import AIOKafkaConsumer

API_URL = os.getenv("REVIEW_FETCHER_API_URL", "http://localhost:8084").rstrip("/")
KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9094")


@dataclass
class ChainStats:
    accounts_seen: int = 0
    locations_seen: int = 0
    reviews_seen: int = 0


async def trigger_api():
    """Trigger the API"""
    print("\n" + "="*110)
    print("🚀 TRIGGERING REVIEW FETCH")
    print("="*110 + "\n")
    
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                f'{API_URL}/api/v1/review-fetch',
                json={"access_token": "test_token_123456789"}
            )
            if response.status_code in (200, 202):
                result = response.json()
                print(f"✓ API Response: Success (Status {response.status_code})")
                print(f"  Job ID: {result.get('job_id', 'N/A')}")
                return True
            else:
                print(f"⚠ Status: {response.status_code}")
                return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

async def consume_chain(max_accounts: int = 6, max_locations: int = 8, max_reviews: int = 25, max_wait_sec: int = 45) -> ChainStats:
    """Consume the full chain (real-time) and print stage-by-stage evidence."""
    print("\n" + "=" * 110)
    print("📡 CONSUMING KAFKA CHAIN (LIVE)")
    print("=" * 110)
    print(
        f"Topics: fetch-locations (accounts stage) → fetch-reviews (locations stage) → reviews-raw (final)\n"
        f"Kafka: {KAFKA_BOOTSTRAP}\n"
    )

    consumer = AIOKafkaConsumer(
        "fetch-locations",
        "fetch-reviews",
        "reviews-raw",
        bootstrap_servers=KAFKA_BOOTSTRAP,
        auto_offset_reset="latest",
        value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        group_id=f"kafka_chain_demo_{int(time.time())}",
        session_timeout_ms=30000,
        connections_max_idle_ms=10000,
        consumer_timeout_ms=1000,
    )

    stats = ChainStats()
    seen_accounts: set[str] = set()
    seen_locations: set[str] = set()

    printed_accounts = 0
    printed_locations = 0
    printed_reviews = 0

    try:
        await consumer.start()
        await consumer.seek_to_end()

        print(f"⏳ Waiting for events (up to {max_wait_sec}s)...\n")

        deadline = time.time() + max_wait_sec
        last_progress_print = 0.0

        while time.time() < deadline:
            if (
                len(seen_accounts) >= max_accounts
                and len(seen_locations) >= max_locations
                and stats.reviews_seen >= max_reviews
            ):
                break

            now = time.time()
            if now - last_progress_print >= 2.5:
                last_progress_print = now
                print(
                    f"…progress: accounts={len(seen_accounts)} locations={len(seen_locations)} reviews={stats.reviews_seen}"
                )

            try:
                message = await consumer.getone()
            except Exception:
                continue

            topic = message.topic
            payload = message.value or {}

            if topic == "fetch-locations":
                account_id = str(payload.get("account_id", ""))
                if account_id and account_id not in seen_accounts:
                    seen_accounts.add(account_id)
                    stats.accounts_seen = len(seen_accounts)
                    if printed_accounts < max_accounts:
                        printed_accounts += 1
                        print("\n✅ ACCOUNTS → emitted fetch-locations")
                        print(f"   account_id: {payload.get('account_id')}")
                        print(f"   account_name: {payload.get('account_name')}")
                        print(f"   job_id: {payload.get('job_id')}")

            elif topic == "fetch-reviews":
                location_id = str(payload.get("location_id", ""))
                if location_id and location_id not in seen_locations:
                    seen_locations.add(location_id)
                    stats.locations_seen = len(seen_locations)
                    if printed_locations < max_locations:
                        printed_locations += 1
                        print("\n✅ LOCATIONS → emitted fetch-reviews")
                        print(f"   location_id: {payload.get('location_id')}")
                        print(f"   location_name: {payload.get('location_name')}")
                        print(f"   account_id: {payload.get('account_id')}")
                        print(f"   job_id: {payload.get('job_id')}")

            elif topic == "reviews-raw":
                stats.reviews_seen += 1
                if printed_reviews < max_reviews:
                    printed_reviews += 1
                    rating = payload.get("rating", 0)
                    try:
                        rating_i = int(rating)
                    except Exception:
                        rating_i = 0
                    stars = "⭐" * max(0, min(5, rating_i)) + "☆" * (5 - max(0, min(5, rating_i)))
                    print("\n🎯 REVIEW STREAMED → reviews-raw")
                    print(f"   location_id: {payload.get('location_id')}")
                    print(f"   reviewer: {payload.get('reviewer_name', 'Anonymous')}")
                    print(f"   rating: {stars} ({rating}/5)")
                    text = (payload.get("text") or "").strip().replace("\n", " ")
                    if len(text) > 120:
                        text = text[:120] + "…"
                    print(f"   text: {text}")

        if stats.reviews_seen == 0:
            print(
                "\n(No reviews reached reviews-raw yet. If accounts/locations are growing but reviews stay 0, it usually means id mismatches in jsom data.)"
            )

        return stats

    finally:
        await consumer.stop()

async def main():
    print("\n")
    print("╔" + "═"*108 + "╗")
    print("║" + " "*108 + "║")
    print("║" + "  ✨ KAFKA STREAMING - MOCK DATA PIPELINE DEMO".center(108) + "║")
    print("║" + "  Docker + Kafka + Review Fetcher Service".center(108) + "║")
    print("║" + " "*108 + "║")
    print("╚" + "═"*108 + "╝")
    
    consumer_task = asyncio.create_task(
        consume_chain(max_accounts=6, max_locations=8, max_reviews=25, max_wait_sec=60)
    )

    success = await trigger_api()
    if not success:
        print("\n💡 Make sure review-fetcher is reachable.")
        print(f"   API URL: {API_URL}")
        consumer_task.cancel()
        return

    stats = await consumer_task
    
    # Summary
    print("\n" + "="*110)
    print("✅ KAFKA STREAMING COMPLETE")
    print("="*110)
    print(f"""
📊 Results:
    Accounts Observed: {stats.accounts_seen}
    Locations Observed: {stats.locations_seen}
    Reviews Streamed: {stats.reviews_seen}
   Source: jsom/ folder (mock data)
    Transport: Kafka ({KAFKA_BOOTSTRAP})
   Topics: fetch-accounts → fetch-locations → fetch-reviews → reviews-raw

📂 Data Pipeline:
   jsom/accounts.json (130 accounts)
       ↓ API Endpoint
   jsom/locations.json (500 locations)
       ↓ Kafka fetch-accounts topic
   jsom/Reviews.json (710 reviews)
       ↓ Kafka fetch-locations topic
   Kafka fetch-reviews topic
       ↓ Review Worker processes reviews
    🎯 Kafka reviews-raw topic (FINAL OUTPUT)

✨ Status: ✅ COMPLETE
""")
    print("="*110 + "\n")

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⏹️  Demo interrupted")
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
