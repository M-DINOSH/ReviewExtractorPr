"""
Command pattern implementation for request handling
"""

from typing import Dict, List, Any, Optional
from abc import ABC, abstractmethod
import asyncio

from ..core.interfaces import ICommand
from ..core.services import logger
from .interfaces import ISyncService


class BaseCommand(ICommand, ABC):
    """Base command class"""

    def __init__(self, name: str):
        self._name = name

    def get_name(self) -> str:
        """Get command name"""
        return self._name


class SyncReviewsCommand(BaseCommand):
    """Command for syncing reviews"""

    def __init__(self, sync_service: ISyncService, access_token: str):
        super().__init__("sync_reviews")
        self.sync_service = sync_service
        self.access_token = access_token

    async def execute(self) -> Dict[str, Any]:
        """Execute the sync reviews command"""
        logger.info("Executing sync reviews command", command=self._name)
        try:
            result = await self.sync_service.sync_reviews(self.access_token)
            logger.info("Sync reviews command completed successfully", command=self._name)
            return result
        except Exception as e:
            logger.error("Sync reviews command failed", command=self._name, error=str(e))
            raise


class HealthCheckCommand(BaseCommand):
    """Command for health checks"""

    def __init__(self, services: List[Any]):
        super().__init__("health_check")
        self.services = services

    async def execute(self) -> Dict[str, Any]:
        """Execute the health check command"""
        logger.debug("Executing health check command", command=self._name)

        health_results = {}
        overall_status = "healthy"

        for service in self.services:
            try:
                health = await service.get_health()
                health_results[service.name] = {
                    "status": health.status.value,
                    "version": health.version,
                    "uptime": health.uptime,
                    "metrics": health.metrics
                }
                if health.status != health.status.HEALTHY:
                    overall_status = "degraded"
            except Exception as e:
                health_results[service.name] = {"status": "error", "error": str(e)}
                overall_status = "unhealthy"

        return {
            "status": overall_status,
            "services": health_results,
            "timestamp": asyncio.get_event_loop().time()
        }


class CommandInvoker:
    """Invoker for executing commands"""

    def __init__(self):
        self._command_history: List[ICommand] = []

    async def execute_command(self, command: ICommand) -> Any:
        """Execute a command and track it"""
        logger.debug("Invoking command", command_name=command.get_name())

        try:
            result = await command.execute()
            self._command_history.append(command)
            return result
        except Exception as e:
            logger.error("Command execution failed",
                        command_name=command.get_name(),
                        error=str(e))
            raise

    def get_command_history(self) -> List[str]:
        """Get list of executed command names"""
        return [cmd.get_name() for cmd in self._command_history]

    def clear_history(self) -> None:
        """Clear command history"""
        self._command_history.clear()</content>
<parameter name="filePath">/Users/dinoshm/Desktop/applic/ReviewExtractorPr/review-fetcher-service/app/commands/__init__.py