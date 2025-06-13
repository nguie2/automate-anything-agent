"""Slack API integration with OAuth2 authentication."""

from datetime import datetime
from typing import Dict, List, Any, Optional
import re

import httpx
from sqlalchemy.orm import Session

from ..database.models import ServiceType
from ..auth.oauth2 import oauth2_manager
from ..utils.logging import get_logger
from .base import BaseIntegration

logger = get_logger(__name__)


class SlackIntegration(BaseIntegration):
    """Slack API integration for automation workflows."""
    
    def __init__(self, db_session: Session, user_id: int):
        super().__init__(db_session, user_id, ServiceType.SLACK)
        self.base_url = "https://slack.com/api"
    
    async def get_messages(
        self, 
        channel_name: str, 
        limit: int = 50, 
        unread_only: bool = False
    ) -> Dict[str, Any]:
        """
        Get messages from a Slack channel.
        
        Args:
            channel_name: Name of the channel (with or without #)
            limit: Number of messages to retrieve
            unread_only: Only get unread messages
            
        Returns:
            Dictionary containing messages and metadata
        """
        try:
            # Get valid access token
            token = await oauth2_manager.get_valid_token(
                self.db, self.user_id, ServiceType.SLACK
            )
            if not token:
                raise Exception("No valid Slack token found. Please authenticate first.")
            
            # Clean channel name
            channel_name = channel_name.lstrip('#')
            
            # Get channel ID
            channel_id = await self._get_channel_id(token, channel_name)
            if not channel_id:
                raise Exception(f"Channel '{channel_name}' not found")
            
            # Get messages
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            
            params = {
                "channel": channel_id,
                "limit": min(limit, 1000),  # Slack API limit
                "include_all_metadata": True
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/conversations.history",
                    headers=headers,
                    params=params
                )
                
                if response.status_code != 200:
                    raise Exception(f"Slack API error: {response.status_code} - {response.text}")
                
                data = response.json()
                
                if not data.get("ok"):
                    raise Exception(f"Slack API error: {data.get('error')}")
                
                messages = data.get("messages", [])
                
                # Filter for unread messages if requested
                if unread_only:
                    # This would require additional API calls to get user's read status
                    # For now, we'll return recent messages (last hour)
                    one_hour_ago = datetime.utcnow().timestamp() - 3600
                    messages = [
                        msg for msg in messages 
                        if float(msg.get("ts", 0)) > one_hour_ago
                    ]
                
                # Enrich messages with user information
                enriched_messages = await self._enrich_messages(token, messages)
                
                return {
                    "channel": channel_name,
                    "channel_id": channel_id,
                    "message_count": len(enriched_messages),
                    "messages": enriched_messages,
                    "has_more": data.get("has_more", False),
                    "retrieved_at": datetime.utcnow().isoformat()
                }
                
        except Exception as e:
            logger.error(f"Failed to get Slack messages: {e}")
            raise
    
    async def send_message(
        self, 
        channel_name: str, 
        text: str, 
        thread_ts: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send a message to a Slack channel.
        
        Args:
            channel_name: Name of the channel
            text: Message text
            thread_ts: Optional thread timestamp for replies
            
        Returns:
            Message information
        """
        try:
            token = await oauth2_manager.get_valid_token(
                self.db, self.user_id, ServiceType.SLACK
            )
            if not token:
                raise Exception("No valid Slack token found")
            
            channel_name = channel_name.lstrip('#')
            channel_id = await self._get_channel_id(token, channel_name)
            
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "channel": channel_id,
                "text": text
            }
            
            if thread_ts:
                payload["thread_ts"] = thread_ts
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/chat.postMessage",
                    headers=headers,
                    json=payload
                )
                
                data = response.json()
                
                if not data.get("ok"):
                    raise Exception(f"Failed to send message: {data.get('error')}")
                
                return {
                    "message_ts": data.get("ts"),
                    "channel": channel_name,
                    "text": text,
                    "sent_at": datetime.utcnow().isoformat()
                }
                
        except Exception as e:
            logger.error(f"Failed to send Slack message: {e}")
            raise
    
    async def delete_message(self, channel_name: str, message_ts: str) -> Dict[str, Any]:
        """
        Delete a Slack message (for rollback capability).
        
        Args:
            channel_name: Name of the channel
            message_ts: Message timestamp
            
        Returns:
            Deletion confirmation
        """
        try:
            token = await oauth2_manager.get_valid_token(
                self.db, self.user_id, ServiceType.SLACK
            )
            if not token:
                raise Exception("No valid Slack token found")
            
            channel_name = channel_name.lstrip('#')
            channel_id = await self._get_channel_id(token, channel_name)
            
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "channel": channel_id,
                "ts": message_ts
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/chat.delete",
                    headers=headers,
                    json=payload
                )
                
                data = response.json()
                
                if not data.get("ok"):
                    raise Exception(f"Failed to delete message: {data.get('error')}")
                
                return {
                    "deleted": True,
                    "message_ts": message_ts,
                    "channel": channel_name,
                    "deleted_at": datetime.utcnow().isoformat()
                }
                
        except Exception as e:
            logger.error(f"Failed to delete Slack message: {e}")
            raise
    
    async def get_channels(self) -> List[Dict[str, Any]]:
        """Get list of channels the user has access to."""
        try:
            token = await oauth2_manager.get_valid_token(
                self.db, self.user_id, ServiceType.SLACK
            )
            if not token:
                raise Exception("No valid Slack token found")
            
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            
            params = {
                "exclude_archived": True,
                "types": "public_channel,private_channel"
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/conversations.list",
                    headers=headers,
                    params=params
                )
                
                data = response.json()
                
                if not data.get("ok"):
                    raise Exception(f"Failed to get channels: {data.get('error')}")
                
                channels = data.get("channels", [])
                
                return [
                    {
                        "id": channel["id"],
                        "name": channel["name"],
                        "is_private": channel.get("is_private", False),
                        "member_count": channel.get("num_members", 0),
                        "purpose": channel.get("purpose", {}).get("value", ""),
                        "topic": channel.get("topic", {}).get("value", "")
                    }
                    for channel in channels
                ]
                
        except Exception as e:
            logger.error(f"Failed to get Slack channels: {e}")
            raise
    
    async def _get_channel_id(self, token: str, channel_name: str) -> Optional[str]:
        """Get channel ID by name."""
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        params = {
            "exclude_archived": True,
            "types": "public_channel,private_channel"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/conversations.list",
                headers=headers,
                params=params
            )
            
            data = response.json()
            
            if not data.get("ok"):
                return None
            
            for channel in data.get("channels", []):
                if channel["name"] == channel_name:
                    return channel["id"]
            
            return None
    
    async def _enrich_messages(self, token: str, messages: List[Dict]) -> List[Dict[str, Any]]:
        """Enrich messages with user information."""
        if not messages:
            return messages
        
        # Get unique user IDs
        user_ids = set()
        for message in messages:
            if "user" in message:
                user_ids.add(message["user"])
        
        # Get user information
        user_info = {}
        if user_ids:
            user_info = await self._get_users_info(token, list(user_ids))
        
        # Enrich messages
        enriched = []
        for message in messages:
            enriched_msg = {
                "ts": message.get("ts"),
                "text": message.get("text", ""),
                "user_id": message.get("user"),
                "user_name": user_info.get(message.get("user"), {}).get("real_name", "Unknown"),
                "user_display_name": user_info.get(message.get("user"), {}).get("display_name", "Unknown"),
                "type": message.get("type", "message"),
                "subtype": message.get("subtype"),
                "thread_ts": message.get("thread_ts"),
                "reply_count": message.get("reply_count", 0),
                "reactions": message.get("reactions", []),
                "attachments": message.get("attachments", []),
                "blocks": message.get("blocks", []),
                "timestamp": datetime.fromtimestamp(float(message.get("ts", 0))).isoformat(),
                "has_urgency_keywords": self._check_urgency_keywords(message.get("text", ""))
            }
            enriched.append(enriched_msg)
        
        return enriched
    
    async def _get_users_info(self, token: str, user_ids: List[str]) -> Dict[str, Dict]:
        """Get user information for multiple users."""
        user_info = {}
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        # Slack API allows up to 50 users per request
        for i in range(0, len(user_ids), 50):
            batch = user_ids[i:i+50]
            
            params = {
                "users": ",".join(batch)
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/users.info",
                    headers=headers,
                    params=params
                )
                
                data = response.json()
                
                if data.get("ok") and "user" in data:
                    user = data["user"]
                    user_info[user["id"]] = {
                        "real_name": user.get("real_name", ""),
                        "display_name": user.get("profile", {}).get("display_name", ""),
                        "email": user.get("profile", {}).get("email", "")
                    }
        
        return user_info
    
    def _check_urgency_keywords(self, text: str) -> bool:
        """Check if message contains urgency keywords."""
        if not text:
            return False
        
        urgency_keywords = [
            "outage", "down", "critical", "emergency", "urgent", "broken",
            "failure", "error", "issue", "problem", "help", "fire", "alert",
            "crash", "bug", "incident", "escalate", "immediate", "asap"
        ]
        
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in urgency_keywords)