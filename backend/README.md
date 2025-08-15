# Social Media Manager - Backend Development Setup

## Quick Start for Local Development

### 1. Virtual Environment Setup

The project uses a virtual environment that's already configured. Activate it:

```bash
source venv/bin/activate
```

### 2. Install Dependencies

Install the required packages:

```bash
pip install django==4.2.23 djangorestframework==3.15.2 django-cors-headers==4.6.0 django-extensions==3.2.3 celery==5.3.6 redis==5.2.0 django-celery-beat==2.8.0 requests==2.32.3 python-decouple==3.8
```

### 3. Database Setup

The development environment uses SQLite (no external database required):

```bash
python manage.py migrate
```

### 4. Run Development Server

Start the Django development server:

```bash
python manage.py runserver 8080
```

The API will be available at: `http://localhost:8080`

## Environment Configuration

### Development Settings

The project uses modular settings:

- **Development**: `social_backend.settings.development` (default for `manage.py`)
- **Production**: `social_backend.settings.production` (used in deployment)

### Environment Variables

Create/update `.env` file in the backend directory:

```bash
SECRET_KEY=your-development-secret-key
DEBUG=True
DJANGO_SETTINGS_MODULE=social_backend.settings.development

# Social Platform API Keys (for testing)
FACEBOOK_APP_ID=your_facebook_app_id
FACEBOOK_APP_SECRET=your_facebook_app_secret
INSTAGRAM_APP_ID=your_instagram_app_id
INSTAGRAM_APP_SECRET=your_instagram_app_secret

# Optional: Local Redis for Celery (otherwise uses in-memory)
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

## Features

### Instagram Graph API 2025

The backend includes Instagram Graph API 2025 implementation:

- **Media Requirement**: Instagram requires images/videos for posts
- **Text-only posts**: Not supported by Instagram API 2025
- **Error Handling**: Clear error messages for API limitations

### Celery Task Processing

Development configuration:

- **In-memory broker**: No Redis required for local development
- **Synchronous execution**: Tasks run immediately for easier debugging
- **Background workers**: Optional Redis setup for production-like testing

### Database

- **Development**: SQLite (no setup required)
- **Production**: PostgreSQL with connection pooling

## Testing the Instagram Service

Test the Instagram posting functionality:

```python
python manage.py shell

# In the shell:
from social.services.instagram_service import InstagramService
service = InstagramService()

# Test media requirement validation
result = service.publish_post(None, 'Test content', [])
print(result)
# Expected: Media requirement error
```

## API Testing

Test the API endpoints:

```bash
# Check server health
curl http://localhost:8080/api/social/accounts/

# Expected response: Authentication required
```

## Troubleshooting

### ModuleNotFoundError

Always use the virtual environment:

```bash
source venv/bin/activate
python manage.py runserver
```

### Port Already in Use

Try a different port:

```bash
python manage.py runserver 8080
# or
python manage.py runserver 8001
```

### Missing Dependencies

Install missing packages in the virtual environment:

```bash
source venv/bin/activate
pip install package-name
```

## Development vs Production

| Feature | Development | Production |
|---------|-------------|------------|
| Database | SQLite | PostgreSQL |
| Celery Broker | In-memory | Redis |
| Debug | Enabled | Disabled |
| Security | Relaxed | HTTPS + Security headers |
| Logging | Console | Files + Rotation |

## Next Steps

1. **Frontend Setup**: See `../frontend/README.md` for React setup
2. **API Documentation**: Available at `/api/docs/` when server is running
3. **Production Deployment**: See `../PRODUCTION_DEPLOY.md`

---

🤖 This setup ensures you can develop locally without external dependencies while maintaining production compatibility.