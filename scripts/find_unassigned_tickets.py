#!/usr/bin/env python3
"""
Find tickets without Technical Owner assigned for testing.
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from app.jira_client import JiraClient


async def find_unassigned_tickets():
    """Find recent tickets without Technical Owner."""
    
    jira_client = JiraClient()
    
    # Search for tickets without Technical Owner
    jql = '''
        project = NFSAAS 
        AND "Technical Owner" is EMPTY 
        AND created >= -30d
        ORDER BY created DESC
    '''
    
    try:
        result = await jira_client.search_issues(
            jql=jql,
            max_results=10,
            fields=['summary', 'created', 'status']
        )
        
        tickets = result.get('issues', [])
        
        print(f"Found {len(tickets)} tickets without Technical Owner:")
        print("=" * 60)
        
        for ticket in tickets:
            key = ticket['key']
            summary = ticket['fields']['summary']
            created = ticket['fields']['created'][:10]  # Date part only
            status = ticket['fields']['status']['name']
            
            print(f"{key} - {summary[:50]}... ({status}, {created})")
        
        return tickets
        
    except Exception as e:
        print(f"Error searching for tickets: {e}")
        return []


async def main():
    tickets = await find_unassigned_tickets()
    
    if tickets:
        print(f"\nYou can test team assignment with any of these tickets:")
        print("python scripts/test_team_assignment.py TICKET_KEY")
    else:
        print("\nNo unassigned tickets found in the last 30 days.")


if __name__ == "__main__":
    asyncio.run(main())