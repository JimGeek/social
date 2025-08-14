from django.core.management.base import BaseCommand
from django.conf import settings
import subprocess
import sys
import os

class Command(BaseCommand):
    help = 'Start Celery worker for social media tasks'

    def add_arguments(self, parser):
        parser.add_argument(
            '--loglevel',
            default='info',
            help='Set the logging level for the worker (default: info)'
        )
        parser.add_argument(
            '--concurrency',
            type=int,
            default=4,
            help='Number of concurrent worker processes (default: 4)'
        )
        parser.add_argument(
            '--queues',
            default='social_publishing,social_scheduling,social_sync,ai_processing,analytics',
            help='Comma-separated list of queues to consume from'
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('Starting Celery worker for social media tasks...')
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

        # Prepare Celery command
        celery_cmd = [
            sys.executable, '-m', 'celery',
            'worker',
            '-A', 'genius',
            '--loglevel', options['loglevel'],
            '--concurrency', str(options['concurrency']),
            '--queues', options['queues'],
            '--pool', 'prefork',
            '--without-gossip',
            '--without-mingle',
            '--without-heartbeat'
        ]

        self.stdout.write(f"Command: {' '.join(celery_cmd)}")
        
        try:
            # Change to the project directory
            os.chdir(settings.BASE_DIR)
            
            # Start the Celery worker
            subprocess.run(celery_cmd, check=True)
            
        except KeyboardInterrupt:
            self.stdout.write(
                self.style.SUCCESS('\nCelery worker stopped by user')
            )
        except subprocess.CalledProcessError as e:
            self.stdout.write(
                self.style.ERROR(f'Celery worker failed: {e}')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error starting Celery worker: {e}')
            )