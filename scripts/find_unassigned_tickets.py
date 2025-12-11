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
    
    # Get today's date in JIRA format
    from datetime import datetime
    today = datetime.now().strftime('%Y-%m-%d')
    
    # Search for bugs without Technical Owner created today
    jql = f'''
        project = NFSAAS 
        AND issuetype = Bug
        AND "Technical Owner" is EMPTY 
        AND created >= "{today}"
        ORDER BY created DESC
    '''
    
    print(f"🔍 Searching for unassigned bugs created today ({today})...")
    print(f"JQL: {jql}\n")
    
    try:
        result = await jira_client.search_issues(
            jql=jql,
            max_results=50,
            fields=['summary', 'created', 'status', 'customfield_16202']
        )
        
        tickets = result.get('issues', [])
        
        print(f"✅ Found {len(tickets)} unassigned bugs created today:")
        print("=" * 100)
        
        for ticket in tickets:
            key = ticket['key']
            summary = ticket['fields']['summary']
            created = ticket['fields']['created']  # Full timestamp
            status = ticket['fields']['status']['name']
            
            # Get hyperscaler info (customfield_16202 is an array)
            hyperscaler = ticket['fields'].get('customfield_16202', [])
            hyperscaler_value = 'N/A'
            if hyperscaler and isinstance(hyperscaler, list) and len(hyperscaler) > 0:
                hyperscaler_value = hyperscaler[0].get('value', 'N/A')
            
            print(f"🎫 {key:15} | {hyperscaler_value:8} | {status:12} | {created[:19]} | {summary[:50]}")
        
        return tickets
        
    except Exception as e:
        print(f"Error searching for tickets: {e}")
        return []


async def main():
    tickets = await find_unassigned_tickets()
    
    if tickets:
        print(f"\n{'='*100}")
        print(f"📊 Summary: {len(tickets)} unassigned bugs found")
        
        # Count by hyperscaler
        azure_count = 0
        other_count = 0
        for ticket in tickets:
            hyperscaler = ticket['fields'].get('customfield_16202', [])
            if hyperscaler and isinstance(hyperscaler, list) and len(hyperscaler) > 0:
                if hyperscaler[0].get('value', '').upper() == 'AZURE':
                    azure_count += 1
                else:
                    other_count += 1
            else:
                other_count += 1
        
        print(f"   Azure: {azure_count} tickets")
        print(f"   Other: {other_count} tickets")
        
        print(f"\n💡 You can test team assignment with:")
        print(f"   venv/bin/python3.11 scripts/simple_predict.py TICKET_KEY")
        print(f"\n🤖 Or run the scheduler to auto-assign:")
        print(f"   venv/bin/python3.11 scripts/auto_assign_scheduler.py")
    else:
        print("\n✅ No unassigned bugs found today - all caught up!")


if __name__ == "__main__":
    asyncio.run(main())