import audioop
import base64
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class TwilioAudioConverter:
    """Handles audio conversion between Twilio (mu-law 8kHz) and ElevenLabs (PCM 16kHz)"""

    @staticmethod
    def mulaw_to_pcm(mulaw_base64: str) -> bytes:
        """
        Convert Twilio's mu-law 8kHz audio to ElevenLabs PCM 16kHz

        Args:
            mulaw_base64: Base64-encoded mu-law audio from Twilio

        Returns:
            PCM 16kHz audio bytes suitable for ElevenLabs
        """
        try:
            # Decode base64
            mulaw_data = base64.b64decode(mulaw_base64)

            # mu-law to linear PCM (16-bit)
            pcm_8khz = audioop.ulaw2lin(mulaw_data, 2)

            # Resample 8kHz → 16kHz
            pcm_16khz, _ = audioop.ratecv(
                pcm_8khz,
                2,      # Sample width (2 bytes = 16-bit)
                1,      # Channels (mono)
                8000,   # Input sample rate
                16000,  # Output sample rate
                None
            )

            return pcm_16khz

        except Exception as e:
            logger.error(f"Error converting mu-law to PCM: {e}")
            raise

    @staticmethod
    def pcm_to_mulaw(pcm_16khz: bytes) -> str:
        """
        Convert ElevenLabs PCM 16kHz audio to Twilio's mu-law 8kHz

        Args:
            pcm_16khz: PCM 16kHz audio bytes from ElevenLabs

        Returns:
            Base64-encoded mu-law audio for Twilio
        """
        try:
            # Resample 16kHz → 8kHz
            pcm_8khz, _ = audioop.ratecv(
                pcm_16khz,
                2,      # Sample width (2 bytes = 16-bit)
                1,      # Channels (mono)
                16000,  # Input sample rate
                8000,   # Output sample rate
                None
            )

            # Linear PCM to mu-law
            mulaw_data = audioop.lin2ulaw(pcm_8khz, 2)

            # Encode to base64
            return base64.b64encode(mulaw_data).decode('utf-8')

        except Exception as e:
            logger.error(f"Error converting PCM to mu-law: {e}")
            raise


class TwilioMessageBuilder:
    """Builds Twilio WebSocket messages"""

    @staticmethod
    def build_media_message(stream_sid: str, audio_payload: str) -> Dict:
        """
        Build a Twilio media message with audio payload

        Args:
            stream_sid: Twilio stream identifier
            audio_payload: Base64-encoded mu-law audio

        Returns:
            Twilio media message dict
        """
        return {
            "event": "media",
            "streamSid": stream_sid,
            "media": {
                "payload": audio_payload
            }
        }

    @staticmethod
    def build_mark_message(stream_sid: str, mark_name: str) -> Dict:
        """
        Build a Twilio mark message (for synchronization)

        Args:
            stream_sid: Twilio stream identifier
            mark_name: Name of the mark

        Returns:
            Twilio mark message dict
        """
        return {
            "event": "mark",
            "streamSid": stream_sid,
            "mark": {
                "name": mark_name
            }
        }


def generate_twiml_response(websocket_url: str) -> str:
    """
    Generate TwiML response to start media streaming

    Args:
        websocket_url: WebSocket URL for Twilio to connect to

    Returns:
        TwiML XML string
    """
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="{websocket_url}" />
    </Connect>
</Response>'''


# In-memory storage for call contexts (use Redis in production)
call_contexts: Dict[str, Dict] = {}


def store_call_context(call_sid: str, context: Dict) -> None:
    """Store context for a call session"""
    call_contexts[call_sid] = context
    logger.info(f"Stored context for call {call_sid}")


def get_call_context(call_sid: str) -> Optional[Dict]:
    """Retrieve context for a call session"""
    return call_contexts.get(call_sid)


def cleanup_call_context(call_sid: str) -> None:
    """Remove context for a call session"""
    if call_sid in call_contexts:
        del call_contexts[call_sid]
        logger.info(f"Cleaned up context for call {call_sid}")
