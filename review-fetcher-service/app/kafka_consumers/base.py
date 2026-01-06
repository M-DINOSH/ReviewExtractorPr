"""
Base consumer class and interfaces
Implements Abstract Factory and Template Method patterns
"""

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Optional, Callable
from datetime import datetime

logger = logging.getLogger(__name__)


class KafkaConsumerBase(ABC):
    """
    Abstract base for all Kafka consumers
    Implements Template Method pattern
    """
    
    def __init__(
        self,
        topic: str,
        consumer_group: str,
        bootstrap_servers: list[str],
        on_message: Callable[[dict], None]
    ):
        self.topic = topic
        self.consumer_group = consumer_group
        self.bootstrap_servers = bootstrap_servers
        self.on_message = on_message
        self.is_running = False
    
    @abstractmethod
    async def connect(self) -> None:
        """Connect to Kafka broker"""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from Kafka"""
        pass
    
    @abstractmethod
    async def consume(self) -> None:
        """Consume messages in a loop"""
        pass
    
    async def start(self) -> None:
        """Start consumer (non-blocking)"""
        self.is_running = True
        await self.connect()
        logger.info("%s_started topic=%s", self.__class__.__name__, self.topic)
    
    async def stop(self) -> None:
        """Stop consumer"""
        self.is_running = False
        await self.disconnect()
        logger.info("%s_stopped", self.__class__.__name__)


class MockKafkaConsumer(KafkaConsumerBase):
    """Mock consumer for testing without Kafka broker"""
    
    def __init__(self, topic: str, consumer_group: str, on_message: Callable):
        super().__init__(topic, consumer_group, ["localhost:9092"], on_message)
        self.messages: list[dict] = []
    
    async def connect(self) -> None:
        """Mock connect"""
        logger.info("mock_consumer_connected topic=%s", self.topic)
    
    async def disconnect(self) -> None:
        """Mock disconnect"""
        logger.info("mock_consumer_disconnected topic=%s", self.topic)
    
    async def consume(self) -> None:
        """Mock consume - process queued messages"""
        while self.is_running:
            if self.messages:
                message = self.messages.pop(0)
                try:
                    await self.on_message(message)
                except Exception as e:
                    logger.error("message_processing_error %s", str(e))
            
            await asyncio.sleep(0.1)
    
    def add_message(self, message: dict) -> None:
        """Add message for processing (for testing)"""
        self.messages.append(message)


class AIokafkaConsumer(KafkaConsumerBase):
    """
    Production consumer using aiokafka
    Handles offset management and error recovery
    """
    
    def __init__(
        self,
        topic: str,
        consumer_group: str,
        bootstrap_servers: list[str],
        on_message: Callable,
        auto_offset_reset: str = "earliest"
    ):
        super().__init__(topic, consumer_group, bootstrap_servers, on_message)
        self.auto_offset_reset = auto_offset_reset
        self.consumer = None
    
    async def connect(self) -> None:
        """Establish Kafka connection"""
        try:
            from aiokafka import AIOKafkaConsumer
            
            self.consumer = AIOKafkaConsumer(
                self.topic,
                bootstrap_servers=self.bootstrap_servers,
                group_id=self.consumer_group,
                auto_offset_reset=self.auto_offset_reset,
                enable_auto_commit=False,  # Manual commit for reliability
                max_poll_records=100,
                value_deserializer=lambda m: json.loads(m.decode("utf-8"))
            )
            
            await self.consumer.start()
            logger.info(
                "aiokafka_consumer_connected topic=%s group=%s",
                self.topic,
                self.consumer_group,
            )
        except ImportError:
            logger.error("aiokafka_not_installed")
            raise
        except Exception as e:
            logger.error("consumer_connection_failed %s", str(e))
            raise
    
    async def disconnect(self) -> None:
        """Close consumer connection"""
        if self.consumer:
            await self.consumer.stop()
            logger.info("aiokafka_consumer_disconnected topic=%s", self.topic)
    
    async def consume(self) -> None:
        """Consume messages with auto-commit"""
        if not self.consumer:
            logger.error("consumer_not_connected")
            return
        
        try:
            async for message in self.consumer:
                if not self.is_running:
                    break
                
                try:
                    await self.on_message(message.value)
                    # Only commit after successful processing
                    await self.consumer.commit()
                except Exception as e:
                    logger.error(
                        "message_processing_error topic=%s error=%s",
                        self.topic,
                        str(e),
                    )
                    # Don't commit - message will be reprocessed
        except Exception as e:
            logger.error("consumer_error topic=%s error=%s", self.topic, str(e))
