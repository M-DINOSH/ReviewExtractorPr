import json
from kafka import KafkaProducer
from app.config import settings
import structlog

logger = structlog.get_logger()


class KafkaProducer:
    def __init__(self):
        self.producer = None

    def start(self):
        self.producer = KafkaProducer()
        logger.info("Kafka producer started")

    def send_review(self, review_data: dict):
        try:
            data = json.dumps(review_data).encode('utf-8')
            future = self.producer.send(
                settings.kafka_topic,
                data
            )
            # Wait for the send to complete
            future.get(timeout=10)
            logger.info("Review sent to Kafka", review_id=review_data.get("review_id"))
        except Exception as e:
            logger.error("Failed to send review to Kafka", error=str(e), review_id=review_data.get("review_id"))
            raise

    def stop(self):
        if self.producer:
            self.producer.close()
            logger.info("Kafka producer stopped")


# Global instance
kafka_producer = KafkaProducer()