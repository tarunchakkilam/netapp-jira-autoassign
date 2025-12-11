#!/usr/bin/env python3
"""
Simple prediction: Embed ticket → Match in ChromaDB → Predict team
"""
import os
import sys
import asyncio
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.enhanced_chroma_client import EnhancedTicketEmbeddingClient
from app.jira_client import JiraClient

load_dotenv()


def fetch_ticket_from_jira(ticket_key):
    """Fetch ticket from JIRA."""
    jira_client = JiraClient()
    ticket = jira_client.fetch_ticket(ticket_key)
    
    return {
        'key': ticket.get('key', ticket_key),
        'summary': ticket.get('summary', ''),
        'description': ticket.get('description', '')
    }


async def predict_team(ticket_key):
    """Predict team for a ticket."""
    
    print(f"🎯 PREDICTING TEAM FOR {ticket_key}")
    print("=" * 80)
    
    # Step 1: Fetch ticket
    print(f"\n📥 Step 1: Fetching ticket from JIRA...")
    ticket = fetch_ticket_from_jira(ticket_key)
    print(f"✅ Fetched: {ticket['summary'][:80]}...")
    
    # Step 2: Create content for embedding
    full_content = f"{ticket['summary']} {ticket['description']}"
    print(f"\n📝 Step 2: Prepared content ({len(full_content)} characters)")
    
    # Step 3: Initialize ChromaDB client
    print(f"\n🔌 Step 3: Connecting to ChromaDB...")
    client = EnhancedTicketEmbeddingClient()
    total_tickets = client.tickets_collection.count()
    print(f"✅ Connected. Database has {total_tickets} tickets")
    
    # Step 4: Generate embedding for the ticket
    print(f"\n🧮 Step 4: Generating embedding using LLM...")
    embedding = await client.generate_embedding(full_content)
    print(f"✅ Generated embedding vector (dimension: {len(embedding)})")
    
    # Step 5: Search ChromaDB for similar tickets
    print(f"\n🔍 Step 5: Searching ChromaDB for similar tickets...")
    results = client.tickets_collection.query(
        query_embeddings=[embedding],
        n_results=20
    )
    print(f"✅ Found {len(results['ids'][0])} similar tickets")
    
    # Step 6: Prepare similar tickets context for LLM
    print(f"\n� Step 6: Preparing context for LLM...")
    similar_tickets_context = []
    for i in range(len(results['ids'][0])):
        similar_tickets_context.append({
            "ticket_id": results['ids'][0][i],
            "team": results['metadatas'][0][i].get('team', 'unknown'),
            "summary": results['metadatas'][0][i].get('summary', 'N/A'),
            "distance": results['distances'][0][i]
        })
    
    # Step 7: Send to LLM for prediction
    print(f"\n🤖 Step 7: Sending to LLM for team prediction...")
    predicted_team, confidence, llm_reasoning = await client._predict_team_with_llm(
        new_ticket={
            "key": ticket_key,
            "summary": ticket['summary'],
            "description": ticket['description']
        },
        similar_tickets=similar_tickets_context
    )
    
    print(f"✅ LLM analysis complete")
    
    # Display results
    print("\n" + "=" * 80)
    print("📊 PREDICTION RESULTS (LLM-Based)")
    print("=" * 80)
    print(f"\n🎯 Predicted Team: {predicted_team.upper()}")
    print(f"📈 Confidence: {confidence:.1%}")
    print(f"\n💭 LLM Reasoning:")
    print(f"   {llm_reasoning}")
    
    print(f"\n� Vote Distribution (for reference):")
    team_votes = {}
    for ticket in similar_tickets_context:
        team = ticket['team']
        team_votes[team] = team_votes.get(team, 0) + 1
    for team, votes in sorted(team_votes.items(), key=lambda x: x[1], reverse=True):
        pct = votes / len(similar_tickets_context) * 100
        bar = '█' * int(pct / 2.5)
        print(f"   {team:25} {votes:2}/20 ({pct:5.1f}%) {bar}")
    
    print(f"\n📌 Top 10 Most Similar Tickets:")
    for i in range(min(10, len(results['ids'][0]))):
        ticket_id = results['ids'][0][i]
        team = results['metadatas'][0][i].get('team', 'unknown')
        summary = results['metadatas'][0][i].get('summary', 'N/A')[:70]
        distance = results['distances'][0][i]
        print(f"   {i+1:2}. {ticket_id:15} → {team:20} (dist: {distance:.4f})")
        print(f"       {summary}")
    
    print("\n" + "=" * 80)
    print(f"✅ RECOMMENDATION: Assign {ticket_key} to {predicted_team.upper()}")
    print("=" * 80)


if __name__ == '__main__':
    import sys
    ticket_key = sys.argv[1] if len(sys.argv) > 1 else 'NFSAAS-148554'
    asyncio.run(predict_team(ticket_key))
