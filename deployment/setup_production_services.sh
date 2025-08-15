#!/bin/bash

# Comprehensive production setup script for Social Media Manager
# Sets up systemd services for auto-restart and startup, plus webhook deployment

set -e

echo "🚀 Setting up production services for Social Media Manager..."

# Ensure we're running as root
if [ "$EUID" -ne 0 ]; then
    echo "❌ This script must be run as root"
    exit 1
fi

# Stop any existing manual processes
echo "🛑 Stopping existing manual processes..."
pkill -f "gunicorn.*8002" || true
pkill -f "celery.*worker" || true
pkill -f "celery.*beat" || true
sleep 3

# Install Flask for webhook system
echo "📦 Installing webhook dependencies..."
cd /opt/social-media/backend
source venv/bin/activate
pip install flask gunicorn

# Make scripts executable
chmod +x deployment_webhook.py

# Copy systemd service files
echo "📋 Installing systemd service files..."
cp /opt/social-media/deployment/social-api-gunicorn.service /etc/systemd/system/
cp /opt/social-media/deployment/social-api-celery-worker.service /etc/systemd/system/
cp /opt/social-media/deployment/social-api-celery-beat.service /etc/systemd/system/
cp /opt/social-media/deployment/deployment-webhook.service /etc/systemd/system/

# Reload systemd
systemctl daemon-reload

# Enable services for auto-start on boot
echo "🔄 Enabling services for auto-start..."
systemctl enable social-api-gunicorn
systemctl enable social-api-celery-worker
systemctl enable social-api-celery-beat
systemctl enable deployment-webhook

# Create log files with proper permissions
echo "📝 Setting up log files..."
touch /var/log/social-api-access.log
touch /var/log/social-api-error.log
touch /var/log/celery-worker.log
touch /var/log/celery-beat.log
touch /var/log/deployment-webhook.log
chown root:root /var/log/social-api-*.log /var/log/celery-*.log /var/log/deployment-webhook.log
chmod 644 /var/log/social-api-*.log /var/log/celery-*.log /var/log/deployment-webhook.log

# Update nginx configuration for webhook
echo "🌐 Configuring nginx for webhook..."
if ! grep -q "location /webhook/" /etc/nginx/sites-available/social-api; then
    # Insert webhook location before the main Django location
    sed -i '/location \/ {/i \
    # Webhook deployment endpoint\
    location /webhook/ {\
        proxy_pass http://127.0.0.1:5001;\
        proxy_set_header Host $host;\
        proxy_set_header X-Real-IP $remote_addr;\
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;\
        proxy_set_header X-Forwarded-Proto $scheme;\
        \
        # Timeout settings for deployment\
        proxy_connect_timeout 300s;\
        proxy_send_timeout 300s;\
        proxy_read_timeout 300s;\
        \
        # Allow larger request bodies for webhook payloads\
        client_max_body_size 10M;\
    }\
    ' /etc/nginx/sites-available/social-api
    
    # Test and reload nginx
    nginx -t && systemctl reload nginx
    echo "✅ Nginx configuration updated"
else
    echo "ℹ️ Webhook location already exists in nginx configuration"
fi

# Start all services
echo "🚀 Starting all services..."
systemctl start social-api-gunicorn
systemctl start social-api-celery-worker
systemctl start social-api-celery-beat
systemctl start deployment-webhook

# Wait a moment for services to start
sleep 5

# Check service status
echo "📊 Checking service status..."
echo ""
echo "=== Gunicorn Status ==="
systemctl status social-api-gunicorn --no-pager -l
echo ""
echo "=== Celery Worker Status ==="
systemctl status social-api-celery-worker --no-pager -l
echo ""
echo "=== Celery Beat Status ==="
systemctl status social-api-celery-beat --no-pager -l
echo ""
echo "=== Deployment Webhook Status ==="
systemctl status deployment-webhook --no-pager -l

# Test API endpoint
echo ""
echo "🧪 Testing API endpoint..."
API_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8002/api/social/platforms/ || echo "000")
if [ "$API_RESPONSE" = "401" ]; then
    echo "✅ API is responding correctly (401 - unauthorized, as expected)"
else
    echo "⚠️ API response: $API_RESPONSE (expected 401)"
fi

# Test webhook endpoint
echo ""
echo "🧪 Testing webhook endpoint..."
WEBHOOK_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:5001/webhook/status || echo "000")
if [ "$WEBHOOK_RESPONSE" = "200" ]; then
    echo "✅ Webhook endpoint is responding correctly"
else
    echo "⚠️ Webhook response: $WEBHOOK_RESPONSE (expected 200)"
fi

echo ""
echo "🎉 Production services setup complete!"
echo ""
echo "📋 Service Summary:"
echo "   ✅ social-api-gunicorn.service - Django API server"
echo "   ✅ social-api-celery-worker.service - Background task processor"
echo "   ✅ social-api-celery-beat.service - Task scheduler"
echo "   ✅ deployment-webhook.service - Automatic deployment webhook"
echo ""
echo "🔗 Endpoints:"
echo "   - API: https://social-api.marvelhomes.pro/api/social/platforms/"
echo "   - Webhook: https://social-api.marvelhomes.pro/webhook/deploy"
echo "   - Webhook Status: https://social-api.marvelhomes.pro/webhook/status"
echo ""
echo "📝 Management Commands:"
echo "   - Check status: systemctl status social-api-*"
echo "   - Restart all: systemctl restart social-api-*"
echo "   - View logs: journalctl -u social-api-gunicorn -f"
echo "   - View celery logs: tail -f /var/log/celery-*.log"
echo ""
echo "🔗 GitHub Webhook Configuration:"
echo "   - Payload URL: https://social-api.marvelhomes.pro/webhook/deploy"
echo "   - Content type: application/json"
echo "   - Secret: social_media_webhook_secret_2025"
echo "   - Events: Just the push event"
echo "   - Active: ✓"
echo ""
echo "⚠️ IMPORTANT: All services are configured to:"
echo "   - Start automatically on server boot"
echo "   - Restart automatically if they crash"
echo "   - Use proper environment variables from .env file"
echo "   - Log to /var/log/ for monitoring"