"""
Django management command to setup social media platforms
Usage: python manage.py setup_platforms
"""

from django.core.management.base import BaseCommand
from social.models import SocialPlatform


class Command(BaseCommand):
    help = 'Setup social media platforms in the database'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Setting up social media platforms...'))
        
        # Define platform data
        platforms_data = [
            {
                'name': 'facebook',
                'display_name': 'Facebook',
                'icon_class': 'fab fa-facebook-f',
                'color_hex': '#1877F2',
                'max_text_length': 63206,
                'max_image_count': 10,
                'max_video_size_mb': 4000,
                'supports_scheduling': True,
                'supports_hashtags': True,
                'supports_first_comment': True,
                'api_version': 'v21.0'
            },
            {
                'name': 'instagram',
                'display_name': 'Instagram', 
                'icon_class': 'fab fa-instagram',
                'color_hex': '#E4405F',
                'max_text_length': 2200,
                'max_image_count': 10,
                'max_video_size_mb': 100,
                'supports_scheduling': True,
                'supports_hashtags': True,
                'supports_first_comment': True,
                'api_version': 'v21.0'
            },
            {
                'name': 'linkedin',
                'display_name': 'LinkedIn',
                'icon_class': 'fab fa-linkedin-in',
                'color_hex': '#0A66C2',
                'max_text_length': 3000,
                'max_image_count': 9,
                'max_video_size_mb': 200,
                'supports_scheduling': True,
                'supports_hashtags': True,
                'supports_first_comment': False,
                'api_version': 'v2'
            },
            {
                'name': 'twitter',
                'display_name': 'Twitter/X',
                'icon_class': 'fab fa-x-twitter',
                'color_hex': '#000000',
                'max_text_length': 280,
                'max_image_count': 4,
                'max_video_size_mb': 512,
                'supports_scheduling': True,
                'supports_hashtags': True,
                'supports_first_comment': False,
                'api_version': 'v2'
            },
            {
                'name': 'youtube',
                'display_name': 'YouTube',
                'icon_class': 'fab fa-youtube',
                'color_hex': '#FF0000',
                'max_text_length': 5000,
                'max_image_count': 1,
                'max_video_size_mb': 128000,
                'supports_scheduling': True,
                'supports_hashtags': True,
                'supports_first_comment': False,
                'api_version': 'v3'
            },
            {
                'name': 'pinterest',
                'display_name': 'Pinterest',
                'icon_class': 'fab fa-pinterest',
                'color_hex': '#BD081C',
                'max_text_length': 500,
                'max_image_count': 1,
                'max_video_size_mb': 2000,
                'supports_scheduling': True,
                'supports_hashtags': True,
                'supports_first_comment': False,
                'api_version': 'v5'
            },
            {
                'name': 'tiktok',
                'display_name': 'TikTok',
                'icon_class': 'fab fa-tiktok',
                'color_hex': '#000000',
                'max_text_length': 2200,
                'max_image_count': 1,
                'max_video_size_mb': 287,
                'supports_scheduling': False,
                'supports_hashtags': True,
                'supports_first_comment': False,
                'api_version': 'v1'
            }
        ]
        
        # Create or update platforms
        created_count = 0
        updated_count = 0
        
        for platform_data in platforms_data:
            platform, created = SocialPlatform.objects.get_or_create(
                name=platform_data['name'],
                defaults=platform_data
            )
            
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'✅ Created platform: {platform.display_name}')
                )
            else:
                # Update existing platform with new data
                for field, value in platform_data.items():
                    setattr(platform, field, value)
                platform.save()
                updated_count += 1
                self.stdout.write(
                    self.style.WARNING(f'🔄 Updated platform: {platform.display_name}')
                )
        
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(f'📊 Platform Setup Summary:'))
        self.stdout.write(f'   Created: {created_count} new platforms')
        self.stdout.write(f'   Updated: {updated_count} existing platforms')
        self.stdout.write(f'   Total: {SocialPlatform.objects.count()} platforms in database')
        self.stdout.write('')
        
        # List all platforms
        self.stdout.write(self.style.SUCCESS('🌐 Available platforms:'))
        for platform in SocialPlatform.objects.all().order_by('display_name'):
            status = '✅ Active' if platform.is_active else '❌ Inactive'
            self.stdout.write(f'   {platform.display_name} ({platform.name}) - {status}')
        
        self.stdout.write('')
        self.stdout.write(
            self.style.SUCCESS('✅ Platform setup completed! Platforms are now available in the Social Media Manager.')
        )