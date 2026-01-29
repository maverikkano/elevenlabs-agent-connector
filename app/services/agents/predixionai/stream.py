"""
PredixionAI Voice Agent Stream

Handles LiveKit Room connection and bidirectional audio streaming.
"""

import logging
import asyncio
from typing import AsyncGenerator, Dict, Any, Optional
from livekit import rtc

from app.services.agents.base import AgentStream
from app.services.agents.types import AgentEvent, AgentEventTypes
from app.services.agents.predixionai.message_handler import PredixionAIMessageHandler

logger = logging.getLogger(__name__)


class PredixionAIAgentStream(AgentStream):
    """
    PredixionAI implementation of AgentStream using LiveKit.
    Connects to LiveKit room and manages audio track publishing/subscribing.
    """

    def __init__(
        self,
        room_token: str,
        websocket_url: str,
        message_handler: PredixionAIMessageHandler,
        call_id: str,
        dynamic_variables: Dict[str, Any]
    ):
        """
        Initialize PredixionAI stream.

        Args:
            room_token: LiveKit room access token
            websocket_url: LiveKit server WebSocket URL
            message_handler: Message handler for audio conversion
            call_id: Unique call identifier
            dynamic_variables: Context variables for the session
        """
        logger.info(f"[{call_id}] Initializing PredixionAI stream")
        logger.debug(f"[{call_id}] WebSocket URL: {websocket_url}")
        logger.debug(f"[{call_id}] Dynamic variables: {list(dynamic_variables.keys())}")

        self.room_token = room_token
        self.websocket_url = websocket_url
        self.message_handler = message_handler
        self.call_id = call_id
        self.dynamic_variables = dynamic_variables

        # LiveKit components
        self.room: Optional[rtc.Room] = None
        self.audio_source: Optional[rtc.AudioSource] = None
        self.audio_track: Optional[rtc.LocalAudioTrack] = None

        # Queue for receiving audio from agent
        self.audio_queue: asyncio.Queue = asyncio.Queue()
        self._receive_task: Optional[asyncio.Task] = None
        self._connected = False

        logger.info(f"[{call_id}] PredixionAI stream initialized")

    async def initialize(self) -> None:
        """
        Initialize LiveKit connection and publish audio track.
        Called once after creation, before any audio is sent.
        """
        logger.info(f"[{self.call_id}] 🚀 Starting LiveKit connection initialization")

        try:
            # Step 1: Create Room instance
            logger.debug(f"[{self.call_id}] Creating LiveKit Room instance")
            self.room = rtc.Room()

            # Step 2: Set up event handlers
            logger.debug(f"[{self.call_id}] Setting up LiveKit event handlers")
            self._setup_event_handlers()

            # Step 3: Connect to LiveKit room
            logger.info(f"[{self.call_id}] Connecting to LiveKit room at {self.websocket_url}")
            await self.room.connect(self.websocket_url, self.room_token)
            self._connected = True
            logger.info(f"[{self.call_id}] ✅ Connected to LiveKit room: {self.room.name}")

            # Step 4: Create audio source (16kHz mono)
            logger.debug(f"[{self.call_id}] Creating audio source (16kHz mono)")
            self.audio_source = rtc.AudioSource(sample_rate=16000, num_channels=1)
            logger.debug(f"[{self.call_id}] Audio source created")

            # Step 5: Create local audio track
            logger.debug(f"[{self.call_id}] Creating local audio track")
            self.audio_track = rtc.LocalAudioTrack.create_audio_track(
                "gateway-audio",
                self.audio_source
            )
            logger.debug(f"[{self.call_id}] Local audio track created: gateway-audio")

            # Step 6: Publish track to room
            logger.info(f"[{self.call_id}] Publishing audio track to room")
            publication = await self.room.local_participant.publish_track(self.audio_track)
            logger.info(f"[{self.call_id}] ✅ Audio track published: {publication.sid}")

            logger.info(f"[{self.call_id}] 🎉 LiveKit initialization complete")

        except Exception as e:
            logger.error(f"[{self.call_id}] ❌ Failed to initialize LiveKit connection: {e}", exc_info=True)
            self._connected = False
            raise

    def _setup_event_handlers(self) -> None:
        """Set up LiveKit room event handlers with detailed logging."""
        logger.debug(f"[{self.call_id}] Registering LiveKit event handlers")

        @self.room.on("participant_connected")
        def on_participant_connected(participant: rtc.RemoteParticipant):
            logger.info(f"[{self.call_id}] 👤 Participant connected: {participant.identity} (sid: {participant.sid})")
            logger.debug(f"[{self.call_id}] Participant name: {participant.name}")

        @self.room.on("participant_disconnected")
        def on_participant_disconnected(participant: rtc.RemoteParticipant):
            logger.info(f"[{self.call_id}] 👋 Participant disconnected: {participant.identity}")

        @self.room.on("track_published")
        def on_track_published(publication: rtc.RemoteTrackPublication, participant: rtc.RemoteParticipant):
            logger.info(
                f"[{self.call_id}] 📢 Track published by {participant.identity}: "
                f"{publication.kind} (sid: {publication.sid})"
            )

        @self.room.on("track_subscribed")
        def on_track_subscribed(
            track: rtc.Track,
            publication: rtc.RemoteTrackPublication,
            participant: rtc.RemoteParticipant
        ):
            logger.info(
                f"[{self.call_id}] 🎧 Track subscribed from {participant.identity}: "
                f"{track.kind} (sid: {track.sid})"
            )

            # If it's an audio track from the agent, start consuming it
            if isinstance(track, rtc.RemoteAudioTrack):
                logger.info(f"[{self.call_id}] 🔊 Starting audio consumption from agent")
                asyncio.create_task(self._consume_agent_audio(track, participant.identity))

        @self.room.on("track_unsubscribed")
        def on_track_unsubscribed(
            track: rtc.Track,
            publication: rtc.RemoteTrackPublication,
            participant: rtc.RemoteParticipant
        ):
            logger.info(f"[{self.call_id}] 🔇 Track unsubscribed from {participant.identity}: {track.kind}")

        @self.room.on("disconnected")
        def on_disconnected():
            logger.info(f"[{self.call_id}] 📡 Disconnected from LiveKit room")
            self._connected = False

        logger.debug(f"[{self.call_id}] All event handlers registered")

    async def _consume_agent_audio(self, track: rtc.RemoteAudioTrack, participant_identity: str) -> None:
        """
        Consume audio frames from agent's track and queue them for receive().

        Args:
            track: Remote audio track from agent
            participant_identity: Identity of the participant (agent)
        """
        logger.info(f"[{self.call_id}] 🎵 Starting audio frame consumption from {participant_identity}")
        frame_count = 0

        try:
            # Create AudioStream from track to iterate over frames
            audio_stream = rtc.AudioStream(track)

            async for frame_event in audio_stream:
                frame = frame_event.frame
                frame_count += 1

                if frame_count % 50 == 0:  # Log every 50 frames to avoid spam
                    logger.debug(
                        f"[{self.call_id}] Received audio frame #{frame_count} from agent: "
                        f"{frame.samples_per_channel} samples"
                    )

                # Convert frame to bytes and queue
                audio_bytes = self.message_handler._audio_frame_to_bytes(frame)
                await self.audio_queue.put(audio_bytes)

        except Exception as e:
            logger.error(f"[{self.call_id}] ❌ Error consuming agent audio: {e}", exc_info=True)
            # Put error in queue
            await self.audio_queue.put(AgentEvent(type=AgentEventTypes.ERROR, data=str(e), error=e))

        logger.info(f"[{self.call_id}] 🛑 Audio consumption ended (total frames: {frame_count})")

    async def send_audio(self, audio_data: bytes) -> None:
        """
        Send PCM audio chunk to LiveKit room.

        Args:
            audio_data: PCM 16kHz mono 16-bit signed little-endian bytes
        """
        if not self._connected or not self.audio_source:
            logger.warning(f"[{self.call_id}] ⚠️ Cannot send audio: not connected or no audio source")
            return

        try:
            # Convert bytes to AudioFrame
            frame = self.message_handler.build_audio_message(audio_data)

            # Capture frame to audio source (publishes to room)
            await self.audio_source.capture_frame(frame)

            # Log periodically to avoid spam (every ~1 second at 20ms frames)
            if hasattr(self, '_send_count'):
                self._send_count += 1
                if self._send_count % 50 == 0:
                    logger.debug(f"[{self.call_id}] 📤 Sent {self._send_count} audio frames to agent")
            else:
                self._send_count = 1
                logger.debug(f"[{self.call_id}] 📤 Sending audio to agent via LiveKit track")

        except Exception as e:
            logger.error(f"[{self.call_id}] ❌ Error sending audio to LiveKit: {e}", exc_info=True)
            raise

    async def receive(self) -> AsyncGenerator[AgentEvent, None]:
        """
        Yield audio events from agent.
        Reads from the audio queue populated by track subscription.
        """
        logger.info(f"[{self.call_id}] 🎧 Starting to receive audio events from agent")
        event_count = 0

        try:
            while self._connected or not self.audio_queue.empty():
                try:
                    # Wait for audio with timeout to allow checking connection status
                    audio_data = await asyncio.wait_for(self.audio_queue.get(), timeout=1.0)

                    event_count += 1
                    if event_count % 50 == 0:
                        logger.debug(f"[{self.call_id}] 📥 Received event #{event_count} from agent")

                    # If it's already an AgentEvent (error), yield it
                    if isinstance(audio_data, AgentEvent):
                        yield audio_data
                    else:
                        # Otherwise, wrap as audio event
                        yield AgentEvent(type=AgentEventTypes.AUDIO, data=audio_data)

                except asyncio.TimeoutError:
                    # No audio received, check if still connected
                    if not self._connected:
                        logger.info(f"[{self.call_id}] Connection closed, ending receive loop")
                        break
                    continue

        except Exception as e:
            logger.error(f"[{self.call_id}] ❌ Error in receive loop: {e}", exc_info=True)
            yield AgentEvent(type=AgentEventTypes.ERROR, data=str(e), error=e)

        logger.info(f"[{self.call_id}] 🛑 Receive loop ended (total events: {event_count})")

    async def close(self) -> None:
        """Close the LiveKit connection and cleanup resources."""
        logger.info(f"[{self.call_id}] 🔌 Closing PredixionAI LiveKit connection")

        try:
            # Mark as disconnected
            self._connected = False

            # Unpublish track
            if self.audio_track and self.room and self.room.local_participant:
                logger.debug(f"[{self.call_id}] Unpublishing audio track")
                try:
                    await self.room.local_participant.unpublish_track(self.audio_track)
                    logger.debug(f"[{self.call_id}] Audio track unpublished")
                except Exception as e:
                    logger.warning(f"[{self.call_id}] Error unpublishing track: {e}")

            # Disconnect from room
            if self.room:
                logger.debug(f"[{self.call_id}] Disconnecting from LiveKit room")
                try:
                    await self.room.disconnect()
                    logger.info(f"[{self.call_id}] ✅ Disconnected from LiveKit room")
                except Exception as e:
                    logger.warning(f"[{self.call_id}] Error disconnecting from room: {e}")

            logger.info(f"[{self.call_id}] ✅ PredixionAI connection closed successfully")

        except Exception as e:
            logger.error(f"[{self.call_id}] ❌ Error closing PredixionAI connection: {e}", exc_info=True)
