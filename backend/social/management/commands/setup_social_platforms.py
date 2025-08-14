from django.core.management.base import BaseCommand
from social.models import SocialPlatform


class Command(BaseCommand):
    help = 'Set up social media platforms with default configurations'

    def handle(self, *args, **options):
        platforms = [
            {
                'name': 'facebook',
                'display_name': 'Facebook',
                'icon_class': 'fab fa-facebook',
                'color_hex': '#1877F2',
                'max_text_length': 63206,
                'max_image_count': 10,
                'max_video_size_mb': 4000,
                'supports_scheduling': True,
                'supports_hashtags': True,
                'supports_first_comment': True,
                'api_version': 'v18.0',
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
                'api_version': 'v18.0',
            },
            {
                'name': 'linkedin',
                'display_name': 'LinkedIn',
                'icon_class': 'fab fa-linkedin',
                'color_hex': '#0077B5',
                'max_text_length': 1300,
                'max_image_count': 9,
                'max_video_size_mb': 5000,
                'supports_scheduling': True,
                'supports_hashtags': True,
                'supports_first_comment': False,
                'api_version': 'v2',
            },
            {
                'name': 'twitter',
                'display_name': 'Twitter/X',
                'icon_class': 'fab fa-twitter',
                'color_hex': '#1DA1F2',
                'max_text_length': 280,
                'max_image_count': 4,
                'max_video_size_mb': 512,
                'supports_scheduling': True,
                'supports_hashtags': True,
                'supports_first_comment': False,
                'api_version': 'v2',
            },
            {
                'name': 'youtube',
                'display_name': 'YouTube',
                'icon_class': 'fab fa-youtube',
                'color_hex': '#FF0000',
                'max_text_length': 5000,
                'max_image_count': 1,
                'max_video_size_mb': 256000,  # 256GB for premium
                'supports_scheduling': True,
                'supports_hashtags': True,
                'supports_first_comment': False,
                'api_version': 'v3',
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
                'api_version': 'v5',
            },
            {
                'name': 'google_business',
                'display_name': 'Google My Business',
                'icon_class': 'fab fa-google',
                'color_hex': '#4285F4',
                'max_text_length': 1500,
                'max_image_count': 10,
                'max_video_size_mb': 100,
                'supports_scheduling': True,
                'supports_hashtags': False,
                'supports_first_comment': False,
                'api_version': 'v4.9',
            },
            {
                'name': 'tiktok',
                'display_name': 'TikTok',
                'icon_class': 'fab fa-tiktok',
                'color_hex': '#000000',
                'max_text_length': 2200,
                'max_image_count': 35,
                'max_video_size_mb': 4000,
                'supports_scheduling': True,
                'supports_hashtags': True,
                'supports_first_comment': False,
                'api_version': 'v1',
            },
        ]

        created_count = 0
        updated_count = 0

        for platform_data in platforms:
            platform, created = SocialPlatform.objects.update_or_create(
                name=platform_data['name'],
                defaults=platform_data
            )
            
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'Created platform: {platform.display_name}')
                )
            else:
                updated_count += 1
                self.stdout.write(
                    self.style.WARNING(f'Updated platform: {platform.display_name}')
                )

        self.stdout.write(
            self.style.SUCCESS(
                f'\nSetup complete! Created {created_count} platforms, updated {updated_count} platforms.'
            )
        )