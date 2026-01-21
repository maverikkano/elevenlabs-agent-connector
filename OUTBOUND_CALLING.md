# Outbound Calling with Twilio

This guide explains how to make outbound calls from Twilio to customers, connecting them to your ElevenLabs AI agent.

## Architecture

```
Your System (API Call) → Twilio → Calls Customer's Phone
                                         ↓
                              Customer Answers
                                         ↓
                          Twilio connects to your WebSocket
                                         ↓
                      Your Gateway ↔ ElevenLabs Agent
                                         ↓
                          Customer ↔ AI Agent conversation
```

## How It Works

1. **Your system** calls the `/twilio/outbound-call` API endpoint with customer data
2. **Twilio** makes an outbound call to the customer's phone number
3. **When customer answers**, Twilio connects to your WebSocket endpoint (`/twilio/media-stream`)
4. **Your gateway** bridges the call to ElevenLabs agent
5. **Customer** has a conversation with the AI agent

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

This includes the new `twilio==8.10.0` package.

### 2. Configure Environment Variables

Make sure your `.env` file has Twilio credentials:

```env
# Twilio Configuration
TWILIO_ACCOUNT_SID=your_account_sid_here
TWILIO_AUTH_TOKEN=your_auth_token_here
TWILIO_PHONE_NUMBER=+1234567890

# Other settings
ELEVENLABS_API_KEY=your_api_key
API_KEYS=test_key_123
ENVIRONMENT=development
HOST=0.0.0.0
PORT=8000
```

### 3. Start the Server

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## API Endpoint

### `POST /twilio/outbound-call`

Initiates an outbound call to a customer.

**Headers:**
```
X-API-Key: test_key_123
Content-Type: application/json
```

**Request Body:**
```json
{
  "agent_id": "agent_7201keyx3brmfk68gdwytc6a4tna",
  "session_id": "optional-session-id",
  "metadata": {
    "to_number": "+919876543210",
    "dynamic_variables": {
      "name": "Sumit Sharma",
      "due_date": "30th January 2026",
      "total_enr_amount": "25000",
      "emi_eligibility": true,
      "waiver_eligible": false,
      "emi_eligible": true
    }
  }
}
```

**Required Fields:**
- `agent_id`: Your ElevenLabs agent ID
- `metadata.to_number`: Customer's phone number (E.164 format: +[country code][number])

**Optional Fields:**
- `session_id`: Custom session identifier
- `metadata.dynamic_variables`: Custom data to pass to the agent

**Response (Success):**
```json
{
  "success": true,
  "call_sid": "CA1234567890abcdef",
  "to": "+919876543210",
  "status": "queued",
  "message": "Outbound call initiated successfully"
}
```

**Response (Error):**
```json
{
  "detail": "Error message"
}
```

## Testing

### Quick Test

Use the provided test script:

```bash
python test_outbound_call.py
```

**Before running:**
1. Edit `test_outbound_call.py` and update:
   - `API_KEY` with your actual API key
   - `to_number` with a valid phone number you own
   - `agent_id` with your ElevenLabs agent ID

### Bulk Calling

For calling multiple customers:

```bash
python bulk_outbound_calls.py
```

**Features:**
- Reads customer list from the script (can be adapted for CSV)
- Adds delay between calls (configurable)
- Shows success/failure statistics
- Prevents rate limiting

### Manual cURL Test

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
        "total_enr_amount": "25000",
        "emi_eligibility": true,
        "waiver_eligible": false
      }
    }
  }'
```

## Production Deployment

### 1. Deploy to Public Server

Your server must be publicly accessible for Twilio to connect to the WebSocket.

**Options:**
- Cloud provider (AWS, GCP, Azure)
- VPS (DigitalOcean, Linode)
- Serverless (Railway, Render)

### 2. Use WSS (Secure WebSocket)

Update `.env`:
```env
ENVIRONMENT=production
HOST=your-domain.com
```

The code automatically switches to `wss://` in production mode.

### 3. Update Twilio Configuration

No additional Twilio configuration needed! The outbound call includes the TwiML with your WebSocket URL automatically.

## Use Cases

### 1. Debt Collection Reminders
```python
{
  "to_number": "+919876543210",
  "dynamic_variables": {
    "name": "John Doe",
    "due_date": "15th February 2026",
    "total_enr_amount": "50000",
    "emi_eligibility": true
  }
}
```

### 2. Appointment Reminders
```python
{
  "to_number": "+919876543210",
  "dynamic_variables": {
    "name": "Sarah Smith",
    "appointment_date": "20th January 2026",
    "appointment_time": "10:30 AM",
    "doctor_name": "Dr. Patel"
  }
}
```

