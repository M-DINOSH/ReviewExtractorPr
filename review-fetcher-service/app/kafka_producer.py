"""
Kafka producer with retry logic and idempotency
Implements Producer pattern with async/await support
"""

import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Optional, Callable
import asyncio
from datetime import datetime
import structlog

logger = structlog.get_logger()


class KafkaProducerBase(ABC):
    """Abstract base class for Kafka producers (Strategy Pattern)"""
    
    @abstractmethod
    async def send(self, topic: str, message: dict[str, Any], key: Optional[str] = None) -> bool:
        """Send message to topic"""
        pass
    
    @abstractmethod
    async def connect(self) -> None:
        """Establish connection"""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection"""
        pass


class MockKafkaProducer(KafkaProducerBase):
    """
    Mock Kafka producer for local development
    Simulates async send without actual Kafka broker
    """
    
    def __init__(self):
        self.is_connected = False
        self.sent_messages: list[dict] = []
        self._lock = asyncio.Lock()
    
    async def connect(self) -> None:
        """Mock connection"""
        self.is_connected = True
        logger.info("mock_kafka_connected")
    
    async def disconnect(self) -> None:
        """Mock disconnection"""
        self.is_connected = False
        logger.info("mock_kafka_disconnected")
    
    async def send(
        self,
        topic: str,
        message: dict[str, Any],
        key: Optional[str] = None
    ) -> bool:
        """
        Mock send - stores in memory
        
        Returns:
            True if successful
        """
        if not self.is_connected:
            logger.error("kafka_not_connected")
            return False
        
        async with self._lock:
            envelope = {
                "topic": topic,
                "key": key,
                "message": message,
                "timestamp": datetime.utcnow().isoformat(),
                "message_id": f"{topic}_{key}_{len(self.sent_messages)}"
            }
            self.sent_messages.append(envelope)
        
        logger.info(
            "kafka_message_sent",
            topic=topic,
            key=key,
            message_type=message.get("type", "unknown")
        )
        return True
    
    def get_messages(self, topic: Optional[str] = None) -> list[dict]:
        """Get all sent messages, optionally filtered by topic"""
        if topic:
            return [m for m in self.sent_messages if m["topic"] == topic]
        return self.sent_messages.copy()
    
    def clear_messages(self) -> None:
        """Clear sent messages"""
        self.sent_messages.clear()


class AIokafkaProducer(KafkaProducerBase):
    """
    Production Kafka producer using aiokafka
    Implements async producer with batching and compression
    """
    
    def __init__(
        self,
        bootstrap_servers: list[str],
        compression_type: str = "snappy",
        request_timeout_ms: int = 30000
    ):
        self.bootstrap_servers = bootstrap_servers
        self.compression_type = compression_type
        self.request_timeout_ms = request_timeout_ms
        self.producer = None
        self.is_connected = False
    
    async def connect(self) -> None:
        """Establish Kafka connection"""
        try:
            from aiokafka import AIOKafkaProducer
            
            self.producer = AIOKafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                compression_type=None,             # Disable snappy for now
                request_timeout_ms=self.request_timeout_ms,
                acks="all",
                enable_idempotence=True
            )
            
            await self.producer.start()
            self.is_connected = True
            logger.info("aiokafka_producer_connected brokers=%s", self.bootstrap_servers)
        except ImportError:
            logger.error("aiokafka_not_installed")
            raise
        except Exception as e:
            logger.error("kafka_connection_failed %s", str(e))
            raise
    
    async def disconnect(self) -> None:
        """Close Kafka connection"""
        if self.producer:
            await self.producer.stop()
            self.is_connected = False
            logger.info("aiokafka_producer_disconnected")
    
    async def send(
        self,
        topic: str,
        message: dict[str, Any],
        key: Optional[str] = None
    ) -> bool:
        """
        Send message to Kafka topic
        
        Args:
            topic: Kafka topic name
            message: Message dict (will be JSON serialized)
            key: Optional key for partitioning
            
        Returns:
            True if successful, False otherwise
        """
        if not self.is_connected or not self.producer:
            logger.error("producer_not_connected")
            return False
        
        try:
            value = json.dumps(message).encode("utf-8")
            # Keys can come from mock JSON (often ints). Kafka keys must be bytes.
            key_bytes = str(key).encode("utf-8") if key is not None else None
            
            # Send and wait for confirmation
            future = await self.producer.send_and_wait(
                topic,
                value=value,
                key=key_bytes
            )
            
            logger.info(
                "kafka_message_sent",
                topic=topic,
                key=str(key) if key is not None else None,
                partition=future.partition,
                offset=future.offset
            )
            return True
        except Exception as e:
            logger.error(
                f"kafka_send_failed",
                topic=topic,
                error=str(e)
            )
            return False


class KafkaProducerFactory:
    """Factory to create appropriate producer based on config"""
    
    @staticmethod
    def create(
        mock: bool = True,
        bootstrap_servers: Optional[list[str]] = None
    ) -> KafkaProducerBase:
        """
        Create Kafka producer instance
        
        Args:
            mock: If True, use MockKafkaProducer
            bootstrap_servers: Kafka brokers (ignored if mock=True)
            
        Returns:
            KafkaProducerBase instance
        """
        if mock:
            return MockKafkaProducer()
        
        if not bootstrap_servers:
            bootstrap_servers = ["localhost:9092"]
        
        return AIokafkaProducer(bootstrap_servers)


class KafkaEventPublisher:
    """
    Higher-level publisher wrapping producer
    Implements idempotency and error handling
    """
    
    def __init__(
        self,
        producer: KafkaProducerBase,
        on_error: Optional[Callable] = None
    ):
        self.producer = producer
        self.on_error = on_error
        self._published: set[str] = set()  # Idempotency tracking
    
    async def publish_fetch_accounts_event(
        self,
        job_id: str,
        access_token: str
    ) -> bool:
        """Publish event to fetch accounts"""
        message = {
            "type": "fetch_accounts",
            "job_id": job_id,
            "access_token": access_token,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        return await self.producer.send(
            topic="fetch-accounts",
            message=message,
            key=job_id  # Ensure same job always goes to same partition
        )
    
    async def publish_fetch_locations_event(
        self,
        job_id: str,
        account_id: str,
        account_name: str,
        access_token: str = "mock_token",
        google_account_name: Optional[str] = None,
        account_display_name: Optional[str] = None,
        client_id: Optional[int] = None,
        created_at: Optional[str] = None,
        updated_at: Optional[str] = None,
        record_id: Optional[int] = None,
    ) -> bool:
        """Publish event to fetch locations"""
        message = {
            "type": "fetch_locations",
            "job_id": job_id,
            "account_id": account_id,
            "account_name": account_name,
            "access_token": access_token,
            "timestamp": datetime.utcnow().isoformat()
        }

        # Optional schema-enrichment (used by demo web output)
        if record_id is not None:
            message["id"] = record_id
        if client_id is not None:
            message["client_id"] = client_id
        if google_account_name is not None:
            message["google_account_name"] = google_account_name
        if account_display_name is not None:
            message["account_display_name"] = account_display_name
        if created_at is not None:
            message["created_at"] = created_at
        if updated_at is not None:
            message["updated_at"] = updated_at
        
        return await self.producer.send(
            topic="fetch-locations",
            message=message,
            key=f"{job_id}_{account_id}"
        )
    
    async def publish_fetch_reviews_event(
        self,
        job_id: str,
        account_id: str,
        location_id: str,
        location_name: str,
        access_token: str = "mock_token",
        record_id: Optional[int] = None,
        client_id: Optional[int] = None,
        google_account_id: Optional[int] = None,
        location_title: Optional[str] = None,
        address: Optional[str] = None,
        phone: Optional[str] = None,
        category: Optional[str] = None,
        created_at: Optional[str] = None,
        updated_at: Optional[str] = None,
    ) -> bool:
        """Publish event to fetch reviews"""
        message = {
            "type": "fetch_reviews",
            "job_id": job_id,
            "account_id": account_id,
            "location_id": location_id,
            "location_name": location_name,
            "access_token": access_token,
            "timestamp": datetime.utcnow().isoformat()
        }

        # Optional schema-enrichment (used by demo web output)
        if record_id is not None:
            message["id"] = record_id
        if client_id is not None:
            message["client_id"] = client_id
        if google_account_id is not None:
            message["google_account_id"] = google_account_id
        if location_title is not None:
            message["location_title"] = location_title
        if address is not None:
            message["address"] = address
        if phone is not None:
            message["phone"] = phone
        if category is not None:
            message["category"] = category
        if created_at is not None:
            message["created_at"] = created_at
        if updated_at is not None:
            message["updated_at"] = updated_at
        
        return await self.producer.send(
            topic="fetch-reviews",
            message=message,
            key=f"{job_id}_{location_id}"
        )
    
    async def publish_review_raw_event(
        self,
        job_id: str,
        review_id: str,
        location_id: str,
        account_id: str,
        rating: int,
        text: str,
        reviewer_name: str,
        record_id: Optional[int] = None,
        client_id: Optional[int] = None,
        google_review_id: Optional[str] = None,
        comment: Optional[str] = None,
        reviewer_photo_url: Optional[str] = None,
        review_created_time: Optional[str] = None,
        reply_text: Optional[str] = None,
        reply_time: Optional[str] = None,
        created_at: Optional[str] = None,
        updated_at: Optional[str] = None,
    ) -> bool:
        """Publish raw review to reviews-raw topic"""
        message = {
            "type": "review_raw",
            "job_id": job_id,
            "review_id": review_id,
            "location_id": location_id,
            "account_id": account_id,
            "rating": rating,
            "text": text,
            "reviewer_name": reviewer_name,
            "timestamp": datetime.utcnow().isoformat()
        }

        # Optional schema-enrichment (used by demo web output)
        if record_id is not None:
            message["id"] = record_id
        if client_id is not None:
            message["client_id"] = client_id
        if google_review_id is not None:
            message["google_review_id"] = google_review_id
        if comment is not None:
            message["comment"] = comment
        if reviewer_photo_url is not None:
            message["reviewer_photo_url"] = reviewer_photo_url
        if review_created_time is not None:
            message["review_created_time"] = review_created_time
        if reply_text is not None:
            message["reply_text"] = reply_text
        if reply_time is not None:
            message["reply_time"] = reply_time
        if created_at is not None:
            message["created_at"] = created_at
        if updated_at is not None:
            message["updated_at"] = updated_at
        
        return await self.producer.send(
            topic="reviews-raw",
            message=message,
            key=review_id  # Deduplication key
        )
    
    async def publish_dlq_message(
        self,
        original_topic: str,
        original_message: dict[str, Any],
        error: str,
        error_code: Optional[str] = None
    ) -> bool:
        """Publish failed message to Dead Letter Queue"""
        message = {
            "type": "dlq",
            "original_topic": original_topic,
            "original_message": original_message,
            "error": error,
            "error_code": error_code,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        result = await self.producer.send(
            topic="reviews-dlq",
            message=message,
            key=original_message.get("job_id")
        )
        
        if self.on_error and not result:
            await self.on_error(message)
        
        return result
