"""Core AI automation agent with OpenAI function calling capabilities."""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass
import asyncio

from sqlalchemy.orm import Session

from ..config import settings
from .llm_client import get_llm_client, LLMResponse
from ..database.models import AutomationAction, FunctionCall, ActionStatus, ServiceType
from ..integrations.slack import SlackIntegration
from ..integrations.jira import JiraIntegration  
from ..integrations.aws_s3 import AWSS3Integration
from ..integrations.github import GitHubIntegration
from ..utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class AgentResponse:
    """Response from agent execution."""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    action_id: Optional[int] = None
    rollback_available: bool = False


class AutomationAgent:
    """
    Core AI automation agent that uses OpenAI function calling to interact
    with multiple APIs and services.
    """
    
    def __init__(self, db_session: Session, user_id: int):
        """
        Initialize the automation agent.
        
        Args:
            db_session: Database session for logging
            user_id: ID of the user executing the automation
        """
        self.db = db_session
        self.user_id = user_id
        self.llm_client = get_llm_client()
        
        # Initialize service integrations
        self.integrations = {
            ServiceType.SLACK: SlackIntegration(db_session, user_id),
            ServiceType.JIRA: JiraIntegration(db_session, user_id),
            ServiceType.AWS_S3: AWSS3Integration(db_session, user_id),
            ServiceType.GITHUB: GitHubIntegration(db_session, user_id),
        }
        
        # Function definitions for OpenAI
        self.functions = self._build_function_definitions()
        
    def _build_function_definitions(self) -> List[Dict[str, Any]]:
        """Build OpenAI function definitions from available integrations."""
        functions = [
            {
                "name": "get_slack_messages",
                "description": "Get messages from a Slack channel",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "channel_name": {
                            "type": "string",
                            "description": "Name of the Slack channel (with or without #)"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Number of messages to retrieve (default: 50)",
                            "default": 50
                        },
                        "unread_only": {
                            "type": "boolean",
                            "description": "Only get unread messages",
                            "default": False
                        }
                    },
                    "required": ["channel_name"]
                }
            },
            {
                "name": "create_jira_ticket",
                "description": "Create a new Jira ticket/issue",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "project_key": {
                            "type": "string",
                            "description": "Jira project key (e.g., 'PROJ')"
                        },
                        "summary": {
                            "type": "string",
                            "description": "Brief summary/title of the issue"
                        },
                        "description": {
                            "type": "string",
                            "description": "Detailed description of the issue"
                        },
                        "issue_type": {
                            "type": "string",
                            "description": "Type of issue (e.g., Bug, Task, Story)",
                            "default": "Task"
                        },
                        "priority": {
                            "type": "string",
                            "description": "Priority level (Highest, High, Medium, Low, Lowest)",
                            "default": "Medium"
                        },
                        "labels": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Labels to add to the ticket"
                        }
                    },
                    "required": ["project_key", "summary", "description"]
                }
            },
            {
                "name": "upload_to_s3",
                "description": "Upload content to AWS S3",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "content": {
                            "type": "string",
                            "description": "Content to upload"
                        },
                        "key": {
                            "type": "string",
                            "description": "S3 object key/path"
                        },
                        "content_type": {
                            "type": "string",
                            "description": "MIME type of the content",
                            "default": "text/plain"
                        }
                    },
                    "required": ["content", "key"]
                }
            },
            {
                "name": "search_github_repos",
                "description": "Search GitHub repositories",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query"
                        },
                        "sort": {
                            "type": "string",
                            "description": "Sort by: stars, forks, updated",
                            "default": "stars"
                        },
                        "order": {
                            "type": "string",
                            "description": "Sort order: asc, desc",
                            "default": "desc"
                        }
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "analyze_text",
                "description": "Analyze text content for sentiment, keywords, or patterns",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "Text content to analyze"
                        },
                        "analysis_type": {
                            "type": "string",
                            "description": "Type of analysis: sentiment, keywords, urgency, summary",
                            "default": "summary"
                        }
                    },
                    "required": ["text"]
                }
            }
        ]
        return functions
    
    async def execute_command(self, command: str) -> AgentResponse:
        """
        Execute a natural language automation command.
        
        Args:
            command: Natural language command from user
            
        Returns:
            AgentResponse with execution results
        """
        # Create automation action record
        action = AutomationAction(
            user_id=self.user_id,
            action_type="ai_automation",
            command=command,
            status=ActionStatus.IN_PROGRESS,
            input_data={"command": command},
            started_at=datetime.utcnow()
        )
        self.db.add(action)
        self.db.commit()
        
        try:
            logger.info(f"Executing command: {command}")
            
            # Use OpenAI to determine which functions to call
            response = await self._call_llm_with_functions(command, action.id)
            
            # Update action status
            action.status = ActionStatus.COMPLETED
            action.completed_at = datetime.utcnow()
            action.duration_ms = int((action.completed_at - action.started_at).total_seconds() * 1000)
            action.output_data = response
            
            self.db.commit()
            
            return AgentResponse(
                success=True,
                message="Command executed successfully",
                data=response,
                action_id=action.id,
                rollback_available=action.can_rollback
            )
            
        except Exception as e:
            logger.error(f"Error executing command: {e}")
            action.status = ActionStatus.FAILED
            action.error_message = str(e)
            action.completed_at = datetime.utcnow()
            self.db.commit()
            
            return AgentResponse(
                success=False,
                message=f"Command execution failed: {str(e)}",
                action_id=action.id
            )
    
    async def _call_llm_with_functions(self, command: str, action_id: int) -> Dict[str, Any]:
        """
        Call LLM with function calling to determine and execute actions.
        
        Args:
            command: User command
            action_id: Database action ID for logging
            
        Returns:
            Execution results
        """
        messages = [
            {
                "role": "system",
                "content": """You are an AI automation agent that can interact with multiple services:
                - Slack: Get messages, analyze content
                - Jira: Create tickets, manage issues  
                - AWS S3: Upload and manage files
                - GitHub: Search repositories and code
                
                When users ask you to do something, break it down into function calls.
                For example, if asked to "summarize Slack messages and create a Jira ticket if urgent":
                1. Get Slack messages from the specified channel
                2. Analyze the messages for urgency/sentiment
                3. If urgent content is found, create a Jira ticket
                
                Always be specific about what you're doing and why."""
            },
            {
                "role": "user", 
                "content": command
            }
        ]
        
        response = await self.llm_client.chat_completion(
            messages=messages,
            functions=self.functions,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens
        )
        
        results = []
        
        # Handle function calls
        if response.has_function_calls:
            for function_call in response.function_calls:
                result = await self._execute_function_call(
                    function_call, action_id
                )
                results.append(result)
        
        # If no function calls, just return the message
        if not results:
            return {"response": response.content}
            
        return {
            "function_results": results,
            "summary": response.content if response.content else "Functions executed successfully"
        }
    
    async def _execute_function_call(self, function_call: Dict[str, Any], action_id: int) -> Dict[str, Any]:
        """
        Execute a specific function call and log it.
        
        Args:
            function_call: Function call dictionary with 'name' and 'arguments'
            action_id: Parent action ID
            
        Returns:
            Function execution result
        """
        function_name = function_call["name"]
        parameters = function_call["arguments"]
        
        # Log function call
        func_call = FunctionCall(
            automation_action_id=action_id,
            function_name=function_name,
            parameters=parameters,
            called_at=datetime.utcnow()
        )
        
        try:
            # Execute the function
            if function_name == "get_slack_messages":
                func_call.service_type = ServiceType.SLACK
                result = await self.integrations[ServiceType.SLACK].get_messages(
                    channel_name=parameters["channel_name"],
                    limit=parameters.get("limit", 50),
                    unread_only=parameters.get("unread_only", False)
                )
                
            elif function_name == "create_jira_ticket":
                func_call.service_type = ServiceType.JIRA
                result = await self.integrations[ServiceType.JIRA].create_ticket(
                    project_key=parameters["project_key"],
                    summary=parameters["summary"],
                    description=parameters["description"],
                    issue_type=parameters.get("issue_type", "Task"),
                    priority=parameters.get("priority", "Medium"),
                    labels=parameters.get("labels", [])
                )
                # Mark as rollback-able
                func_call.rollback_function = "delete_jira_ticket"
                func_call.rollback_parameters = {"ticket_key": result.get("key")}
                
            elif function_name == "upload_to_s3":
                func_call.service_type = ServiceType.AWS_S3
                result = await self.integrations[ServiceType.AWS_S3].upload_content(
                    content=parameters["content"],
                    key=parameters["key"],
                    content_type=parameters.get("content_type", "text/plain")
                )
                # Mark as rollback-able
                func_call.rollback_function = "delete_s3_object"
                func_call.rollback_parameters = {"key": parameters["key"]}
                
            elif function_name == "search_github_repos":
                func_call.service_type = ServiceType.GITHUB
                result = await self.integrations[ServiceType.GITHUB].search_repositories(
                    query=parameters["query"],
                    sort=parameters.get("sort", "stars"),
                    order=parameters.get("order", "desc")
                )
                
            elif function_name == "analyze_text":
                func_call.service_type = None  # Internal analysis function
                result = await self._analyze_text(
                    text=parameters["text"],
                    analysis_type=parameters.get("analysis_type", "summary")
                )
                
            else:
                raise ValueError(f"Unknown function: {function_name}")
            
            # Update function call record
            func_call.status = ActionStatus.COMPLETED
            func_call.response = result
            func_call.completed_at = datetime.utcnow()
            func_call.duration_ms = int(
                (func_call.completed_at - func_call.called_at).total_seconds() * 1000
            )
            
            self.db.add(func_call)
            self.db.commit()
            
            return {
                "function": function_name,
                "parameters": parameters,
                "result": result,
                "status": "success"
            }
            
        except Exception as e:
            logger.error(f"Function execution failed: {function_name} - {e}")
            func_call.status = ActionStatus.FAILED
            func_call.error_message = str(e)
            func_call.completed_at = datetime.utcnow()
            
            self.db.add(func_call)
            self.db.commit()
            
            return {
                "function": function_name,
                "parameters": parameters,
                "error": str(e),
                "status": "failed"
            }
    
    async def _analyze_text(self, text: str, analysis_type: str = "summary") -> Dict[str, Any]:
        """
        Analyze text using LLM for various purposes.
        
        Args:
            text: Text to analyze
            analysis_type: Type of analysis to perform
            
        Returns:
            Analysis results
        """
        prompts = {
            "sentiment": "Analyze the sentiment of this text. Return positive, negative, or neutral with confidence score.",
            "keywords": "Extract the key topics and important keywords from this text.",
            "urgency": "Determine if this text indicates an urgent issue. Look for words like 'outage', 'critical', 'emergency', 'down', etc.",
            "summary": "Provide a concise summary of this text, highlighting the main points."
        }
        
        prompt = prompts.get(analysis_type, prompts["summary"])
        
        response = await self.llm_client.chat_completion(
            messages=[
                {"role": "system", "content": f"{prompt}\n\nText to analyze: {text}"}
            ],
            temperature=0.1
        )
        
        return {
            "analysis_type": analysis_type,
            "result": response.content,
            "original_text_length": len(text)
        }
    
    async def rollback_action(self, action_id: int, reason: str = "") -> AgentResponse:
        """
        Rollback a previously executed action.
        
        Args:
            action_id: ID of the action to rollback
            reason: Reason for rollback
            
        Returns:
            Rollback result
        """
        action = self.db.query(AutomationAction).filter(
            AutomationAction.id == action_id,
            AutomationAction.user_id == self.user_id
        ).first()
        
        if not action:
            return AgentResponse(
                success=False,
                message="Action not found or access denied"
            )
        
        if not action.can_rollback:
            return AgentResponse(
                success=False,
                message="Action cannot be rolled back"
            )
        
        if action.status == ActionStatus.ROLLED_BACK:
            return AgentResponse(
                success=False,
                message="Action already rolled back"
            )
        
        try:
            # Rollback function calls in reverse order
            function_calls = self.db.query(FunctionCall).filter(
                FunctionCall.automation_action_id == action_id,
                FunctionCall.rollback_function.isnot(None)
            ).order_by(FunctionCall.called_at.desc()).all()
            
            rollback_results = []
            for func_call in function_calls:
                try:
                    # Execute rollback function
                    integration = self.integrations[func_call.service_type]
                    rollback_method = getattr(integration, func_call.rollback_function)
                    result = await rollback_method(**func_call.rollback_parameters)
                    rollback_results.append({
                        "function_call_id": func_call.id,
                        "rollback_function": func_call.rollback_function,
                        "result": result
                    })
                except Exception as e:
                    logger.error(f"Rollback failed for function call {func_call.id}: {e}")
                    rollback_results.append({
                        "function_call_id": func_call.id,
                        "rollback_function": func_call.rollback_function,
                        "error": str(e)
                    })
            
            # Update action status
            action.status = ActionStatus.ROLLED_BACK
            action.rolled_back_at = datetime.utcnow()
            action.rollback_reason = reason
            action.rollback_data = {"results": rollback_results}
            
            self.db.commit()
            
            return AgentResponse(
                success=True,
                message="Action rolled back successfully",
                data={"rollback_results": rollback_results},
                action_id=action_id
            )
            
        except Exception as e:
            logger.error(f"Rollback failed: {e}")
            return AgentResponse(
                success=False,
                message=f"Rollback failed: {str(e)}",
                action_id=action_id
            )