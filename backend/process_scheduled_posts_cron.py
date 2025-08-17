#!/opt/social-media/venv/bin/python3
import os
import sys
import django

# Add the backend directory to the Python path
sys.path.append('/opt/social-media/backend')

# Set Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'social_backend.settings.production')

# Setup Django
django.setup()

# Now import and run the task
from social.tasks import process_scheduled_posts
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/social-api/cron-scheduler.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

try:
    logger.info('Starting scheduled posts processing via cron')
    result = process_scheduled_posts()
    logger.info(f'Scheduled posts processing completed: {result}')
except Exception as e:
    logger.error(f'Error in scheduled posts processing: {str(e)}')
    import traceback
    logger.error(traceback.format_exc())
