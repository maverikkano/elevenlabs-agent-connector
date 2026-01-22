"""
Abstract base classes for dialer plugins

This module defines the core interfaces that all dialer plugins must implement
to integrate with the gateway.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class AudioConverter(ABC):
    """
    Abstract interface for audio format conversion

    Converts between dialer-specific audio formats and PCM 16kHz format
    expected by ElevenLabs.
    """

    @abstractmethod
    def dialer_to_pcm(self, audio_data: str) -> bytes:
        """
        Convert dialer audio format to PCM 16kHz for ElevenLabs

        Args:
            audio_data: Base64-encoded audio in dialer format

        Returns:
            PCM 16kHz audio as bytes
        """
        pass

    @abstractmethod
    def pcm_to_dialer(self, pcm_data: bytes) -> str:
        """
        Convert PCM 16kHz from ElevenLabs to dialer format

        Args:
            pcm_data: PCM 16kHz audio bytes from ElevenLabs

        Returns:
            Base64-encoded audio in dialer format
        """
        pass


class MessageBuilder(ABC):
    """
    Abstract interface for building dialer-specific messages

    Handles construction of messages in the format expected by the dialer.
    """

    @abstractmethod
    def build_audio_message(self, stream_id: str, audio_payload: str) -> Dict:
        """
        Build audio message in dialer format

        Args:
            stream_id: Unique stream identifier
            audio_payload: Base64-encoded audio data

        Returns:
            Message dict in dialer format
        """
        pass

    @abstractmethod
    def build_connection_response(
        self,
        websocket_url: str,
        custom_params: Optional[Dict] = None
    ) -> str:
        """
        Build connection response (TwiML, XML, JSON, etc.)

        Args:
            websocket_url: WebSocket URL for media streaming
            custom_params: Optional custom parameters to include

        Returns:
            Response string in dialer format (XML, JSON, etc.)
        """
        pass


class ConnectionHandler(ABC):
    """
    Abstract interface for handling dialer-specific connection protocols

    Parses and standardizes incoming messages from different dialer providers.
    """

    @abstractmethod
    async def handle_incoming_message(self, message: Dict) -> Dict[str, Any]:
        """
        Parse incoming dialer message and return standardized format

        Args:
            message: Raw message from dialer

        Returns:
            Standardized message dict with keys:
            - event_type: "start"|"media"|"stop"|"mark"
            - call_id: Unique call identifier
            - stream_id: Stream identifier
            - audio_payload: Base64 audio (for media events)
            - custom_parameters: Dict of custom params (for start events)
        """
        pass

    @abstractmethod
    async def extract_call_metadata(self, start_data: Dict) -> Dict:
        """
        Extract call metadata from connection start

        Args:
            start_data: Start event data

        Returns:
            Dict with call metadata
        """
        pass


class DialerService(ABC):
    """
    Main abstract interface combining all dialer components

    This is the primary interface that dialer plugins must implement.
    It combines audio conversion, message building, and connection handling.
    """

    def __init__(self):
        """Initialize dialer service with its components"""
        self.audio_converter: AudioConverter = self.get_audio_converter()
        self.message_builder: MessageBuilder = self.get_message_builder()
        self.connection_handler: ConnectionHandler = self.get_connection_handler()

    @abstractmethod
    def get_audio_converter(self) -> AudioConverter:
        """
        Get audio converter instance for this dialer

        Returns:
            AudioConverter implementation
        """
        pass

    @abstractmethod
    def get_message_builder(self) -> MessageBuilder:
        """
        Get message builder instance for this dialer

        Returns:
            MessageBuilder implementation
        """
        pass

    @abstractmethod
    def get_connection_handler(self) -> ConnectionHandler:
        """
        Get connection handler instance for this dialer

        Returns:
            ConnectionHandler implementation
        """
        pass

    @abstractmethod
    async def initiate_outbound_call(
        self,
        to_number: str,
        agent_id: str,
        dynamic_variables: Dict,
        websocket_url: str
    ) -> Dict:
        """
        Initiate outbound call using dialer's API

        Args:
            to_number: Phone number to call (E.164 format)
            agent_id: ElevenLabs agent ID
            dynamic_variables: Variables to pass to agent
            websocket_url: WebSocket URL for media streaming

        Returns:
            Dict with keys:
            - success: bool
            - call_id: str
            - status: str
            - message: str (optional)
        """
        pass

    @abstractmethod
    def get_dialer_name(self) -> str:
        """
        Return dialer provider name

        Returns:
            Provider name (e.g., "twilio", "plivo", "exotel")
        """
        pass

    @abstractmethod
    def validate_config(self) -> bool:
        """
        Validate that dialer configuration is correct

        Returns:
            True if configuration is valid, False otherwise
        """
        pass
