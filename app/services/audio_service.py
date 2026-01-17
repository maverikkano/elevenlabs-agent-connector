import asyncio
import logging
import sounddevice as sd
import numpy as np
import json
import base64
from typing import Optional

logger = logging.getLogger(__name__)

# Audio configuration for ElevenLabs: 16kHz mono PCM
SAMPLE_RATE = 16000
CHANNELS = 1
DTYPE = np.int16
CHUNK_DURATION = 0.1
CHUNK_SIZE = int(SAMPLE_RATE * CHUNK_DURATION)


class MicrophoneStreamer:
    def __init__(self):
        self.is_streaming = False
        self.websocket = None
        self.audio_queue = asyncio.Queue()

    async def stream_to_websocket(self, websocket, dynamic_variables=None):
        self.websocket = websocket
        self.is_streaming = True
        logger.info("Starting microphone audio stream")

        try:
            # IMPORTANT: First message must include dynamic_variables
            if dynamic_variables is None:
                dynamic_variables = {
                    "name": "Sam",
                    "due_date": "3rd January 2026",
                    "total_enr_amount": "25000",
                    "emi_eligibility": True,
                    "waiver_eligible": False,
                    "emi_eligible": True
                }

            init_message = {
                "type": "conversation_initiation_client_data",
                "dynamic_variables": dynamic_variables
            }
            await self.websocket.send(json.dumps(init_message))
            logger.info(f"Sent initialization with dynamic variables: {list(dynamic_variables.keys())}")

            send_task = asyncio.create_task(self._send_audio())
            receive_task = asyncio.create_task(self._receive_audio())
            await asyncio.gather(send_task, receive_task)

        except Exception as e:
            logger.error(f"Error during audio streaming: {str(e)}")
            raise
        finally:
            await self.stop()

    async def _send_audio(self):
        logger.info("Starting microphone capture")

        def audio_callback(indata, frames, time_info, status):
            if status:
                logger.warning(f"Audio input status: {status}")
            audio_bytes = indata.tobytes()
            try:
                self.audio_queue.put_nowait(audio_bytes)
            except asyncio.QueueFull:
                logger.warning("Audio queue full, dropping frame")

        with sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype=DTYPE,
            blocksize=CHUNK_SIZE,
            callback=audio_callback
        ):
            logger.info("Microphone stream started")

            while self.is_streaming:
                try:
                    audio_chunk = await asyncio.wait_for(self.audio_queue.get(), timeout=1.0)

                    # Send as JSON with base64-encoded audio
                    audio_base64 = base64.b64encode(audio_chunk).decode('utf-8')
                    message = {"user_audio_chunk": audio_base64}
                    await self.websocket.send(json.dumps(message))

                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    logger.error(f"Error sending audio: {str(e)}")
                    self.is_streaming = False
                    break

        logger.info("Microphone capture stopped")

    async def _receive_audio(self):
        logger.info("Starting to receive audio from agent")

        try:
            while self.is_streaming:
                message = await self.websocket.recv()

                if isinstance(message, str):
                    try:
                        data = json.loads(message)

                        if "audio_event" in data:
                            audio_base64 = data["audio_event"].get("audio_base_64", "")
                            if audio_base64:
                                audio_bytes = base64.b64decode(audio_base64)
                                logger.debug(f"Received audio chunk: {len(audio_bytes)} bytes")

                                # Play agent audio through speakers
                                audio_array = np.frombuffer(audio_bytes, dtype=DTYPE)
                                sd.play(audio_array, samplerate=SAMPLE_RATE, blocking=False)
                                logger.debug("Playing audio chunk")

                        elif "conversation_initiation_metadata_event" in data:
                            logger.info(f"Conversation metadata: {data}")

                        elif "interruption_event" in data:
                            logger.info("User interrupted agent")

                        elif "ping_event" in data:
                            pong = {"pong_event": {"event_id": data["ping_event"].get("event_id", 0)}}
                            await self.websocket.send(json.dumps(pong))

                        else:
                            logger.info(f"Received event from agent: {list(data.keys())}")

                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse JSON message: {message[:100]}")

                elif isinstance(message, bytes):
                    logger.debug(f"Received binary audio chunk: {len(message)} bytes")

                else:
                    logger.warning(f"Received unexpected message type: {type(message)}")

        except Exception as e:
            logger.error(f"Error receiving audio: {str(e)}")
            self.is_streaming = False

        logger.info("Stopped receiving audio from agent")

    async def stop(self):
        logger.info("Stopping microphone streamer")
        self.is_streaming = False

        if self.websocket:
            try:
                await self.websocket.close()
                logger.info("WebSocket connection closed")
            except Exception as e:
                logger.error(f"Error closing WebSocket: {str(e)}")

        self.websocket = None


async def start_conversation_stream(websocket, duration: Optional[int] = None, dynamic_variables: Optional[dict] = None):
    streamer = MicrophoneStreamer()

    try:
        if duration:
            await asyncio.wait_for(
                streamer.stream_to_websocket(websocket, dynamic_variables),
                timeout=duration
            )
        else:
            await streamer.stream_to_websocket(websocket, dynamic_variables)

        return {"status": "completed", "message": "Conversation stream completed successfully"}

    except asyncio.TimeoutError:
        logger.info(f"Conversation stream completed after {duration} seconds")
        await streamer.stop()
        return {"status": "completed", "message": f"Conversation stream completed after {duration} seconds"}

    except Exception as e:
        logger.error(f"Error in conversation stream: {str(e)}")
        await streamer.stop()
        raise
