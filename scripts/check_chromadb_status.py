#!/usr/bin/env python3
"""
Check ChromaDB status and data availability.
"""
import os
import sys
import asyncio

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.enhanced_chroma_client import EnhancedTicketEmbeddingClient


async def check_chromadb_status():
    """Check ChromaDB collection status and data."""
    
    print("🔍 CHECKING CHROMADB STATUS")
    print("=" * 50)
    
    try:
        client = EnhancedTicketEmbeddingClient()
        
        # Get collection
        collection = client.chroma_client.get_collection('jira_tickets')
        count = collection.count()
        
        print(f"📊 COLLECTION STATS:")
        print(f"   Collection: jira_tickets")
        print(f"   Total tickets: {count}")
        
        if count > 0:
            # Get sample data
            sample = collection.peek(limit=10)
            
            print(f"\n📋 SAMPLE TICKETS:")
            if sample.get('ids'):
                for i, ticket_id in enumerate(sample['ids'][:10]):
                    metadata = sample.get('metadatas', [{}])[i] if i < len(sample.get('metadatas', [])) else {}
                    team = metadata.get('team', 'unknown')
                    summary = metadata.get('summary', 'no summary')[:50]
                    print(f"   {i+1:2d}. {ticket_id:<15} -> {team:<15} | {summary}...")
            
            # Check if we can query
            print(f"\n🔍 TESTING SEMANTIC SEARCH:")
            try:
                test_queries = [
                    "pipeline failing",
                    "cvt jobs",
                    "azure netapp",
                    "volume management"
                ]
                
                for query in test_queries:
                    results = collection.query(
                        query_texts=[query], 
                        n_results=3,
                        include=['metadatas', 'distances']
                    )
                    
                    print(f"\n   Query: '{query}'")
                    if results['ids'][0]:
                        for i, (ticket_id, distance) in enumerate(zip(results['ids'][0], results['distances'][0])):
                            similarity = 1 - distance
                            metadata = results['metadatas'][0][i] if i < len(results['metadatas'][0]) else {}
                            team = metadata.get('team', 'unknown')
                            print(f"     {i+1}. {ticket_id}: {team} (similarity: {similarity:.3f})")
                    else:
                        print(f"     No results found")
                        
            except Exception as e:
                print(f"   ❌ Query error: {e}")
            
            # Test assignment system
            print(f"\n🎯 TESTING ASSIGNMENT SYSTEM:")
            try:
                # Test with a real ticket
                result = await client.assign_team_with_fine_tuning(
                    "NFSAAS-148591",
                    similarity_threshold=0.1,  # Lower threshold
                    min_similar_tickets=1,     # Lower requirement
                    enable_fine_tuning=True
                )
                
                print(f"   Assignment result: {result.get('status') if result else 'None'}")
                if result:
                    print(f"   Recommended team: {result.get('recommended_team', 'None')}")
                    print(f"   Final score: {result.get('final_score', 0.0):.3f}")
                    print(f"   Similar tickets: {result.get('num_similar_tickets', 0)}")
                    print(f"   Keyword boost: {result.get('keyword_boost', 0.0):.3f}")
                    
                    if result.get('similar_tickets'):
                        print(f"   Top similar tickets:")
                        for ticket in result['similar_tickets'][:3]:
                            print(f"     - {ticket.get('ticket_id', 'unknown')}: {ticket.get('team', 'unknown')} (score: {ticket.get('similarity_score', 0.0):.3f})")
                
            except Exception as e:
                print(f"   ❌ Assignment error: {e}")
                import traceback
                traceback.print_exc()
        
        else:
            print("   ⚠️  No tickets found in ChromaDB!")
            print("   This explains why we're only using keyword matching.")
            
        # Check collection metadata
        try:
            collection_info = client.chroma_client.get_collection('jira_tickets')
            print(f"\n📝 COLLECTION INFO:")
            print(f"   Name: {collection_info.name}")
            print(f"   ID: {collection_info.id}")
            # print(f"   Metadata: {collection_info.metadata}")
            
        except Exception as e:
            print(f"   Info error: {e}")
            
    except Exception as e:
        print(f"❌ ChromaDB Error: {e}")
        import traceback
        traceback.print_exc()


async def main():
    await check_chromadb_status()
    
    print(f"\n{'='*50}")
    print("🎯 ANALYSIS COMPLETE")
    print("If ChromaDB has sufficient data but assignment still fails,")
    print("we may need to adjust similarity thresholds or debug the assignment logic.")


if __name__ == "__main__":
    asyncio.run(main())