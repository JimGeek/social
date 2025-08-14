from django.core.management.base import BaseCommand
from django.conf import settings
import subprocess
import sys
import os

class Command(BaseCommand):
    help = 'Start Celery Beat scheduler for periodic social media tasks'

    def add_arguments(self, parser):
        parser.add_argument(
            '--loglevel',
            default='info',
            help='Set the logging level for the beat scheduler (default: info)'
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('Starting Celery Beat scheduler for social media tasks...')
        )

        # Check if Redis is running
        try:
            import redis
            r = redis.Redis.from_url(settings.CELERY_BROKER_URL)
            r.ping()
            self.stdout.write(
                self.style.SUCCESS('✓ Redis connection successful')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'✗ Redis connection failed: {e}')
            )
            self.stdout.write(
                self.style.WARNING('Make sure Redis is running: redis-server')
            )
            return

        # Prepare Celery Beat command
        celery_cmd = [
            sys.executable, '-m', 'celery',
            'beat',
            '-A', 'genius',
            '--loglevel', options['loglevel'],
            '--scheduler', 'django_celery_beat.schedulers:DatabaseScheduler'
        ]

        self.stdout.write(f"Command: {' '.join(celery_cmd)}")
        
        try:
            # Change to the project directory
            os.chdir(settings.BASE_DIR)
            
            # Start Celery Beat
            subprocess.run(celery_cmd, check=True)
            
        except KeyboardInterrupt:
            self.stdout.write(
                self.style.SUCCESS('\nCelery Beat scheduler stopped by user')
            )
        except subprocess.CalledProcessError as e:
            self.stdout.write(
                self.style.ERROR(f'Celery Beat scheduler failed: {e}')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error starting Celery Beat scheduler: {e}')
            )