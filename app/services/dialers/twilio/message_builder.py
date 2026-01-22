"""
Twilio message builder implementation

Builds Twilio-specific messages for WebSocket and TwiML.
"""

from typing import Dict, Optional
from app.services.dialers.base import MessageBuilder


class TwilioMessageBuilder(MessageBuilder):
    """
    Message builder for Twilio

    Constructs messages in Twilio's WebSocket and TwiML formats.
    """

    def build_audio_message(self, stream_id: str, audio_payload: str) -> Dict:
        """
        Build Twilio media message

        Args:
            stream_id: Twilio stream identifier
            audio_payload: Base64-encoded mu-law audio

        Returns:
            Twilio media message dict
        """
        return {
            "event": "media",
            "streamSid": stream_id,
            "media": {
                "payload": audio_payload
            }
        }

    def build_connection_response(
        self,
        websocket_url: str,
        custom_params: Optional[Dict] = None
    ) -> str:
        """
        Build TwiML response for connecting to WebSocket

        Args:
            websocket_url: WebSocket URL for media streaming
            custom_params: Optional parameters to pass via Stream

        Returns:
            TwiML XML string
        """
        # Build parameters XML if provided
        parameters_xml = ""
        if custom_params:
            for key, value in custom_params.items():
                # Convert boolean to string
                if isinstance(value, bool):
                    value = "true" if value else "false"
                parameters_xml += f'<Parameter name="{key}" value="{value}" />\n            '

        # Remove trailing whitespace if no parameters
        if parameters_xml:
            parameters_xml = "\n            " + parameters_xml.rstrip()

        # Build TwiML
        twiml = f'''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="{websocket_url}">{parameters_xml}
        </Stream>
    </Connect>
</Response>'''

        return twiml

    def build_mark_message(self, stream_id: str, mark_name: str) -> Dict:
        """
        Build Twilio mark message for synchronization

        Args:
            stream_id: Twilio stream identifier
            mark_name: Name of the mark

        Returns:
            Twilio mark message dict
        """
        return {
            "event": "mark",
            "streamSid": stream_id,
            "mark": {
                "name": mark_name
            }
        }

    def build_clear_message(self, stream_id: str) -> Dict:
        """
        Build Twilio clear message to clear audio buffer

        Args:
            stream_id: Twilio stream identifier

        Returns:
            Twilio clear message dict
        """
        return {
            "event": "clear",
            "streamSid": stream_id
        }
