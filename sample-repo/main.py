"""
Main application entry point.
"""

import os
from typing import Optional

from config.settings import Settings
from src.auth import authenticate_user, create_access_token
from src.database import get_db_connection
from src.api import create_app


def main() -> None:
    """Initialize and run the application."""
    settings = Settings()
    
    # Initialize database
    db = get_db_connection(settings.database_url)
    
    # Create FastAPI app
    app = create_app(settings)
    
    # Run server
    import uvicorn
    uvicorn.run(app, host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()