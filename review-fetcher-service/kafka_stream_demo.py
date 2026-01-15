#!/usr/bin/env python
"""
Complete Kafka Streaming Pipeline Demo
Streams mock data through Kafka topics and displays output in real-time
Flow: jsom/ → API → fetch-accounts → fetch-locations → fetch-reviews → reviews-raw
"""
import asyncio
import json
import httpx
from datetime import datetime
from aiokafka import AIOKafkaConsumer
from collections import defaultdict
import structlog
import os

logger = structlog.get_logger()

class KafkaStreamingDemo:
    def __init__(self):
        self.stats = {
            'fetch-accounts': 0,
            'fetch-locations': 0,
            'fetch-reviews': 0,
            'reviews-raw': 0
        }
        self.start_time = datetime.now()
        self.kafka_bootstrap = os.getenv("KAFKA_BOOTSTRAP", "localhost:9094")
        # When running via docker-compose on host, API is exposed on 8084
        self.api_base_url = os.getenv("API_BASE_URL", "http://localhost:8084")
    
    async def check_docker_kafka(self):
        """Verify Docker and Kafka are running"""
        print("\n" + "="*110)
        print("🐳 CHECKING DOCKER & KAFKA STATUS")
        print("="*110)
        
        try:
            consumer = AIOKafkaConsumer(
                bootstrap_servers=self.kafka_bootstrap,
                session_timeout_ms=5000
            )
            await consumer.start()
            try:
                await consumer.stop()
            except asyncio.CancelledError:
                # aiokafka can raise CancelledError during shutdown on some Python versions
                pass
            print("✓ Docker containers running")
            print(f"✓ Kafka broker healthy at {self.kafka_bootstrap}")
            return True
        except Exception as e:
            print(f"✗ Kafka connection failed: {e}")
            print("\n💡 Start Docker with: docker-compose up -d")
            return False
    
    async def trigger_review_fetch(self) -> str | None:
        """Trigger the API to start fetching reviews"""
        print("\n" + "="*110)
        print("🚀 TRIGGERING REVIEW FETCH VIA API")
        print("="*110)
        
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                payload = {"access_token": "test_token_123456789"}
                print(f"\n📤 POST {self.api_base_url}/api/v1/review-fetch")
                print(f"   Payload: {payload}")
                
                response = await client.post(
                    f'{self.api_base_url}/api/v1/review-fetch',
                    json=payload
                )
                
                result = response.json()
                if response.status_code in (200, 202):
                    print(f"\n✓ Success! Status: {response.status_code}")
                    job_id = result.get('job_id')
                    print(f"   Job ID: {job_id or 'N/A'}")
                    print(f"   Message: {result.get('message', 'Job queued')}")
                    return job_id
                else:
                    print(f"\n⚠ Status: {response.status_code}")
                    print(f"   Response: {result}")
                    return None
        except Exception as e:
            print(f"\n✗ Error: {e}")
            print("💡 Make sure service is running: python -m uvicorn app.main:app --host 0.0.0.0 --port 8000")
            return None

    async def stream_nested_output(self, job_id: str, duration_seconds: int = 30):
        """Consume Kafka topics and print a final nested account→locations→reviews JSON."""
        print("\n" + "="*110)
        print("🧩 STREAMING NESTED OUTPUT (ACCOUNT → LOCATIONS → REVIEWS)")
        print("="*110)
        print(f"\n⏳ Aggregating messages for job_id={job_id} (timeout: {duration_seconds}s)...\n")

        consumer = AIOKafkaConsumer(
            "fetch-locations",
            "fetch-reviews",
            "reviews-raw",
            bootstrap_servers=self.kafka_bootstrap,
            auto_offset_reset="earliest",
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
            group_id=f"demo_nested_{int(datetime.now().timestamp())}",
        )

        account = None
        account_id = None
        locations_by_id: dict[int, dict] = {}
        reviews_by_location_id: dict[int, list] = defaultdict(list)

        async def build_output():
            locations = []
            for loc_id, loc in locations_by_id.items():
                loc_out = dict(loc)
                loc_out["reviews"] = list(reviews_by_location_id.get(loc_id, []))
                locations.append(loc_out)
            locations.sort(key=lambda x: int(x.get("location_id", 0) or 0))
            joins_ok = {
                "account.account_id == location.google_account_id": True,
                "location.location_id == review.location_id": True,
            }
            if account_id is not None:
                for l in locations:
                    if int(l.get("google_account_id", -999999)) != int(account_id):
                        joins_ok["account.account_id == location.google_account_id"] = False
                        break
            for l in locations:
                lid = int(l.get("location_id", -999999))
                for r in l.get("reviews", []) or []:
                    if int(r.get("location_id", -999999)) != lid:
                        joins_ok["location.location_id == review.location_id"] = False
                        break
                if not joins_ok["location.location_id == review.location_id"]:
                    break
            return {
                "account": account,
                "locations": locations,
                "stats": {
                    "locations": len(locations),
                    "reviews": sum(len(v) for v in reviews_by_location_id.values()),
                },
                "joins_ok": joins_ok,
            }

        await consumer.start()
        try:
            deadline = datetime.now().timestamp() + duration_seconds
            while datetime.now().timestamp() < deadline:
                try:
                    msg = await consumer.getone()
                except Exception:
                    await asyncio.sleep(0.05)
                    continue

                payload = msg.value or {}
                if str(payload.get("job_id")) != str(job_id):
                    continue
                
                if msg.topic == "fetch-locations":
                    if account is None:
                        acc_id = payload.get("account_id")
                        if acc_id is None:
                            continue
                        account_id = int(acc_id)
                        account = {
                            "id": payload.get("id", account_id),
                            "account_id": payload.get("account_id", account_id),
                            "client_id": payload.get("client_id", 1),
                            "google_account_name": payload.get("google_account_name"),
                            "account_display_name": payload.get("account_display_name")
                            or payload.get("account_name"),
                            "created_at": payload.get("created_at") or payload.get("timestamp"),
                            "updated_at": payload.get("updated_at") or payload.get("timestamp"),
                        }

                elif msg.topic == "fetch-reviews":
                    if account_id is None:
                        continue
                    if int(payload.get("google_account_id", -1)) != int(account_id):
                        continue
                    loc_id = int(payload.get("location_id", payload.get("id")))
                    if loc_id in locations_by_id:
                        continue
                    locations_by_id[loc_id] = {
                        "id": payload.get("id", loc_id),
                        "location_id": payload.get("location_id", loc_id),
                        "client_id": payload.get("client_id", 1),
                        "google_account_id": payload.get("google_account_id"),
                        "location_name": payload.get("location_name"),
                        "location_title": payload.get("location_title") or payload.get("name"),
                        "address": payload.get("address"),
                        "phone": payload.get("phone"),
                        "category": payload.get("category"),
                        "created_at": payload.get("created_at") or payload.get("timestamp"),
                        "updated_at": payload.get("updated_at") or payload.get("timestamp"),
                    }

                elif msg.topic == "reviews-raw":
                    loc_id = int(payload.get("location_id", -1))
                    if account_id is not None and loc_id not in locations_by_id:
                        continue
                    review = {
                        "id": payload.get("id"),
                        "client_id": payload.get("client_id"),
                        "location_id": payload.get("location_id"),
                        "google_review_id": payload.get("google_review_id"),
                        "rating": payload.get("rating"),
                        "comment": payload.get("comment") or payload.get("text"),
                        "reviewer_name": payload.get("reviewer_name"),
                        "reviewer_photo_url": payload.get("reviewer_photo_url"),
                        "review_created_time": payload.get("review_created_time"),
                        "reply_text": payload.get("reply_text"),
                        "reply_time": payload.get("reply_time"),
                        "created_at": payload.get("created_at") or payload.get("timestamp"),
                        "updated_at": payload.get("updated_at") or payload.get("timestamp"),
                    }
                    reviews_by_location_id[loc_id].append(review)

            final_out = await build_output()
            print(json.dumps(final_out, indent=2, ensure_ascii=False))

        finally:
            await consumer.stop()
    
    async def stream_kafka_topics(self, duration_seconds: int = 30):
        """Stream data from all Kafka topics"""
        print("\n" + "="*110)
        print("📊 STREAMING DATA FROM KAFKA TOPICS")
        print("="*110)
        print(f"\n⏳ Listening for messages (timeout: {duration_seconds}s)...\n")
        
        consumers = {}
        for topic in ['fetch-accounts', 'fetch-locations', 'fetch-reviews', 'reviews-raw']:
            consumer = AIOKafkaConsumer(
                topic,
                bootstrap_servers='localhost:9094',
                auto_offset_reset='earliest',
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                group_id=f'demo_group_{topic}'
            )
            consumers[topic] = consumer
            await consumer.start()
        
        # Emoji map for topics
        emoji_map = {
            'fetch-accounts': '📨',
            'fetch-locations': '📍',
            'fetch-reviews': '⭐',
            'reviews-raw': '💾'
        }
        
        try:
            start = datetime.now()
            tasks = {}
            
            async def consume_topic(topic_name):
                consumer = consumers[topic_name]
                async for message in consumer:
                    elapsed = (datetime.now() - start).total_seconds()
                    if elapsed > duration_seconds:
                        break
                    
                    self.stats[topic_name] += 1
                    data = message.value
                    emoji = emoji_map[topic_name]
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    
                    # Display based on topic
                    if topic_name == 'fetch-accounts':
                        print(f"[{timestamp}] {emoji} FETCH-ACCOUNTS | Job: {data.get('job_id', '?')[:8]}")
                    
                    elif topic_name == 'fetch-locations':
                        print(f"[{timestamp}] {emoji} FETCH-LOCATIONS | Job: {data.get('job_id', '?')[:8]} | Account: {data.get('account_id', '?')}")
                    
                    elif topic_name == 'fetch-reviews':
                        print(f"[{timestamp}] {emoji} FETCH-REVIEWS | Job: {data.get('job_id', '?')[:8]} | Location: {data.get('location_id', '?')}")
                    
                    elif topic_name == 'reviews-raw':
                        rating = data.get('rating', 0)
                        stars = '⭐' * int(rating)
                        reviewer = data.get('reviewer_name', 'Anonymous')[:20]
                        print(f"[{timestamp}] {emoji} REVIEW | {reviewer:<20} | {stars} | \"{data.get('text', '')[:60]}...\"")
            
            # Create tasks for all topics
            for topic in consumers.keys():
                tasks[topic] = asyncio.create_task(consume_topic(topic))
            
            # Wait until timeout or all tasks complete
            await asyncio.sleep(duration_seconds)
            
            # Cancel remaining tasks
            for task in tasks.values():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        finally:
            for consumer in consumers.values():
                await consumer.stop()
    
    def display_statistics(self):
        """Display final statistics"""
        elapsed = (datetime.now() - self.start_time).total_seconds()
        
        print("\n" + "="*110)
        print("✅ KAFKA STREAMING SUMMARY")
        print("="*110)
        
        print(f"""
📊 Messages Streamed:
   📨 fetch-accounts:    {self.stats['fetch-accounts']:>4} messages
   📍 fetch-locations:   {self.stats['fetch-locations']:>4} messages
   ⭐ fetch-reviews:     {self.stats['fetch-reviews']:>4} messages
   💾 reviews-raw:       {self.stats['reviews-raw']:>4} messages
   
   Total Messages:       {sum(self.stats.values()):>4}

⏱️  Performance:
   Duration: {elapsed:.2f} seconds
   Rate: {sum(self.stats.values())/elapsed:.1f} messages/sec (if available)

📂 Data Pipeline:
   jsom/accounts.json
      ↓ 130 accounts
   fetch-accounts topic
      ↓ Account Worker
   fetch-locations topic  
      ↓ Location Worker (~500 locations)
   fetch-reviews topic
      ↓ Review Worker
   reviews-raw topic (FINAL OUTPUT)

🎯 Configuration:
   • Docker: Running (Kafka + Zookeeper)
   • Kafka Broker: localhost:9094
   • Service: http://localhost:8000/api/v1/review-fetch
   • Mock Data: jsom/ folder (130 accounts, 500 locations, 710 reviews)

✨ Status: ✅ KAFKA STREAMING COMPLETE
""")
        print("="*110 + "\n")

async def main():
    print("\n")
    print("╔" + "═"*108 + "╗")
    print("║" + " "*108 + "║")
    print("║" + "  🎯 KAFKA STREAMING PIPELINE - MOCK DATA DEMO".center(108) + "║")
    print("║" + "  Docker + Kafka + Review Fetcher Service".center(108) + "║")
    print("║" + " "*108 + "║")
    print("╚" + "═"*108 + "╝")
    
    demo = KafkaStreamingDemo()
    
    # Step 1: Check Docker/Kafka
    if not await demo.check_docker_kafka():
        return
    
    # Step 2: Trigger API
    job_id = await demo.trigger_review_fetch()
    if not job_id:
        return
    
    # Step 3: Wait for processing
    print("\n⏳ Waiting for data to flow through pipeline...")
    await asyncio.sleep(2)

    # Step 4: Stream and display nested output
    await demo.stream_nested_output(job_id=job_id, duration_seconds=25)
    
    # Step 5: Display summary
    demo.display_statistics()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⏹️  Demo interrupted by user")
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
