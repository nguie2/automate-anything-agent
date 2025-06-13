"""OAuth2 authentication and user management."""

import json
import secrets
import hashlib
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, Any, List
from urllib.parse import urlencode, urlparse, parse_qs
import requests
from sqlalchemy.orm import Session

from ..database.models import User, ServiceConnection, ActionLog
from ..database.connection import get_session
from ..config import config
from ..utils.logging_utils import get_logger

logger = get_logger(__name__)


class OAuth2Manager:
    """Manages OAuth2 flows for various services."""
    
    def __init__(self):
        self.oauth_configs = {
            'slack': {
                'client_id': config.SLACK_CLIENT_ID,
                'client_secret': config.SLACK_CLIENT_SECRET,
                'auth_url': 'https://slack.com/oauth/v2/authorize',
                'token_url': 'https://slack.com/api/oauth.v2.access',
                'scopes': ['chat:write', 'files:write', 'channels:read', 'users:read']
            },
            'jira': {
                'client_id': config.JIRA_CLIENT_ID,
                'client_secret': config.JIRA_CLIENT_SECRET,
                'auth_url': 'https://auth.atlassian.com/authorize',
                'token_url': 'https://auth.atlassian.com/oauth/token',
                'scopes': ['read:jira-work', 'write:jira-work', 'manage:jira-project']
            },
            'github': {
                'client_id': config.GITHUB_CLIENT_ID,
                'client_secret': config.GITHUB_CLIENT_SECRET,
                'auth_url': 'https://github.com/login/oauth/authorize',
                'token_url': 'https://github.com/login/oauth/access_token',
                'scopes': ['repo', 'user', 'workflow']
            }
        }
        self._state_cache = {}
    
    def generate_auth_url(self, service: str, user_id: int, redirect_uri: str) -> str:
        """Generate OAuth2 authorization URL for a service."""
        if service not in self.oauth_configs:
            raise ValueError(f"Unsupported service: {service}")
        
        config_data = self.oauth_configs[service]
        state = secrets.token_urlsafe(32)
        
        # Store state with user_id for verification
        self._state_cache[state] = {
            'user_id': user_id,
            'service': service,
            'timestamp': time.time()
        }
        
        params = {
            'client_id': config_data['client_id'],
            'redirect_uri': redirect_uri,
            'scope': ' '.join(config_data['scopes']),
            'state': state,
            'response_type': 'code'
        }
        
        # Service-specific parameters
        if service == 'jira':
            params['audience'] = 'api.atlassian.com'
            params['prompt'] = 'consent'
        elif service == 'github':
            params['allow_signup'] = 'false'
        
        auth_url = f"{config_data['auth_url']}?{urlencode(params)}"
        
        logger.info(f"Generated auth URL for {service}", extra={
            'user_id': user_id,
            'service': service
        })
        
        return auth_url
    
    def exchange_code_for_tokens(self, service: str, code: str, state: str, redirect_uri: str) -> Dict[str, Any]:
        """Exchange authorization code for access tokens."""
        # Verify state
        if state not in self._state_cache:
            raise ValueError("Invalid or expired state parameter")
        
        state_data = self._state_cache.pop(state)
        
        # Check if state is not too old (5 minutes max)
        if time.time() - state_data['timestamp'] > 300:
            raise ValueError("State parameter has expired")
        
        if service != state_data['service']:
            raise ValueError("Service mismatch in state parameter")
        
        config_data = self.oauth_configs[service]
        
        token_data = {
            'client_id': config_data['client_id'],
            'client_secret': config_data['client_secret'],
            'code': code,
            'redirect_uri': redirect_uri
        }
        
        # Service-specific token exchange
        if service == 'jira':
            token_data['grant_type'] = 'authorization_code'
        elif service == 'github':
            token_data['grant_type'] = 'authorization_code'
        elif service == 'slack':
            # Slack uses different parameter names
            token_data = {
                'client_id': config_data['client_id'],
                'client_secret': config_data['client_secret'],
                'code': code,
                'redirect_uri': redirect_uri
            }
        
        headers = {'Accept': 'application/json', 'Content-Type': 'application/x-www-form-urlencoded'}
        
        try:
            response = requests.post(
                config_data['token_url'],
                data=token_data,
                headers=headers,
                timeout=30
            )
            response.raise_for_status()
            
            tokens = response.json()
            
            if 'error' in tokens:
                raise ValueError(f"OAuth error: {tokens.get('error_description', tokens['error'])}")
            
            # Standardize token format
            standardized_tokens = {
                'access_token': tokens.get('access_token'),
                'refresh_token': tokens.get('refresh_token'),
                'expires_in': tokens.get('expires_in'),
                'token_type': tokens.get('token_type', 'Bearer'),
                'scope': tokens.get('scope', ' '.join(config_data['scopes'])),
                'service': service,
                'user_id': state_data['user_id']
            }
            
            # Service-specific handling
            if service == 'slack':
                standardized_tokens['team_id'] = tokens.get('team', {}).get('id')
                standardized_tokens['bot_user_id'] = tokens.get('bot_user_id')
            elif service == 'jira':
                standardized_tokens['resource_url'] = tokens.get('resource_url')
            
            logger.info(f"Successfully exchanged code for tokens", extra={
                'service': service,
                'user_id': state_data['user_id'],
                'has_refresh_token': bool(standardized_tokens.get('refresh_token'))
            })
            
            return standardized_tokens
            
        except requests.RequestException as e:
            logger.error(f"Failed to exchange code for tokens", extra={
                'service': service,
                'error': str(e)
            })
            raise ValueError(f"Token exchange failed: {str(e)}")
    
    def refresh_access_token(self, service: str, refresh_token: str) -> Dict[str, Any]:
        """Refresh an access token using refresh token."""
        if service not in self.oauth_configs:
            raise ValueError(f"Unsupported service: {service}")
        
        config_data = self.oauth_configs[service]
        
        refresh_data = {
            'client_id': config_data['client_id'],
            'client_secret': config_data['client_secret'],
            'refresh_token': refresh_token,
            'grant_type': 'refresh_token'
        }
        
        headers = {'Accept': 'application/json', 'Content-Type': 'application/x-www-form-urlencoded'}
        
        try:
            response = requests.post(
                config_data['token_url'],
                data=refresh_data,
                headers=headers,
                timeout=30
            )
            response.raise_for_status()
            
            tokens = response.json()
            
            if 'error' in tokens:
                raise ValueError(f"Token refresh error: {tokens.get('error_description', tokens['error'])}")
            
            refreshed_tokens = {
                'access_token': tokens.get('access_token'),
                'refresh_token': tokens.get('refresh_token', refresh_token),  # Some services don't return new refresh token
                'expires_in': tokens.get('expires_in'),
                'token_type': tokens.get('token_type', 'Bearer'),
                'scope': tokens.get('scope')
            }
            
            logger.info(f"Successfully refreshed access token for {service}")
            
            return refreshed_tokens
            
        except requests.RequestException as e:
            logger.error(f"Failed to refresh access token for {service}: {str(e)}")
            raise ValueError(f"Token refresh failed: {str(e)}")
    
    def revoke_token(self, service: str, token: str) -> bool:
        """Revoke an access token."""
        revoke_urls = {
            'slack': 'https://slack.com/api/auth.revoke',
            'jira': 'https://auth.atlassian.com/oauth/token/revoke',
            'github': None  # GitHub doesn't have a revoke endpoint
        }
        
        if service not in revoke_urls:
            return False
        
        revoke_url = revoke_urls[service]
        if not revoke_url:
            return True  # Consider it successful if no revoke endpoint
        
        try:
            if service == 'slack':
                response = requests.post(
                    revoke_url,
                    headers={'Authorization': f'Bearer {token}'},
                    timeout=30
                )
            else:
                response = requests.post(
                    revoke_url,
                    data={'token': token},
                    timeout=30
                )
            
            response.raise_for_status()
            logger.info(f"Successfully revoked token for {service}")
            return True
            
        except requests.RequestException as e:
            logger.error(f"Failed to revoke token for {service}: {str(e)}")
            return False


