#!/usr/bin/env python3
"""
Simple script to fetch and print full JSON response from JIRA API for a given ticket.
Usage: python scripts/print_jira_json.py TICKET-KEY
Example: python scripts/print_jira_json.py NFSAAS-148711
"""

import sys
import json
import httpx
import os
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

JIRA_BASE_URL = os.getenv("JIRA_BASE_URL", "https://jira.ngage.netapp.com")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN")

if not JIRA_API_TOKEN:
    print("❌ Error: JIRA_API_TOKEN not found in environment variables")
    sys.exit(1)


def fetch_jira_json(ticket_key: str) -> dict:
    """Fetch full JSON response from JIRA API for a ticket."""
    url = f"{JIRA_BASE_URL}/rest/api/2/issue/{ticket_key}"
    
    headers = {
        "Authorization": f"Bearer {JIRA_API_TOKEN}",
        "Accept": "application/json"
    }
    
    print(f"🔍 Fetching JIRA ticket: {ticket_key}")
    print(f"📍 URL: {url}\n")
    
    response = httpx.get(url, headers=headers, timeout=30.0)
    
    if response.status_code == 200:
        return response.json()
    else:
        print(f"❌ Error: HTTP {response.status_code}")
        print(f"Response: {response.text}")
        sys.exit(1)


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/print_jira_json.py TICKET-KEY")
        print("Example: python scripts/print_jira_json.py NFSAAS-148711")
        sys.exit(1)
    
    ticket_key = sys.argv[1]
    
    # Fetch JSON from JIRA
    data = fetch_jira_json(ticket_key)
    
    # Print formatted JSON
    print("=" * 80)
    print(f"FULL JSON RESPONSE FOR {ticket_key}")
    print("=" * 80)
    print(json.dumps(data, indent=2, default=str))
    print("=" * 80)
    
    # Print some key fields for convenience
    print("\n📋 KEY FIELDS:")
    print(f"  ID: {data.get('id')}")
    print(f"  Key: {data.get('key')}")
    print(f"  Summary: {data['fields'].get('summary')}")
    print(f"  Issue Type: {data['fields'].get('issuetype', {}).get('name')}")
    print(f"  Project: {data['fields'].get('project', {}).get('key')}")
    print(f"  Hyperscaler Array (customfield_16202): {data['fields'].get('customfield_16202')}")
    print(f"  Hyperscaler Dict (customfield_17090): {data['fields'].get('customfield_17090')}")
    print(f"  Cloud Provider (customfield_18216): {data['fields'].get('customfield_18216')}")
    print(f"  Technical Owner (customfield_10050): {data['fields'].get('customfield_10050')}")
    print()


if __name__ == "__main__":
    main()
