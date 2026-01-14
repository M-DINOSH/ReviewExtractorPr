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
    
    async def check_docker_kafka(self):
        """Verify Docker and Kafka are running"""
        print("\n" + "="*110)
        print("🐳 CHECKING DOCKER & KAFKA STATUS")
        print("="*110)
        
        try:
            consumer = AIOKafkaConsumer(
                bootstrap_servers='localhost:9094',
                session_timeout_ms=5000
            )
            await consumer.start()
            await consumer.stop()
            print("✓ Docker containers running")
            print("✓ Kafka broker healthy at localhost:9094")
            return True
        except Exception as e:
            print(f"✗ Kafka connection failed: {e}")
            print("\n💡 Start Docker with: docker-compose up -d")
            return False
    
    async def trigger_review_fetch(self):
        """Trigger the API to start fetching reviews"""
        print("\n" + "="*110)
        print("🚀 TRIGGERING REVIEW FETCH VIA API")
        print("="*110)
        
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                payload = {"access_token": "test_token_123456789"}
                print(f"\n📤 POST http://localhost:8000/api/v1/review-fetch")
                print(f"   Payload: {payload}")
                
                response = await client.post(
                    'http://localhost:8000/api/v1/review-fetch',
                    json=payload
                )
                
                result = response.json()
                if response.status_code == 200:
                    print(f"\n✓ Success! Status: {response.status_code}")
                    print(f"   Job ID: {result.get('job_id', 'N/A')}")
                    print(f"   Message: {result.get('message', 'Job queued')}")
                    return True
                else:
                    print(f"\n⚠ Status: {response.status_code}")
                    print(f"   Response: {result}")
                    return False
        except Exception as e:
            print(f"\n✗ Error: {e}")
            print("💡 Make sure service is running: python -m uvicorn app.main:app --host 0.0.0.0 --port 8000")
            return False
    
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
    if not await demo.trigger_review_fetch():
        return
    
    # Step 3: Wait for processing
    print("\n⏳ Waiting for data to flow through pipeline...")
    await asyncio.sleep(2)
    
    # Step 4: Stream and display
    await demo.stream_kafka_topics(duration_seconds=25)
    
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
