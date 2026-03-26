"""
Jira REST API client for ticket assignment operations.
Handles authentication and assignment API calls.
"""
import os
import httpx
import logging
import time
import asyncio
from typing import Optional, Dict, Any, List
from base64 import b64encode

logger = logging.getLogger(__name__)


class JiraClient:
    """
    Client for Jira REST API operations.
    Handles authentication and ticket assignment.
    """
    
    def __init__(
        self,
        base_url: str = None,
        email: str = None,
        api_token: str = None
    ):
        """
        Initialize Jira client with credentials.
        
        Args:
            base_url: Jira instance base URL (e.g., https://company.atlassian.net)
            email: Email address for authentication
            api_token: Jira API token (generate at https://id.atlassian.com/manage-profile/security/api-tokens)
        """
        self.base_url = (base_url or os.getenv("JIRA_BASE_URL", "")).rstrip("/")
        self.email = email or os.getenv("JIRA_EMAIL", "")
        self.api_token = api_token or os.getenv("JIRA_API_TOKEN", "")
        self.technical_owner_field = os.getenv("TECHNICAL_OWNER_FIELD", "customfield_15906")
        self.technical_owner_fallback_field = os.getenv("TECHNICAL_OWNER_FALLBACK_FIELD", "customfield_10050")
        self.hyperscaler_field = os.getenv("HYPERSCALER_FIELD", "customfield_16202")
        self.debug_full_ticket = os.getenv("JIRA_DEBUG_FULL_TICKET", "false").lower() == "true"
        self.max_retries = int(os.getenv("JIRA_MAX_RETRIES", "3"))
        self.retry_backoff_seconds = float(os.getenv("JIRA_RETRY_BACKOFF_SECONDS", "1.0"))
        
        # Check if using Jira Data Center (personal access token) or Cloud (email + API token)
        # Personal Access Tokens use Bearer authentication
        # Cloud uses Basic auth with email:token
        use_bearer_auth = os.getenv("JIRA_USE_BEARER_AUTH", "false").lower() == "true"
        
        if not all([self.base_url, self.api_token]):
            logger.warning("Jira credentials not fully configured. Assignment calls will fail.")
        
        # Set API version based on Jira type
        # Data Center uses /rest/api/2, Cloud uses /rest/api/3
        self.api_version = "2" if use_bearer_auth else "3"
        
        # Create auth header based on Jira type
        if use_bearer_auth:
            # Jira Data Center with Personal Access Token
            self.headers = {
                "Authorization": f"Bearer {self.api_token}",
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
            logger.info(f"Using Bearer token authentication (Jira Data Center) with API v{self.api_version}")
        else:
            # Jira Cloud with email + API token
            auth_string = f"{self.email}:{self.api_token}"
            auth_bytes = auth_string.encode('ascii')
            base64_bytes = b64encode(auth_bytes)
            base64_string = base64_bytes.decode('ascii')
            
            self.headers = {
                "Authorization": f"Basic {base64_string}",
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
            logger.info("Using Basic authentication (Jira Cloud)")

    def _should_retry_status(self, status_code: int) -> bool:
        """Retry on throttling and transient server errors."""
        return status_code in (429, 500, 502, 503, 504)

    async def _async_request_with_retries(
        self,
        method: str,
        url: str,
        *,
        timeout: float = 30.0,
        **kwargs: Any,
    ) -> httpx.Response:
        """Perform async HTTP request with retry/backoff."""
        last_exception: Optional[Exception] = None
        async with httpx.AsyncClient(timeout=timeout) as client:
            for attempt in range(1, self.max_retries + 1):
                try:
                    response = await client.request(method, url, **kwargs)
                    if not self._should_retry_status(response.status_code):
                        return response
                    if attempt == self.max_retries:
                        return response
                    sleep_for = self.retry_backoff_seconds * attempt
                    logger.warning(
                        "Retrying %s %s after status %s (attempt %s/%s, sleep %.1fs)",
                        method,
                        url,
                        response.status_code,
                        attempt,
                        self.max_retries,
                        sleep_for,
                    )
                    await asyncio.sleep(sleep_for)
                except (httpx.TimeoutException, httpx.TransportError) as exc:
                    last_exception = exc
                    if attempt == self.max_retries:
                        raise
                    sleep_for = self.retry_backoff_seconds * attempt
                    logger.warning(
                        "Retrying %s %s after transport error: %s (attempt %s/%s, sleep %.1fs)",
                        method,
                        url,
                        exc,
                        attempt,
                        self.max_retries,
                        sleep_for,
                    )
                    await asyncio.sleep(sleep_for)
        if last_exception:
            raise last_exception
        raise RuntimeError("Request failed unexpectedly")

    def _sync_request_with_retries(
        self,
        method: str,
        url: str,
        *,
        timeout: float = 30.0,
        **kwargs: Any,
    ) -> httpx.Response:
        """Perform sync HTTP request with retry/backoff."""
        last_exception: Optional[Exception] = None
        with httpx.Client(timeout=timeout) as client:
            for attempt in range(1, self.max_retries + 1):
                try:
                    response = client.request(method, url, **kwargs)
                    if not self._should_retry_status(response.status_code):
                        return response
                    if attempt == self.max_retries:
                        return response
                    sleep_for = self.retry_backoff_seconds * attempt
                    logger.warning(
                        "Retrying %s %s after status %s (attempt %s/%s, sleep %.1fs)",
                        method,
                        url,
                        response.status_code,
                        attempt,
                        self.max_retries,
                        sleep_for,
                    )
                    time.sleep(sleep_for)
                except (httpx.TimeoutException, httpx.TransportError) as exc:
                    last_exception = exc
                    if attempt == self.max_retries:
                        raise
                    sleep_for = self.retry_backoff_seconds * attempt
                    logger.warning(
                        "Retrying %s %s after transport error: %s (attempt %s/%s, sleep %.1fs)",
                        method,
                        url,
                        exc,
                        attempt,
                        self.max_retries,
                        sleep_for,
                    )
                    time.sleep(sleep_for)
        if last_exception:
            raise last_exception
        raise RuntimeError("Request failed unexpectedly")
        
    async def assign_ticket(
        self,
        issue_key: str,
        account_id: str
    ) -> Dict[str, Any]:
        """
        Assign a Jira ticket to a specific user.
        
        Args:
            issue_key: Jira issue key (e.g., PROJ-123)
            account_id: Jira account ID of the assignee
            
        Returns:
            Dict with status and message
            
        Example:
            result = await client.assign_ticket("PROJ-123", "5f8a9b1c2d3e4f5g6h7i8j9k")
        """
        url = f"{self.base_url}/rest/api/{self.api_version}/issue/{issue_key}/assignee"
        
        # Data Center uses 'name' field, Cloud uses 'accountId'
        if self.api_version == "2":
            payload = {"name": account_id}  # In Data Center, this is the username
        else:
            payload = {"accountId": account_id}
        
        logger.info(f"Assigning {issue_key} to account {account_id}")
        
        try:
            response = await self._async_request_with_retries(
                "PUT",
                url,
                json=payload,
                headers=self.headers,
            )
            if response.status_code == 204:
                logger.info(f"Successfully assigned {issue_key} to {account_id}")
                return {
                    "success": True,
                    "status_code": 204,
                    "message": "Ticket assigned successfully"
                }
            elif response.status_code == 404:
                logger.error(f"Issue {issue_key} not found")
                return {
                    "success": False,
                    "status_code": 404,
                    "message": f"Issue {issue_key} not found"
                }
            else:
                error_text = response.text
                logger.error(f"Failed to assign {issue_key}: {response.status_code} - {error_text}")
                return {
                    "success": False,
                    "status_code": response.status_code,
                    "message": f"Assignment failed: {error_text}"
                }
                    
        except httpx.TimeoutException:
            logger.error(f"Timeout while assigning {issue_key}")
            return {
                "success": False,
                "status_code": 0,
                "message": "Request timeout"
            }
        except Exception as e:
            logger.error(f"Error assigning {issue_key}: {str(e)}")
            return {
                "success": False,
                "status_code": 0,
                "message": str(e)
            }
    
    def fetch_ticket(self, issue_key: str) -> Optional[Dict[str, Any]]:
        """
        Fetch ticket details from JIRA (synchronous).
        
        Args:
            issue_key: JIRA issue key (e.g., NFSAAS-12345)
            
        Returns:
            Dict with ticket fields or None if error
        """
        # Request specific fields including custom fields
        fields = ",".join([
            "summary",
            "description",
            "project",
            "issuetype",
            self.technical_owner_field,
            self.technical_owner_fallback_field,
            self.hyperscaler_field,
        ])
        url = f"{self.base_url}/rest/api/{self.api_version}/issue/{issue_key}?fields={fields}"
        
        try:
            response = self._sync_request_with_retries("GET", url, headers=self.headers)

            if response.status_code == 200:
                data = response.json()

                if self.debug_full_ticket:
                    logger.info(f"JIRA_DEBUG_FULL_TICKET enabled for {issue_key}")
                    import json
                    logger.info(json.dumps(data, indent=2, default=str))

                fields = data.get('fields', {})
                technical_owner = (
                    fields.get(self.technical_owner_field)
                    or fields.get(self.technical_owner_fallback_field)
                )
                hyperscaler = fields.get(self.hyperscaler_field)

                # Extract relevant fields
                return {
                    'key': issue_key,
                    'summary': fields.get('summary', ''),
                    'description': fields.get('description', ''),
                    'project': fields.get('project', {}),
                    'issuetype': fields.get('issuetype', {}),
                    'technical_owner': technical_owner,
                    'hyperscaler': hyperscaler,
                    # Backward-compatible keys for current callers
                    self.technical_owner_field: fields.get(self.technical_owner_field),
                    self.technical_owner_fallback_field: fields.get(self.technical_owner_fallback_field),
                    self.hyperscaler_field: hyperscaler,
                }
            else:
                logger.error(f"Failed to fetch {issue_key}: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Error fetching {issue_key}: {str(e)}")
            return None

    async def get_technical_owner(
        self,
        issue_key: str
    ) -> Optional[str]:
        """
        Get the Technical Owner field value for a ticket.
        
        Args:
            issue_key: Jira issue key (e.g., PROJ-123)
            
        Returns:
            Technical Owner value or None if empty/not found
        """
        url = f"{self.base_url}/rest/api/{self.api_version}/issue/{issue_key}"
        
        try:
            response = await self._async_request_with_retries(
                "GET",
                url,
                headers=self.headers,
                params={"fields": f"{self.technical_owner_field},{self.technical_owner_fallback_field}"},
            )

            if response.status_code == 200:
                data = response.json()
                fields = data.get("fields", {})
                tech_owner = fields.get(self.technical_owner_field) or fields.get(self.technical_owner_fallback_field)
                return tech_owner if tech_owner else None
            else:
                logger.error(f"Failed to get technical owner for {issue_key}: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Exception getting technical owner: {e}")
            return None

    async def update_technical_owner(self, issue_key: str, team_name: str) -> Dict[str, Any]:
        """
        Update the Technical Owner field for a Jira issue.
        
        Args:
            issue_key: The Jira issue key (e.g., 'NFSAAS-12345')
            team_name: The team name to assign (e.g., 'Team Himalaya')
            
        Returns:
            Dict containing success status and details
        """
        # Check if Technical Owner is already set
        current_owner = await self.get_technical_owner(issue_key)
        if current_owner:
            logger.info(f"Technical Owner already set for {issue_key}: {current_owner}")
            return {
                "success": False,
                "status_code": 200,
                "message": f"Technical Owner already set to: {current_owner}",
                "skip_reason": "already_assigned"
            }
        
        url = f"{self.base_url}/rest/api/{self.api_version}/issue/{issue_key}"
        
        payload = {
            "fields": {
                self.technical_owner_field: {"value": team_name}
            }
        }
        
        try:
            response = await self._async_request_with_retries(
                "PUT",
                url,
                json=payload,
                headers=self.headers,
            )

            if response.status_code == 204:
                logger.info(f"Successfully updated Technical Owner for {issue_key} to {team_name}")
                return {
                    "success": True,
                    "status_code": 204,
                    "message": f"Technical Owner updated to {team_name}"
                }
            elif response.status_code == 404:
                logger.error(f"Issue {issue_key} not found")
                return {
                    "success": False,
                    "status_code": 404,
                    "message": f"Issue {issue_key} not found"
                }
            else:
                error_text = response.text
                logger.error(f"Failed to update Technical Owner for {issue_key}: {response.status_code} - {error_text}")
                return {
                    "success": False,
                    "status_code": response.status_code,
                    "message": f"Update failed: {error_text}"
                }
                    
        except httpx.TimeoutException:
            logger.error(f"Timeout while updating Technical Owner for {issue_key}")
            return {
                "success": False,
                "status_code": 0,
                "message": "Request timeout"
            }
        except Exception as e:
            logger.error(f"Error updating Technical Owner for {issue_key}: {str(e)}")
            return {
                "success": False,
                "status_code": 0,
                "message": str(e)
            }
    
    async def add_label(
        self,
        issue_key: str,
        label: str
    ) -> Dict[str, Any]:
        """
        Add a label to a Jira ticket.
        Used to tag tickets as "triage_needed" when no suitable assignee is found.
        
        Args:
            issue_key: Jira issue key (e.g., PROJ-123)
            label: Label to add
            
        Returns:
            Dict with status and message
        """
        url = f"{self.base_url}/rest/api/{self.api_version}/issue/{issue_key}"
        payload = {
            "update": {
                "labels": [{"add": label}]
            }
        }
        
        logger.info(f"Adding label '{label}' to {issue_key}")
        
        try:
            response = await self._async_request_with_retries(
                "PUT",
                url,
                json=payload,
                headers=self.headers,
            )

            if response.status_code == 204:
                logger.info(f"Successfully added label '{label}' to {issue_key}")
                return {
                    "success": True,
                    "status_code": 204,
                    "message": f"Label '{label}' added successfully"
                }
            else:
                error_text = response.text
                logger.error(f"Failed to add label to {issue_key}: {response.status_code} - {error_text}")
                return {
                    "success": False,
                    "status_code": response.status_code,
                    "message": f"Failed to add label: {error_text}"
                }
                    
        except Exception as e:
            logger.error(f"Error adding label to {issue_key}: {str(e)}")
            return {
                "success": False,
                "status_code": 0,
                "message": f"Error: {str(e)}"
            }
    
    async def get_issue(self, issue_key: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve issue details from Jira.
        
        Args:
            issue_key: Jira issue key (e.g., PROJ-123)
            
        Returns:
            Issue data dict or None if not found
        """
        url = f"{self.base_url}/rest/api/{self.api_version}/issue/{issue_key}"
        
        try:
            response = await self._async_request_with_retries(
                "GET",
                url,
                headers=self.headers,
            )
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to get issue {issue_key}: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Error fetching issue {issue_key}: {str(e)}")
            return None
    
    async def search_issues(
        self,
        jql: str,
        max_results: int = 50,
        fields: list = None
    ) -> List[Dict[str, Any]]:
        """
        Search for issues using JQL (Jira Query Language).
        
        Args:
            jql: JQL query string (e.g., 'assignee = currentUser() AND status = Open')
            max_results: Maximum number of results to return (default 50)
            fields: List of fields to include (default: all fields)
            
        Returns:
            List of issue dictionaries
            
        Example:
            issues = await client.search_issues(
                jql='project = PROJ AND status = Open',
                max_results=100,
                fields=['summary', 'assignee', 'status']
            )
        """
        url = f"{self.base_url}/rest/api/{self.api_version}/search"
        
        # Default fields if not specified
        if fields is None:
            fields = ['summary', 'description', 'status', 'assignee', 'labels', 'components', 'issuetype']
        
        payload = {
            "jql": jql,
            "maxResults": max_results,
            "fields": fields
        }
        
        logger.info(f"Searching issues with JQL: {jql[:100]}...")
        
        try:
            response = await self._async_request_with_retries(
                "POST",
                url,
                timeout=60.0,
                json=payload,
                headers=self.headers,
            )
            if response.status_code == 200:
                data = response.json()
                issues = data.get('issues', [])
                total = data.get('total', 0)

                logger.info(f"Found {len(issues)} issues (total matching: {total})")
                # Return full response with issues and total
                return {
                    'issues': issues,
                    'total': total,
                    'maxResults': data.get('maxResults', max_results),
                    'startAt': data.get('startAt', 0)
                }
            else:
                error_text = response.text
                logger.error(f"Failed to search issues: {response.status_code} - {error_text}")
                return {'issues': [], 'total': 0}

        except httpx.TimeoutException:
            logger.error("Timeout while searching issues")
            return {'issues': [], 'total': 0}
        except Exception as e:
            logger.error(f"Error searching issues: {str(e)}")
            return {'issues': [], 'total': 0}
    
    async def get_user_info(self, account_id: str) -> Optional[Dict[str, Any]]:
        """
        Get user information by account ID.
        
        Args:
            account_id: Jira account ID
            
        Returns:
            User data dict or None if not found
        """
        url = f"{self.base_url}/rest/api/{self.api_version}/user"
        
        # Data Center uses 'username' param, Cloud uses 'accountId'
        if self.api_version == "2":
            params = {"username": account_id}  # In Data Center, this is the username
        else:
            params = {"accountId": account_id}
        
        try:
            response = await self._async_request_with_retries(
                "GET",
                url,
                params=params,
                headers=self.headers,
            )
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to get user {account_id}: {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"Error fetching user {account_id}: {str(e)}")
            return None
    
    def assign_technical_owner(self, issue_key: str, team_name: str) -> bool:
        """
        Synchronous wrapper to update Technical Owner field.
        Used by webhook handler.
        
        Args:
            issue_key: JIRA issue key
            team_name: Team name to assign
            
        Returns:
            True if successful, False otherwise
        """
        import asyncio
        try:
            result = asyncio.run(self.update_technical_owner(issue_key, team_name))
            return result.get('success', False)
        except Exception as e:
            logger.error(f"Error in assign_technical_owner: {e}")
            return False


# Global Jira client instance
jira_client = JiraClient()
