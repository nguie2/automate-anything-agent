#!/usr/bin/env python3
"""Main entry point for the AI Automation Agent FastAPI server."""

import uvicorn
from src.api.main import app
from src.config import settings

if __name__ == "__main__":
    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    ) 