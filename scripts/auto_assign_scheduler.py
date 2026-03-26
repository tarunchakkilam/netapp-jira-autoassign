#!/usr/bin/env python3
"""
Scheduled job to auto-assign unassigned JIRA tickets.
Runs every 20 seconds (configurable) to fetch and process unassigned tickets.

NEW FEATURE:
- Now processes tickets even if Hyperscaler field (customfield_16202) is EMPTY
- LLM will analyze ticket content to determine if it's Azure/ANF related
- If Azure/ANF: LLM assigns to appropriate team
- If NOT Azure/ANF: Ticket is skipped with reasoning logged
- This works because our training DB contains only Azure ANF tickets
"""
import os
import sys
import asyncio
import logging
import json
from datetime import datetime
from typing import List, Dict, Any
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from app.enhanced_chroma_client import EnhancedTicketEmbeddingClient
from app.jira_client import JiraClient

# Configure logging to file with append mode
LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "auto_assign_scheduler.log"

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, mode='a'),  # Append mode - never overwrite
        logging.StreamHandler(sys.stdout)  # Also print to console
    ]
)

logger = logging.getLogger(__name__)


def validate_runtime_configuration() -> None:
    """Fail fast for missing critical runtime configuration."""
    required_env = ["JIRA_BASE_URL", "JIRA_API_TOKEN", "NETAPP_LLM_API_KEY"]
    missing = [name for name in required_env if not os.getenv(name)]
    if missing:
        raise ValueError(f"Missing required environment variable(s): {', '.join(missing)}")


