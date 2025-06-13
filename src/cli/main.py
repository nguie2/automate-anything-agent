"""Command-line interface for the AI automation agent."""

import asyncio
from datetime import datetime
from typing import Optional, List
import os

import typer
from rich.console import Console
from rich.table import Table
from rich.progress import Progress
from rich.panel import Panel
from rich.syntax import Syntax
from sqlalchemy.orm import Session

from ..database import get_db, create_tables
from ..database.models import User, AutomationAction, ActionStatus, ServiceType
from ..core.agent import AutomationAgent
from ..auth.oauth2 import user_manager, oauth2_manager
from ..config import settings
from ..utils.logging import get_logger

logger = get_logger(__name__)
console = Console()

app = typer.Typer(
    name="automation-agent",
    help="AI Automation Agent - Automate workflows across Slack, Jira, AWS S3, and more!"
)

# Global variables
current_user_id: Optional[int] = None
db_session: Optional[Session] = None


def init_database():
    """Initialize database tables."""
    try:
        create_tables()
        console.print("✅ Database initialized successfully", style="green")
    except Exception as e:
        console.print(f"❌ Database initialization failed: {e}", style="red")
        raise typer.Exit(1)


def get_current_user() -> int:
    """Get current authenticated user ID."""
    global current_user_id
    if not current_user_id:
        console.print("❌ Not authenticated. Please login first.", style="red")
        raise typer.Exit(1)
    return current_user_id


def get_db_session() -> Session:
    """Get database session."""
    global db_session
    if not db_session:
        db_session = next(get_db())
    return db_session


@app.command()
def init():
    """Initialize the automation agent database."""
    console.print("🚀 Initializing AI Automation Agent...", style="blue")
    init_database()


@app.command()
def register(
    username: str = typer.Option(..., prompt=True, help="Username"),
    email: str = typer.Option(..., prompt=True, help="Email address"),
    password: str = typer.Option(..., prompt=True, hide_input=True, help="Password")
):
    """Register a new user."""
    try:
        db = get_db_session()
        
        # Check if user already exists
        existing_user = db.query(User).filter(
            (User.username == username) | (User.email == email)
        ).first()
        
        if existing_user:
            console.print("❌ User with this username or email already exists", style="red")
            raise typer.Exit(1)
        
        # Create user
        user = user_manager.create_user(db, username, email, password)
        
        console.print(f"✅ User '{username}' registered successfully!", style="green")
        console.print(f"User ID: {user.id}", style="blue")
        
    except Exception as e:
        console.print(f"❌ Registration failed: {e}", style="red")
        raise typer.Exit(1)


@app.command()
def login(
    username: str = typer.Option(..., prompt=True, help="Username"),
    password: str = typer.Option(..., prompt=True, hide_input=True, help="Password")
):
    """Login to the automation agent."""
    global current_user_id
    
    try:
        db = get_db_session()
        user = user_manager.authenticate_user(db, username, password)
        
        if not user:
            console.print("❌ Invalid username or password", style="red")
            raise typer.Exit(1)
        
        current_user_id = user.id
        
        # Create access token for session
        token = user_manager.create_access_token({"sub": str(user.id)})
        
        console.print(f"✅ Welcome back, {user.username}!", style="green")
        console.print(f"🔑 Session token: {token[:20]}...", style="blue")
        
        # Show connected services
        console.print("🔌 Use 'automation-agent status' to see connected services", style="blue")
        
    except Exception as e:
        console.print(f"❌ Login failed: {e}", style="red")
        raise typer.Exit(1)


@app.command()
def connect(
    service: str = typer.Argument(help="Service to connect (slack, jira, github)")
):
    """Connect to an external service via OAuth2."""
    try:
        user_id = get_current_user()
        
        # Map service names to enum values
        service_map = {
            "slack": ServiceType.SLACK,
            "jira": ServiceType.JIRA,
            "github": ServiceType.GITHUB
        }
        
        if service.lower() not in service_map:
            console.print(f"❌ Unsupported service: {service}", style="red")
            console.print("Supported services: slack, jira, github", style="blue")
            raise typer.Exit(1)
        
        service_type = service_map[service.lower()]
        
        # Generate OAuth2 authorization URL
        auth_url = oauth2_manager.get_authorization_url(service_type)
        
        console.print(f"🔗 Connect to {service.title()}:", style="blue")
        console.print(f"\n{auth_url}\n", style="cyan")
        console.print("After authorizing, the app will handle the callback automatically.", style="yellow")
        
    except Exception as e:
        console.print(f"❌ Connection setup failed: {e}", style="red")
        raise typer.Exit(1)


@app.command()
def execute(command: str = typer.Argument(help="Natural language automation command")):
    """Execute an automation command."""
    asyncio.run(execute_command_async(command))


async def execute_command_async(command: str):
    """Execute automation command asynchronously."""
    try:
        user_id = get_current_user()
        db = get_db_session()
        
        # Create agent
        agent = AutomationAgent(db, user_id)
        
        console.print(f"🤖 Executing: {command}", style="blue")
        
        with Progress() as progress:
            task = progress.add_task("Processing...", total=100)
            
            # Execute command
            response = await agent.execute_command(command)
            progress.update(task, advance=100)
        
        if response.success:
            console.print("✅ Command executed successfully!", style="green")
            
            # Display results
            if response.data:
                console.print("\n📊 Results:", style="blue")
                
                # Pretty print the results
                if isinstance(response.data, dict):
                    for key, value in response.data.items():
                        if key == "function_results":
                            console.print(f"\n🔧 Function Calls:", style="cyan")
                            for result in value:
                                status_style = "green" if result.get("status") == "success" else "red"
                                console.print(f"  • {result.get('function')}: ", style="white", end="")
                                console.print(result.get("status", "unknown"), style=status_style)
                        else:
                            console.print(f"  {key}: {value}")
            
            # Show rollback info
            if response.rollback_available:
                console.print(f"\n🔄 Rollback available (Action ID: {response.action_id})", style="yellow")
                console.print("Use 'automation-agent rollback <action_id>' to undo this action", style="yellow")
        
        else:
            console.print(f"❌ Command failed: {response.message}", style="red")
            if response.action_id:
                console.print(f"Action ID: {response.action_id}", style="blue")
        
    except Exception as e:
        console.print(f"❌ Execution failed: {e}", style="red")
        raise typer.Exit(1)


