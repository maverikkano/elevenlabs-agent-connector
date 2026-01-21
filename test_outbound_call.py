#!/usr/bin/env python3
"""
Test script to initiate an outbound Twilio call to a customer
"""
import requests
import json

# Your API configuration
API_URL = "http://localhost:8000/twilio/outbound-call"
API_KEY = "test_key_123"  # Replace with your actual API key from .env

# Customer data
payload = {
    "agent_id": "agent_7201keyx3brmfk68gdwytc6a4tna",  # Your ElevenLabs agent ID
    "session_id": "test-outbound-001",
    "metadata": {
        "to_number": "+918698760751",  # Customer's phone number to call
        "dynamic_variables": {
            "name": "Sumit Sharma",
            "due_date": "30th January 2026",
            "total_enr_amount": "25000",
            "emi_eligibility": True,
            "waiver_eligible": False,
            "emi_eligible": True
        }
    }
}

# Make the API call
headers = {
    "X-API-Key": API_KEY,
    "Content-Type": "application/json"
}

try:
    print("Initiating outbound call...")
    print(f"To: {payload['metadata']['to_number']}")
    print(f"Customer: {payload['metadata']['dynamic_variables']['name']}")
    print()

    response = requests.post(API_URL, json=payload, headers=headers)

    if response.status_code == 200:
        result = response.json()
        print("✅ Call initiated successfully!")
        print(f"Call SID: {result['call_sid']}")
        print(f"Status: {result['status']}")
        print(f"To: {result['to']}")
    else:
        print(f"❌ Error: {response.status_code}")
        print(response.text)

except Exception as e:
    print(f"❌ Exception: {e}")
