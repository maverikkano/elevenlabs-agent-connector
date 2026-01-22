"""
Agent Plugin Registry
"""

import logging
from typing import Dict, Type, List
from app.services.agents.base import AgentService

logger = logging.getLogger(__name__)


class AgentRegistry:
    """Registry for Voice Agent plugins"""

    _agents: Dict[str, Type[AgentService]] = {}

    @classmethod
    def register(cls, name: str, service_class: Type[AgentService]) -> None:
        """
        Register an agent plugin.

        Args:
            name: Agent provider name (e.g., "elevenlabs")
            service_class: AgentService subclass
        """
        name_lower = name.lower()

        if name_lower in cls._agents:
            logger.warning(f"Agent '{name}' already registered, overwriting")

        if not issubclass(service_class, AgentService):
            raise ValueError(
                f"Agent class must inherit from AgentService, got {service_class}"
            )

        cls._agents[name_lower] = service_class
        logger.info(f"Registered agent plugin: {name}")

    @classmethod
    def get(cls, name: str) -> Type[AgentService]:
        """
        Get agent service class by name.

        Args:
            name: Agent name (case-insensitive)

        Returns:
            AgentService class
            
        Raises:
            ValueError: If agent not found
        """
        name_lower = name.lower()

        if name_lower not in cls._agents:
            available = ", ".join(cls.list_agents())
            raise ValueError(
                f"Agent '{name}' not registered. Available agents: {available}"
            )

        return cls._agents[name_lower]

    @classmethod
    def list_agents(cls) -> List[str]:
        """List all registered agent names"""
        return list(cls._agents.keys())

    @classmethod
    def is_registered(cls, name: str) -> bool:
        """Check if agent is registered"""
        return name.lower() in cls._agents

    @classmethod
    def unregister(cls, name: str) -> None:
        """Unregister an agent plugin"""
        name_lower = name.lower()
        if name_lower in cls._agents:
            del cls._agents[name_lower]
            logger.info(f"Unregistered agent plugin: {name}")

    @classmethod
    def clear(cls) -> None:
        """Clear all registered agents (for testing)"""
        cls._agents.clear()
        logger.info("Cleared all registered agent plugins")
