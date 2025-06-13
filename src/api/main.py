"""FastAPI server for the automation agent with webhooks and API endpoints."""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, Request, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, EmailStr
import uvicorn

from ..auth.oauth2 import oauth2_manager, user_manager
from ..core.agent import AutomationAgent
from ..database.models import User, ServiceConnection, ActionLog
from ..database.connection import get_session
from ..utils.logging_utils import get_logger
from ..config import config

logger = get_logger(__name__)

# Pydantic models for API
class UserRegistration(BaseModel):
    username: str
    email: EmailStr
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime]

class ServiceConnectionResponse(BaseModel):
    id: int
    service_name: str
    service_user_id: Optional[str]
    is_active: bool
    connected_at: datetime
    last_used: Optional[datetime]

class CommandRequest(BaseModel):
    command: str
    context: Optional[Dict[str, Any]] = None

class CommandResponse(BaseModel):
    success: bool
    result: Optional[str]
    actions_taken: List[str]
    rollback_id: Optional[str]

class WebhookPayload(BaseModel):
    service: str
    event_type: str
    data: Dict[str, Any]
    timestamp: Optional[datetime] = None

# FastAPI app setup
app = FastAPI(
    title="Automation Agent API",
    description="API for the AI-powered automation agent with multi-service integration",
    version="1.0.0",
    docs_url="/docs" if config.ENVIRONMENT != "production" else None,
    redoc_url="/redoc" if config.ENVIRONMENT != "production" else None
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8080"],  # Add your frontend URLs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer()

# Global agent instance
agent = AutomationAgent()

# Dependency to get current user
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> User:
    """Get current authenticated user from token."""
    user = user_manager.get_user_from_session(credentials.credentials)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return user

# Authentication endpoints
@app.post("/auth/register", response_model=UserResponse)
async def register_user(user_data: UserRegistration):
    """Register a new user."""
    try:
        user = user_manager.create_user(
            username=user_data.username,
            email=user_data.email,
            password=user_data.password
        )
        
        return UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            is_active=user.is_active,
            created_at=user.created_at,
            last_login=user.last_login
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Registration failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Registration failed")

@app.post("/auth/login")
async def login_user(login_data: UserLogin):
    """Authenticate user and return session token."""
    user = user_manager.authenticate_user(login_data.username, login_data.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    session_token = user_manager.create_session(user.id)
    
    return {
        "access_token": session_token,
        "token_type": "bearer",
        "user": UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            is_active=user.is_active,
            created_at=user.created_at,
            last_login=user.last_login
        )
    }

@app.post("/auth/logout")
async def logout_user(current_user: User = Depends(get_current_user)):
    """Logout current user."""
    # In a real implementation, you'd get the token from the request
    # For now, we'll just acknowledge the logout
    return {"message": "Logged out successfully"}

@app.get("/auth/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user information."""
    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        is_active=current_user.is_active,
        created_at=current_user.created_at,
        last_login=current_user.last_login
    )

# OAuth2 endpoints
@app.get("/oauth/{service}/authorize")
async def oauth_authorize(service: str, current_user: User = Depends(get_current_user)):
    """Start OAuth2 authorization flow for a service."""
    try:
        redirect_uri = f"{config.BASE_URL}/oauth/{service}/callback"
        auth_url = oauth2_manager.generate_auth_url(service, current_user.id, redirect_uri)
        
        logger.info(f"Starting OAuth flow for {service}", extra={
            'user_id': current_user.id,
            'service': service
        })
        
        return {"auth_url": auth_url}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/oauth/{service}/callback")
async def oauth_callback(
    service: str,
    code: str,
    state: str,
    error: Optional[str] = None
):
    """Handle OAuth2 callback from service."""
    if error:
        logger.error(f"OAuth error for {service}: {error}")
        return HTMLResponse(f"""
            <html><body>
                <h1>Authorization Error</h1>
                <p>Error: {error}</p>
                <script>window.close();</script>
            </body></html>
        """)
    
    try:
        redirect_uri = f"{config.BASE_URL}/oauth/{service}/callback"
        tokens = oauth2_manager.exchange_code_for_tokens(service, code, state, redirect_uri)
        
        # Store service connection
        with get_session() as session:
            # Check if connection already exists
            existing_connection = session.query(ServiceConnection).filter(
                ServiceConnection.user_id == tokens['user_id'],
                ServiceConnection.service_name == service
            ).first()
            
            if existing_connection:
                # Update existing connection
                existing_connection.access_token = tokens['access_token']
                existing_connection.refresh_token = tokens.get('refresh_token')
                existing_connection.token_expires_at = (
                    datetime.utcnow() + timedelta(seconds=tokens['expires_in'])
                    if tokens.get('expires_in') else None
                )
                existing_connection.service_metadata = {
                    'scope': tokens.get('scope'),
                    'team_id': tokens.get('team_id'),
                    'bot_user_id': tokens.get('bot_user_id'),
                    'resource_url': tokens.get('resource_url')
                }
                existing_connection.is_active = True
                existing_connection.last_used = datetime.utcnow()
            else:
                # Create new connection
                connection = ServiceConnection(
                    user_id=tokens['user_id'],
                    service_name=service,
                    access_token=tokens['access_token'],
                    refresh_token=tokens.get('refresh_token'),
                    token_expires_at=(
                        datetime.utcnow() + timedelta(seconds=tokens['expires_in'])
                        if tokens.get('expires_in') else None
                    ),
                    service_metadata={
                        'scope': tokens.get('scope'),
                        'team_id': tokens.get('team_id'),
                        'bot_user_id': tokens.get('bot_user_id'),
                        'resource_url': tokens.get('resource_url')
                    },
                    is_active=True,
                    connected_at=datetime.utcnow()
                )
                session.add(connection)
            
            session.commit()
        
        logger.info(f"Successfully connected {service}", extra={
            'user_id': tokens['user_id'],
            'service': service
        })
        
        return HTMLResponse(f"""
            <html><body>
                <h1>Success!</h1>
                <p>{service.title()} has been connected successfully.</p>
                <script>window.close();</script>
            </body></html>
        """)
        
    except Exception as e:
        logger.error(f"OAuth callback failed for {service}: {str(e)}")
        return HTMLResponse(f"""
            <html><body>
                <h1>Connection Failed</h1>
                <p>Failed to connect {service}: {str(e)}</p>
                <script>window.close();</script>
            </body></html>
        """)

# Service management endpoints
@app.get("/services", response_model=List[ServiceConnectionResponse])
async def get_user_services(current_user: User = Depends(get_current_user)):
    """Get all connected services for the current user."""
    services = user_manager.get_user_services(current_user.id)
    
    return [
        ServiceConnectionResponse(
            id=service.id,
            service_name=service.service_name,
            service_user_id=service.service_user_id,
            is_active=service.is_active,
            connected_at=service.connected_at,
            last_used=service.last_used
        )
        for service in services
    ]

@app.delete("/services/{service_name}")
async def disconnect_service(
    service_name: str,
    current_user: User = Depends(get_current_user)
):
    """Disconnect a service for the current user."""
    with get_session() as session:
        connection = session.query(ServiceConnection).filter(
            ServiceConnection.user_id == current_user.id,
            ServiceConnection.service_name == service_name,
            ServiceConnection.is_active == True
        ).first()
        
        if not connection:
            raise HTTPException(status_code=404, detail="Service connection not found")
        
        # Revoke token if possible
        try:
            oauth2_manager.revoke_token(service_name, connection.access_token)
        except Exception as e:
            logger.warning(f"Failed to revoke token for {service_name}: {str(e)}")
        
        # Deactivate connection
        connection.is_active = False
        session.commit()
        
        logger.info(f"Disconnected {service_name}", extra={
            'user_id': current_user.id,
            'service': service_name
        })
        
        return {"message": f"{service_name} disconnected successfully"}

# Command execution endpoints
@app.post("/execute", response_model=CommandResponse)
async def execute_command(
    command_request: CommandRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    """Execute an automation command."""
    try:
        # Execute command asynchronously
        result = await asyncio.to_thread(
            agent.execute_command,
            command_request.command,
            current_user.id,
            command_request.context or {}
        )
        
        # Log execution in background
        background_tasks.add_task(
            log_command_execution,
            current_user.id,
            command_request.command,
            result
        )
        
        return CommandResponse(
            success=result.get('success', False),
            result=result.get('result'),
            actions_taken=result.get('actions_taken', []),
            rollback_id=result.get('rollback_id')
        )
        
    except Exception as e:
        logger.error(f"Command execution failed: {str(e)}", extra={
            'user_id': current_user.id,
            'command': command_request.command
        })
        raise HTTPException(status_code=500, detail=f"Execution failed: {str(e)}")

@app.post("/rollback/{rollback_id}")
async def rollback_actions(
    rollback_id: str,
    current_user: User = Depends(get_current_user)
):
    """Rollback actions using rollback ID."""
    try:
        result = await asyncio.to_thread(agent.rollback_actions, rollback_id, current_user.id)
        
        if result['success']:
            return {"message": "Actions rolled back successfully", "details": result}
        else:
            raise HTTPException(status_code=400, detail=result.get('error', 'Rollback failed'))
            
    except Exception as e:
        logger.error(f"Rollback failed: {str(e)}", extra={
            'user_id': current_user.id,
            'rollback_id': rollback_id
        })
        raise HTTPException(status_code=500, detail=f"Rollback failed: {str(e)}")

# Webhook endpoints
@app.post("/webhooks/slack")
async def slack_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_slack_signature: Optional[str] = Header(None),
    x_slack_request_timestamp: Optional[str] = Header(None)
):
    """Handle Slack webhooks."""
    body = await request.body()
    
    # Verify Slack signature if configured
    if config.SLACK_SIGNING_SECRET:
        # TODO: Implement Slack signature verification
        pass
    
    try:
        # Parse webhook data
        if request.headers.get('content-type') == 'application/json':
            data = json.loads(body)
        else:
            # Form-encoded data (URL verification)
            data = dict(await request.form())
        
        # Handle URL verification challenge
        if data.get('type') == 'url_verification':
            return {"challenge": data.get('challenge')}
        
        # Process webhook in background
        background_tasks.add_task(process_slack_webhook, data)
        
        return {"status": "ok"}
        
    except Exception as e:
        logger.error(f"Slack webhook processing failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Webhook processing failed")

@app.post("/webhooks/github")
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_github_event: Optional[str] = Header(None),
    x_github_signature_256: Optional[str] = Header(None)
):
    """Handle GitHub webhooks."""
    body = await request.body()
    
    # Verify GitHub signature if configured
    if config.GITHUB_WEBHOOK_SECRET:
        # TODO: Implement GitHub signature verification
        pass
    
    try:
        data = json.loads(body)
        
        # Process webhook in background
        background_tasks.add_task(process_github_webhook, x_github_event, data)
        
        return {"status": "ok"}
        
    except Exception as e:
        logger.error(f"GitHub webhook processing failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Webhook processing failed")

