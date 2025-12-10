#!/usr/bin/env python3
"""
Enhanced ChromaDB client with fine-tuning capabilities for better team assignment accuracy.
"""
import os
import sys
import json
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import chromadb
from chromadb.config import Settings
import httpx
from openai import OpenAI

from app.jira_client import JiraClient


class EnhancedTicketEmbeddingClient:
    """Enhanced ChromaDB client with fine-tuning capabilities."""
    
    def __init__(self, host: str = "localhost", port: int = 8000):
        """Initialize the enhanced client."""
        self.host = host
        self.port = port
        
        # Initialize ChromaDB client
        self.chroma_client = chromadb.HttpClient(
            host=host,
            port=port,
            settings=Settings(allow_reset=True)
        )
        
        # Initialize other clients
        self.jira_client = JiraClient()
        self.llm_client = self._init_llm_client()
        
        # Collection names
        self.tickets_collection_name = "jira_tickets"
        
        # Initialize collections
        self._init_collections()
        
        # Fine-tuning parameters
        self.team_expertise_weights = self._load_team_expertise_weights()
        self.component_weights = self._load_component_weights()
        self.keyword_team_mapping = self._load_keyword_team_mapping()
    
    def _init_llm_client(self) -> OpenAI:
        """Initialize OpenAI client for embeddings."""
        api_key = os.getenv('NETAPP_LLM_API_KEY')
        if not api_key:
            raise ValueError("NETAPP_LLM_API_KEY not set in environment")
        
        import httpx
        httpx_client = httpx.Client(verify=False, timeout=60.0)
        
        return OpenAI(
            base_url=os.getenv('NETAPP_LLM_BASE_URL', 'https://llm-proxy-api.ai.openeng.netapp.com'),
            api_key=api_key,
            http_client=httpx_client
        )
    
    def _init_collections(self):
        """Initialize ChromaDB collections."""
        try:
            self.tickets_collection = self.chroma_client.get_collection(
                name=self.tickets_collection_name
            )
            print(f"✅ Connected to existing tickets collection: {self.tickets_collection_name}")
        except Exception:
            self.tickets_collection = self.chroma_client.create_collection(
                name=self.tickets_collection_name,
                metadata={"description": "Jira ticket embeddings for team assignment"}
            )
            print(f"✅ Created new tickets collection: {self.tickets_collection_name}")
    
    def _load_team_expertise_weights(self) -> Dict[str, Dict[str, float]]:
        """Load team expertise weights for fine-tuning."""
        return {
            "Team Nandi": {
                "smb": 1.5,           # Strong SMB expertise
                "cifs": 1.5,          # CIFS protocol expertise
                "kerberos": 1.4,      # Authentication expertise
                "domain": 1.3,        # Domain integration
                "nfsv4": 1.4,         # NFSv4 protocol expertise
                "volume_creation": 1.2, # Volume creation knowledge
                "security": 1.3,      # Security vulnerabilities
                "fedramp": 1.4        # FedRAMP compliance
            },
            "Team ANF PaS": {
                "scale": 1.4,         # Scaling operations
                "infrastructure": 1.5, # Infrastructure management
                "workload": 1.3,      # Workload management
                "cost": 1.2,          # Cost optimization
                "ste": 1.4,           # STE workloads
                "fluentd": 1.3        # Logging infrastructure
            },
            "Team Himalaya": {
                "backup": 1.5,        # Backup operations
                "delete": 1.4,        # Deletion operations
                "cleanup": 1.3,       # Resource cleanup
                "progress": 1.2       # Progress/status issues
            }
        }
    
    def _load_component_weights(self) -> Dict[str, str]:
        """Load component to team mappings."""
        return {
            "SMB": "Team Nandi",
            "CIFS": "Team Nandi", 
            "NFS": "Team Nandi",
            "Kerberos": "Team Nandi",
            "Scale": "Team ANF PaS",
            "Infrastructure": "Team ANF PaS",
            "Backup": "Team Himalaya",
            "Volume Management": "Team Nandi"
        }
    
    def _load_keyword_team_mapping(self) -> Dict[str, List[Tuple[str, float]]]:
        """Load keyword to team mappings with weights."""
        return {
            "smb": [("Team Nandi", 1.5)],
            "cifs": [("Team Nandi", 1.5)],
            "kerberos": [("Team Nandi", 1.4)],
            "nfsv4": [("Team Nandi", 1.4)],
            "domain": [("Team Nandi", 1.3)],
            "volume creation": [("Team Nandi", 1.2)],
            "scale": [("Team ANF PaS", 1.4)],
            "infrastructure": [("Team ANF PaS", 1.5)],
            "workload": [("Team ANF PaS", 1.3)],
            "backup": [("Team Himalaya", 1.5)],
            "delete": [("Team Himalaya", 1.4)]
        }
    
    def _calculate_keyword_boost(self, ticket_content: str, team: str) -> float:
        """Calculate keyword-based boost for a team."""
        content_lower = ticket_content.lower()
        boost = 0.0
        
        for keyword, team_weights in self.keyword_team_mapping.items():
            if keyword in content_lower:
                for mapped_team, weight in team_weights:
                    if mapped_team == team:
                        boost += weight * 0.1  # Scale down the boost
        
        return min(boost, 0.3)  # Cap the boost at 0.3
    
    def _calculate_component_boost(self, components: List[str], team: str) -> float:
        """Calculate component-based boost for a team."""
        boost = 0.0
        
        for component in components:
            if component in self.component_weights:
                preferred_team = self.component_weights[component]
                if preferred_team == team:
                    boost += 0.15  # Add boost for matching component
        
        return min(boost, 0.2)  # Cap the boost at 0.2
    
    def prepare_ticket_content(self, ticket: Dict[str, Any]) -> str:
        """Prepare ticket content for embedding."""
        content_parts = []
        
        if ticket.get('summary'):
            content_parts.append(f"Title: {ticket['summary']}")
        
        if ticket.get('description'):
            desc = ticket['description'][:1000]
            content_parts.append(f"Description: {desc}")
        
        if ticket.get('components'):
            components = ', '.join([c['name'] if isinstance(c, dict) else str(c) for c in ticket['components']])
            content_parts.append(f"Components: {components}")
        
        if ticket.get('labels'):
            labels = ', '.join(ticket['labels'])
            content_parts.append(f"Labels: {labels}")
        
        if ticket.get('issuetype'):
            issue_type = ticket['issuetype']['name'] if isinstance(ticket['issuetype'], dict) else str(ticket['issuetype'])
            content_parts.append(f"Issue Type: {issue_type}")
        
        if ticket.get('priority'):
            priority = ticket['priority']['name'] if isinstance(ticket['priority'], dict) else str(ticket['priority'])
            content_parts.append(f"Priority: {priority}")
        
        return "\n".join(content_parts)
    
    async def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for given text using NetApp LLM."""
        try:
            user = os.getenv('JIRA_EMAIL', '').split('@')[0] if os.getenv('JIRA_EMAIL') else 'embedding_client'
            
            response = self.llm_client.embeddings.create(
                model="text-embedding-ada-002",
                input=text.strip(),
                user=user
            )
            
            return response.data[0].embedding
            
        except Exception as e:
            print(f"Error generating embedding: {e}")
            raise
    
    def find_similar_tickets(
        self, 
        query_embedding: List[float], 
        n_results: int = 20,
        where_filter: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Find similar tickets using vector similarity search."""
        try:
            results = self.tickets_collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                where=where_filter,
                include=['metadatas', 'documents', 'distances']
            )
            
            return {
                'ids': results['ids'][0],
                'distances': results['distances'][0],
                'metadatas': results['metadatas'][0],
                'documents': results['documents'][0]
            }
            
        except Exception as e:
            print(f"Error finding similar tickets: {e}")
            return {'ids': [], 'distances': [], 'metadatas': [], 'documents': []}
    
    async def assign_team_with_fine_tuning(
        self, 
        ticket_key: str, 
        similarity_threshold: float = 0.6,
        min_similar_tickets: int = 2,
        enable_fine_tuning: bool = True
    ) -> Dict[str, Any]:
        """Enhanced team assignment with fine-tuning capabilities."""
        try:
            # Get ticket data
            print(f"Fetching ticket data for {ticket_key}...")
            result = await self.jira_client.search_issues(
                jql=f'key = {ticket_key}',
                max_results=1,
                fields=['summary', 'description', 'components', 'labels', 'issuetype', 
                       'priority', 'status', 'created', 'updated', 'customfield_15906', 'project']
            )
            
            if not result.get('issues'):
                return {"error": f"Ticket {ticket_key} not found"}
            
            ticket_data = result['issues'][0]['fields']
            ticket_data['key'] = ticket_key
            
            # Check if already has Technical Owner
            current_owner = ticket_data.get('customfield_15906')
            if current_owner:
                return {
                    "ticket": ticket_key,
                    "status": "already_assigned",
                    "current_owner": current_owner
                }
            
            # Generate embedding
            content = self.prepare_ticket_content(ticket_data)
            query_embedding = await self.generate_embedding(content)
            
            # Find similar tickets
            similar_results = self.find_similar_tickets(
                query_embedding=query_embedding,
                n_results=25,
                where_filter={"technical_owner": {"$ne": "Unassigned"}}
            )
            
            # Analyze team assignments with fine-tuning
            team_scores = {}
            valid_matches = 0
            
            for i, (ticket_id, distance, metadata) in enumerate(zip(
                similar_results['ids'],
                similar_results['distances'], 
                similar_results['metadatas']
            )):
                similarity = 1 - distance
                
                if similarity >= similarity_threshold:
                    valid_matches += 1
                    team = metadata.get('technical_owner', 'Unknown')
                    
                    if team not in team_scores:
                        team_scores[team] = {
                            'base_score': 0,
                            'keyword_boost': 0,
                            'component_boost': 0,
                            'final_score': 0,
                            'count': 0,
                            'max_similarity': 0,
                            'tickets': []
                        }
                    
                    # Base similarity score
                    base_score = similarity * (1 - i * 0.02)
                    team_scores[team]['base_score'] += base_score
                    team_scores[team]['count'] += 1
                    team_scores[team]['max_similarity'] = max(team_scores[team]['max_similarity'], similarity)
                    team_scores[team]['tickets'].append({
                        'ticket': ticket_id,
                        'similarity': round(similarity, 3)
                    })
            
            if valid_matches < min_similar_tickets:
                return {
                    "ticket": ticket_key,
                    "status": "insufficient_data",
                    "message": f"Only {valid_matches} similar tickets found (minimum: {min_similar_tickets})"
                }
            
            # Apply fine-tuning if enabled
            components = [c['name'] if isinstance(c, dict) else str(c) for c in ticket_data.get('components', [])]
            
            if enable_fine_tuning:
                for team in team_scores:
                    # Calculate boosts
                    keyword_boost = self._calculate_keyword_boost(content, team)
                    component_boost = self._calculate_component_boost(components, team)
                    
                    team_scores[team]['keyword_boost'] = keyword_boost
                    team_scores[team]['component_boost'] = component_boost
                    
                    # Calculate final score
                    avg_base = team_scores[team]['base_score'] / team_scores[team]['count']
                    final_score = avg_base + keyword_boost + component_boost
                    team_scores[team]['final_score'] = final_score
            else:
                # No fine-tuning, just use base scores
                for team in team_scores:
                    team_scores[team]['keyword_boost'] = 0.0
                    team_scores[team]['component_boost'] = 0.0
                    team_scores[team]['final_score'] = team_scores[team]['base_score'] / team_scores[team]['count']
            
            if not team_scores:
                return {
                    "ticket": ticket_key,
                    "status": "no_teams_found",
                    "message": "No teams found in similar tickets"
                }
            
            # Select best team based on final score
            best_team = max(team_scores.items(), key=lambda x: x[1]['final_score'])
            recommended_team = best_team[0]
            team_data = best_team[1]
            
            return {
                "ticket": ticket_key,
                "status": "recommendation_ready",
                "recommended_team": recommended_team,
                "final_score": team_data['final_score'],
                "base_score": team_data['base_score'] / team_data['count'],
                "keyword_boost": team_data['keyword_boost'],
                "component_boost": team_data['component_boost'],
                "similar_tickets_count": valid_matches,
                "fine_tuning_enabled": enable_fine_tuning,
                "team_analysis": {
                    team: {
                        'final_score': data['final_score'],
                        'base_score': data['base_score'] / data['count'],
                        'keyword_boost': data['keyword_boost'],
                        'component_boost': data['component_boost'],
                        'ticket_count': data['count'],
                        'max_similarity': data['max_similarity']
                    }
                    for team, data in team_scores.items()
                },
                "ticket_summary": ticket_data.get('summary', ''),
                "components": components
            }
            
        except Exception as e:
            print(f"Error in enhanced team assignment: {e}")
            return {"error": f"Assignment failed: {str(e)}"}


