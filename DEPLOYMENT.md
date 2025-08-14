# Social Media Manager - Production Deployment Guide

## Overview
- **Backend API**: `social-api.marvelhomes.pro`
- **Frontend**: `social.marvelhomes.pro` (deployed via Vercel)

## Backend Deployment (social-api.marvelhomes.pro)

### 1. Server Access
```bash
ssh root@31.97.224.53
```

### 2. Clone Repository
```bash
git clone [repository-url]
cd social-media/backend
```

### 3. Run Deployment Script
```bash
chmod +x deploy.sh
./deploy.sh
```

### 4. Configure Environment Variables
Edit `/var/www/social-api/.env` and add your API keys:
```bash
# API Keys (required)
OPENAI_API_KEY=your_openai_key
FACEBOOK_APP_ID=your_facebook_app_id
FACEBOOK_APP_SECRET=your_facebook_app_secret
INSTAGRAM_BASIC_APP_ID=your_instagram_app_id
INSTAGRAM_BASIC_APP_SECRET=your_instagram_app_secret

# Database (update password)
DB_PASSWORD=your_secure_password
```

### 5. Configure Nginx
```bash
sudo cp nginx.conf /etc/nginx/sites-available/social-api
sudo ln -s /etc/nginx/sites-available/social-api /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 6. Set up SSL Certificate
```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d social-api.marvelhomes.pro
```

### 7. Configure Supervisor
```bash
sudo cp supervisor.conf /etc/supervisor/conf.d/social-api.conf
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start social-api:*
```

### 8. Verify Services
```bash
sudo supervisorctl status
sudo systemctl status nginx
sudo systemctl status postgresql
sudo systemctl status redis
```

## Frontend Deployment (social.marvelhomes.pro)

### 1. Deploy to Vercel
1. Connect your repository to Vercel
2. Set environment variables in Vercel dashboard:
   - `REACT_APP_API_URL=https://social-api.marvelhomes.pro`
   - `REACT_APP_ENVIRONMENT=production`
3. Deploy from main branch

### 2. Configure Domain
Point `social.marvelhomes.pro` to Vercel in your DNS settings.

## Post-Deployment Checklist

### Backend API (social-api.marvelhomes.pro)
- [ ] API endpoints respond correctly
- [ ] Django admin accessible at `/admin/`
- [ ] Static files loading properly
- [ ] SSL certificate working
- [ ] Celery worker processing tasks
- [ ] Celery beat scheduling tasks
- [ ] Database migrations completed
- [ ] Log files being written

### Frontend (social.marvelhomes.pro)
- [ ] Site loads correctly
- [ ] API calls working
- [ ] Authentication flow working
- [ ] Social media connections working

## Monitoring & Maintenance

### View Logs
```bash
# Django logs
tail -f /var/log/social-api/django.log

# Celery logs
tail -f /var/log/social-api/celery-worker.log
tail -f /var/log/social-api/celery-beat.log

# Nginx logs
tail -f /var/log/nginx/access.log
tail -f /var/log/nginx/error.log
```

### Restart Services
```bash
# Restart all services
sudo supervisorctl restart social-api:*

# Restart individual services
sudo supervisorctl restart social-api-django
sudo supervisorctl restart social-api-celery-worker
sudo supervisorctl restart social-api-celery-beat
```

### Update Code
```bash
cd /var/www/social-api
git pull origin main
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
sudo supervisorctl restart social-api:*
```

## Troubleshooting

### Common Issues
1. **502 Bad Gateway**: Check Django service status
2. **Database Connection**: Verify PostgreSQL and credentials
3. **Celery Tasks Not Running**: Check Redis connection and worker status
4. **Static Files 404**: Run `collectstatic` and check Nginx config
5. **CORS Errors**: Verify `CORS_ALLOWED_ORIGINS` in settings

### Health Checks
- API Health: `https://social-api.marvelhomes.pro/admin/`
- Frontend: `https://social.marvelhomes.pro`
- Database: `sudo -u postgres psql social_db -c "SELECT COUNT(*) FROM auth_user;"`
- Redis: `redis-cli ping`