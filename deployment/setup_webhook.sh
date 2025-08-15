#!/bin/bash

# Setup script for deployment webhook system
# Run this on the production server to install the webhook system

set -e

echo "🚀 Setting up deployment webhook system..."

# Install Flask if not already installed
cd /opt/social-media/backend
source venv/bin/activate
pip install flask

# Make webhook script executable
chmod +x deployment_webhook.py

# Copy systemd service file
sudo cp /opt/social-media/deployment/deployment-webhook.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable deployment-webhook
sudo systemctl start deployment-webhook

# Add webhook location to nginx configuration
if ! grep -q "location /webhook/" /etc/nginx/sites-available/social-api; then
    echo "Adding webhook location to nginx configuration..."
    
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
    
    # Test nginx configuration
    sudo nginx -t && sudo systemctl reload nginx
    echo "✅ Nginx configuration updated"
else
    echo "ℹ️ Webhook location already exists in nginx configuration"
fi

# Create log files
sudo touch /var/log/deployment-webhook.log
sudo chown root:root /var/log/deployment-webhook.log

# Check service status
echo "📊 Checking webhook service status..."
sudo systemctl status deployment-webhook --no-pager

echo ""
echo "✅ Deployment webhook system setup complete!"
echo ""
echo "📝 Configuration Summary:"
echo "   - Webhook endpoint: https://social-api.marvelhomes.pro/webhook/deploy"
echo "   - Status endpoint: https://social-api.marvelhomes.pro/webhook/status"
echo "   - Service: deployment-webhook.service"
echo "   - Logs: /var/log/deployment-webhook.log"
echo ""
echo "🔗 GitHub Webhook Configuration:"
echo "   - Payload URL: https://social-api.marvelhomes.pro/webhook/deploy"
echo "   - Content type: application/json"
echo "   - Secret: social_media_webhook_secret_2025"
echo "   - Events: Just the push event"
echo "   - Active: ✓"
echo ""
echo "⚠️  IMPORTANT: Add the webhook secret to your GitHub webhook configuration!"
echo "   Secret: social_media_webhook_secret_2025"