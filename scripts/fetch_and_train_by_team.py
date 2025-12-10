#!/usr/bin/env python3
"""
Fetch actual tickets assigned to each team from JIRA and train embeddings.
No keyword detection - use actual team assignments from JIRA.
"""
import os
import sys
import json
import asyncio
from datetime import datetime, timedelta
from jira import JIRA
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables from .env file
load_dotenv()

from app.enhanced_chroma_client import EnhancedTicketEmbeddingClient


# 12 NFSAAS teams to train
TEAMS = [
    'team-cit',
    'team-himalaya',
    'team-mercury',
    'team-meteor',
    'team-nandi',
    'team-omega',
    'team-rocket',
    'team-sirius',
    'team-supernova',
    'team-svl',
    'team-tunnel-snakes',
    'team-vega'
]


def connect_jira():
    """Connect to JIRA using credentials from .env file."""
    jira_url = os.getenv('JIRA_BASE_URL', 'https://jira.ngage.netapp.com')
    jira_token = os.getenv('JIRA_API_TOKEN')
    use_bearer = os.getenv('JIRA_USE_BEARER_AUTH', 'false').lower() == 'true'
    
    if not jira_token:
        raise ValueError("Please set JIRA_API_TOKEN in .env file")
    
    print(f"🔐 Connecting to JIRA: {jira_url}")
    
    if use_bearer:
        print(f"� Using Bearer authentication")
        # Bearer token authentication
        jira = JIRA(server=jira_url, token_auth=jira_token)
    else:
        jira_user = os.getenv('JIRA_EMAIL')
        if not jira_user:
            raise ValueError("Please set JIRA_EMAIL in .env file for basic auth")
        print(f"�👤 User: {jira_user} (Basic Auth)")
        jira = JIRA(server=jira_url, basic_auth=(jira_user, jira_token))
    
    print("✅ Connected to JIRA\n")
    return jira


def fetch_team_tickets(jira, team_name, days=90):
    """
    Fetch tickets assigned to a specific team from last N days.
    
    Args:
        jira: JIRA client
        team_name: Team name (e.g., 'team-mercury')
        days: Number of days to look back (default 90)
    
    Returns:
        List of ticket dictionaries
    """
    # Calculate date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    start_date_str = start_date.strftime('%Y-%m-%d')
    
    print(f"📥 Fetching tickets for {team_name} from {start_date_str}...")
    
    # Format team name for Technical Owner field (capitalize properly)
    # Convert 'team-mercury' to 'Team Mercury' format
    team_display = ' '.join(word.capitalize() for word in team_name.split('-'))
    
    # JQL query to find tickets assigned to this team via Technical Owner field
    jql = f'''
        "Technical Owner" = "{team_display}" AND 
        created >= "{start_date_str}" 
        ORDER BY created DESC
    '''
    
    try:
        # Fetch tickets in batches
        tickets = []
        start_at = 0
        max_results = 100
        
        while True:
            batch = jira.search_issues(
                jql,
                startAt=start_at,
                maxResults=max_results,
                fields='key,summary,description,created,labels,assignee,status,priority'
            )
            
            if not batch:
                break
            
            for issue in batch:
                ticket = {
                    'key': issue.key,
                    'summary': issue.fields.summary or '',
                    'description': issue.fields.description or '',
                    'created': str(issue.fields.created),
                    'assignee': str(issue.fields.assignee) if issue.fields.assignee else 'Unassigned',
                    'status': str(issue.fields.status),
                    'priority': str(issue.fields.priority) if issue.fields.priority else 'None',
                    'team': team_name
                }
                tickets.append(ticket)
            
            if len(batch) < max_results:
                break
            
            start_at += max_results
        
        print(f"   ✅ Found {len(tickets)} tickets for {team_name}")
        return tickets
    
    except Exception as e:
        print(f"   ⚠️  Error fetching tickets for {team_name}: {e}")
        return []


