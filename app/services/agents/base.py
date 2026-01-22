"""
Abstract Base Classes for Agent Plugins
"""

from abc import ABC, abstractmethod
from typing import AsyncGenerator, Dict, Any, Optional
from app.services.agents.types import AgentEvent


# Audio Format Contract for all Agent implementations
# All agent plugins must handle conversion to/from this format internally.
AGENT_AUDIO_FORMAT = "PCM 16kHz mono 16-bit signed little-endian"


class AgentMessageHandler(ABC):
    """Handles agent-specific message formatting"""

    @abstractmethod
    def build_audio_message(self, audio_data: bytes) -> Any:
        """
        Build agent-specific audio message from PCM bytes.
        
        Args:
            audio_data: PCM 16kHz audio bytes
            
        Returns:
            Message payload (str, dict, or bytes) ready to send over WebSocket
        """
        pass

    @abstractmethod
    def build_initialization_message(self, dynamic_variables: Dict[str, Any]) -> Any:
        """
        Build agent-specific initialization message.
        
        Args:
            dynamic_variables: Variables to personalize the session
            
        Returns:
            Message payload
        """
        pass

    @abstractmethod
    def parse_message(self, message: Any) -> AgentEvent:
        """
        Parse agent-specific message to standardized AgentEvent.
        
        Args:
            message: Raw message received from agent (str, bytes, or dict)
            
        Returns:
            Standardized AgentEvent
        """
        pass


class AgentStream(ABC):
    """
    Represents an active connection stream to a Voice Agent.
    """
    
    # Whether the base class should automatically handle ping/pong if implemented
    auto_ping_pong: bool = True

    @abstractmethod
    async def initialize(self) -> None:
        """
        Send initialization data to the agent.
        Called once after connection, before any audio is sent.
        """
        pass

    @abstractmethod
    async def send_audio(self, audio_data: bytes) -> None:
        """
        Send PCM 16kHz audio chunk to the agent.
        
        Args:
            audio_data: PCM 16kHz mono 16-bit signed little-endian bytes
        """
        pass

    @abstractmethod
    async def receive(self) -> AsyncGenerator[AgentEvent, None]:
        """
        Yield standardized events from the agent.
        """
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close the connection and cleanup resources."""
        pass


class AgentService(ABC):
    """
    Factory class for creating agent connections.
    """

    @abstractmethod
    def get_message_handler(self) -> AgentMessageHandler:
        """Return the message handler instance for this agent"""
        pass

    @abstractmethod
    async def connect(
        self, 
        agent_id: str, 
        dynamic_variables: Dict[str, Any]
    ) -> AgentStream:
        """
        Establish connection to the agent.

        Args:
            agent_id: Identifier for the specific agent/persona
            dynamic_variables: Context variables for the session

        Returns:
            An active AgentStream instance
        """
        pass

    @abstractmethod
    def get_agent_name(self) -> str:
        """Return agent provider name (e.g., 'elevenlabs', 'openai')"""
        pass

    @abstractmethod
    def validate_config(self) -> bool:
        """Check if API keys and required settings are valid"""
        pass
