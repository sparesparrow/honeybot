"""
FastAPI REST API for SCAIPOT admin dashboard
"""
from .server import app, create_app

__all__ = ["create_app", "app"]