@app.post("/webhooks/jira")
async def jira_webhook(
    request: Request,
    background_tasks: BackgroundTasks
):
    """Handle Jira webhooks."""
    try:
        data = await request.json()
        
        # Process webhook in background
        background_tasks.add_task(process_jira_webhook, data)
        
        return {"status": "ok"}
        
    except Exception as e:
        logger.error(f"Jira webhook processing failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Webhook processing failed")

# Admin endpoints
@app.get("/admin/logs")
async def get_action_logs(
    limit: int = 100,
    offset: int = 0,
    current_user: User = Depends(get_current_user)
):
    """Get action logs for the current user."""
    with get_session() as session:
        logs = session.query(ActionLog).filter(
            ActionLog.user_id == current_user.id
        ).order_by(ActionLog.created_at.desc()).offset(offset).limit(limit).all()
        
        return [
            {
                "id": log.id,
                "action_type": log.action_type,
                "service_name": log.service_name,
                "status": log.status,
                "result_data": log.result_data,
                "error_message": log.error_message,
                "created_at": log.created_at,
                "rollback_data": log.rollback_data is not None
            }
            for log in logs
        ]

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow(),
        "version": "1.0.0"
    }

# Background task functions
async def log_command_execution(user_id: int, command: str, result: Dict[str, Any]):
    """Log command execution to database."""
    try:
        with get_session() as session:
            log = ActionLog(
                user_id=user_id,
                action_type="command_execution",
                service_name="agent",
                status="success" if result.get('success') else "error",
                result_data={"command": command, "result": result},
                created_at=datetime.utcnow()
            )
            session.add(log)
            session.commit()
    except Exception as e:
        logger.error(f"Failed to log command execution: {str(e)}")

