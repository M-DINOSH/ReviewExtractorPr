"""
Observer pattern implementation for monitoring and event handling
"""

from typing import Dict, List, Any
from abc import ABC, abstractmethod
import asyncio
import time

from ..core.interfaces import IObserver
from ..core.services import logger


class BaseObserver(IObserver, ABC):
    """Base observer class"""

    def __init__(self, name: str):
        self.name = name

    async def update(self, event: str, data: Dict[str, Any]) -> None:
        """Handle event notification"""
        await self._handle_event(event, data)

    @abstractmethod
    async def _handle_event(self, event: str, data: Dict[str, Any]) -> None:
        """Handle specific event"""
        pass


class MetricsObserver(BaseObserver):
    """Observer for collecting metrics"""

    def __init__(self):
        super().__init__("metrics")
        self.metrics = {
            "requests_total": 0,
            "requests_success": 0,
            "requests_error": 0,
            "sync_operations": 0,
            "processing_time_total": 0.0,
            "events_processed": 0
        }

    async def _handle_event(self, event: str, data: Dict[str, Any]) -> None:
        """Handle metrics events"""
        self.metrics["events_processed"] += 1

        if event == "request_started":
            self.metrics["requests_total"] += 1
        elif event == "request_completed":
            self.metrics["requests_success"] += 1
            if "processing_time" in data:
                self.metrics["processing_time_total"] += data["processing_time"]
        elif event == "request_error":
            self.metrics["requests_error"] += 1
        elif event == "sync_started":
            self.metrics["sync_operations"] += 1

    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics"""
        metrics = self.metrics.copy()
        if metrics["requests_total"] > 0:
            metrics["avg_processing_time"] = metrics["processing_time_total"] / metrics["requests_total"]
            metrics["success_rate"] = metrics["requests_success"] / metrics["requests_total"]
        return metrics


class LoggingObserver(BaseObserver):
    """Observer for enhanced logging"""

    def __init__(self):
        super().__init__("logging")

    async def _handle_event(self, event: str, data: Dict[str, Any]) -> None:
        """Handle logging events"""
        if event == "request_started":
            logger.info(
                "Request started request_id=%s client_id=%s",
                data.get("request_id"),
                data.get("client_id"),
            )
        elif event == "request_completed":
            logger.info(
                "Request completed request_id=%s processing_time=%s",
                data.get("request_id"),
                data.get("processing_time"),
            )
        elif event == "request_error":
            logger.error(
                "Request failed request_id=%s error=%s",
                data.get("request_id"),
                data.get("error"),
            )
        elif event == "sync_started":
            logger.info(
                "Sync operation started account_id=%s strategy=%s",
                data.get("account_id"),
                data.get("strategy"),
            )
        elif event == "sync_completed":
            logger.info(
                "Sync operation completed account_id=%s locations_count=%s",
                data.get("account_id"),
                data.get("locations_count"),
            )
        elif event == "shutdown":
            logger.info("Service shutting down service=%s", data.get("service"))


class AlertingObserver(BaseObserver):
    """Observer for alerting on critical events"""

    def __init__(self, error_threshold: int = 10):
        super().__init__("alerting")
        self.error_threshold = error_threshold
        self.recent_errors = []
        self.alert_cooldown = 300  # 5 minutes
        self.last_alert_time = 0

    async def _handle_event(self, event: str, data: Dict[str, Any]) -> None:
        """Handle alerting events"""
        if event == "request_error":
            self.recent_errors.append({
                "timestamp": time.time(),
                "error": data.get("error"),
                "request_id": data.get("request_id")
            })

            # Clean old errors (keep last 10 minutes)
            cutoff_time = time.time() - 600
            self.recent_errors = [
                err for err in self.recent_errors
                if err["timestamp"] > cutoff_time
            ]

            # Check if we should alert
            if len(self.recent_errors) >= self.error_threshold:
                current_time = time.time()
                if current_time - self.last_alert_time > self.alert_cooldown:
                    await self._send_alert()
                    self.last_alert_time = current_time

    async def _send_alert(self) -> None:
        """Send alert notification"""
        logger.warning(
            "CRITICAL: High error rate detected error_count=%s threshold=%s",
            len(self.recent_errors),
            self.error_threshold,
        )

        # In a real implementation, this would send emails, Slack notifications, etc.
        # For now, just log the alert
        print(f"🚨 ALERT: {len(self.recent_errors)} errors in the last 10 minutes!")


class HealthObserver(BaseObserver):
    """Observer for health monitoring"""

    def __init__(self):
        super().__init__("health")
        self.service_health = {}

    async def _handle_event(self, event: str, data: Dict[str, Any]) -> None:
        """Handle health events"""
        if event == "health_check":
            service_name = data.get("service")
            status = data.get("status")
            self.service_health[service_name] = {
                "status": status,
                "timestamp": time.time(),
                "metrics": data.get("metrics", {})
            }
        elif event == "shutdown":
            service_name = data.get("service")
            if service_name in self.service_health:
                del self.service_health[service_name]

    def get_health_status(self) -> Dict[str, Any]:
        """Get overall health status"""
        if not self.service_health:
            return {"status": "unknown", "services": {}}

        unhealthy_services = [
            name for name, health in self.service_health.items()
            if health["status"] != "healthy"
        ]

        overall_status = "unhealthy" if unhealthy_services else "healthy"

        return {
            "status": overall_status,
            "services": self.service_health,
            "unhealthy_count": len(unhealthy_services)
        }


# Global observer instances
metrics_observer = MetricsObserver()
logging_observer = LoggingObserver()
alerting_observer = AlertingObserver()
health_observer = HealthObserver()</content>
<parameter name="filePath">/Users/dinoshm/Desktop/applic/ReviewExtractorPr/review-fetcher-service/app/observers/__init__.py