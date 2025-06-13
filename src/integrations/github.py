"""GitHub API integration with OAuth2 authentication."""

from datetime import datetime
from typing import Dict, List, Any
import httpx
from sqlalchemy.orm import Session

from ..database.models import ServiceType
from ..auth.oauth2 import oauth2_manager
from ..utils.logging import get_logger
from .base import BaseIntegration

logger = get_logger(__name__)


class GitHubIntegration(BaseIntegration):
    """GitHub API integration for automation workflows."""
    
    def __init__(self, db_session: Session, user_id: int):
        super().__init__(db_session, user_id, ServiceType.GITHUB)
        self.base_url = "https://api.github.com"
    
    async def search_repositories(
        self,
        query: str,
        sort: str = "stars",
        order: str = "desc"
    ) -> Dict[str, Any]:
        """Search GitHub repositories."""
        try:
            token = await oauth2_manager.get_valid_token(
                self.db, self.user_id, ServiceType.GITHUB
            )
            if not token:
                raise Exception("No valid GitHub token found")
            
            headers = {
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json"
            }
            
            params = {
                "q": query,
                "sort": sort,
                "order": order,
                "per_page": 30
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/search/repositories",
                    headers=headers,
                    params=params
                )
                
                if response.status_code != 200:
                    raise Exception(f"GitHub API error: {response.status_code} - {response.text}")
                
                data = response.json()
                
                repositories = []
                for repo in data.get("items", []):
                    repositories.append({
                        "name": repo["name"],
                        "full_name": repo["full_name"],
                        "description": repo.get("description", ""),
                        "stars": repo["stargazers_count"],
                        "forks": repo["forks_count"],
                        "language": repo.get("language"),
                        "url": repo["html_url"],
                        "clone_url": repo["clone_url"],
                        "created_at": repo["created_at"],
                        "updated_at": repo["updated_at"]
                    })
                
                return {
                    "total_count": data["total_count"],
                    "repositories": repositories,
                    "query": query,
                    "searched_at": datetime.utcnow().isoformat()
                }
                
        except Exception as e:
            logger.error(f"Failed to search GitHub repositories: {e}")
            raise 