async def process_slack_webhook(data: Dict[str, Any]):
    """Process Slack webhook data."""
    try:
        event_type = data.get('type')
        
        if event_type == 'event_callback':
            event = data.get('event', {})
            event_subtype = event.get('type')
            
            logger.info(f"Processing Slack event: {event_subtype}", extra={
                'event_data': event
            })
            
            # TODO: Implement specific event handling
            # For example: message events, file shared events, etc.
            
    except Exception as e:
        logger.error(f"Failed to process Slack webhook: {str(e)}")

async def process_github_webhook(event_type: str, data: Dict[str, Any]):
    """Process GitHub webhook data."""
    try:
        logger.info(f"Processing GitHub event: {event_type}", extra={
            'repository': data.get('repository', {}).get('full_name'),
            'action': data.get('action')
        })
        
        # TODO: Implement specific event handling
        # For example: push events, pull request events, issue events, etc.
        
    except Exception as e:
        logger.error(f"Failed to process GitHub webhook: {str(e)}")

async def process_jira_webhook(data: Dict[str, Any]):
    """Process Jira webhook data."""
    try:
        webhook_event = data.get('webhookEvent')
        issue_event_type = data.get('issue_event_type_name')
        
        logger.info(f"Processing Jira event: {webhook_event}", extra={
            'issue_event_type': issue_event_type,
            'issue_key': data.get('issue', {}).get('key')
        })
        
        # TODO: Implement specific event handling
        # For example: issue created, issue updated, etc.
        
    except Exception as e:
        logger.error(f"Failed to process Jira webhook: {str(e)}")

# Startup and shutdown events
@app.on_event("startup")
async def startup_event():
    """Initialize application on startup."""
    logger.info("Automation Agent API starting up")
    
    # Initialize database tables
    try:
        from ..database.connection import init_db
        init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {str(e)}")
    
    # Clean up expired sessions periodically
    asyncio.create_task(periodic_cleanup())

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up on application shutdown."""
    logger.info("Automation Agent API shutting down")

async def periodic_cleanup():
    """Periodic cleanup of expired sessions and tokens."""
    while True:
        try:
            user_manager.cleanup_expired_sessions()
            await asyncio.sleep(3600)  # Run every hour
        except Exception as e:
            logger.error(f"Periodic cleanup failed: {str(e)}")
            await asyncio.sleep(300)  # Wait 5 minutes before retrying

# Development server
if __name__ == "__main__":
    uvicorn.run(
        "src.api.main:app",
        host="0.0.0.0",
        port=config.API_PORT,
        reload=config.ENVIRONMENT == "development",
        log_level="info"
    ) 