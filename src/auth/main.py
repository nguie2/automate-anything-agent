"""Authentication utilities and CLI commands for user management."""

import click
from typing import Optional
from getpass import getpass

from .oauth2 import oauth2_manager, user_manager
from ..database.connection import get_session
from ..database.models import User, ServiceConnection
from ..utils.logging_utils import get_logger

logger = get_logger(__name__)


@click.group()
def auth():
    """Authentication and user management commands."""
    pass


@auth.command()
@click.option('--username', prompt=True, help='Username for the new account')
@click.option('--email', prompt=True, help='Email address for the new account')
@click.option('--password', prompt=True, hide_input=True, confirmation_prompt=True, help='Password for the new account')
def register(username: str, email: str, password: str):
    """Register a new user account."""
    try:
        user = user_manager.create_user(username, email, password)
        click.echo(f"✅ User '{username}' registered successfully!")
        click.echo(f"User ID: {user.id}")
        logger.info(f"New user registered: {username}")
    except ValueError as e:
        click.echo(f"❌ Registration failed: {e}", err=True)
    except Exception as e:
        click.echo(f"❌ Unexpected error: {e}", err=True)
        logger.error(f"Registration error: {e}")


@auth.command()
@click.option('--username', prompt=True, help='Username or email')
@click.option('--password', prompt=True, hide_input=True, help='Password')
def login(username: str, password: str):
    """Login to your account."""
    user = user_manager.authenticate_user(username, password)
    if user:
        session_token = user_manager.create_session(user.id)
        click.echo(f"✅ Welcome back, {user.username}!")
        click.echo(f"Session token: {session_token}")
        logger.info(f"User logged in: {user.username}")
        
        # Save session token to a file for CLI usage
        import os
        config_dir = os.path.expanduser("~/.automation-agent")
        os.makedirs(config_dir, exist_ok=True)
        
        with open(os.path.join(config_dir, "session"), "w") as f:
            f.write(session_token)
        
        click.echo(f"Session saved to {config_dir}/session")
    else:
        click.echo("❌ Invalid credentials", err=True)


@auth.command()
def logout():
    """Logout from your current session."""
    import os
    session_file = os.path.expanduser("~/.automation-agent/session")
    
    if os.path.exists(session_file):
        # Read session token
        with open(session_file, "r") as f:
            session_token = f.read().strip()
        
        # Invalidate session
        user_manager.invalidate_session(session_token)
        
        # Remove session file
        os.remove(session_file)
        click.echo("✅ Logged out successfully")
    else:
        click.echo("❌ No active session found")


@auth.command()
def whoami():
    """Show current user information."""
    session_token = get_current_session_token()
    if not session_token:
        click.echo("❌ Not logged in", err=True)
        return
    
    user = user_manager.get_user_from_session(session_token)
    if user:
        click.echo(f"Username: {user.username}")
        click.echo(f"Email: {user.email}")
        click.echo(f"User ID: {user.id}")
        click.echo(f"Created: {user.created_at}")
        click.echo(f"Last login: {user.last_login}")
        
        # Show connected services
        services = user_manager.get_user_services(user.id)
        if services:
            click.echo("\nConnected services:")
            for service in services:
                status = "✅" if service.is_active else "❌"
                click.echo(f"  {status} {service.service_name.title()}")
        else:
            click.echo("\nNo services connected")
    else:
        click.echo("❌ Invalid session", err=True)


@auth.command()
@click.argument('service', type=click.Choice(['slack', 'jira', 'github', 'aws']))
def connect(service: str):
    """Connect to a service via OAuth2."""
    session_token = get_current_session_token()
    if not session_token:
        click.echo("❌ Please login first", err=True)
        return
    
    user = user_manager.get_user_from_session(session_token)
    if not user:
        click.echo("❌ Invalid session", err=True)
        return
    
    try:
        # Generate OAuth URL
        redirect_uri = f"http://localhost:8000/oauth/{service}/callback"
        auth_url = oauth2_manager.generate_auth_url(service, user.id, redirect_uri)
        
        click.echo(f"🔗 Please visit this URL to authorize {service.title()}:")
        click.echo(f"\n{auth_url}\n")
        click.echo("After authorization, the connection will be saved automatically.")
        
    except Exception as e:
        click.echo(f"❌ Failed to generate authorization URL: {e}", err=True)


@auth.command()
@click.argument('service', type=click.Choice(['slack', 'jira', 'github', 'aws']))
def disconnect(service: str):
    """Disconnect from a service."""
    session_token = get_current_session_token()
    if not session_token:
        click.echo("❌ Please login first", err=True)
        return
    
    user = user_manager.get_user_from_session(session_token)
    if not user:
        click.echo("❌ Invalid session", err=True)
        return
    
    with get_session() as session:
        connection = session.query(ServiceConnection).filter(
            ServiceConnection.user_id == user.id,
            ServiceConnection.service_name == service,
            ServiceConnection.is_active == True
        ).first()
        
        if not connection:
            click.echo(f"❌ {service.title()} is not connected", err=True)
            return
        
        # Revoke token
        try:
            oauth2_manager.revoke_token(service, connection.access_token)
        except Exception as e:
            logger.warning(f"Failed to revoke token for {service}: {e}")
        
        # Deactivate connection
        connection.is_active = False
        session.commit()
        
        click.echo(f"✅ Disconnected from {service.title()}")


@auth.command()
@click.option('--old-password', prompt=True, hide_input=True, help='Current password')
@click.option('--new-password', prompt=True, hide_input=True, confirmation_prompt=True, help='New password')
def change_password(old_password: str, new_password: str):
    """Change your password."""
    session_token = get_current_session_token()
    if not session_token:
        click.echo("❌ Please login first", err=True)
        return
    
    user = user_manager.get_user_from_session(session_token)
    if not user:
        click.echo("❌ Invalid session", err=True)
        return
    
    if user_manager.change_password(user.id, old_password, new_password):
        click.echo("✅ Password changed successfully")
        logger.info(f"Password changed for user: {user.username}")
    else:
        click.echo("❌ Failed to change password. Check your current password.", err=True)


@auth.command()
def services():
    """List all connected services."""
    session_token = get_current_session_token()
    if not session_token:
        click.echo("❌ Please login first", err=True)
        return
    
    user = user_manager.get_user_from_session(session_token)
    if not user:
        click.echo("❌ Invalid session", err=True)
        return
    
    services = user_manager.get_user_services(user.id)
    
    if not services:
        click.echo("No services connected")
        click.echo("\nTo connect a service, use: automation-agent auth connect <service>")
        return
    
    click.echo("Connected services:")
    click.echo("-" * 50)
    
    for service in services:
        status = "Active" if service.is_active else "Inactive"
        click.echo(f"Service: {service.service_name.title()}")
        click.echo(f"Status: {status}")
        click.echo(f"Connected: {service.connected_at}")
        if service.last_used:
            click.echo(f"Last used: {service.last_used}")
        click.echo("-" * 30)


def get_current_session_token() -> Optional[str]:
    """Get the current session token from the stored file."""
    import os
    session_file = os.path.expanduser("~/.automation-agent/session")
    
    if os.path.exists(session_file):
        with open(session_file, "r") as f:
            return f.read().strip()
    return None


def get_current_user() -> Optional[User]:
    """Get the current authenticated user."""
    session_token = get_current_session_token()
    if session_token:
        return user_manager.get_user_from_session(session_token)
    return None


if __name__ == "__main__":
    auth() 