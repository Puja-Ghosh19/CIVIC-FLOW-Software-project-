"""WSGI entry point for production hosting (Render, etc.)."""
from app import app, init_db

# Create/upgrade tables and seed initial service data when the server starts.
# Database environment variables must be configured before deployment.
init_db()
