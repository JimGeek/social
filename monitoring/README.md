# Production Multi-Project Monitoring Stack

🎯 **Single Interface at `/health`** | 🔐 **Secure Authentication** | 🚀 **Scalable Architecture**

## 🌟 Features

### ✅ **Centralized Access**
- **Single URL**: `https://yourdomain.com/health`
- **Unified Dashboard**: All projects in one interface
- **Service Controls**: Restart services directly from Grafana
- **Real-time Monitoring**: Live metrics and logs

### ✅ **Multi-Project Support**
- **Scalable Design**: Add new projects easily
- **Project Isolation**: Separate metrics and logs per project
- **Template-based**: Consistent monitoring across projects
- **Dynamic Discovery**: Automatic service detection

### ✅ **Comprehensive Monitoring**
- **System Metrics**: CPU, Memory, Disk usage
- **Application Metrics**: Gunicorn, Celery, Redis
- **HTTP Monitoring**: Request rates, response times
- **Log Aggregation**: Centralized log collection and analysis
- **Service Status**: Real-time process monitoring

### ✅ **Production Features**
- **SSL/TLS**: Secure HTTPS access
- **Authentication**: Secure access control
- **Rate Limiting**: DDoS protection
- **Backup System**: Automated data backups
- **Auto-restart**: Systemd service integration

## 🚀 Quick Start

### **1. Deploy on Production Server**

```bash
# Connect to your production server
ssh user@31.97.224.53

# Clone the monitoring configuration
git clone git@github.com:JimGeek/social.git
cd social/monitoring

# Run automated deployment
./deploy-production.sh
```

### **2. Configure Environment**

```bash
# Edit configuration
nano .env

# Key settings to update:
GRAFANA_ADMIN_PASSWORD=your-secure-password
API_TOKEN=your-secure-api-token
MONITORING_DOMAIN=your-domain.com
```

### **3. Access Dashboard**

```
🌐 https://your-domain.com/health
👤 Username: admin
🔑 Password: [from .env file]
```

## 📊 Architecture Overview

```
Internet → Nginx (Port 80/443) → Grafana (/health) → Service Controller API
                                     ↑
                         Prometheus + Loki (Internal)
                                     ↑
                              Project Applications
```

### **Components**

| Component | Purpose | Internal Port | Public Access |
|-----------|---------|---------------|---------------|
| **Nginx** | Reverse Proxy & SSL | 80, 443 | ✅ `/health` only |
| **Grafana** | Main Dashboard | 3000 | ❌ Internal only |
| **Prometheus** | Metrics Storage | 9090 | ❌ Internal only |
| **Loki** | Log Aggregation | 3100 | ❌ Internal only |
| **Service Controller** | Service Management | 8080 | ❌ Internal API |

## 🔧 Service Management

### **Restart Services via Grafana**

1. **Go to Dashboard**: `https://yourdomain.com/health`
2. **Navigate to**: "Service Status & Controls" panel
3. **Click**: "Restart Service" button for any service
4. **Monitor**: Status changes in real-time

### **Available Service Controls**

- **Gunicorn**: Web server restart
- **Celery Worker**: Task processor restart  
- **Celery Beat**: Scheduler restart
- **Redis**: Cache/queue restart

### **API Access** (Optional)

```bash
# Direct API access with authentication
curl -H "Authorization: Bearer your-api-token" \
     https://yourdomain.com/health/api/control/projects/social-media/services/gunicorn/restart
```

## 📈 Adding New Projects

### **1. Update Configuration**

Edit `service-controller/projects.yml`:

```yaml
projects:
  # Existing social-media project
  social-media: { ... }
  
  # Add new project
  new-project:
    name: "New Project Name"
    description: "Project description"
    supervisor_config: "/etc/supervisor/conf.d/new-project.conf"
    metrics_endpoint: "http://new-project.domain.com:8000/health/metrics"
    log_paths:
      - "/var/log/new-project/app.log"
      - "/var/log/new-project/worker.log"
    services:
      gunicorn: "new-project-gunicorn"
      celery-worker: "new-project-celery-worker"
      celery-beat: "new-project-celery-beat"
      redis: "new-project-redis"
```

