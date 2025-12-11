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
import httpx
from openai import OpenAI

from app.jira_client import JiraClient


class EnhancedTicketEmbeddingClient:
    """Enhanced ChromaDB client with fine-tuning capabilities."""
    
    # Team name mapping: database format -> JIRA format
    TEAM_NAME_MAPPING = {
        "team-nandi": "Team Nandi",
        "team-himalaya": "Team Himalaya",
        "team-kilimanjaro": "Team Kilimanjaro",
        "team-fuji": "Team Fuji",
        "team-rushmore": "Team Rushmore",
        "team-k2": "Team K2",
        "team-everest": "Team Everest",
        "team-matterhorn": "Team Matterhorn",
        "team-supernova": "Team Supernova",
        "team-denali": "Team Denali",
        "team-elbrus": "Team Elbrus",
    }
    
    def __init__(self, host: str = "localhost", port: int = 8000):
        """Initialize the enhanced client."""
        self.host = host
        self.port = port
        
        # Initialize ChromaDB client (v1.x API)
        self.chroma_client = chromadb.HttpClient(
            host=host,
            port=port
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
    
    def _normalize_team_name(self, team_name: str) -> str:
        """
        Convert team name from database format to JIRA format.
        E.g., 'team-nandi' -> 'Team Nandi'
        """
        # Try exact match first
        if team_name in self.TEAM_NAME_MAPPING:
            return self.TEAM_NAME_MAPPING[team_name]
        
        # Try case-insensitive match
        team_lower = team_name.lower()
        for db_name, jira_name in self.TEAM_NAME_MAPPING.items():
            if db_name.lower() == team_lower:
                return jira_name
        
        # Fallback: title case with spaces instead of hyphens
        return team_name.replace('-', ' ').replace('_', ' ').title()
    
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
    
    def send_email_notification(self, ticket_key: str, result: Dict[str, Any], error: str = None):
        """
        Send email notification with prediction results.
        
        Args:
            ticket_key: JIRA ticket key
            result: Prediction result dictionary
            error: Error message if assignment failed
        """
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        
        # Get email configuration from environment
        smtp_server = os.getenv('SMTP_SERVER')
        smtp_port = int(os.getenv('SMTP_PORT', 25))
        smtp_user = os.getenv('SMTP_USER')
        smtp_password = os.getenv('SMTP_PASSWORD', '')
        notification_email = os.getenv('NOTIFICATION_EMAIL', 'tc12411@netapp.com')
        
        if not smtp_server or not smtp_user:
            print("⚠️  SMTP not configured (missing SMTP_SERVER or SMTP_USER), skipping email notification")
            return
        
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            
            if error:
                # Failure email
                msg['Subject'] = f"❌ JIRA Ticket Assignment Failed: {ticket_key}"
                html_body = f"""
                <html>
                <body style="font-family: Arial, sans-serif; line-height: 1.6;">
                    <h2 style="color: #d32f2f;">❌ Ticket Assignment Failed</h2>
                    <p><strong>Ticket:</strong> <a href="https://jira.netapp.com/browse/{ticket_key}">{ticket_key}</a></p>
                    <p><strong>Error:</strong> {error}</p>
                    <p>Please manually review and assign this ticket.</p>
                </body>
                </html>
                """
            else:
                # Success email
                predicted_team = result.get('recommended_team', result.get('predicted_team', 'Unknown'))
                confidence = result.get('base_score', result.get('confidence', 0)) * 100
                llm_reasoning = result.get('llm_reasoning', 'N/A')
                similar_tickets = result.get('similar_tickets', [])
                
                msg['Subject'] = f"✅ JIRA Ticket Auto-Assigned: {ticket_key}"
                
                # Build similar tickets HTML
                similar_html = ""
                for i, ticket in enumerate(similar_tickets[:5], 1):
                    similar_html += f"""
                    <div style="margin: 5px 0; padding: 10px; background: #f5f5f5; border-radius: 5px;">
                        <strong>{i}. {ticket['ticket_id']}</strong> → {ticket['team']} (distance: {ticket['distance']:.4f})<br/>
                        <span style="color: #666; font-size: 13px;">{ticket['summary'][:80]}...</span>
                    </div>
                    """
                
                html_body = f"""
                <html>
                <body style="font-family: Arial, sans-serif; line-height: 1.6;">
                    <h2 style="color: #4CAF50;">✅ Ticket Successfully Assigned</h2>
                    <p><strong>Ticket:</strong> <a href="https://jira.netapp.com/browse/{ticket_key}">{ticket_key}</a></p>
                    <p><strong>Assigned Team:</strong> {predicted_team}</p>
                    <p><strong>Confidence:</strong> {confidence:.1f}%</p>
                    
                    <h3>🤖 LLM Analysis:</h3>
                    <p style="background: #e3f2fd; padding: 10px; border-radius: 5px; border-left: 4px solid #2196F3;">
                        {llm_reasoning}
                    </p>
                    
                    <h3>🔍 Top Similar Tickets (from ChromaDB):</h3>
                    {similar_html}
                    
                    <p style="margin-top: 20px; color: #666; font-size: 12px;">
                        System: NetApp JIRA Auto-Assignment (LLM-Enhanced)
                    </p>
                </body>
                </html>
                """
            
            msg['From'] = smtp_user
            msg['To'] = notification_email
            msg.attach(MIMEText(html_body, 'html'))
            
            # Send email
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                # Only use STARTTLS and authentication for ports 587/465
                if smtp_port in [587, 465]:
                    server.starttls()
                    if smtp_password:
                        server.login(smtp_user, smtp_password)
                # For port 25 (internal relay), no authentication needed
                server.send_message(msg)
            
            print(f"✅ Email notification sent to {notification_email}")
            
        except Exception as e:
            print(f"⚠️  Failed to send email notification: {e}")
    
    async def _predict_team_with_llm(
        self,
        new_ticket: Dict[str, str],
        similar_tickets: List[Dict[str, Any]]
    ) -> Tuple[str, float, str]:
        """
        Use LLM to predict the best team based on new ticket and similar historical tickets.
        
        Args:
            new_ticket: Dict with 'key', 'summary', 'description' of new ticket
            similar_tickets: List of similar tickets from ChromaDB with team assignments
            
        Returns:
            Tuple of (predicted_team, confidence, reasoning)
        """
        # Build prompt for LLM
        similar_tickets_text = "\n".join([
            f"{i+1}. [{ticket['ticket_id']}] Team: {ticket['team']} | Distance: {ticket['distance']:.4f}\n"
            f"   Summary: {ticket['summary']}"
            for i, ticket in enumerate(similar_tickets[:10])
        ])
        
        prompt = f"""You are an expert JIRA ticket triaging system for NetApp. Your task is to assign a new JIRA ticket to the most appropriate team based on similar historical tickets.

NEW TICKET TO ASSIGN:
Ticket: {new_ticket['key']}
Summary: {new_ticket['summary']}
Description: {new_ticket['description'][:500]}...

TOP 10 MOST SIMILAR HISTORICAL TICKETS (from ChromaDB vector search):
{similar_tickets_text}

INSTRUCTIONS:
1. Analyze the new ticket's technical content (protocols, components, error messages, keywords)
2. Compare it with the similar historical tickets
3. Consider the team assignments of the most similar tickets (lower distance = more similar)
4. Determine which team is the best match

RESPOND IN THIS EXACT FORMAT:
TEAM: <team-name>
CONFIDENCE: <0.0-1.0>
REASONING: <brief explanation of why this team is the best match>

Example response:
TEAM: team-supernova
CONFIDENCE: 0.85
REASONING: The ticket involves FabricPool and cool tier issues, which are handled by team-supernova. The top 3 most similar tickets (distance < 0.2) were all assigned to team-supernova and deal with similar cold data tiering problems.
"""
        
        try:
            # Call LLM (NetApp proxy requires 'user' field with email format)
            user = os.getenv('JIRA_EMAIL', '').split('@')[0] if os.getenv('JIRA_EMAIL') else 'webhook_client'
            
            response = self.llm_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an expert JIRA ticket assignment system."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=300,
                user=user  # Required by NetApp LLM proxy
            )
            
            llm_response = response.choices[0].message.content.strip()
            
            # Parse LLM response
            lines = llm_response.split('\n')
            team = None
            confidence = 0.5
            reasoning = ""
            
            for line in lines:
                if line.startswith('TEAM:'):
                    team = line.replace('TEAM:', '').strip()
                elif line.startswith('CONFIDENCE:'):
                    confidence = float(line.replace('CONFIDENCE:', '').strip())
                elif line.startswith('REASONING:'):
                    reasoning = line.replace('REASONING:', '').strip()
            
            # Fallback: if LLM didn't follow format, use vote counting
            if not team:
                print("⚠️  LLM response didn't follow format, falling back to vote counting")
                team_votes = {}
                for ticket in similar_tickets:
                    team = ticket['team']
                    team_votes[team] = team_votes.get(team, 0) + 1
                team = max(team_votes.items(), key=lambda x: x[1])[0]
                confidence = team_votes[team] / len(similar_tickets)
                reasoning = f"Vote counting fallback: {team_votes[team]}/{len(similar_tickets)} similar tickets assigned to {team}"
            
            return team, confidence, reasoning
            
        except Exception as e:
            print(f"⚠️  LLM prediction failed: {e}, falling back to vote counting")
            # Fallback to simple vote counting
            team_votes = {}
            for ticket in similar_tickets:
                team = ticket['team']
                team_votes[team] = team_votes.get(team, 0) + 1
            team = max(team_votes.items(), key=lambda x: x[1])[0]
            confidence = team_votes[team] / len(similar_tickets)
            reasoning = f"LLM failed, used vote counting: {team_votes[team]}/{len(similar_tickets)} votes"
            return team, confidence, reasoning
    
    async def process_webhook_ticket(self, ticket_key: str, assign_in_jira: bool = True) -> Dict[str, Any]:
        """
        Process a ticket from webhook: filter, predict, assign, notify.
        
        Args:
            ticket_key: JIRA ticket key
            assign_in_jira: Whether to update JIRA Technical Owner field
            
        Returns:
            Dictionary with processing results
        """
        try:
            # Fetch ticket from JIRA
            print(f"🎫 Processing webhook for {ticket_key}")
            ticket = self.jira_client.fetch_ticket(ticket_key)
            
            if not ticket:
                return {"status": "error", "message": "Failed to fetch ticket from JIRA"}
            
            # Check filters: NFSAAS project + Bug type + Azure + No Technical Owner
            project_key = ticket.get('project', {}).get('key', '')
            issue_type = ticket.get('issuetype', {}).get('name', '')
            technical_owner = ticket.get('customfield_10050')  # Technical Owner field
            
            # Get Hyperscaler field (customfield_16202) - Azure (array format)
            hyperscaler_field = ticket.get('customfield_16202')
            if hyperscaler_field:
                # Field is an array: [{"value": "Azure", "id": "16809"}]
                if isinstance(hyperscaler_field, list) and len(hyperscaler_field) > 0:
                    hyperscaler_value = hyperscaler_field[0].get('value', '')
                elif isinstance(hyperscaler_field, dict):
                    hyperscaler_value = hyperscaler_field.get('value', '')
                else:
                    hyperscaler_value = str(hyperscaler_field)
            else:
                hyperscaler_value = ''
            
            # Filter 1: NFSAAS project
            if project_key != 'NFSAAS':
                print(f"⏭️  Skipping: Not NFSAAS project (found: {project_key})")
                return {"status": "skipped", "reason": "Not NFSAAS project"}
            
            # Filter 2: Bug type
            if issue_type != 'Bug':
                print(f"⏭️  Skipping: Not Bug type (found: {issue_type})")
                return {"status": "skipped", "reason": "Not Bug type"}
            
            # Filter 3: Hyperscaler must be Azure
            if hyperscaler_value.upper() != 'AZURE':
                print(f"⏭️  Skipping: Not Azure hyperscaler (found: {hyperscaler_value})")
                return {"status": "skipped", "reason": f"Not Azure (found: {hyperscaler_value})"}
            
            # Filter 4: No existing Technical Owner
            if technical_owner:
                print(f"⏭️  Skipping: Already has Technical Owner: {technical_owner}")
                return {"status": "skipped", "reason": "Already assigned"}
            
            print(f"✅ Ticket passes filters: NFSAAS + Bug + Azure + No owner")
            
            # Generate embedding and query ChromaDB for similar tickets
            full_content = f"{ticket.get('summary', '')} {ticket.get('description', '')}"
            embedding = await self.generate_embedding(full_content)
            
            results = self.tickets_collection.query(
                query_embeddings=[embedding],
                n_results=20
            )
            
            # Prepare context for LLM with top similar tickets
            print(f"🔍 Found {len(results['ids'][0])} similar tickets, sending to LLM for analysis...")
            
            similar_tickets_context = []
            for i in range(len(results['ids'][0])):
                similar_tickets_context.append({
                    "ticket_id": results['ids'][0][i],
                    "team": results['metadatas'][0][i].get('team', 'unknown'),
                    "summary": results['metadatas'][0][i].get('summary', 'N/A'),
                    "distance": results['distances'][0][i]
                })
            
            # Send to LLM for team prediction
            predicted_team, confidence, llm_reasoning = await self._predict_team_with_llm(
                new_ticket={
                    "key": ticket_key,
                    "summary": ticket.get('summary', ''),
                    "description": ticket.get('description', '')
                },
                similar_tickets=similar_tickets_context
            )
            
            print(f"🎯 LLM Predicted: {predicted_team} ({confidence:.1%} confidence)")
            print(f"💭 LLM Reasoning: {llm_reasoning}")
            
            # Normalize team name for JIRA (convert team-nandi -> Team Nandi)
            jira_team_name = self._normalize_team_name(predicted_team)
            print(f"📝 Normalized team name: {predicted_team} -> {jira_team_name}")
            
            # Assign in JIRA if requested
            if assign_in_jira:
                result_update = await self.jira_client.update_technical_owner(ticket_key, jira_team_name)
                success = result_update.get('success', False)
                if not success:
                    error_msg = "Failed to update JIRA Technical Owner field"
                    self.send_email_notification(ticket_key, None, error=error_msg)
                    return {"status": "error", "message": error_msg}
                print(f"✅ Updated Technical Owner in JIRA: {jira_team_name}")
            
            # Prepare result
            result = {
                "status": "success",
                "ticket": ticket_key,
                "predicted_team": predicted_team,
                "confidence": confidence,
                "llm_reasoning": llm_reasoning,
                "similar_tickets": similar_tickets_context[:5]  # Top 5 for email
            }
            
            # Send success email notification
            self.send_email_notification(ticket_key, result)
            
            return result
            
        except Exception as e:
            error_msg = f"Webhook processing failed: {str(e)}"
            print(f"❌ {error_msg}")
            self.send_email_notification(ticket_key, None, error=error_msg)
            return {"status": "error", "message": error_msg}


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