"""
Health monitoring and metrics collection for Social Media Manager
Provides Prometheus metrics and system health information
"""

import os
import sys
import json
import subprocess
import logging
from datetime import datetime
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
import psutil
import redis
from celery import Celery
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST

# Setup logging
logger = logging.getLogger(__name__)

# Prometheus Metrics
REQUEST_COUNT = Counter('http_requests_total', 'Total HTTP requests', ['method', 'endpoint', 'status'])
REQUEST_DURATION = Histogram('http_request_duration_seconds', 'HTTP request duration')
GUNICORN_WORKERS = Gauge('gunicorn_workers_active', 'Active Gunicorn workers')
CELERY_QUEUE_LENGTH = Gauge('celery_queue_length', 'Celery queue length', ['queue'])
CELERY_ACTIVE_TASKS = Gauge('celery_active_tasks', 'Active Celery tasks')
CELERY_FAILED_TASKS = Counter('celery_failed_tasks_total', 'Total failed Celery tasks')
REDIS_CONNECTED_CLIENTS = Gauge('redis_connected_clients', 'Redis connected clients')
REDIS_USED_MEMORY = Gauge('redis_used_memory_bytes', 'Redis used memory in bytes')
SYSTEM_CPU_USAGE = Gauge('system_cpu_usage_percent', 'System CPU usage percentage')
SYSTEM_MEMORY_USAGE = Gauge('system_memory_usage_percent', 'System memory usage percentage')
SYSTEM_DISK_USAGE = Gauge('system_disk_usage_percent', 'System disk usage percentage')

def get_system_metrics():
    """Collect system metrics"""
    try:
        # CPU usage
        cpu_percent = psutil.cpu_percent(interval=1)
        SYSTEM_CPU_USAGE.set(cpu_percent)
        
        # Memory usage
        memory = psutil.virtual_memory()
        SYSTEM_MEMORY_USAGE.set(memory.percent)
        
        # Disk usage
        disk = psutil.disk_usage('/')
        disk_percent = (disk.used / disk.total) * 100
        SYSTEM_DISK_USAGE.set(disk_percent)
        
        return {
            'cpu_percent': cpu_percent,
            'memory_percent': memory.percent,
            'memory_total': memory.total,
            'memory_used': memory.used,
            'disk_percent': disk_percent,
            'disk_total': disk.total,
            'disk_used': disk.used
        }
    except Exception as e:
        logger.error(f"Error collecting system metrics: {e}")
        return {}