class UserManager:
    """Manages user authentication and sessions."""
    
    def __init__(self):
        self.session_cache = {}
    
    def hash_password(self, password: str) -> str:
        """Hash a password using PBKDF2."""
        salt = secrets.token_hex(16)
        hashed = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000)
        return f"{salt}:{hashed.hex()}"
    
    def verify_password(self, password: str, hashed_password: str) -> bool:
        """Verify a password against its hash."""
        try:
            salt, hash_hex = hashed_password.split(':')
            hashed = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000)
            return hashed.hex() == hash_hex
        except Exception:
            return False
    
    def create_user(self, username: str, email: str, password: str) -> User:
        """Create a new user."""
        with get_session() as session:
            # Check if user already exists
            existing_user = session.query(User).filter(
                (User.username == username) | (User.email == email)
            ).first()
            
            if existing_user:
                if existing_user.username == username:
                    raise ValueError("Username already exists")
                else:
                    raise ValueError("Email already exists")
            
            # Create new user
            user = User(
                username=username,
                email=email,
                password_hash=self.hash_password(password),
                is_active=True,
                created_at=datetime.utcnow()
            )
            
            session.add(user)
            session.commit()
            session.refresh(user)
            
            logger.info(f"Created new user: {username}", extra={
                'user_id': user.id,
                'email': email
            })
            
            return user
    
    def authenticate_user(self, username: str, password: str) -> Optional[User]:
        """Authenticate a user with username/password."""
        with get_session() as session:
            user = session.query(User).filter(
                (User.username == username) | (User.email == username)
            ).first()
            
            if user and user.is_active and self.verify_password(password, user.password_hash):
                # Update last login
                user.last_login = datetime.utcnow()
                session.commit()
                
                logger.info(f"User authenticated successfully", extra={
                    'user_id': user.id,
                    'username': user.username
                })
                
                return user
            
            logger.warning(f"Failed authentication attempt for username: {username}")
            return None
    
    def create_session(self, user_id: int) -> str:
        """Create a new session for a user."""
        session_token = secrets.token_urlsafe(32)
        
        self.session_cache[session_token] = {
            'user_id': user_id,
            'created_at': time.time(),
            'last_activity': time.time()
        }
        
        logger.info(f"Created session for user", extra={'user_id': user_id})
        
        return session_token
    
    def get_user_from_session(self, session_token: str) -> Optional[User]:
        """Get user from session token."""
        if session_token not in self.session_cache:
            return None
        
        session_data = self.session_cache[session_token]
        
        # Check if session is expired (24 hours)
        if time.time() - session_data['created_at'] > 86400:
            del self.session_cache[session_token]
            return None
        
        # Update last activity
        session_data['last_activity'] = time.time()
        
        with get_session() as session:
            user = session.query(User).filter(User.id == session_data['user_id']).first()
            if user and user.is_active:
                return user
            
            # Clean up invalid session
            del self.session_cache[session_token]
            return None
    
    def invalidate_session(self, session_token: str) -> bool:
        """Invalidate a session."""
        if session_token in self.session_cache:
            del self.session_cache[session_token]
            logger.info("Session invalidated")
            return True
        return False
    
    def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Get user by ID."""
        with get_session() as session:
            return session.query(User).filter(User.id == user_id).first()
    
    def get_user_by_username(self, username: str) -> Optional[User]:
        """Get user by username."""
        with get_session() as session:
            return session.query(User).filter(User.username == username).first()
    
    def update_user_profile(self, user_id: int, **updates) -> bool:
        """Update user profile."""
        with get_session() as session:
            user = session.query(User).filter(User.id == user_id).first()
            if not user:
                return False
            
            # Only allow certain fields to be updated
            allowed_fields = ['email', 'full_name']
            for field, value in updates.items():
                if field in allowed_fields and hasattr(user, field):
                    setattr(user, field, value)
            
            user.updated_at = datetime.utcnow()
            session.commit()
            
            logger.info(f"Updated user profile", extra={
                'user_id': user_id,
                'updated_fields': list(updates.keys())
            })
            
            return True
    
    def change_password(self, user_id: int, old_password: str, new_password: str) -> bool:
        """Change user password."""
        with get_session() as session:
            user = session.query(User).filter(User.id == user_id).first()
            if not user:
                return False
            
            # Verify old password
            if not self.verify_password(old_password, user.password_hash):
                logger.warning(f"Invalid old password for password change", extra={'user_id': user_id})
                return False
            
            # Update password
            user.password_hash = self.hash_password(new_password)
            user.updated_at = datetime.utcnow()
            session.commit()
            
            logger.info(f"Password changed successfully", extra={'user_id': user_id})
            
            return True
    
    def get_user_services(self, user_id: int) -> List[ServiceConnection]:
        """Get all connected services for a user."""
        with get_session() as session:
            return session.query(ServiceConnection).filter(
                ServiceConnection.user_id == user_id,
                ServiceConnection.is_active == True
            ).all()
    
    def cleanup_expired_sessions(self):
        """Clean up expired sessions."""
        current_time = time.time()
        expired_tokens = []
        
        for token, data in self.session_cache.items():
            if current_time - data['created_at'] > 86400:  # 24 hours
                expired_tokens.append(token)
        
        for token in expired_tokens:
            del self.session_cache[token]
        
        if expired_tokens:
            logger.info(f"Cleaned up {len(expired_tokens)} expired sessions")


# Global instances
oauth2_manager = OAuth2Manager()
user_manager = UserManager() 