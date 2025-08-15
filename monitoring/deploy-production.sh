#!/bin/bash
# Production Monitoring Stack Deployment Script
# Run this on your production server

set -e

echo "🚀 Deploying Production Monitoring Stack..."

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   echo "⚠️  This script should not be run as root for security reasons"
   exit 1
fi

# Configuration
MONITORING_DIR="/opt/monitoring"
LOG_DIR="/var/log/monitoring"
DATA_DIR="/var/lib/monitoring"

# Create directories
sudo mkdir -p $MONITORING_DIR
sudo mkdir -p $LOG_DIR
sudo mkdir -p $DATA_DIR/{prometheus,grafana,loki}

# Set permissions
sudo chown -R $USER:$USER $MONITORING_DIR
sudo chown -R 472:472 $DATA_DIR/grafana  # Grafana user
sudo chown -R nobody:nogroup $DATA_DIR/{prometheus,loki}

# Copy configuration files
echo "📁 Copying configuration files..."
cp -r . $MONITORING_DIR/
cd $MONITORING_DIR

# Check for .env file
if [[ ! -f .env ]]; then
    echo "📝 Creating .env from template..."
    cp .env.production .env
    echo "⚠️  Please edit .env file with your configuration before continuing"
    echo "   nano $MONITORING_DIR/.env"
    read -p "Press Enter after configuring .env file..."
fi

# Load environment variables
source .env

# Install Docker if not present
if ! command -v docker &> /dev/null; then
    echo "🐳 Installing Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
    rm get-docker.sh
    echo "⚠️  Please log out and log back in to use Docker, then run this script again"
    exit 1
fi

# Install Docker Compose if not present
if ! command -v docker-compose &> /dev/null; then
    echo "🔧 Installing Docker Compose..."
    sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
fi

# Create log directories for projects
echo "📂 Setting up log directories..."
sudo mkdir -p /var/log/social-api
sudo mkdir -p /var/log/nginx
sudo chown -R syslog:adm /var/log/social-api
sudo chown -R www-data:adm /var/log/nginx

# Setup SSL certificates (self-signed for now)
if [[ ! -f nginx/ssl/cert.pem ]]; then
    echo "🔒 Generating self-signed SSL certificates..."
    mkdir -p nginx/ssl
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout nginx/ssl/key.pem \
        -out nginx/ssl/cert.pem \
        -subj "/C=US/ST=State/L=City/O=Organization/OU=OrgUnit/CN=${MONITORING_DOMAIN:-localhost}"
fi

# Build service controller image
echo "🔨 Building service controller..."
docker build -t monitoring-service-controller:latest service-controller/

# Deploy the stack
echo "🚀 Starting monitoring stack..."
docker-compose -f docker-compose.production.yml up -d

# Wait for services to start
echo "⏳ Waiting for services to start..."
sleep 30

# Check service status
echo "✅ Checking service status..."
docker-compose -f docker-compose.production.yml ps

# Setup logrotate for monitoring logs
echo "🗂️  Setting up log rotation..."
sudo tee /etc/logrotate.d/monitoring << EOF
/var/log/monitoring/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 root adm
    postrotate
        docker-compose -f $MONITORING_DIR/docker-compose.production.yml restart promtail
    endscript
}
EOF

# Setup systemd service for auto-start
echo "⚙️  Setting up systemd service..."
sudo tee /etc/systemd/system/monitoring-stack.service << EOF
[Unit]
Description=Production Monitoring Stack
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=$MONITORING_DIR
ExecStart=/usr/local/bin/docker-compose -f docker-compose.production.yml up -d
ExecStop=/usr/local/bin/docker-compose -f docker-compose.production.yml down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable monitoring-stack.service

# Setup firewall rules
echo "🔥 Configuring firewall..."
sudo ufw allow 80/tcp comment "Monitoring HTTP"
sudo ufw allow 443/tcp comment "Monitoring HTTPS"

# Setup backup script
echo "💾 Setting up backup script..."
sudo tee /usr/local/bin/monitoring-backup.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/var/backups/monitoring"
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP_DIR

# Backup Grafana data
docker run --rm -v monitoring_grafana-storage:/data -v $BACKUP_DIR:/backup alpine tar czf /backup/grafana_$DATE.tar.gz -C /data .

# Backup Prometheus data
docker run --rm -v monitoring_prometheus-storage:/data -v $BACKUP_DIR:/backup alpine tar czf /backup/prometheus_$DATE.tar.gz -C /data .

# Cleanup old backups (keep last 7 days)
find $BACKUP_DIR -name "*.tar.gz" -mtime +7 -delete

echo "Backup completed: $BACKUP_DIR"
EOF

sudo chmod +x /usr/local/bin/monitoring-backup.sh

# Setup cron for daily backups
echo "0 2 * * * /usr/local/bin/monitoring-backup.sh" | sudo crontab -

echo "🎉 Production monitoring stack deployed successfully!"
echo ""
echo "📊 Access your monitoring dashboard at:"
echo "   http://${MONITORING_DOMAIN:-localhost}/health"
echo ""
echo "🔧 Default credentials:"
echo "   Username: ${GRAFANA_ADMIN_USER:-admin}"
echo "   Password: Check your .env file"
echo ""
echo "📚 Additional information:"
echo "   • Service Controller API: /health/api/control/docs"
echo "   • Logs directory: /var/log/monitoring/"
echo "   • Data directory: /var/lib/monitoring/"
echo "   • Configuration: $MONITORING_DIR"
echo ""
echo "🔄 To restart the stack:"
echo "   sudo systemctl restart monitoring-stack"
echo ""
echo "💾 To backup data:"
echo "   sudo /usr/local/bin/monitoring-backup.sh"