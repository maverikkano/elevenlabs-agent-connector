"""
Dialer plugin registry

Manages registration and retrieval of dialer plugins.
"""

import logging
from typing import Dict, Type, List
from app.services.dialers.base import DialerService

logger = logging.getLogger(__name__)


class DialerRegistry:
    """Registry for dialer plugins"""

    _dialers: Dict[str, Type[DialerService]] = {}

    @classmethod
    def register(cls, name: str, dialer_class: Type[DialerService]) -> None:
        """
        Register a dialer plugin

        Args:
            name: Dialer name (e.g., "twilio", "plivo")
            dialer_class: DialerService subclass

        Raises:
            ValueError: If name already registered or invalid class
        """
        name_lower = name.lower()

        if name_lower in cls._dialers:
            logger.warning(f"Dialer '{name}' already registered, overwriting")

        if not issubclass(dialer_class, DialerService):
            raise ValueError(
                f"Dialer class must inherit from DialerService, got {dialer_class}"
            )

        cls._dialers[name_lower] = dialer_class
        logger.info(f"Registered dialer: {name}")

    @classmethod
    def get(cls, name: str) -> Type[DialerService]:
        """
        Get dialer by name

        Args:
            name: Dialer name (case-insensitive)

        Returns:
            DialerService class

        Raises:
            ValueError: If dialer not found
        """
        name_lower = name.lower()

        if name_lower not in cls._dialers:
            available = ", ".join(cls.list_dialers())
            raise ValueError(
                f"Dialer '{name}' not registered. Available dialers: {available}"
            )

        return cls._dialers[name_lower]

    @classmethod
    def list_dialers(cls) -> List[str]:
        """
        List all registered dialers

        Returns:
            List of dialer names
        """
        return list(cls._dialers.keys())

    @classmethod
    def is_registered(cls, name: str) -> bool:
        """
        Check if dialer is registered

        Args:
            name: Dialer name

        Returns:
            True if registered, False otherwise
        """
        return name.lower() in cls._dialers

    @classmethod
    def unregister(cls, name: str) -> None:
        """
        Unregister a dialer

        Args:
            name: Dialer name

        Raises:
            ValueError: If dialer not found
        """
        name_lower = name.lower()

        if name_lower not in cls._dialers:
            raise ValueError(f"Dialer '{name}' not registered")

        del cls._dialers[name_lower]
        logger.info(f"Unregistered dialer: {name}")

    @classmethod
    def clear(cls) -> None:
        """Clear all registered dialers (useful for testing)"""
        cls._dialers.clear()
        logger.info("Cleared all registered dialers")
