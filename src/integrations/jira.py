"""Jira API integration with OAuth2 authentication."""

from datetime import datetime
from typing import Dict, List, Any, Optional

import httpx
from sqlalchemy.orm import Session

from ..database.models import ServiceType
from ..auth.oauth2 import oauth2_manager
from ..utils.logging import get_logger
from .base import BaseIntegration

logger = get_logger(__name__)


class JiraIntegration(BaseIntegration):
    """Jira API integration for automation workflows."""
    
    def __init__(self, db_session: Session, user_id: int):
        super().__init__(db_session, user_id, ServiceType.JIRA)
        from ..config import settings
        self.base_url = f"{settings.jira_base_url}/rest/api/3"
    
    async def create_ticket(
        self,
        project_key: str,
        summary: str,
        description: str,
        issue_type: str = "Task",
        priority: str = "Medium",
        labels: List[str] = None
    ) -> Dict[str, Any]:
        """Create a new Jira ticket."""
        try:
            token = await oauth2_manager.get_valid_token(
                self.db, self.user_id, ServiceType.JIRA
            )
            if not token:
                raise Exception("No valid Jira token found")
            
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "fields": {
                    "project": {"key": project_key},
                    "summary": summary,
                    "description": {
                        "type": "doc",
                        "version": 1,
                        "content": [{
                            "type": "paragraph",
                            "content": [{
                                "type": "text",
                                "text": description
                            }]
                        }]
                    },
                    "issuetype": {"name": issue_type},
                    "priority": {"name": priority}
                }
            }
            
            if labels:
                payload["fields"]["labels"] = labels
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/issue",
                    headers=headers,
                    json=payload
                )
                
                if response.status_code not in [200, 201]:
                    raise Exception(f"Jira API error: {response.status_code} - {response.text}")
                
                data = response.json()
                
                return {
                    "key": data["key"],
                    "id": data["id"],
                    "self": data["self"],
                    "summary": summary,
                    "project_key": project_key,
                    "issue_type": issue_type,
                    "priority": priority,
                    "labels": labels or [],
                    "created_at": datetime.utcnow().isoformat()
                }
                
        except Exception as e:
            logger.error(f"Failed to create Jira ticket: {e}")
            raise
    
    async def delete_jira_ticket(self, ticket_key: str) -> Dict[str, Any]:
        """Delete a Jira ticket (for rollback)."""
        try:
            token = await oauth2_manager.get_valid_token(
                self.db, self.user_id, ServiceType.JIRA
            )
            if not token:
                raise Exception("No valid Jira token found")
            
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.delete(
                    f"{self.base_url}/issue/{ticket_key}",
                    headers=headers
                )
                
                if response.status_code != 204:
                    raise Exception(f"Failed to delete ticket: {response.status_code}")
                
                return {
                    "deleted": True,
                    "ticket_key": ticket_key,
                    "deleted_at": datetime.utcnow().isoformat()
                }
                
        except Exception as e:
            logger.error(f"Failed to delete Jira ticket: {e}")
            raise 