@app.command()
def rollback(action_id: int = typer.Argument(help="Action ID to rollback")):
    """Rollback a previously executed action."""
    asyncio.run(rollback_action_async(action_id))


async def rollback_action_async(action_id: int):
    """Rollback action asynchronously."""
    try:
        user_id = get_current_user()
        db = get_db_session()
        
        agent = AutomationAgent(db, user_id)
        
        reason = typer.prompt("Reason for rollback (optional)", default="User requested rollback")
        
        console.print(f"🔄 Rolling back action {action_id}...", style="yellow")
        
        response = await agent.rollback_action(action_id, reason)
        
        if response.success:
            console.print("✅ Action rolled back successfully!", style="green")
            if response.data:
                console.print(f"Rollback details: {response.data}", style="blue")
        else:
            console.print(f"❌ Rollback failed: {response.message}", style="red")
        
    except Exception as e:
        console.print(f"❌ Rollback failed: {e}", style="red")
        raise typer.Exit(1)


@app.command()
def history(limit: int = typer.Option(10, help="Number of recent actions to show")):
    """Show automation history."""
    try:
        user_id = get_current_user()
        db = get_db_session()
        
        actions = db.query(AutomationAction).filter(
            AutomationAction.user_id == user_id
        ).order_by(AutomationAction.started_at.desc()).limit(limit).all()
        
        if not actions:
            console.print("No automation history found.", style="yellow")
            return
        
        table = Table(title="Automation History")
        table.add_column("ID", style="cyan")
        table.add_column("Command", style="white")
        table.add_column("Status", style="green")
        table.add_column("Started", style="blue")
        table.add_column("Duration", style="magenta")
        
        for action in actions:
            status_style = {
                ActionStatus.COMPLETED: "green",
                ActionStatus.FAILED: "red",
                ActionStatus.IN_PROGRESS: "yellow",
                ActionStatus.ROLLED_BACK: "orange1"
            }.get(action.status, "white")
            
            duration = "N/A"
            if action.duration_ms:
                duration = f"{action.duration_ms}ms"
            
            table.add_row(
                str(action.id),
                action.command[:50] + "..." if len(action.command) > 50 else action.command,
                action.status.value,
                action.started_at.strftime("%Y-%m-%d %H:%M:%S"),
                duration
            )
        
        console.print(table)
        
    except Exception as e:
        console.print(f"❌ Failed to get history: {e}", style="red")
        raise typer.Exit(1)


@app.command()
def status():
    """Show current agent status and connections."""
    asyncio.run(show_status_async())


async def show_status_async():
    """Show status asynchronously."""
    try:
        user_id = get_current_user()
        db = get_db_session()
        
        user = db.query(User).filter(User.id == user_id).first()
        
        console.print(Panel.fit(
            f"👤 User: {user.username}\n"
            f"📧 Email: {user.email}\n"
            f"🆔 ID: {user.id}\n"
            f"📅 Created: {user.created_at.strftime('%Y-%m-%d %H:%M:%S')}",
            title="User Information",
            style="blue"
        ))
        
        await show_connected_services()
        
    except Exception as e:
        console.print(f"❌ Failed to get status: {e}", style="red")
        raise typer.Exit(1)


async def show_connected_services():
    """Show connected services."""
    try:
        user_id = get_current_user()
        db = get_db_session()
        
        from ..database.models import OAuthToken
        
        tokens = db.query(OAuthToken).filter(OAuthToken.user_id == user_id).all()
        
        if not tokens:
            console.print("🔌 No services connected", style="yellow")
            return
        
        table = Table(title="Connected Services")
        table.add_column("Service", style="cyan")
        table.add_column("Status", style="green")
        table.add_column("Connected", style="blue")
        table.add_column("Expires", style="magenta")
        
        for token in tokens:
            status = "✅ Active"
            if token.expires_at and token.expires_at <= datetime.utcnow():
                status = "⚠️ Expired"
            
            expires = "Never"
            if token.expires_at:
                expires = token.expires_at.strftime("%Y-%m-%d %H:%M:%S")
            
            table.add_row(
                token.service_type.value.title(),
                status,
                token.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                expires
            )
        
        console.print(table)
        
    except Exception as e:
        console.print(f"❌ Failed to get connected services: {e}", style="red")


@app.command()
def examples():
    """Show example automation commands."""
    console.print(Panel.fit(
        "🤖 Example Automation Commands:\n\n"
        "• 'Summarize unread Slack messages from #urgent and create a high-priority Jira ticket if any contain the word \"outage\"'\n\n"
        "• 'Get messages from #general channel and upload a summary to S3 as daily-report.txt'\n\n"
        "• 'Search GitHub for python automation repositories and save the top 5 to S3'\n\n"
        "• 'Check #alerts channel for critical messages and create Jira tickets for each urgent issue'\n\n"
        "• 'Analyze sentiment of messages in #feedback channel and create a summary report'",
        title="Example Commands",
        style="green"
    ))


if __name__ == "__main__":
    app() 