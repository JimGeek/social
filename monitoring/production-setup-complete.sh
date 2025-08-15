#!/bin/bash
# Complete Production Monitoring Setup Script
# Run this on production server: ssh root@31.97.224.53

set -e
echo "🚀 Starting complete monitoring stack setup on production server..."

# Update system
apt update && apt upgrade -y

# Install required packages
apt install -y curl wget git docker.io docker-compose nginx-full ufw

# Start and enable Docker
systemctl start docker
systemctl enable docker

# Create monitoring directory
mkdir -p /opt/monitoring
cd /opt/monitoring

# Clone the repository (you'll need to provide the repository)
echo "📁 Setting up monitoring files..."

# Create docker-compose.production.yml
cat > docker-compose.production.yml << 'EOF'
version: '3.8'

services:
  nginx-monitoring:
    image: nginx:alpine
    container_name: monitoring-nginx
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/ssl:/etc/nginx/ssl:ro
    depends_on:
      - grafana
    networks:
      - monitoring
    restart: unless-stopped

  grafana:
    image: grafana/grafana:latest
    container_name: monitoring-grafana
    environment:
      - GF_SECURITY_ADMIN_USER=admin
      - GF_SECURITY_ADMIN_PASSWORD=admin123
      - GF_USERS_ALLOW_SIGN_UP=false
      - GF_SERVER_ROOT_URL=%(protocol)s://%(domain)s/health/
      - GF_SERVER_SERVE_FROM_SUB_PATH=true
    volumes:
      - grafana-storage:/var/lib/grafana
      - ./grafana/provisioning:/etc/grafana/provisioning
      - ./grafana/dashboards:/var/lib/grafana/dashboards
    depends_on:
      - prometheus
      - loki
    networks:
      - monitoring
    restart: unless-stopped

  prometheus:
    image: prom/prometheus:latest
    container_name: monitoring-prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--storage.tsdb.retention.time=30d'
    volumes:
      - ./prometheus:/etc/prometheus
      - prometheus-storage:/prometheus
    networks:
      - monitoring
    restart: unless-stopped

  loki:
    image: grafana/loki:latest
    container_name: monitoring-loki
    command: -config.file=/etc/loki/local-config.yaml
    volumes:
      - ./loki:/etc/loki
      - loki-storage:/loki
    networks:
      - monitoring
    restart: unless-stopped

  promtail:
    image: grafana/promtail:latest
    container_name: monitoring-promtail
    command: -config.file=/etc/promtail/config.yml
    volumes:
      - ./promtail:/etc/promtail
      - /var/log:/var/log:ro
      - /var/log/social-api:/logs/social-api:ro
    depends_on:
      - loki
    networks:
      - monitoring
    restart: unless-stopped

  service-controller:
    build: 
      context: ./service-controller
      dockerfile: Dockerfile
    container_name: monitoring-service-controller
    environment:
      - SUPERVISOR_HOST=host.docker.internal
      - API_TOKEN=monitoring-api-token-2025
    volumes:
      - ./service-controller/projects.yml:/app/projects.yml:ro
    networks:
      - monitoring
    restart: unless-stopped

volumes:
  prometheus-storage:
  loki-storage:
  grafana-storage:

networks:
  monitoring:
    driver: bridge
EOF

# Create directory structure
mkdir -p nginx/ssl
mkdir -p prometheus
mkdir -p loki
mkdir -p promtail
mkdir -p grafana/provisioning/{dashboards,datasources}
mkdir -p grafana/dashboards
mkdir -p service-controller

# Create nginx configuration
cat > nginx/nginx.conf << 'EOF'
events {
    worker_connections 1024;
}