async def train_with_team_tickets():
    """Fetch tickets from JIRA for each team and train embeddings."""
    
    print("🎯 TRAINING SYSTEM WITH ACTUAL TEAM ASSIGNMENTS")
    print("=" * 80)
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    print("📋 TEAMS TO TRAIN:")
    for i, team in enumerate(TEAMS, 1):
        print(f"   {i:2}. {team}")
    print()
    
    # Connect to JIRA
    try:
        jira = connect_jira()
    except Exception as e:
        print(f"❌ Failed to connect to JIRA: {e}")
        print("⚠️  Please set JIRA_USER and JIRA_TOKEN environment variables")
        return
    
    # Fetch tickets for each team
    print("🔍 FETCHING TICKETS FROM JIRA (Last 90 Days)")
    print("-" * 80)
    
    all_tickets = []
    team_counts = {}
    
    for team in TEAMS:
        tickets = fetch_team_tickets(jira, team, days=90)
        team_counts[team] = len(tickets)
        all_tickets.extend(tickets)
    
    print(f"\n📊 TOTAL TICKETS FETCHED: {len(all_tickets)}\n")
    
    if not all_tickets:
        print("❌ No tickets found! Check your JQL query and Technical Owner field.")
        return
    
    # Save tickets to file for reference
    output_file = 'data/team_assigned_tickets_90days.json'
    os.makedirs('data', exist_ok=True)
    with open(output_file, 'w') as f:
        json.dump(all_tickets, f, indent=2)
    print(f"💾 Saved tickets to: {output_file}\n")
    
    # Initialize embedding client
    print("🧹 CLEANING UP CHROMADB")
    print("-" * 80)
    client = EnhancedTicketEmbeddingClient()
    
    try:
        client.chroma_client.delete_collection('jira_tickets')
        print("✅ Deleted existing collection")
    except:
        print("ℹ️  No existing collection to delete")
    
    collection = client.chroma_client.create_collection(
        name='jira_tickets',
        metadata={"description": "NFSAAS tickets from actual team assignments - 12 teams"}
    )
    print("✅ Created fresh collection\n")
    
    # Train with fetched tickets
    print("🚀 TRAINING WITH TEAM-ASSIGNED TICKETS")
    print("-" * 80)
    print(f"📦 Total tickets to process: {len(all_tickets)}")
    print(f"⏱️  Estimated time: ~{(len(all_tickets) * 2) // 60} minutes\n")
    
    # Process in batches
    batch_size = 50
    successful = 0
    failed = 0
    
    for i in range(0, len(all_tickets), batch_size):
        batch = all_tickets[i:i + batch_size]
        batch_num = i // batch_size + 1
        total_batches = (len(all_tickets) + batch_size - 1) // batch_size
        
        print(f"📦 Batch {batch_num}/{total_batches} - Processing tickets {i+1} to {min(i+batch_size, len(all_tickets))}...")
        
        batch_successful = 0
        batch_failed = 0
        
        for j, ticket in enumerate(batch):
            try:
                # Create full text for embedding
                full_text = f"{ticket['summary']} {ticket['description']}"
                
                # Truncate if too long (to prevent token overflow)
                if len(full_text) > 6000:
                    full_text = full_text[:6000]
                
                # Generate embedding
                embedding = await client.generate_embedding(full_text)
                
                # Add to ChromaDB with team assignment
                collection.add(
                    ids=[ticket['key']],
                    embeddings=[embedding],
                    documents=[full_text],
                    metadatas=[{
                        'team': ticket['team'],
                        'summary': ticket['summary'][:200],
                        'created': ticket['created'],
                        'status': ticket['status']
                    }]
                )
                successful += 1
                batch_successful += 1
                
                # Show progress within batch every 10 tickets
                if (j + 1) % 10 == 0:
                    print(f"   ✓ {j + 1}/{len(batch)} tickets in this batch")
                
            except Exception as e:
                print(f"   ⚠️  Failed {ticket['key']}: {str(e)[:80]}")
                failed += 1
                batch_failed += 1
        
        print(f"   ✅ Batch complete: {batch_successful} successful, {batch_failed} failed")
        print(f"   📊 Overall progress: {successful}/{len(all_tickets)} ({(successful/len(all_tickets)*100):.1f}%)\n")
    
    # Summary
    print("=" * 80)
    print("🎉 TRAINING COMPLETE!")
    print("=" * 80)
    print(f"✅ Successfully trained: {successful} tickets")
    print(f"❌ Failed: {failed} tickets")
    print(f"📈 Success Rate: {(successful/len(all_tickets)*100):.1f}%\n")
    
    print("📊 TICKETS PER TEAM:")
    print("-" * 80)
    for team in sorted(team_counts.keys()):
        count = team_counts[team]
        bar = '█' * (count // 5) if count > 0 else ''
        print(f"   {team:25} {count:4} tickets {bar}")
    
    print("\n" + "=" * 80)
    print(f"End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)


if __name__ == '__main__':
    asyncio.run(train_with_team_tickets())
