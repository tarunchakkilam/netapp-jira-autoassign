#!/usr/bin/env python3
"""
Show detailed team training data statistics from ChromaDB.
"""
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.enhanced_chroma_client import EnhancedTicketEmbeddingClient


def show_trained_teams():
    """Show which teams have training data in ChromaDB."""
    
    print("🎯 TRAINED TEAMS IN CHROMADB")
    print("=" * 70)
    
    client = EnhancedTicketEmbeddingClient()
    collection = client.chroma_client.get_collection('jira_tickets')
    
    # Get all tickets
    results = collection.get(include=['metadatas'])
    
    total_tickets = len(results['ids'])
    print(f"\n📊 Total Tickets in ChromaDB: {total_tickets}\n")
    
    # Count tickets per team
    team_counts = {}
    team_tickets = {}
    
    for ticket_id, metadata in zip(results['ids'], results['metadatas']):
        team = metadata.get('team', 'unknown')
        
        if team not in team_counts:
            team_counts[team] = 0
            team_tickets[team] = []
        
        team_counts[team] += 1
        team_tickets[team].append(ticket_id)
    
    # Sort by count
    sorted_teams = sorted(team_counts.items(), key=lambda x: x[1], reverse=True)
    
    print("📋 TEAMS WITH TRAINING DATA:")
    print("-" * 70)
    
    trained_teams = []
    untrained_teams = []
    
    for i, (team, count) in enumerate(sorted_teams, 1):
        if count > 0:
            trained_teams.append(team)
            percentage = (count / total_tickets) * 100
            bar = "█" * int(percentage / 2)
            
            print(f"{i:2}. {team:25} {count:4} tickets  {percentage:5.1f}% {bar}")
    
    print()
    print("=" * 70)
    print(f"✅ TRAINED TEAMS: {len(trained_teams)}")
    for team in trained_teams:
        print(f"   • {team}")
    
    # Show all 12 configured teams
    all_teams = [
        'team-mercury', 'team-nandi', 'team-sirius', 'team-supernova',
        'team-omega', 'team-rocket', 'team-tunnel-snakes', 'team-svl',
        'team-vega', 'team-phoenix', 'team-atlas', 'team-zeus'
    ]
    
    untrained = [t for t in all_teams if t not in trained_teams]
    
    if untrained:
        print(f"\n❌ UNTRAINED TEAMS (need more data): {len(untrained)}")
        for team in untrained:
            print(f"   • {team}")
    
    print()
    print("=" * 70)
    
    # Show sample tickets from each trained team
    print("\n📝 SAMPLE TICKETS FROM EACH TRAINED TEAM:")
    print("-" * 70)
    
    for team in trained_teams[:5]:  # Show top 5 teams
        sample_tickets = team_tickets[team][:3]
        print(f"\n{team} (showing 3/{len(team_tickets[team])} tickets):")
        for ticket_id in sample_tickets:
            # Get metadata for this ticket
            idx = results['ids'].index(ticket_id)
            metadata = results['metadatas'][idx]
            summary = metadata.get('summary', 'No summary')[:60]
            keywords = metadata.get('keywords', '')
            
            print(f"   • {ticket_id}: {summary}...")
            if keywords:
                print(f"     🔑 {keywords}")


if __name__ == "__main__":
    show_trained_teams()