http {
    include       /etc/nginx/mime.types;
    default_type  application/octet-stream;

    access_log /var/log/nginx/access.log;
    error_log  /var/log/nginx/error.log;

    upstream grafana {
        server grafana:3000;
    }

    upstream service_controller {
        server service-controller:8080;
    }

    server {
        listen 80;
        server_name _;

        location /health/ {
            proxy_pass http://grafana/;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
        }

        location /health/api/control/ {
            proxy_pass http://service_controller/;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        }

        location / {
            return 404;
        }
    }
}
EOF

# Create Prometheus configuration
cat > prometheus/prometheus.yml << 'EOF'
global:
  scrape_interval: 30s

scrape_configs:
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  - job_name: 'social-media-backend'
    static_configs:
      - targets: ['social-api.marvelhomes.pro:8000']
    scrape_interval: 30s
    metrics_path: '/health/metrics'
    scrape_timeout: 10s

  - job_name: 'social-media-backup'
    static_configs:
      - targets: ['31.97.224.53:8000']
    scrape_interval: 30s
    metrics_path: '/health/metrics'
    scrape_timeout: 10s
EOF

# Create Loki configuration
cat > loki/local-config.yaml << 'EOF'
auth_enabled: false

server:
  http_listen_port: 3100
  grpc_listen_port: 9096

common:
  path_prefix: /loki
  storage:
    filesystem:
      chunks_directory: /loki/chunks
      rules_directory: /loki/rules
  replication_factor: 1
  ring:
    instance_addr: 127.0.0.1
    kvstore:
      store: inmemory

limits_config:
  allow_structured_metadata: false
  ingestion_rate_mb: 32
  ingestion_burst_size_mb: 64
  retention_period: 30d

schema_config:
  configs:
    - from: 2020-10-24
      store: boltdb-shipper
      object_store: filesystem
      schema: v11
      index:
        prefix: index_
        period: 24h
EOF

# Create Promtail configuration
cat > promtail/config.yml << 'EOF'
server:
  http_listen_port: 9080
  grpc_listen_port: 0

positions:
  filename: /tmp/positions.yaml

clients:
  - url: http://loki:3100/loki/api/v1/push

scrape_configs:
  - job_name: social-media-django
    static_configs:
      - targets:
          - localhost
        labels:
          job: social-media
          service: django
          project: social-media-manager
          __path__: /logs/social-api/*.log
EOF

# Create Service Controller
cat > service-controller/Dockerfile << 'EOF'
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y supervisor curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080

CMD ["python", "app.py"]
EOF

cat > service-controller/requirements.txt << 'EOF'
fastapi==0.104.1
uvicorn[standard]==0.24.0
pydantic==2.5.0
pyyaml==6.0.1
psutil==5.9.6
EOF

# Create Service Controller App
cat > service-controller/app.py << 'EOF'
#!/usr/bin/env python3
import os
import subprocess
import psutil
from typing import Dict, List
from datetime import datetime

from fastapi import FastAPI, HTTPException, Security, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import uvicorn

app = FastAPI(title="Production Service Controller")
security = HTTPBearer()

class ServiceStatus(BaseModel):
    name: str
    status: str
    pid: int = None

def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)):
    if credentials.credentials != "monitoring-api-token-2025":
        raise HTTPException(status_code=401, detail="Invalid API token")
    return credentials.credentials

def get_service_status_supervisor(service_name: str) -> Dict:
    try:
        result = subprocess.run(['supervisorctl', 'status', service_name], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0 and 'RUNNING' in result.stdout:
            return {'status': 'running', 'output': result.stdout}
        return {'status': 'stopped', 'output': result.stdout}
    except Exception as e:
        return {'status': 'error', 'error': str(e)}

def restart_service_supervisor(service_name: str) -> Dict:
    try:
        result = subprocess.run(['supervisorctl', 'restart', service_name],
                              capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            return {'success': True, 'message': f'Service {service_name} restarted'}
        return {'success': False, 'error': result.stderr}
    except Exception as e:
        return {'success': False, 'error': str(e)}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.get("/projects")
async def list_projects(token: str = Depends(verify_token)):
    return {"projects": ["social-media"]}

@app.get("/projects/{project}/services")
async def get_project_services(project: str, token: str = Depends(verify_token)):
    if project != "social-media":
        raise HTTPException(status_code=404, detail=f"Project {project} not found")
    
    services = []
    for service in ['social-api-gunicorn', 'social-api-celery-worker', 'social-api-celery-beat']:
        status_info = get_service_status_supervisor(service)
        services.append(ServiceStatus(name=service, status=status_info['status']))
    
    return {"project": project, "services": services}

@app.post("/projects/{project}/services/{service}/restart")
async def restart_service(project: str, service: str, token: str = Depends(verify_token)):
    if project != "social-media":
        raise HTTPException(status_code=404, detail=f"Project {project} not found")
    
    service_map = {
        'gunicorn': 'social-api-gunicorn',
        'celery-worker': 'social-api-celery-worker',
        'celery-beat': 'social-api-celery-beat'
    }
    
    if service not in service_map:
        raise HTTPException(status_code=404, detail=f"Service {service} not found")
    
    result = restart_service_supervisor(service_map[service])
    if result.get('success'):
        return {"message": f"Service {service} restarted successfully"}
    else:
        raise HTTPException(status_code=500, detail=result.get('error'))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
EOF

# Create projects configuration
cat > service-controller/projects.yml << 'EOF'
projects:
  social-media:
    name: "Social Media Manager"
    services:
      gunicorn: "social-api-gunicorn"
      celery-worker: "social-api-celery-worker" 
      celery-beat: "social-api-celery-beat"
EOF

# Create Grafana datasources
cat > grafana/provisioning/datasources/datasources.yml << 'EOF'
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true

  - name: Loki
    type: loki
    access: proxy
    url: http://loki:3100
EOF

# Create Grafana dashboard provisioning
cat > grafana/provisioning/dashboards/dashboards.yml << 'EOF'
apiVersion: 1

providers:
  - name: 'monitoring-dashboards'
    orgId: 1
    folder: 'Monitoring'
    type: file
    disableDeletion: false
    options:
      path: /var/lib/grafana/dashboards
EOF

# Create basic dashboard (simplified)
cat > grafana/dashboards/health-dashboard.json << 'EOF'
{
  "dashboard": {
    "id": null,
    "title": "Production Health Monitor",
    "panels": [
      {
        "id": 1,
        "title": "System CPU Usage",
        "type": "stat",
        "targets": [{"expr": "system_cpu_usage_percent"}],
        "gridPos": {"h": 8, "w": 12, "x": 0, "y": 0}
      }
    ],
    "time": {"from": "now-1h", "to": "now"},
    "refresh": "30s"
  }
}
EOF

# Create log directories
mkdir -p /var/log/social-api
chown -R syslog:adm /var/log/social-api

# Generate SSL certificates
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout nginx/ssl/key.pem \
    -out nginx/ssl/cert.pem \
    -subj "/C=US/ST=State/L=City/O=Organization/CN=social-api.marvelhomes.pro"

# Configure firewall
ufw allow 22/tcp  # SSH
ufw allow 80/tcp  # HTTP
ufw allow 443/tcp # HTTPS
ufw --force enable

# Start the monitoring stack
echo "🚀 Starting monitoring stack..."
docker-compose -f docker-compose.production.yml up -d

# Wait for services
sleep 30

# Check status
echo "✅ Checking service status..."
docker-compose -f docker-compose.production.yml ps

# Setup systemd service
cat > /etc/systemd/system/monitoring-stack.service << EOF
[Unit]
Description=Production Monitoring Stack
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/monitoring
ExecStart=/usr/bin/docker-compose -f docker-compose.production.yml up -d
ExecStop=/usr/bin/docker-compose -f docker-compose.production.yml down

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable monitoring-stack.service

echo "🎉 Monitoring stack setup complete!"
echo ""
echo "🌐 Access your dashboard at:"
echo "   http://$(hostname -I | awk '{print $1}')/health"
echo "   http://social-api.marvelhomes.pro/health"
echo ""
echo "🔐 Default credentials:"
echo "   Username: admin"
echo "   Password: admin123"
echo ""
echo "📊 Dashboard should be available in 1-2 minutes"
EOF