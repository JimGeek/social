# 🚀 Social Media Manager - Production Deployment

## Repository Information
- **GitHub**: `git@github.com:JimGeek/social.git`
- **Production Server**: `ssh root@31.97.224.53`
- **Backend API**: `social-api.marvelhomes.pro`
- **Frontend**: `social.marvelhomes.pro` (Vercel)

## 🖥️ Backend Deployment Steps

### 1. Connect to Production Server
```bash
ssh root@31.97.224.53
```

### 2. Clone Repository
```bash
cd /var/www
git clone git@github.com:JimGeek/social.git
cd social/backend
```

### 3. Run Automated Deployment
```bash
chmod +x deploy.sh
./deploy.sh
```

### 4. Configure API Keys
Edit the environment file:
```bash
nano /var/www/social-api/.env
```

Add your API keys:
```env
# Required API Keys
OPENAI_API_KEY=your_openai_api_key_here
FACEBOOK_APP_ID=your_facebook_app_id
FACEBOOK_APP_SECRET=your_facebook_app_secret
INSTAGRAM_BASIC_APP_ID=your_instagram_app_id
INSTAGRAM_BASIC_APP_SECRET=your_instagram_app_secret

# Update database password
DB_PASSWORD=your_secure_database_password
```

### 5. Set up SSL Certificate
```bash
sudo certbot --nginx -d social-api.marvelhomes.pro
```

### 6. Start All Services
```bash
sudo supervisorctl start social-api:*
sudo systemctl restart nginx
```

### 7. Verify Deployment
```bash
# Check service status
sudo supervisorctl status

# Test API endpoint
curl https://social-api.marvelhomes.pro/admin/

# Check logs
tail -f /var/log/social-api/django.log
```

## 🌐 Frontend Deployment (Vercel)

### 1. Connect to Vercel
1. Go to [vercel.com](https://vercel.com)
2. Import project from GitHub: `JimGeek/social`
3. Set root directory to: `frontend`

### 2. Configure Environment Variables
In Vercel dashboard, add:
```
REACT_APP_API_URL=https://social-api.marvelhomes.pro
REACT_APP_ENVIRONMENT=production
```

### 3. Set Custom Domain
- Add domain: `social.marvelhomes.pro`
- Update DNS to point to Vercel

## ✅ Post-Deployment Checklist

### Backend Health Checks
- [ ] API responds at `https://social-api.marvelhomes.pro/admin/`
- [ ] SSL certificate is active
- [ ] Django service running
- [ ] Celery worker running
- [ ] Celery beat scheduler running
- [ ] Database accessible
- [ ] Redis accessible

### Frontend Health Checks
- [ ] Site loads at `https://social.marvelhomes.pro`
- [ ] Login page accessible
- [ ] API calls working (check browser console)
- [ ] Registration flow working

### Feature Testing
- [ ] User registration/login
- [ ] Facebook account connection
- [ ] Instagram account connection
- [ ] Post creation
- [ ] Post scheduling
- [ ] Calendar view
- [ ] Analytics dashboard

## 🔧 Production Management Commands

### Service Management
```bash
# Restart all services
sudo supervisorctl restart social-api:*

# View logs
tail -f /var/log/social-api/django.log
tail -f /var/log/social-api/celery-worker.log
tail -f /var/log/social-api/celery-beat.log

# Update code from GitHub
cd /var/www/social
git pull origin master
cd backend
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
sudo supervisorctl restart social-api:*
```

### Database Management
```bash
# Create Django superuser
cd /var/www/social/backend
source venv/bin/activate
python manage.py createsuperuser

# Run migrations
python manage.py migrate

# Database backup
pg_dump social_db > backup_$(date +%Y%m%d_%H%M%S).sql
```

## 🚨 Troubleshooting

### Common Issues & Solutions

1. **502 Bad Gateway**
   ```bash
   sudo supervisorctl status social-api-django
   sudo supervisorctl restart social-api-django
   ```

2. **Database Connection Error**
   ```bash
   sudo systemctl status postgresql
   sudo -u postgres psql -l
   ```

3. **Celery Tasks Not Running**
   ```bash
   redis-cli ping
   sudo supervisorctl restart social-api-celery-worker
   sudo supervisorctl restart social-api-celery-beat
   ```

4. **Static Files 404**
   ```bash
   cd /var/www/social/backend
   python manage.py collectstatic --noinput
   ```

5. **CORS Errors**
   - Verify `CORS_ALLOWED_ORIGINS` in settings includes frontend URL

## 📞 Support

- **Repository**: https://github.com/JimGeek/social
- **Issues**: Create GitHub issues for bugs/features
- **Documentation**: See `DEPLOYMENT.md` for detailed instructions

---

**🎉 Your Social Media Manager is ready for production!**