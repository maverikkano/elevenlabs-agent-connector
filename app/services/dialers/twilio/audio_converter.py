"""
Twilio audio converter implementation

Converts between Twilio's mu-law 8kHz format and ElevenLabs PCM 16kHz format.
"""

import base64
import audioop
from app.services.dialers.base import AudioConverter


class TwilioAudioConverter(AudioConverter):
    """
    Audio converter for Twilio

    Twilio uses mu-law (G.711) encoding at 8kHz sample rate.
    ElevenLabs expects PCM 16-bit at 16kHz sample rate.
    """

    def dialer_to_pcm(self, audio_data: str) -> bytes:
        """
        Convert Twilio mu-law 8kHz to PCM 16kHz for ElevenLabs

        Args:
            audio_data: Base64-encoded mu-law audio from Twilio

        Returns:
            PCM 16kHz audio bytes
        """
        # Decode base64
        mulaw_data = base64.b64decode(audio_data)

        # Convert mu-law to PCM (16-bit linear)
        pcm_8khz = audioop.ulaw2lin(mulaw_data, 2)

        # Resample from 8kHz to 16kHz
        pcm_16khz, _ = audioop.ratecv(
            pcm_8khz,
            2,  # sample width (16-bit = 2 bytes)
            1,  # channels (mono)
            8000,  # input sample rate
            16000,  # output sample rate
            None  # state (None for first call)
        )

        return pcm_16khz

    def pcm_to_dialer(self, pcm_data: bytes) -> str:
        """
        Convert PCM 16kHz from ElevenLabs to Twilio mu-law 8kHz

        Args:
            pcm_data: PCM 16kHz audio bytes from ElevenLabs

        Returns:
            Base64-encoded mu-law audio for Twilio
        """
        # Resample from 16kHz to 8kHz
        pcm_8khz, _ = audioop.ratecv(
            pcm_data,
            2,  # sample width (16-bit = 2 bytes)
            1,  # channels (mono)
            16000,  # input sample rate
            8000,  # output sample rate
            None  # state (None for first call)
        )

        # Convert PCM to mu-law
        mulaw_data = audioop.lin2ulaw(pcm_8khz, 2)

        # Encode to base64
        return base64.b64encode(mulaw_data).decode('utf-8')
