"""
Twilio connection handler implementation

Handles parsing and standardization of Twilio WebSocket messages.
"""

from typing import Dict, Any
from app.services.dialers.base import ConnectionHandler


class TwilioConnectionHandler(ConnectionHandler):
    """
    Connection handler for Twilio

    Parses Twilio Media Streams WebSocket messages and standardizes them.
    """

    async def handle_incoming_message(self, message: Dict) -> Dict[str, Any]:
        """
        Parse Twilio WebSocket message and return standardized format

        Twilio sends messages with an "event" field that can be:
        - "start": Connection initiated
        - "media": Audio data
        - "stop": Connection ended
        - "mark": Synchronization marker

        Args:
            message: Raw Twilio WebSocket message

        Returns:
            Standardized message dict with:
            - event_type: "start"|"media"|"stop"|"mark"
            - call_id: CallSid
            - stream_id: StreamSid
            - audio_payload: Base64 audio (for media)
            - custom_parameters: Custom params (for start)
            - mark_name: Mark name (for mark)
        """
        event_type = message.get("event")

        if event_type == "start":
            return await self._handle_start(message)
        elif event_type == "media":
            return self._handle_media(message)
        elif event_type == "stop":
            return self._handle_stop(message)
        elif event_type == "mark":
            return self._handle_mark(message)
        else:
            # Unknown event type
            return {
                "event_type": "unknown",
                "raw_message": message
            }

    async def _handle_start(self, message: Dict) -> Dict[str, Any]:
        """Handle start event"""
        start_data = message.get("start", {})

        return {
            "event_type": "start",
            "call_id": start_data.get("callSid"),
            "stream_id": start_data.get("streamSid"),
            "custom_parameters": start_data.get("customParameters", {}),
            "account_sid": start_data.get("accountSid"),
            "tracks": start_data.get("tracks", []),
            "media_format": start_data.get("mediaFormat", {}),
            "raw_start_data": start_data
        }

    def _handle_media(self, message: Dict) -> Dict[str, Any]:
        """Handle media event"""
        media_data = message.get("media", {})

        return {
            "event_type": "media",
            "stream_id": message.get("streamSid"),
            "sequence_number": message.get("sequenceNumber"),
            "audio_payload": media_data.get("payload"),
            "timestamp": media_data.get("timestamp"),
            "track": media_data.get("track", "inbound")
        }

    def _handle_stop(self, message: Dict) -> Dict[str, Any]:
        """Handle stop event"""
        stop_data = message.get("stop", {})

        return {
            "event_type": "stop",
            "call_id": stop_data.get("callSid"),
            "stream_id": message.get("streamSid"),
            "account_sid": stop_data.get("accountSid")
        }

    def _handle_mark(self, message: Dict) -> Dict[str, Any]:
        """Handle mark event"""
        mark_data = message.get("mark", {})

        return {
            "event_type": "mark",
            "stream_id": message.get("streamSid"),
            "mark_name": mark_data.get("name")
        }

    async def extract_call_metadata(self, start_data: Dict) -> Dict:
        """
        Extract call metadata from Twilio start event

        Args:
            start_data: Standardized start event data

        Returns:
            Dict with call metadata
        """
        return {
            "call_id": start_data.get("call_id"),
            "stream_id": start_data.get("stream_id"),
            "account_sid": start_data.get("account_sid"),
            "custom_parameters": start_data.get("custom_parameters", {}),
            "tracks": start_data.get("tracks", []),
            "media_format": start_data.get("media_format", {})
        }
