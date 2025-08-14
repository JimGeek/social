#!/bin/bash

# Production deployment script for Social Media Manager API
# Run this script on the production server

set -e

echo "🚀 Starting deployment of Social Media Manager API..."

# Create necessary directories
sudo mkdir -p /var/www/social-api
sudo mkdir -p /var/log/social-api
sudo chown -R $USER:$USER /var/www/social-api
sudo chown -R $USER:$USER /var/log/social-api

# Update system packages
sudo apt update && sudo apt upgrade -y

# Install Python and required system packages
sudo apt install -y python3 python3-pip python3-venv nginx postgresql postgresql-contrib redis-server supervisor

# Create Python virtual environment
cd /var/www/social-api
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt

# Set up environment variables
echo "Setting up environment variables..."
cat > .env << EOF
DEBUG=False
SECRET_KEY=$(python3 -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())')
ALLOWED_HOSTS=social-api.marvelhomes.pro,localhost,127.0.0.1
CORS_ALLOWED_ORIGINS=https://social.marvelhomes.pro,http://localhost:3000

# Database settings
DB_NAME=social_db
DB_USER=social_user
DB_PASSWORD=your_secure_password_here
DB_HOST=localhost
DB_PORT=5432

# Redis settings
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# API Keys (to be configured)
OPENAI_API_KEY=
FACEBOOK_APP_ID=
FACEBOOK_APP_SECRET=
INSTAGRAM_BASIC_APP_ID=
INSTAGRAM_BASIC_APP_SECRET=

# URLs
FACEBOOK_REDIRECT_URI=https://social-api.marvelhomes.pro/api/social/auth/facebook/callback/
FRONTEND_URL=https://social.marvelhomes.pro
EOF

echo "⚠️  IMPORTANT: Please edit /var/www/social-api/.env and add your API keys!"

# Create database and user
sudo -u postgres createdb social_db 2>/dev/null || true
sudo -u postgres createuser social_user 2>/dev/null || true
sudo -u postgres psql -c "ALTER USER social_user WITH PASSWORD 'your_secure_password_here';" 2>/dev/null || true
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE social_db TO social_user;" 2>/dev/null || true

# Run Django migrations
export DJANGO_SETTINGS_MODULE=social_backend.settings_production
python3 manage.py migrate
python3 manage.py collectstatic --noinput

# Create Django superuser (optional)
# python3 manage.py createsuperuser

echo "✅ API deployment completed!"
echo "🔧 Next steps:"
echo "1. Edit /var/www/social-api/.env and add your API keys"
echo "2. Configure Nginx (see nginx.conf)"
echo "3. Set up Supervisor for Celery processes"
echo "4. Start the services"