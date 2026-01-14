#!/usr/bin/env python3
"""
Consumer to display actual review data flowing through Kafka reviews-raw topic.
Shows the final output: reviews with ratings, text, reviewer names from mock data.
"""
import asyncio
import json
import sys
from aiokafka import AIOKafkaConsumer
from datetime import datetime

async def consume_reviews():
    """Consume and display reviews from reviews-raw topic."""
    consumer = AIOKafkaConsumer(
        'reviews-raw',
        bootstrap_servers='localhost:9094',
        auto_offset_reset='earliest',
        value_deserializer=lambda m: json.loads(m.decode('utf-8')),
        group_id='review_display_group'
    )
    
    await consumer.start()
    print("\n" + "="*80)
    print("📖 STREAMING MOCK DATA REVIEWS FROM KAFKA")
    print("="*80)
    print(f"Source: jsom/Reviews.json (mock data) → review-fetcher → Kafka")
    print(f"Connected to: localhost:9094")
    print(f"Topic: reviews-raw")
    print(f"Waiting for reviews...")
    print("="*80 + "\n")
    
    review_count = 0
    try:
        async for message in consumer:
            review_count += 1
            review = message.value
            timestamp = datetime.fromtimestamp(message.timestamp / 1000).strftime("%H:%M:%S")
            
            # Display review in formatted output
            print(f"\n[{timestamp}] 💾 REVIEW #{review_count}")
            print(f"  Review ID:    {review.get('review_id', 'N/A')}")
            print(f"  Location:     {review.get('location_id', 'N/A')}")
            print(f"  Reviewer:     {review.get('reviewer_name', 'Anonymous')}")
            print(f"  Rating:       {'⭐' * review.get('rating', 0)} ({review.get('rating', 0)}/5)")
            print(f"  Text:         {review.get('text', 'No text')[:80]}...")
            print(f"  Timestamp:    {review.get('review_time', 'N/A')}")
            
            if review_count % 10 == 0:
                print(f"\n{'='*80}")
                print(f"✓ Received {review_count} reviews so far...")
                print(f"{'='*80}")
    
    except KeyboardInterrupt:
        print(f"\n\n✓ Final count: {review_count} reviews consumed from reviews-raw topic")
    finally:
        await consumer.stop()

if __name__ == '__main__':
    try:
        asyncio.run(consume_reviews())
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
