"""
FastAPI REST API for SCAIPOT admin dashboard
"""
from .server import create_app, app

__all__ = ["create_app", "app"]