async def test_fine_tuning():
    """Test the fine-tuning system."""
    print("🔧 Testing Enhanced Team Assignment with Fine-Tuning")
    print("=" * 70)
    
    client = EnhancedTicketEmbeddingClient()
    
    # Test NFSAAS-148554 with and without fine-tuning
    ticket_key = "NFSAAS-148554"
    
    print(f"Testing ticket: {ticket_key}")
    print("ANF[WestUS2-Stage]: SMB volume creation failing")
    print("\n" + "-" * 50)
    
    # Test without fine-tuning
    print("🔸 WITHOUT Fine-Tuning:")
    result_no_tuning = await client.assign_team_with_fine_tuning(
        ticket_key=ticket_key,
        enable_fine_tuning=False
    )
    
    if result_no_tuning.get("status") == "recommendation_ready":
        print(f"   Recommended: {result_no_tuning['recommended_team']}")
        print(f"   Score: {result_no_tuning['final_score']:.3f}")
    
    print("\n" + "-" * 50)
    
    # Test with fine-tuning
    print("🔧 WITH Fine-Tuning:")
    result_with_tuning = await client.assign_team_with_fine_tuning(
        ticket_key=ticket_key,
        enable_fine_tuning=True
    )
    
    if result_with_tuning.get("status") == "recommendation_ready":
        print(f"   Recommended: {result_with_tuning['recommended_team']}")
        print(f"   Final Score: {result_with_tuning['final_score']:.3f}")
        print(f"   Base Score: {result_with_tuning['base_score']:.3f}")
        print(f"   Keyword Boost: {result_with_tuning['keyword_boost']:.3f}")
        print(f"   Component Boost: {result_with_tuning['component_boost']:.3f}")
        
        print(f"\n📊 Top 3 Teams (Fine-Tuned):")
        team_analysis = result_with_tuning.get('team_analysis', {})
        for team, data in sorted(team_analysis.items(), key=lambda x: x[1]['final_score'], reverse=True)[:3]:
            print(f"   {team}:")
            print(f"     Final: {data['final_score']:.3f} = Base: {data['base_score']:.3f} + Keyword: {data['keyword_boost']:.3f} + Component: {data['component_boost']:.3f}")


if __name__ == "__main__":
    asyncio.run(test_fine_tuning())