class JiraAutoAssignScheduler:
    """Scheduler to automatically assign unassigned JIRA tickets."""
    
    def __init__(self, interval_seconds: int = 20):
        """
        Initialize the scheduler.
        
        Args:
            interval_seconds: How often to check for unassigned tickets (default: 60 seconds)
        """
        self.interval_seconds = interval_seconds
        self.jira_client = JiraClient()
        self.embedding_client = None
        self.processed_tickets = set()  # Track processed tickets to avoid duplicates
        self.processed_tickets_state_file = Path(
            os.getenv(
                "PROCESSED_TICKETS_STATE_FILE",
                str(Path(__file__).parent.parent / "data" / "processed_tickets_state.json"),
            )
        )
        self.start_time = datetime.now()  # Record when scheduler started
        self.is_running = False  # Lock to prevent concurrent runs
        self._load_processed_tickets()

    def _load_processed_tickets(self) -> None:
        """Load processed ticket cache from disk."""
        try:
            if not self.processed_tickets_state_file.exists():
                return
            with open(self.processed_tickets_state_file, "r", encoding="utf-8") as f:
                state = json.load(f)
            if isinstance(state, list):
                self.processed_tickets = set(str(item) for item in state)
            elif isinstance(state, dict):
                items = state.get("tickets", [])
                self.processed_tickets = set(str(item) for item in items)
            logger.info(
                "Loaded %s processed ticket(s) from %s",
                len(self.processed_tickets),
                self.processed_tickets_state_file,
            )
        except Exception as e:
            logger.warning("Failed to load processed ticket cache: %s", e)

    def _save_processed_tickets(self) -> None:
        """Persist processed ticket cache to disk."""
        try:
            self.processed_tickets_state_file.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "updated_at": datetime.now().isoformat(),
                "tickets": sorted(self.processed_tickets),
            }
            with open(self.processed_tickets_state_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
        except Exception as e:
            logger.warning("Failed to save processed ticket cache: %s", e)
        
    def _get_embedding_client(self) -> EnhancedTicketEmbeddingClient:
        """Get or create embedding client (lazy initialization)."""
        if self.embedding_client is None:
            self.embedding_client = EnhancedTicketEmbeddingClient()
        return self.embedding_client
    
    async def fetch_unassigned_tickets(self) -> List[str]:
        """
        Fetch unassigned JIRA tickets created after the scheduler started.
        
        Returns:
            List of ticket keys
        """
        # Format start time for JIRA query (YYYY-MM-DD HH:MM)
        # JIRA accepts format like "2025-12-11 14:30"
        start_timestamp = self.start_time.strftime('%Y-%m-%d %H:%M')
        
        # JQL query for unassigned tickets created after scheduler start
        # Note: We'll filter by Azure and Technical Owner in code after fetching
        # since JQL field names may vary by JIRA instance
        # IMPORTANT: Exclude Done/Resolved/Closed tickets
        jql = f'''
            project = NFSAAS 
            AND issuetype = Bug 
            AND created >= "{start_timestamp}"
            AND status NOT IN (Done, Resolved, Closed, Cancelled, Withdrawn)
            ORDER BY created ASC
        '''
        
        print(f"🔍 Searching for tickets created after {start_timestamp}...")
        
        try:
            # Search for tickets
            result = await self.jira_client.search_issues(
                jql=jql,
                fields=[
                    'key',
                    'summary',
                    'created',
                    self.jira_client.hyperscaler_field,
                    self.jira_client.technical_owner_field,
                    self.jira_client.technical_owner_fallback_field,
                ],
                max_results=100  # Fetch more since we'll filter in code
            )
            
            tickets = result.get('issues', [])
            
            # Filter tickets in code (Azure + no Technical Owner)
            # NEW FEATURE: Also include tickets with empty hyperscaler field - LLM will determine if it's Azure/ANF
            filtered_keys = []
            empty_hyperscaler_keys = []  # Track tickets with empty hyperscaler for logging
            
            for ticket in tickets:
                fields = ticket.get('fields', {})
                
                # Check Hyperscaler = Azure (array format)
                hyperscaler = fields.get(self.jira_client.hyperscaler_field)
                hyperscaler_value = None
                if hyperscaler and isinstance(hyperscaler, list) and len(hyperscaler) > 0:
                    hyperscaler_value = hyperscaler[0].get('value')
                
                # Check Technical Owner is empty (support primary + fallback fields)
                technical_owner = (
                    fields.get(self.jira_client.technical_owner_field)
                    or fields.get(self.jira_client.technical_owner_fallback_field)
                )
                
                # Include tickets if:
                # 1. Hyperscaler = Azure AND no Technical Owner (original logic)
                # 2. Hyperscaler is empty AND no Technical Owner (NEW: LLM will analyze)
                if not technical_owner:
                    if hyperscaler_value and hyperscaler_value.upper() == 'AZURE':
                        filtered_keys.append(ticket['key'])
                    elif not hyperscaler_value:
                        # Empty hyperscaler - let LLM determine if it's Azure/ANF
                        filtered_keys.append(ticket['key'])
                        empty_hyperscaler_keys.append(ticket['key'])
            
            if filtered_keys:
                print(f"✅ Found {len(filtered_keys)} unassigned ticket(s): {', '.join(filtered_keys)}")
                if empty_hyperscaler_keys:
                    print(f"   📝 Note: {len(empty_hyperscaler_keys)} ticket(s) have empty hyperscaler field - LLM will analyze: {', '.join(empty_hyperscaler_keys)}")
            else:
                print(f"✅ No unassigned tickets found (checked {len(tickets)} total tickets)")
            
            return filtered_keys
            
        except Exception as e:
            print(f"❌ Error fetching tickets: {e}")
            return []
    
    async def process_ticket(self, ticket_key: str) -> Dict[str, Any]:
        """
        Process a single ticket for auto-assignment.
        
        Args:
            ticket_key: JIRA ticket key
            
        Returns:
            Result dictionary
        """
        try:
            print(f"\n{'='*80}")
            print(f"🎫 Processing: {ticket_key}")
            print(f"{'='*80}")
            
            # Get embedding client
            client = self._get_embedding_client()
            
            # Process ticket
            logger.info(f"{'='*80}")
            logger.info(f"Processing ticket: {ticket_key}")
            logger.info(f"{'='*80}")
            
            result = await client.process_webhook_ticket(ticket_key, assign_in_jira=True)
            
            if result.get('status') == 'success':
                predicted_team = result.get('predicted_team', 'Unknown')
                confidence = result.get('confidence', 0)
                llm_reasoning = result.get('llm_reasoning', 'N/A')
                
                print(f"✅ Successfully processed {ticket_key}")
                print(f"   Team: {predicted_team}")
                print(f"   Confidence: {confidence:.1%}")
                
                logger.info(f"✅ SUCCESS - Ticket {ticket_key} assigned to {predicted_team}")
                logger.info(f"   Confidence: {confidence:.1%}")
                logger.info(f"   LLM Reasoning: {llm_reasoning}")
                
                # Log similar tickets if available
                similar_tickets = result.get('similar_tickets', [])
                if similar_tickets:
                    logger.info(f"   Top 5 Similar Tickets:")
                    for i, ticket in enumerate(similar_tickets[:5], 1):
                        logger.info(f"      {i}. {ticket.get('ticket_id')} → {ticket.get('team')} (distance: {ticket.get('distance', 0):.4f})")
                
            elif result.get('status') == 'skipped':
                reason = result.get('reason', 'Unknown')
                print(f"⏭️  Skipped {ticket_key}: {reason}")
                logger.info(f"⏭️ SKIPPED - Ticket {ticket_key}: {reason}")
                
            else:
                error_message = result.get('message', 'Unknown error')
                print(f"❌ Failed to process {ticket_key}: {error_message}")
                logger.error(f"❌ FAILED - Ticket {ticket_key}: {error_message}")
                
                # Log additional details if available
                if result.get('predicted_team'):
                    logger.error(f"   Predicted Team: {result.get('predicted_team')}")
                    logger.error(f"   Confidence: {result.get('confidence', 0):.1%}")
                if result.get('llm_reasoning'):
                    logger.error(f"   LLM Reasoning: {result.get('llm_reasoning')}")
            
            return result
            
        except Exception as e:
            print(f"❌ Error processing {ticket_key}: {e}")
            logger.error(f"❌ EXCEPTION - Error processing {ticket_key}: {e}")
            import traceback
            traceback.print_exc()
            logger.error(f"Traceback: {traceback.format_exc()}")
            return {
                'status': 'error',
                'ticket': ticket_key,
                'message': str(e)
            }
    
    async def run_once(self):
        """Run one iteration of the scheduler."""
        # Check if a job is already running
        if self.is_running:
            print(f"\n⚠️  Skipping job - previous job still running at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            logger.warning(f"Skipped job - previous job still running")
            return
        
        # Set lock
        self.is_running = True
        
        try:
            job_start_time = datetime.now()
            print(f"\n{'='*80}")
            print(f"🚀 Auto-Assignment Job Started - {job_start_time.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"{'='*80}")
        
            logger.info(f"\n{'='*80}")
            logger.info(f"🚀 Auto-Assignment Job Started - {job_start_time.strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info(f"   Scheduler started at: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info(f"   Total processed so far: {len(self.processed_tickets)} tickets")
            logger.info(f"{'='*80}")
            
            # Fetch unassigned tickets
            ticket_keys = await self.fetch_unassigned_tickets()
            
            # Filter out already processed tickets
            new_tickets = [key for key in ticket_keys if key not in self.processed_tickets]
            
            # Track results
            success_count = 0
            failed_count = 0
            skipped_count = 0
            
            if new_tickets:
                print(f"📋 Processing {len(new_tickets)} new ticket(s)...")
                logger.info(f"📋 Processing {len(new_tickets)} new ticket(s): {', '.join(new_tickets)}")
                
                # Process each ticket
                for ticket_key in new_tickets:
                    result = await self.process_ticket(ticket_key)
                    
                    # Track results
                    status = result.get('status', 'unknown')
                    if status == 'success':
                        success_count += 1
                    elif status == 'skipped':
                        skipped_count += 1
                    else:
                        failed_count += 1
                    
                    # Mark as processed (even if failed, to avoid retrying immediately)
                    self.processed_tickets.add(ticket_key)
                    self._save_processed_tickets()
                    
                    # Small delay between tickets to avoid rate limiting
                    await asyncio.sleep(2)
                
                # Log summary
                logger.info(f"\n📊 Job Summary:")
                logger.info(f"   ✅ Successfully assigned: {success_count}")
                logger.info(f"   ⏭️  Skipped: {skipped_count}")
                logger.info(f"   ❌ Failed: {failed_count}")
                logger.info(f"   📝 Total processed in this run: {len(new_tickets)}")
                
            else:
                if ticket_keys:
                    print(f"ℹ️  All {len(ticket_keys)} ticket(s) already processed in this session")
                    logger.info(f"ℹ️  All {len(ticket_keys)} ticket(s) already processed in this session")
            
                job_end_time = datetime.now()
                duration = (job_end_time - job_start_time).total_seconds()
                
                print(f"\n{'='*80}")
                print(f"✅ Job Completed - {job_end_time.strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"{'='*80}\n")
                
                logger.info(f"\n{'='*80}")
                logger.info(f"✅ Job Completed - {job_end_time.strftime('%Y-%m-%d %H:%M:%S')}")
                logger.info(f"   Duration: {duration:.1f} seconds")
                logger.info(f"{'='*80}\n")
        
        finally:
            # Always release the lock
            self.is_running = False
    
    async def run_forever(self):
        """Run the scheduler continuously."""
        print(f"\n{'='*80}")
        print(f"🤖 JIRA Auto-Assignment Scheduler Started")
        print(f"{'='*80}")
        print(f"⏰ Check interval: Every {self.interval_seconds} seconds")
        print(f"🎯 Target: NFSAAS Bugs with Azure Hyperscaler")
        print(f"📅 Filter: Created after {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}, no Technical Owner")
        print(f"⏱️  Scheduler started at: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*80}\n")
        
        # Clear processed tickets at the start of each day
        last_clear_date = datetime.now().date()
        
        while True:
            try:
                # Check if it's a new day - clear processed tickets
                current_date = datetime.now().date()
                if current_date != last_clear_date:
                    print(f"📅 New day detected - clearing processed tickets cache")
                    self.processed_tickets.clear()
                    self._save_processed_tickets()
                    last_clear_date = current_date
                
                # Run one iteration
                await self.run_once()
                
                # Wait for next interval
                print(f"⏳ Waiting {self.interval_seconds} seconds until next check...\n")
                await asyncio.sleep(self.interval_seconds)
                
            except KeyboardInterrupt:
                print("\n\n⚠️  Scheduler stopped by user (Ctrl+C)")
                break
            except Exception as e:
                print(f"\n❌ Unexpected error in scheduler: {e}")
                import traceback
                traceback.print_exc()
                print(f"⏳ Retrying in {self.interval_seconds} seconds...\n")
                await asyncio.sleep(self.interval_seconds)


def main():
    """Main entry point."""
    validate_runtime_configuration()
    # Get interval from environment or use default (20 seconds)
    interval = int(os.getenv('AUTO_ASSIGN_INTERVAL', 20))
    
    # Create and run scheduler
    scheduler = JiraAutoAssignScheduler(interval_seconds=interval)
    
    try:
        asyncio.run(scheduler.run_forever())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")


if __name__ == '__main__':
    main()