def get_gunicorn_metrics():
    """Get Gunicorn worker processes"""
    try:
        workers = []
        for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'status', 'cpu_percent', 'memory_percent']):
            try:
                if proc.info['name'] and 'gunicorn' in proc.info['name']:
                    workers.append({
                        'pid': proc.info['pid'],
                        'name': proc.info['name'],
                        'status': proc.info['status'],
                        'cpu_percent': proc.info['cpu_percent'],
                        'memory_percent': proc.info['memory_percent']
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        GUNICORN_WORKERS.set(len(workers))
        return workers
    except Exception as e:
        logger.error(f"Error collecting Gunicorn metrics: {e}")
        GUNICORN_WORKERS.set(0)
        return []

def get_celery_metrics():
    """Get Celery metrics"""
    try:
        from social_backend.celery import app as celery_app
        
        # Get inspector
        inspect = celery_app.control.inspect()
        
        # Get active tasks
        active_tasks = inspect.active() or {}
        total_active = sum(len(tasks) for tasks in active_tasks.values())
        CELERY_ACTIVE_TASKS.set(total_active)
        
        # Get queue lengths (this is an approximation)
        reserved_tasks = inspect.reserved() or {}
        total_reserved = sum(len(tasks) for tasks in reserved_tasks.values())
        CELERY_QUEUE_LENGTH.labels(queue='default').set(total_reserved)
        
        # Get stats
        stats = inspect.stats() or {}
        
        return {
            'active_tasks': total_active,
            'reserved_tasks': total_reserved,
            'workers': list(active_tasks.keys()) if active_tasks else [],
            'stats': stats
        }
    except Exception as e:
        logger.error(f"Error collecting Celery metrics: {e}")
        CELERY_ACTIVE_TASKS.set(0)
        CELERY_QUEUE_LENGTH.labels(queue='default').set(0)
        return {'error': str(e)}

def get_redis_metrics():
    """Get Redis metrics"""
    try:
        r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
        info = r.info()
        
        REDIS_CONNECTED_CLIENTS.set(info.get('connected_clients', 0))
        REDIS_USED_MEMORY.set(info.get('used_memory', 0))
        
        return {
            'connected_clients': info.get('connected_clients', 0),
            'used_memory': info.get('used_memory', 0),
            'used_memory_human': info.get('used_memory_human', 'N/A'),
            'redis_version': info.get('redis_version', 'N/A'),
            'uptime_in_seconds': info.get('uptime_in_seconds', 0)
        }
    except Exception as e:
        logger.error(f"Error collecting Redis metrics: {e}")
        REDIS_CONNECTED_CLIENTS.set(0)
        REDIS_USED_MEMORY.set(0)
        return {'error': str(e)}

def restart_gunicorn():
    """Restart Gunicorn via supervisorctl"""
    try:
        result = subprocess.run(['supervisorctl', 'restart', 'social-api-gunicorn'], 
                              capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            logger.info("Gunicorn restarted successfully")
            return {'success': True, 'output': result.stdout}
        else:
            logger.error(f"Failed to restart Gunicorn: {result.stderr}")
            return {'success': False, 'error': result.stderr}
    except subprocess.TimeoutExpired:
        return {'success': False, 'error': 'Restart command timed out'}
    except FileNotFoundError:
        return {'success': False, 'error': 'supervisorctl not found. Service may not be managed by supervisor.'}
    except Exception as e:
        logger.error(f"Error restarting Gunicorn: {e}")
        return {'success': False, 'error': str(e)}

def restart_celery_worker():
    """Restart Celery worker"""
    try:
        result = subprocess.run(['supervisorctl', 'restart', 'social-api-celery-worker'],
                              capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            logger.info("Celery worker restarted successfully")
            return {'success': True, 'output': result.stdout}
        else:
            logger.error(f"Failed to restart Celery worker: {result.stderr}")
            return {'success': False, 'error': result.stderr}
    except subprocess.TimeoutExpired:
        return {'success': False, 'error': 'Restart command timed out'}
    except FileNotFoundError:
        return {'success': False, 'error': 'supervisorctl not found. Service may not be managed by supervisor.'}
    except Exception as e:
        logger.error(f"Error restarting Celery worker: {e}")
        return {'success': False, 'error': str(e)}

def restart_celery_beat():
    """Restart Celery beat"""
    try:
        result = subprocess.run(['supervisorctl', 'restart', 'social-api-celery-beat'],
                              capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            logger.info("Celery beat restarted successfully")
            return {'success': True, 'output': result.stdout}
        else:
            logger.error(f"Failed to restart Celery beat: {result.stderr}")
            return {'success': False, 'error': result.stderr}
    except subprocess.TimeoutExpired:
        return {'success': False, 'error': 'Restart command timed out'}
    except FileNotFoundError:
        return {'success': False, 'error': 'supervisorctl not found. Service may not be managed by supervisor.'}
    except Exception as e:
        logger.error(f"Error restarting Celery beat: {e}")
        return {'success': False, 'error': str(e)}

def get_service_status():
    """Get status of all services"""
    try:
        result = subprocess.run(['supervisorctl', 'status'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            services = []
            for line in result.stdout.strip().split('\n'):
                if line.strip():
                    parts = line.split()
                    if len(parts) >= 2:
                        services.append({
                            'name': parts[0],
                            'status': parts[1],
                            'description': ' '.join(parts[2:]) if len(parts) > 2 else ''
                        })
            return {'success': True, 'services': services}
        else:
            return {'success': False, 'error': result.stderr}
    except Exception as e:
        logger.error(f"Error getting service status: {e}")
        return {'success': False, 'error': str(e)}

def collect_all_metrics():
    """Collect all metrics for Prometheus"""
    get_system_metrics()
    get_gunicorn_metrics()
    get_celery_metrics()
    get_redis_metrics()

# Django Views

def metrics_view(request):
    """Prometheus metrics endpoint"""
    collect_all_metrics()
    return HttpResponse(generate_latest(), content_type=CONTENT_TYPE_LATEST)

@staff_member_required
def health_dashboard(request):
    """Main health dashboard at /health"""
    context = {
        'system_metrics': get_system_metrics(),
        'gunicorn_workers': get_gunicorn_metrics(),
        'celery_metrics': get_celery_metrics(),
        'redis_metrics': get_redis_metrics(),
        'service_status': get_service_status()
    }
    return render(request, 'health/dashboard.html', context)

@staff_member_required
@csrf_exempt
def health_control(request):
    """Health control API for service management"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            action = data.get('action')
            
            if action == 'restart_gunicorn':
                result = restart_gunicorn()
            elif action == 'restart_celery_worker':
                result = restart_celery_worker()
            elif action == 'restart_celery_beat':
                result = restart_celery_beat()
            else:
                result = {'success': False, 'error': 'Invalid action'}
                
            return JsonResponse(result)
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Invalid JSON'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)

@staff_member_required
def health_api(request):
    """Health API endpoint for real-time data"""
    data = {
        'timestamp': datetime.now().isoformat(),
        'system': get_system_metrics(),
        'gunicorn': get_gunicorn_metrics(),
        'celery': get_celery_metrics(),
        'redis': get_redis_metrics(),
        'services': get_service_status()
    }
    return JsonResponse(data)