### 3. Survey/Feedback Collection
```python
{
  "to_number": "+919876543210",
  "dynamic_variables": {
    "name": "Mike Johnson",
    "order_id": "ORD-12345",
    "product_name": "Wireless Headphones"
  }
}
```

## Integration with N8N

### Workflow Example

1. **Trigger**: Scheduled (e.g., every day at 9 AM)
2. **Database Query**: Fetch customers with pending payments
3. **HTTP Request** to your API:
   - Method: `POST`
   - URL: `https://your-domain.com/twilio/outbound-call`
   - Headers: `X-API-Key`, `Content-Type`
   - Body: Customer data from database

4. **Error Handling**: Log failed calls

### N8N HTTP Request Node Configuration

```
Method: POST
URL: https://your-domain.com/twilio/outbound-call
Authentication: None (using header)

Headers:
  X-API-Key: test_key_123
  Content-Type: application/json

Body (JSON):
{
  "agent_id": "{{$node["Customer Query"].json["agent_id"]}}",
  "metadata": {
    "to_number": "{{$node["Customer Query"].json["phone"]}}",
    "dynamic_variables": {
      "name": "{{$node["Customer Query"].json["name"]}}",
      "due_date": "{{$node["Customer Query"].json["due_date"]}}",
      "total_enr_amount": "{{$node["Customer Query"].json["amount"]}}"
    }
  }
}
```

## Monitoring

### Check Call Status

You can check the call status in Twilio Console:
1. Go to **Monitor** → **Logs** → **Calls**
2. Search by Call SID (returned in API response)
3. View call duration, status, and recordings

### Application Logs

Monitor your application logs for:
- `Media stream started` - Call connected to WebSocket
- `Connecting to ElevenLabs agent` - Agent connection initiated
- `Sent initialization to ElevenLabs` - Agent received customer data
- `User said:` - Customer speech transcriptions
- `Agent response:` - Agent responses

## Troubleshooting

### Error: "Twilio credentials not configured"
- Check your `.env` file has `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER`
- Restart the server after updating `.env`

### Error: "to_number is required"
- Make sure `metadata.to_number` is included in your request
- Phone number must be in E.164 format: `+[country code][number]`

### Call connects but no audio
- Check WebSocket URL is publicly accessible
- Verify you're using `wss://` in production (not `ws://`)
- Check firewall allows WebSocket connections

### Agent doesn't receive dynamic variables
- Check logs for "Sent initialization to ElevenLabs"
- Verify dynamic variables match your agent's configuration
- Ensure variables are properly formatted (strings, booleans, numbers)

### Call fails immediately
- Verify Twilio phone number is active and can make outbound calls
- Check destination number is valid and reachable
- Review Twilio call logs for detailed error messages

## Rate Limiting

Twilio has rate limits for outbound calls:
- **Default**: 1 call per second
- **With verification**: Higher limits available

**Best Practices:**
- Add delays between calls (3-5 seconds recommended)
- Use the bulk calling script with `DELAY_BETWEEN_CALLS`
- Contact Twilio support to increase limits for production

## Cost Considerations

Twilio charges for:
- **Outbound calls**: $0.013 - $0.10 per minute (varies by country)
- **Phone number**: ~$1 per month
- **Additional fees**: May apply for certain countries

**Cost Optimization:**
- Use shorter conversations where possible
- Implement call timeout limits
- Monitor call durations in Twilio console

## Difference: Inbound vs Outbound

| Feature | Inbound (`/twilio/incoming-call`) | Outbound (`/twilio/outbound-call`) |
|---------|-----------------------------------|-------------------------------------|
| **Initiated by** | Customer calls your Twilio number | Your system calls customer |
| **Use case** | Customer support hotline | Proactive outreach, reminders |
| **Data passing** | Hardcoded or DB lookup by phone | Passed in API request |
| **Twilio config** | Configure in Phone Numbers settings | No Twilio config needed |
| **Testing** | Call your Twilio number | Call API endpoint |

## Next Steps

1. **Test with your own phone number** first
2. **Configure ElevenLabs agent** with appropriate prompts and dynamic variables
3. **Set up production deployment** with public domain
4. **Integrate with your CRM/database** for dynamic customer data
5. **Monitor and optimize** based on call success rates

## Support

For issues:
- Application bugs: Check logs and error messages
- Twilio issues: Check Twilio Console → Monitor → Logs
- ElevenLabs issues: Check ElevenLabs dashboard
