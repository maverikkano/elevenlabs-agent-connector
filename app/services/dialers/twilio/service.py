"""
Twilio dialer service implementation

Main service class combining all Twilio components.
"""

import logging
from typing import Dict
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

from app.services.dialers.base import (
    DialerService,
    AudioConverter,
    MessageBuilder,
    ConnectionHandler
)
from app.services.dialers.twilio.audio_converter import TwilioAudioConverter
from app.services.dialers.twilio.message_builder import TwilioMessageBuilder
from app.services.dialers.twilio.connection_handler import TwilioConnectionHandler
from app.config import settings

logger = logging.getLogger(__name__)


class TwilioDialerService(DialerService):
    """
    Twilio dialer service

    Implements the DialerService interface for Twilio.
    """

    def get_audio_converter(self) -> AudioConverter:
        """Get Twilio audio converter"""
        return TwilioAudioConverter()

    def get_message_builder(self) -> MessageBuilder:
        """Get Twilio message builder"""
        return TwilioMessageBuilder()

    def get_connection_handler(self) -> ConnectionHandler:
        """Get Twilio connection handler"""
        return TwilioConnectionHandler()

    async def initiate_outbound_call(
        self,
        to_number: str,
        agent_id: str,
        dynamic_variables: Dict,
        websocket_url: str
    ) -> Dict:
        """
        Initiate outbound call using Twilio

        Args:
            to_number: Phone number to call (E.164 format)
            agent_id: ElevenLabs agent ID
            dynamic_variables: Variables to pass to agent
            websocket_url: WebSocket URL for media streaming

        Returns:
            Dict with call details

        Raises:
            TwilioRestException: If Twilio API call fails
        """
        try:
            # Initialize Twilio client
            client = Client(settings.twilio_account_sid, settings.twilio_auth_token)

            # Build custom parameters for TwiML
            custom_params = {
                "agent_id": agent_id,
                "to_number": to_number,
                **dynamic_variables
            }
            logger.info(f"Custom parameters for TwiML: {custom_params}")

            # Build TwiML with Stream parameters
            twiml = self.message_builder.build_connection_response(
                websocket_url=websocket_url,
                custom_params=custom_params
            )

            logger.info(f"Initiating Twilio call to {to_number}")
            logger.info(f"TwiML:\n{twiml}")

            # Make outbound call
            call = client.calls.create(
                from_=settings.twilio_phone_number,
                to=to_number,
                twiml=twiml
            )

            logger.info(f"✅ Twilio call initiated - CallSid: {call.sid}")

            return {
                "success": True,
                "call_id": call.sid,
                "to": to_number,
                "from": settings.twilio_phone_number,
                "status": call.status,
                "message": "Outbound call initiated successfully"
            }

        except TwilioRestException as e:
            logger.error(f"Twilio API error: {e.msg} (Code: {e.code})")
            return {
                "success": False,
                "call_id": None,
                "status": "failed",
                "message": f"Twilio error: {e.msg}",
                "error_code": e.code
            }

        except Exception as e:
            logger.error(f"Error initiating Twilio call: {e}", exc_info=True)
            return {
                "success": False,
                "call_id": None,
                "status": "failed",
                "message": f"Failed to initiate call: {str(e)}"
            }

    def get_dialer_name(self) -> str:
        """Return dialer provider name"""
        return "twilio"

    def validate_config(self) -> bool:
        """
        Validate Twilio configuration

        Returns:
            True if configuration is valid, False otherwise
        """
        if not settings.twilio_account_sid:
            logger.error("Twilio Account SID not configured")
            return False

        if not settings.twilio_auth_token:
            logger.error("Twilio Auth Token not configured")
            return False

        if not settings.twilio_phone_number:
            logger.error("Twilio Phone Number not configured")
            return False

        # Validate format of credentials
        if not settings.twilio_account_sid.startswith("AC"):
            logger.error("Invalid Twilio Account SID format")
            return False

        # Basic phone number validation (E.164 format)
        if not settings.twilio_phone_number.startswith("+"):
            logger.error("Twilio phone number must be in E.164 format (+country code)")
            return False

        return True
