"""
Health monitoring URLs for Social Media Manager
"""

from django.urls import path
from . import health_monitor

urlpatterns = [
    # Health dashboard (requires admin login)
    path('', health_monitor.health_dashboard, name='health_dashboard'),
    
    # Prometheus metrics endpoint (public for scraping)
    path('metrics', health_monitor.metrics_view, name='health_metrics'),
    
    # Health API for real-time data (requires admin login)
    path('api', health_monitor.health_api, name='health_api'),
    
    # Control API for service management (requires admin login)
    path('control', health_monitor.health_control, name='health_control'),
]