#!/bin/bash

# Service monitoring script for Social Media Manager
# Can be run manually or added to cron for periodic health checks

set -e

echo "🔍 Social Media Manager - Service Status Monitor"
echo "================================================="
echo "📅 $(date)"
echo ""

# Define services to monitor
SERVICES=(
    "social-api-gunicorn"
    "social-api-celery-worker"
    "social-api-celery-beat"
    "deployment-webhook"
    "nginx"
    "postgresql"
    "redis-server"
)

# Check each service status
for service in "${SERVICES[@]}"; do
    echo "🔍 Checking $service..."
    if systemctl is-active --quiet "$service"; then
        echo "  ✅ $service is running"
    else
        echo "  ❌ $service is NOT running"
        echo "  📋 Status: $(systemctl is-active $service)"
        
        # Attempt to restart if it's one of our main services
        if [[ "$service" == social-api-* ]] || [[ "$service" == "deployment-webhook" ]]; then
            echo "  🔄 Attempting to restart $service..."
            systemctl restart "$service"
            sleep 3
            if systemctl is-active --quiet "$service"; then
                echo "  ✅ $service restarted successfully"
            else
                echo "  ❌ Failed to restart $service"
            fi
        fi
    fi
    echo ""
done

# Test API endpoint
echo "🧪 Testing API endpoint..."
API_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8002/api/social/platforms/ 2>/dev/null || echo "000")
if [ "$API_RESPONSE" = "401" ]; then
    echo "  ✅ API is responding correctly (401 - unauthorized)"
elif [ "$API_RESPONSE" = "000" ]; then
    echo "  ❌ API is not reachable"
else
    echo "  ⚠️ API response: $API_RESPONSE (expected 401)"
fi

# Test webhook endpoint
echo "🧪 Testing webhook endpoint..."
WEBHOOK_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:5001/webhook/status 2>/dev/null || echo "000")
if [ "$WEBHOOK_RESPONSE" = "200" ]; then
    echo "  ✅ Webhook endpoint is responding correctly"
elif [ "$WEBHOOK_RESPONSE" = "000" ]; then
    echo "  ❌ Webhook endpoint is not reachable"
else
    echo "  ⚠️ Webhook response: $WEBHOOK_RESPONSE (expected 200)"
fi

# Check disk space
echo ""
echo "💾 Disk space check..."
DISK_USAGE=$(df /opt/social-media | awk 'NR==2 {print $5}' | sed 's/%//')
if [ "$DISK_USAGE" -gt 80 ]; then
    echo "  ⚠️ Disk usage is high: ${DISK_USAGE}%"
else
    echo "  ✅ Disk usage is normal: ${DISK_USAGE}%"
fi

# Check log file sizes
echo ""
echo "📝 Log file sizes..."
for log_file in /var/log/social-api-*.log /var/log/celery-*.log /var/log/deployment-webhook.log; do
    if [ -f "$log_file" ]; then
        size=$(ls -lh "$log_file" | awk '{print $5}')
        echo "  📄 $(basename $log_file): $size"
    fi
done

echo ""
echo "🏁 Monitoring complete!"
echo ""
echo "💡 Useful commands:"
echo "   - View service logs: journalctl -u social-api-gunicorn -f"
echo "   - Restart all services: systemctl restart social-api-*"
echo "   - Check service status: systemctl status social-api-*"