### **2. Update Prometheus Config**

Edit `prometheus/prometheus.yml`:

```yaml
scrape_configs:
  # Add new project metrics
  - job_name: 'new-project-backend'
    static_configs:
      - targets: ['new-project.domain.com:8000']
    scrape_interval: 30s
    metrics_path: '/health/metrics'
```

### **3. Update Log Collection**

Edit `promtail/config.yml`:

```yaml
scrape_configs:
  # Add new project logs
  - job_name: new-project-django
    static_configs:
      - targets: [localhost]
        labels:
          job: new-project
          service: django
          project: new-project-name
          __path__: /logs/new-project/django*.log
```

### **4. Restart Stack**

```bash
sudo systemctl restart monitoring-stack
```

## 🛠️ Maintenance

### **Daily Operations**

```bash
# Check service status
sudo systemctl status monitoring-stack

# View logs
docker-compose -f docker-compose.production.yml logs -f

# Restart specific service
docker-compose -f docker-compose.production.yml restart grafana
```

### **Backup & Restore**

```bash
# Manual backup
sudo /usr/local/bin/monitoring-backup.sh

# Restore from backup
docker run --rm -v monitoring_grafana-storage:/data -v /var/backups/monitoring:/backup alpine tar xzf /backup/grafana_YYYYMMDD_HHMMSS.tar.gz -C /data
```

### **Updates**

```bash
# Update stack
cd /opt/monitoring
docker-compose -f docker-compose.production.yml pull
docker-compose -f docker-compose.production.yml up -d
```

## 🔒 Security Features

### **Access Control**
- **Nginx Rate Limiting**: 10 requests/second per IP
- **Grafana Authentication**: Admin-only access
- **API Token Authentication**: Bearer token for API calls
- **Internal Network**: All services on private network

### **SSL/TLS**
- **HTTPS Enforcement**: Automatic HTTP→HTTPS redirect
- **Modern TLS**: TLSv1.2+ with secure ciphers
- **HSTS Headers**: HTTP Strict Transport Security
- **Security Headers**: XSS protection, content type sniffing prevention

### **Network Security**
- **Firewall Rules**: Only ports 80/443 exposed
- **Internal Services**: Prometheus/Loki not publicly accessible
- **Docker Network**: Isolated container communication

## 📞 Support & Troubleshooting

### **Common Issues**

1. **Can't access /health**
   ```bash
   # Check nginx status
   docker-compose -f docker-compose.production.yml ps nginx-monitoring
   
   # Check logs
   docker-compose -f docker-compose.production.yml logs nginx-monitoring
   ```

2. **Service restart not working**
   ```bash
   # Check service controller logs
   docker-compose -f docker-compose.production.yml logs service-controller
   
   # Test API manually
   curl -H "Authorization: Bearer your-token" http://localhost:8080/projects
   ```

3. **No metrics showing**
   ```bash
   # Check Prometheus targets
   curl http://localhost:9090/api/v1/targets
   
   # Verify project endpoints
   curl http://social-api.marvelhomes.pro:8000/health/metrics
   ```

### **Log Locations**

- **Application Logs**: `/var/log/monitoring/`
- **Container Logs**: `docker-compose logs [service]`
- **System Logs**: `/var/log/syslog`
- **Nginx Logs**: `/var/log/nginx/`

### **Configuration Files**

- **Main Config**: `/opt/monitoring/`
- **Environment**: `/opt/monitoring/.env`
- **Project Config**: `/opt/monitoring/service-controller/projects.yml`
- **SSL Certificates**: `/opt/monitoring/nginx/ssl/`

---

## 📝 Version History

- **v1.0.0**: Initial production-ready release
- Multi-project support
- Service restart functionality
- Comprehensive monitoring
- Security hardening

---

**🚀 Built for Production | 🔐 Security First | 📊 Comprehensive Monitoring**