"""
PredixionAI Voice Message Handler

Handles audio format conversion for LiveKit-based agents.
Unlike ElevenLabs which uses JSON messages, PredixionAI uses LiveKit's
RTC audio tracks, so this handler primarily provides format conversion utilities.
"""

import logging
import numpy as np
from typing import Any, Dict
from livekit import rtc

from app.services.agents.base import AgentMessageHandler
from app.services.agents.types import AgentEvent, AgentEventTypes

logger = logging.getLogger(__name__)


class PredixionAIMessageHandler(AgentMessageHandler):
    """Handles PredixionAI LiveKit-specific audio format conversion"""

    def build_audio_message(self, audio_data: bytes) -> rtc.AudioFrame:
        """
        Convert PCM bytes to LiveKit AudioFrame.

        Args:
            audio_data: PCM 16kHz mono 16-bit signed little-endian bytes

        Returns:
            LiveKit AudioFrame ready to be captured by AudioSource
        """
        try:
            logger.debug(f"Converting {len(audio_data)} bytes to AudioFrame")

            # Convert bytes to numpy array (int16)
            samples = np.frombuffer(audio_data, dtype=np.int16)

            # Create AudioFrame for LiveKit
            # LiveKit expects float32 samples normalized to [-1, 1]
            samples_float = samples.astype(np.float32) / 32768.0

            frame = rtc.AudioFrame(
                data=samples_float.tobytes(),
                sample_rate=16000,
                num_channels=1,
                samples_per_channel=len(samples)
            )

            logger.debug(f"Created AudioFrame: {len(samples)} samples, 16kHz mono")
            return frame

        except Exception as e:
            logger.error(f"Error converting bytes to AudioFrame: {e}", exc_info=True)
            raise

    def build_initialization_message(self, dynamic_variables: Dict[str, Any]) -> Any:
        """
        PredixionAI initialization happens via HTTP POST to JobDispatch.
        No WebSocket initialization message needed.

        Args:
            dynamic_variables: Context variables (sent via HTTP, not WebSocket)

        Returns:
            None (initialization handled elsewhere)
        """
        logger.debug("PredixionAI initialization handled via HTTP POST, not WebSocket message")
        return None

    def parse_message(self, message: Any) -> AgentEvent:
        """
        Parse LiveKit audio frame or event to standardized AgentEvent.

        Args:
            message: Either rtc.AudioFrame or event data

        Returns:
            Standardized AgentEvent
        """
        try:
            # Handle AudioFrame from LiveKit track
            if isinstance(message, rtc.AudioFrame):
                logger.debug(f"Parsing AudioFrame: {message.samples_per_channel} samples")
                audio_bytes = self._audio_frame_to_bytes(message)
                return AgentEvent(type=AgentEventTypes.AUDIO, data=audio_bytes)

            # Handle raw bytes (already converted)
            elif isinstance(message, bytes):
                logger.debug(f"Parsing raw audio bytes: {len(message)} bytes")
                return AgentEvent(type=AgentEventTypes.AUDIO, data=message)

            # Handle other event types (metadata, errors, etc.)
            elif isinstance(message, dict):
                msg_type = message.get("type", "unknown")
                logger.debug(f"Parsing dict message type: {msg_type}")

                if msg_type == "error":
                    return AgentEvent(
                        type=AgentEventTypes.ERROR,
                        data=message.get("message", "Unknown error"),
                        error=Exception(message.get("message", "Unknown error"))
                    )

                # Default: treat as metadata
                return AgentEvent(
                    type=AgentEventTypes.METADATA,
                    data=message,
                    metadata={"original_type": msg_type}
                )

            else:
                logger.warning(f"Received unexpected message type: {type(message)}")
                return AgentEvent(
                    type=AgentEventTypes.ERROR,
                    data=f"Unexpected message type: {type(message)}"
                )

        except Exception as e:
            logger.error(f"Error parsing PredixionAI message: {e}", exc_info=True)
            return AgentEvent(
                type=AgentEventTypes.ERROR,
                data=str(e),
                error=e
            )

    def _audio_frame_to_bytes(self, frame: rtc.AudioFrame) -> bytes:
        """
        Convert LiveKit AudioFrame to PCM bytes.

        Args:
            frame: LiveKit AudioFrame (float32 samples)

        Returns:
            PCM 16kHz mono 16-bit signed little-endian bytes
        """
        try:
            # LiveKit AudioFrame data is float32 normalized to [-1, 1]
            samples_float = np.frombuffer(frame.data, dtype=np.float32)

            # Handle NaN and inf values
            samples_float = np.nan_to_num(samples_float, nan=0.0, posinf=1.0, neginf=-1.0)

            # Clip to [-1, 1] range to prevent overflow
            samples_float = np.clip(samples_float, -1.0, 1.0)

            # Convert to int16 PCM with proper scaling
            samples_int16 = (samples_float * 32767.0).astype(np.int16)

            audio_bytes = samples_int16.tobytes()
            logger.debug(f"Converted AudioFrame to {len(audio_bytes)} PCM bytes")

            return audio_bytes

        except Exception as e:
            logger.error(f"Error converting AudioFrame to bytes: {e}", exc_info=True)
            raise
