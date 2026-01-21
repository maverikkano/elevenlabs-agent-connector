# Quick Start: Outbound Calling

Get your first outbound call working in 5 minutes!

## 1. Install the Twilio SDK

```bash
pip install twilio==8.10.0
```

Or install all dependencies:
```bash
pip install -r requirements.txt
```

## 2. Configure Environment

Add to your `.env` file:

```env
# Twilio Configuration
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_auth_token_here
TWILIO_PHONE_NUMBER=+1234567890

# ElevenLabs
ELEVENLABS_API_KEY=your_api_key

# API Keys
API_KEYS=test_key_123

# Server settings
ENVIRONMENT=development
HOST=0.0.0.0
PORT=8000
```

## 3. Start the Server

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## 4. Test Outbound Call

### Option A: Use the Test Script

1. Edit `test_outbound_call.py`:
   ```python
   # Update these values
   API_KEY = "test_key_123"  # From your .env

   payload = {
       "agent_id": "agent_7201keyx3brmfk68gdwytc6a4tna",  # Your ElevenLabs agent ID
       "metadata": {
           "to_number": "+919876543210",  # Phone number to call
           "dynamic_variables": {
               "name": "Test Customer"
           }
       }
   }
   ```

2. Run it:
   ```bash
   python test_outbound_call.py
   ```

### Option B: Use cURL

```bash
curl -X POST http://localhost:8000/twilio/outbound-call \
  -H "X-API-Key: test_key_123" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "agent_7201keyx3brmfk68gdwytc6a4tna",
    "metadata": {
      "to_number": "+919876543210",
      "dynamic_variables": {
        "name": "Test Customer",
        "due_date": "30th January 2026",
        "total_enr_amount": "25000"
      }
    }
  }'
```

## 5. What Happens Next

1. ✅ API returns call SID immediately
2. 📞 Twilio calls the phone number
3. 🎧 Customer answers
4. 🔗 Twilio connects to your WebSocket
5. 🤖 Your gateway bridges to ElevenLabs
6. 💬 Customer talks to AI agent!

## Expected Response

```json
{
  "success": true,
  "call_sid": "CA1234567890abcdef",
  "to": "+919876543210",
  "status": "queued",
  "message": "Outbound call initiated successfully"
}
```

## Monitor the Call

Watch your server logs:
```
INFO:     Twilio WebSocket connection established
INFO:     Media stream started - CallSid: CA123..., StreamSid: MZ456...
INFO:     Using custom parameters from outbound call
INFO:     Connecting to ElevenLabs agent agent_7201...
INFO:     Sent initialization to ElevenLabs
INFO:     User said: Hello, who is this?
INFO:     Agent response: Hi! I'm calling from...
```

## Common Issues

### "Twilio credentials not configured"
- Double-check your `.env` file
- Restart the server after updating `.env`

### "to_number is required"
- Make sure you include `metadata.to_number` in the request
- Use E.164 format: `+[country code][number]`

### Call doesn't connect
- Verify your Twilio account is active
- Check you have sufficient Twilio credits
- Ensure destination number is valid

## Next Steps

1. ✅ **Test successfully**: You're ready for production!
2. 📖 **Read full docs**: [OUTBOUND_CALLING.md](OUTBOUND_CALLING.md)
3. 🚀 **Deploy**: Deploy to a public server
4. 🔄 **Automate**: Integrate with N8N or your CRM
5. 📊 **Monitor**: Track calls in Twilio Console

## Need Help?

- **Full documentation**: [OUTBOUND_CALLING.md](OUTBOUND_CALLING.md)
- **Twilio integration**: [TWILIO_INTEGRATION.md](TWILIO_INTEGRATION.md)
- **Main README**: [README.md](README.md)
