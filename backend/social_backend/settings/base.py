"""
Base Django settings for social_backend project.

Common settings shared between development and production.
"""

from pathlib import Path
from decouple import config
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.celery import CeleryIntegration

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    
    # Third party apps
    "rest_framework",
    "rest_framework.authtoken",
    "corsheaders",
    "django_extensions",
    "django_celery_beat",
    
    # Local apps
    "social",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "social_backend.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "social_backend.wsgi.application"

# Password validation
# https://docs.djangoproject.com/en/4.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# Internationalization
# https://docs.djangoproject.com/en/4.2/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.2/howto/static-files/

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
# https://docs.djangoproject.com/en/4.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Django REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
}

# Celery Configuration
CELERY_TIMEZONE = TIME_ZONE

# Celery Beat Schedule
CELERY_BEAT_SCHEDULE = {
    'process-scheduled-posts': {
        'task': 'social.tasks.process_scheduled_posts',
        'schedule': 60.0,  # Run every 60 seconds
    },
    'sync-social-comments': {
        'task': 'social.tasks.sync_social_comments',
        'schedule': 300.0,  # Run every 5 minutes
    },
    'daily-analytics-sync': {
        'task': 'social.tasks.daily_analytics_sync',
        'schedule': 3600.0 * 24,  # Run daily
    },
    'update-account-followers': {
        'task': 'social.tasks.update_account_followers',
        'schedule': 3600.0 * 6,  # Run every 6 hours
    },
}

# Social Platform API Keys - These should be overridden in environment-specific settings
FACEBOOK_APP_ID = config('FACEBOOK_APP_ID', default='')
FACEBOOK_APP_SECRET = config('FACEBOOK_APP_SECRET', default='')
FACEBOOK_API_VERSION = config('FACEBOOK_API_VERSION', default='v18.0')
FACEBOOK_SCOPES = [
    'pages_manage_posts',          # Required to publish to Pages
    'pages_read_engagement',       # Required to read Page insights
    'pages_show_list',            # Required to get list of Pages
    'business_management',         # Required for Business Manager
    'instagram_basic',            # Required for Instagram Basic Display
    'instagram_content_publish',   # Required to publish to Instagram
    'public_profile',             # Basic profile information
]

# Instagram Business API (via Facebook)
INSTAGRAM_APP_ID = config('INSTAGRAM_APP_ID', default='')
INSTAGRAM_APP_SECRET = config('INSTAGRAM_APP_SECRET', default='')

# Instagram Login API (for direct Instagram authentication - 2025)
INSTAGRAM_BASIC_APP_ID = config('INSTAGRAM_BASIC_APP_ID', default='')
INSTAGRAM_BASIC_APP_SECRET = config('INSTAGRAM_BASIC_APP_SECRET', default='')

LINKEDIN_CLIENT_ID = config('LINKEDIN_CLIENT_ID', default='')
LINKEDIN_CLIENT_SECRET = config('LINKEDIN_CLIENT_SECRET', default='')

# OpenAI API
OPENAI_API_KEY = config('OPENAI_API_KEY', default='')

# Sentry Configuration for Error Monitoring
SENTRY_DSN = config('SENTRY_DSN', default='')
SENTRY_ENVIRONMENT = config('SENTRY_ENVIRONMENT', default='development')

# Initialize Sentry if DSN is provided
if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[
            DjangoIntegration(
                transaction_style='url',
                middleware_spans=True,
                signals_spans=True,
            ),
            CeleryIntegration(
                monitor_beat_tasks=True,
                propagate_traces=True,
            ),
        ],
        
        # Performance Monitoring
        traces_sample_rate=config('SENTRY_TRACES_SAMPLE_RATE', default=1.0, cast=float),
        
        # Error Monitoring
        send_default_pii=config('SENTRY_SEND_PII', default=True, cast=bool),
        
        # Environment and Release Tracking
        environment=SENTRY_ENVIRONMENT,
        release=config('SENTRY_RELEASE', default=None),
        
        # Additional Options
        attach_stacktrace=True,
        max_breadcrumbs=50,
        
        # Filter out common non-critical errors
        before_send=lambda event, hint: None if 'Http404' in str(hint.get('exc_info', '')) else event,
    )