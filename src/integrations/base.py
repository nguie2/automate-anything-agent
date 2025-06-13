"""Base integration class for all service integrations."""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from ..database.models import ServiceType


class BaseIntegration(ABC):
    """Base class for all service integrations."""
    
    def __init__(self, db_session: Session, user_id: int, service_type: ServiceType):
        """
        Initialize base integration.
        
        Args:
            db_session: Database session
            user_id: User ID for authentication
            service_type: Type of service integration
        """
        self.db = db_session
        self.user_id = user_id
        self.service_type = service_type
    
    def log_api_call(self, method: str, endpoint: str, response_data: Dict[str, Any]):
        """Log API call for auditing purposes."""
        # This could be extended to log all API calls to the database
        pass
    
    def handle_rate_limit(self, response_headers: Dict[str, str]) -> Optional[int]:
        """
        Handle rate limiting by extracting retry-after or rate limit info.
        
        Args:
            response_headers: HTTP response headers
            
        Returns:
            Seconds to wait before retrying, or None if no rate limit
        """
        # Common rate limit headers
        retry_after = response_headers.get('retry-after')
        if retry_after:
            return int(retry_after)
        
        # GitHub style
        remaining = response_headers.get('x-ratelimit-remaining')
        if remaining and int(remaining) == 0:
            reset_time = response_headers.get('x-ratelimit-reset')
            if reset_time:
                import time
                return max(0, int(reset_time) - int(time.time()))
        
        # Slack style
        remaining = response_headers.get('x-rate-limit-remaining')
        if remaining and int(remaining) == 0:
            retry_after = response_headers.get('x-rate-limit-retry-after')
            if retry_after:
                return int(retry_after)
        
        return None 