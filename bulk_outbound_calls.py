#!/usr/bin/env python3
"""
Bulk outbound calling script
Reads customer data from CSV and initiates calls
"""
import requests
import json
import csv
import time
from typing import List, Dict

# Configuration
API_URL = "http://localhost:8000/twilio/outbound-call"
API_KEY = "test_key_123"  # Replace with your actual API key
AGENT_ID = "agent_7201keyx3brmfk68gdwytc6a4tna"  # Your ElevenLabs agent ID
DELAY_BETWEEN_CALLS = 5  # Seconds between each call

# Sample customer data (you can replace this with CSV reading)
customers = [
    {
        "phone": "+919876543210",
        "name": "Sumit Sharma",
        "due_date": "30th January 2026",
        "total_enr_amount": "25000",
        "emi_eligibility": True,
        "waiver_eligible": False
    },
    {
        "phone": "+919123456789",
        "name": "Priya Patel",
        "due_date": "5th February 2026",
        "total_enr_amount": "40000",
        "emi_eligibility": True,
        "waiver_eligible": True
    },
    # Add more customers here
]


def initiate_call(customer: Dict) -> bool:
    """
    Initiate a call to a single customer

    Args:
        customer: Dictionary with customer data

    Returns:
        True if successful, False otherwise
    """
    payload = {
        "agent_id": AGENT_ID,
        "session_id": f"bulk-{customer['phone']}-{int(time.time())}",
        "metadata": {
            "to_number": customer["phone"],
            "dynamic_variables": {
                "name": customer["name"],
                "due_date": customer["due_date"],
                "total_enr_amount": customer["total_enr_amount"],
                "emi_eligibility": customer["emi_eligibility"],
                "waiver_eligible": customer.get("waiver_eligible", False),
                "emi_eligible": customer.get("emi_eligibility", False),
                "caller_number": customer["phone"]
            }
        }
    }

    headers = {
        "X-API-Key": API_KEY,
        "Content-Type": "application/json"
    }

    try:
        print(f"📞 Calling {customer['name']} at {customer['phone']}...")

        response = requests.post(API_URL, json=payload, headers=headers)

        if response.status_code == 200:
            result = response.json()
            print(f"   ✅ Success - Call SID: {result['call_sid']}")
            return True
        else:
            print(f"   ❌ Failed - Status: {response.status_code}")
            print(f"   Error: {response.text}")
            return False

    except Exception as e:
        print(f"   ❌ Exception: {e}")
        return False


def main():
    """Main function to process all customers"""
    print("=" * 60)
    print("Bulk Outbound Call Campaign")
    print("=" * 60)
    print(f"Total customers: {len(customers)}")
    print(f"Delay between calls: {DELAY_BETWEEN_CALLS}s")
    print("=" * 60)
    print()

    success_count = 0
    failure_count = 0

    for i, customer in enumerate(customers, 1):
        print(f"[{i}/{len(customers)}]", end=" ")

        if initiate_call(customer):
            success_count += 1
        else:
            failure_count += 1

        # Wait before next call (except for last one)
        if i < len(customers):
            print(f"   ⏳ Waiting {DELAY_BETWEEN_CALLS}s before next call...")
            time.sleep(DELAY_BETWEEN_CALLS)

        print()

    # Summary
    print("=" * 60)
    print("Campaign Summary")
    print("=" * 60)
    print(f"✅ Successful calls: {success_count}")
    print(f"❌ Failed calls: {failure_count}")
    print(f"📊 Success rate: {(success_count/len(customers)*100):.1f}%")
    print("=" * 60)


if __name__ == "__main__":
    main()
