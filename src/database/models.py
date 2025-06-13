"""Database models for the AI automation agent."""

from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Boolean, 
    JSON, ForeignKey, Enum as SQLEnum, Index
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum


Base = declarative_base()


class ActionStatus(enum.Enum):
    """Status of an automation action."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class ServiceType(enum.Enum):
    """Supported service types."""
    SLACK = "slack"
    JIRA = "jira"
    AWS_S3 = "aws_s3"
    GITHUB = "github"
    OPENAI = "openai"


class User(Base):
    """User model for authentication and authorization."""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    oauth_tokens = relationship("OAuthToken", back_populates="user")
    automation_actions = relationship("AutomationAction", back_populates="user")


class OAuthToken(Base):
    """OAuth tokens for external service authentication."""
    __tablename__ = "oauth_tokens"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    service_type = Column(SQLEnum(ServiceType), nullable=False)
    access_token = Column(Text, nullable=False)
    refresh_token = Column(Text, nullable=True)
    token_type = Column(String(50), default="Bearer")
    expires_at = Column(DateTime(timezone=True), nullable=True)
    scope = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="oauth_tokens")
    
    # Indexes
    __table_args__ = (
        Index("idx_oauth_user_service", "user_id", "service_type"),
    )


class AutomationAction(Base):
    """Log of all automation actions with rollback capability."""
    __tablename__ = "automation_actions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    action_type = Column(String(100), nullable=False)  # e.g., "slack_to_jira", "analyze_messages"
    command = Column(Text, nullable=False)  # Original user command
    status = Column(SQLEnum(ActionStatus), default=ActionStatus.PENDING)
    
    # Input/Output tracking
    input_data = Column(JSON, nullable=True)  # Input parameters
    output_data = Column(JSON, nullable=True)  # Results/response
    error_message = Column(Text, nullable=True)
    
    # Service interactions
    services_used = Column(JSON, nullable=True)  # List of services called
    api_calls = Column(JSON, nullable=True)  # Detailed API call logs
    
    # Rollback information
    rollback_data = Column(JSON, nullable=True)  # Data needed for rollback
    can_rollback = Column(Boolean, default=False)
    rolled_back_at = Column(DateTime(timezone=True), nullable=True)
    rollback_reason = Column(Text, nullable=True)
    
    # Timing
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    duration_ms = Column(Integer, nullable=True)  # Duration in milliseconds
    
    # Metadata
    metadata = Column(JSON, nullable=True)  # Additional context
    
    # Relationships
    user = relationship("User", back_populates="automation_actions")
    function_calls = relationship("FunctionCall", back_populates="automation_action")
    
    # Indexes
    __table_args__ = (
        Index("idx_action_user_status", "user_id", "status"),
        Index("idx_action_type", "action_type"),
        Index("idx_action_started_at", "started_at"),
    )


class FunctionCall(Base):
    """Individual OpenAI function calls within an automation action."""
    __tablename__ = "function_calls"
    
    id = Column(Integer, primary_key=True, index=True)
    automation_action_id = Column(Integer, ForeignKey("automation_actions.id"), nullable=False)
    function_name = Column(String(100), nullable=False)
    service_type = Column(SQLEnum(ServiceType), nullable=False)
    
    # Function call details
    parameters = Column(JSON, nullable=True)
    response = Column(JSON, nullable=True)
    status = Column(SQLEnum(ActionStatus), default=ActionStatus.PENDING)
    error_message = Column(Text, nullable=True)
    
    # Timing
    called_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    duration_ms = Column(Integer, nullable=True)
    
    # Rollback information
    rollback_function = Column(String(100), nullable=True)  # Function to call for rollback
    rollback_parameters = Column(JSON, nullable=True)
    
    # Relationships
    automation_action = relationship("AutomationAction", back_populates="function_calls")
    
    # Indexes
    __table_args__ = (
        Index("idx_function_action_status", "automation_action_id", "status"),
        Index("idx_function_service", "service_type"),
    )


class WebhookEvent(Base):
    """Webhook events received from external services."""
    __tablename__ = "webhook_events"
    
    id = Column(Integer, primary_key=True, index=True)
    service_type = Column(SQLEnum(ServiceType), nullable=False)
    event_type = Column(String(100), nullable=False)
    event_id = Column(String(255), nullable=True)  # Service-specific event ID
    
    # Event data
    headers = Column(JSON, nullable=True)
    payload = Column(JSON, nullable=False)
    signature = Column(String(255), nullable=True)  # Webhook signature for verification
    
    # Processing
    processed = Column(Boolean, default=False)
    processed_at = Column(DateTime(timezone=True), nullable=True)
    processing_error = Column(Text, nullable=True)
    
    # Automation trigger
    triggered_action_id = Column(Integer, ForeignKey("automation_actions.id"), nullable=True)
    
    # Timing
    received_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Indexes
    __table_args__ = (
        Index("idx_webhook_service_processed", "service_type", "processed"),
        Index("idx_webhook_received_at", "received_at"),
    ) 