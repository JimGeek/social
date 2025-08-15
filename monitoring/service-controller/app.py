#!/usr/bin/env python3
"""
Production Service Controller API
Handles service restart requests from Grafana dashboards
Supports multiple projects and service types
"""

import os
import yaml
import subprocess
import psutil
import docker
from typing import Dict, List, Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException, Security, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import uvicorn

# Configuration
PROJECTS_CONFIG = os.getenv('PROJECTS_CONFIG', '/app/projects.yml')
API_TOKEN = os.getenv('API_TOKEN', 'monitoring-api-token-2025')

app = FastAPI(
    title="Production Service Controller",
    description="API for managing services across multiple projects",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

security = HTTPBearer()

# Models
class ServiceRestartRequest(BaseModel):
    project: str
    service: str
    action: str  # restart, start, stop, status

class ServiceStatus(BaseModel):
    name: str
    status: str
    pid: Optional[int] = None
    uptime: Optional[str] = None
    cpu_percent: Optional[float] = None
    memory_percent: Optional[float] = None

class ProjectStatus(BaseModel):
    project: str
    services: List[ServiceStatus]
    last_updated: datetime

# Load projects configuration
def load_projects_config():
    try:
        with open(PROJECTS_CONFIG, 'r') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        return {
            'projects': {
                'social-media': {
                    'supervisor_config': '/etc/supervisor/conf.d/social-api.conf',
                    'services': {
                        'gunicorn': 'social-api-gunicorn',
                        'celery-worker': 'social-api-celery-worker',
                        'celery-beat': 'social-api-celery-beat',
                        'redis': 'redis-server'
                    }
                }
            }
        }

# Authentication
def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)):
    if credentials.credentials != API_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid API token")
    return credentials.credentials

# Service Management Functions
def get_service_status_supervisor(service_name: str) -> Dict:
    """Get service status using supervisorctl"""
    try:
        result = subprocess.run(
            ['supervisorctl', 'status', service_name],
            capture_output=True, text=True, timeout=10
        )
        
        if result.returncode == 0:
            output = result.stdout.strip()
            if 'RUNNING' in output:
                # Extract PID if available
                parts = output.split()
                pid = None
                for i, part in enumerate(parts):
                    if part == 'pid' and i + 1 < len(parts):
                        pid = int(parts[i + 1].rstrip(','))
                        break
                
                return {
                    'status': 'running',
                    'pid': pid,
                    'raw_output': output
                }
            elif 'STOPPED' in output:
                return {'status': 'stopped', 'raw_output': output}
            elif 'FATAL' in output:
                return {'status': 'failed', 'raw_output': output}
        
        return {'status': 'unknown', 'raw_output': result.stdout}
    
    except Exception as e:
        return {'status': 'error', 'error': str(e)}

def restart_service_supervisor(service_name: str) -> Dict:
    """Restart service using supervisorctl"""
    try:
        result = subprocess.run(
            ['supervisorctl', 'restart', service_name],
            capture_output=True, text=True, timeout=30
        )
        
        if result.returncode == 0:
            return {
                'success': True,
                'message': f'Service {service_name} restarted successfully',
                'output': result.stdout
            }
        else:
            return {
                'success': False,
                'message': f'Failed to restart {service_name}',
                'error': result.stderr
            }
    
    except Exception as e:
        return {
            'success': False,
            'message': f'Exception restarting {service_name}',
            'error': str(e)
        }

def get_process_metrics(pid: int) -> Dict:
    """Get CPU and memory metrics for a process"""
    try:
        process = psutil.Process(pid)
        return {
            'cpu_percent': process.cpu_percent(interval=1),
            'memory_percent': process.memory_percent(),
            'uptime': str(datetime.now() - datetime.fromtimestamp(process.create_time()))
        }
    except:
        return {}

# API Endpoints
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "Production Service Controller",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/projects")
async def list_projects(token: str = Depends(verify_token)):
    """List all configured projects"""
    config = load_projects_config()
    return {
        "projects": list(config.get('projects', {}).keys()),
        "total": len(config.get('projects', {}))
    }

@app.get("/projects/{project}/services")
async def get_project_services(project: str, token: str = Depends(verify_token)):
    """Get all services for a specific project"""
    config = load_projects_config()
    
    if project not in config.get('projects', {}):
        raise HTTPException(status_code=404, detail=f"Project {project} not found")
    
    project_config = config['projects'][project]
    services = []
    
    for service_type, service_name in project_config.get('services', {}).items():
        status_info = get_service_status_supervisor(service_name)
        
        service_status = ServiceStatus(
            name=service_name,
            status=status_info.get('status', 'unknown')
        )
        
        # Add process metrics if running
        if status_info.get('pid'):
            metrics = get_process_metrics(status_info['pid'])
            service_status.pid = status_info['pid']
            service_status.cpu_percent = metrics.get('cpu_percent')
            service_status.memory_percent = metrics.get('memory_percent')
            service_status.uptime = metrics.get('uptime')
        
        services.append(service_status)
    
    return ProjectStatus(
        project=project,
        services=services,
        last_updated=datetime.now()
    )

@app.post("/projects/{project}/services/{service}/restart")
async def restart_service(project: str, service: str, token: str = Depends(verify_token)):
    """Restart a specific service"""
    config = load_projects_config()
    
    if project not in config.get('projects', {}):
        raise HTTPException(status_code=404, detail=f"Project {project} not found")
    
    project_config = config['projects'][project]
    
    if service not in project_config.get('services', {}):
        raise HTTPException(status_code=404, detail=f"Service {service} not found in project {project}")
    
    service_name = project_config['services'][service]
    result = restart_service_supervisor(service_name)
    
    if result.get('success'):
        return {
            "message": f"Service {service} restarted successfully",
            "project": project,
            "service": service,
            "supervisor_service": service_name,
            "timestamp": datetime.now().isoformat(),
            "details": result
        }
    else:
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to restart service {service}: {result.get('error', 'Unknown error')}"
        )

@app.get("/system/metrics")
async def get_system_metrics(token: str = Depends(verify_token)):
    """Get system-wide metrics"""
    try:
        return {
            "cpu_percent": psutil.cpu_percent(interval=1),
            "memory": {
                "total": psutil.virtual_memory().total,
                "available": psutil.virtual_memory().available,
                "percent": psutil.virtual_memory().percent
            },
            "disk": {
                "total": psutil.disk_usage('/').total,
                "used": psutil.disk_usage('/').used,
                "free": psutil.disk_usage('/').free,
                "percent": psutil.disk_usage('/').percent
            },
            "load_average": list(psutil.getloadavg()) if hasattr(psutil, 'getloadavg') else None,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get system metrics: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8080,
        log_level="info",
        access_log=True
    )