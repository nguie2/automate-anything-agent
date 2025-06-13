"""AWS S3 integration for file operations."""

import boto3
from datetime import datetime
from typing import Dict, Any
from sqlalchemy.orm import Session

from ..database.models import ServiceType
from ..utils.logging import get_logger
from .base import BaseIntegration

logger = get_logger(__name__)


class AWSS3Integration(BaseIntegration):
    """AWS S3 integration for automation workflows."""
    
    def __init__(self, db_session: Session, user_id: int):
        super().__init__(db_session, user_id, ServiceType.AWS_S3)
        from ..config import settings
        self.bucket_name = settings.aws_s3_bucket
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name=settings.aws_region
        )
    
    async def upload_content(
        self,
        content: str,
        key: str,
        content_type: str = "text/plain"
    ) -> Dict[str, Any]:
        """Upload content to S3."""
        try:
            # Upload to S3
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=content.encode('utf-8'),
                ContentType=content_type,
                Metadata={
                    'uploaded_by': f'user_{self.user_id}',
                    'upload_time': datetime.utcnow().isoformat()
                }
            )
            
            # Generate URL
            url = f"https://{self.bucket_name}.s3.amazonaws.com/{key}"
            
            return {
                "bucket": self.bucket_name,
                "key": key,
                "url": url,
                "content_type": content_type,
                "size": len(content.encode('utf-8')),
                "uploaded_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to upload to S3: {e}")
            raise
    
    async def delete_s3_object(self, key: str) -> Dict[str, Any]:
        """Delete an S3 object (for rollback)."""
        try:
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=key
            )
            
            return {
                "deleted": True,
                "bucket": self.bucket_name,
                "key": key,
                "deleted_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to delete S3 object: {e}")
            raise 