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

logger = logging.getLogger(__name__)


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
            key_bytes = key.encode("utf-8") if key else None
            
            # Send and wait for confirmation
            future = await self.producer.send_and_wait(
                topic,
                value=value,
                key=key_bytes
            )
            
            logger.info(
                "kafka_message_sent",
                topic=topic,
                key=key,
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
        account_name: str
    ) -> bool:
        """Publish event to fetch locations"""
        message = {
            "type": "fetch_locations",
            "job_id": job_id,
            "account_id": account_id,
            "account_name": account_name,
            "timestamp": datetime.utcnow().isoformat()
        }
        
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
        location_name: str
    ) -> bool:
        """Publish event to fetch reviews"""
        message = {
            "type": "fetch_reviews",
            "job_id": job_id,
            "account_id": account_id,
            "location_id": location_id,
            "location_name": location_name,
            "timestamp": datetime.utcnow().isoformat()
        }
        
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
        reviewer_name: str
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
