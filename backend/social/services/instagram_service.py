"""
Instagram Graph API Service for Social Media Manager

Implements Instagram Graph API 2025 for:
- Publishing posts with media (images/videos)
- Account management
- Analytics and insights

Note: Instagram Graph API 2025 requires media (images/videos) for posts.
Text-only posts are not supported.
"""

import logging
import requests
from typing import Dict, List, Any, Optional, Tuple
from django.conf import settings
from django.utils import timezone
from urllib.parse import urlencode

from ..models import SocialAccount

logger = logging.getLogger(__name__)


class InstagramService:
    """Instagram Graph API service for posting and account management"""
    
    def __init__(self):
        self.base_url = "https://graph.facebook.com/v21.0"
        self.app_id = settings.INSTAGRAM_APP_ID
        self.app_secret = settings.INSTAGRAM_APP_SECRET
    
    def publish_post(self, account: SocialAccount, content: str, media_urls: List[str] = None, 
                    first_comment: str = None) -> Dict[str, Any]:
        """
        Publish a post to Instagram using Graph API 2025
        
        Args:
            account: SocialAccount instance for Instagram
            content: Post caption text
            media_urls: List of media URLs (required for Instagram)
            first_comment: Optional first comment
            
        Returns:
            Dict with success status, post_id, post_url, and error info
        """
        try:
            # Validate media requirement
            if not media_urls or len(media_urls) == 0:
                return {
                    'success': False,
                    'error': 'Instagram requires at least one image or video. Text-only posts are not supported by Instagram Graph API 2025.',
                    'error_code': 'MEDIA_REQUIRED',
                    'post_id': None,
                    'post_url': None
                }
            
            # For single media post
            if len(media_urls) == 1:
                return self._publish_single_media_post(account, content, media_urls[0], first_comment)
            else:
                # For carousel post (multiple media)
                return self._publish_carousel_post(account, content, media_urls, first_comment)
                
        except Exception as e:
            logger.error(f"Error publishing Instagram post: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'error_code': 'PUBLISH_ERROR',
                'post_id': None,
                'post_url': None
            }
    
    def _publish_single_media_post(self, account: SocialAccount, caption: str, media_url: str, 
                                  first_comment: str = None) -> Dict[str, Any]:
        """Publish a single media post to Instagram"""
        try:
            # Step 1: Create media container
            container_response = self._create_media_container(account, caption, media_url)
            
            if not container_response['success']:
                return container_response
            
            container_id = container_response['container_id']
            
            # Step 2: Publish the container
            publish_response = self._publish_media_container(account, container_id)
            
            if not publish_response['success']:
                return publish_response
            
            post_id = publish_response['post_id']
            post_url = f"https://www.instagram.com/p/{self._get_shortcode_from_id(post_id)}/"
            
            # Step 3: Add first comment if provided
            if first_comment:
                self._add_comment(account, post_id, first_comment)
            
            return {
                'success': True,
                'post_id': post_id,
                'post_url': post_url,
                'error': None,
                'error_code': None
            }
            
        except Exception as e:
            logger.error(f"Error publishing single media Instagram post: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'error_code': 'SINGLE_MEDIA_ERROR',
                'post_id': None,
                'post_url': None
            }
    
    def _publish_carousel_post(self, account: SocialAccount, caption: str, media_urls: List[str], 
                              first_comment: str = None) -> Dict[str, Any]:
        """Publish a carousel post (multiple media) to Instagram"""
        try:
            # Step 1: Create media containers for each media item
            container_ids = []
            
            for media_url in media_urls:
                container_response = self._create_media_container(account, "", media_url, is_carousel_item=True)
                
                if not container_response['success']:
                    return container_response
                
                container_ids.append(container_response['container_id'])
            
            # Step 2: Create carousel container
            carousel_response = self._create_carousel_container(account, caption, container_ids)
            
            if not carousel_response['success']:
                return carousel_response
            
            carousel_container_id = carousel_response['container_id']
            
            # Step 3: Publish the carousel
            publish_response = self._publish_media_container(account, carousel_container_id)
            
            if not publish_response['success']:
                return publish_response
            
            post_id = publish_response['post_id']
            post_url = f"https://www.instagram.com/p/{self._get_shortcode_from_id(post_id)}/"
            
            # Step 4: Add first comment if provided
            if first_comment:
                self._add_comment(account, post_id, first_comment)
            
            return {
                'success': True,
                'post_id': post_id,
                'post_url': post_url,
                'error': None,
                'error_code': None
            }
            
        except Exception as e:
            logger.error(f"Error publishing carousel Instagram post: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'error_code': 'CAROUSEL_ERROR',
                'post_id': None,
                'post_url': None
            }
    
    def _create_media_container(self, account: SocialAccount, caption: str, media_url: str, 
                               is_carousel_item: bool = False) -> Dict[str, Any]:
        """Create a media container for Instagram posting"""
        try:
            url = f"{self.base_url}/{account.account_id}/media"
            
            # Determine media type
            media_type = self._get_media_type(media_url)
            
            data = {
                'access_token': account.access_token,
                'media_type': media_type.upper()
            }
            
            if media_type == 'image':
                data['image_url'] = media_url
            elif media_type == 'video':
                data['video_url'] = media_url
            else:
                return {
                    'success': False,
                    'error': f'Unsupported media type: {media_type}',
                    'error_code': 'UNSUPPORTED_MEDIA_TYPE',
                    'container_id': None
                }
            
            # Add caption only for single posts, not carousel items
            if caption and not is_carousel_item:
                data['caption'] = caption
            
            # For carousel items
            if is_carousel_item:
                data['is_carousel_item'] = 'true'
            
            response = requests.post(url, data=data)
            
            if response.status_code == 200:
                result = response.json()
                return {
                    'success': True,
                    'container_id': result.get('id'),
                    'error': None,
                    'error_code': None
                }
            else:
                error_data = response.json()
                error_message = error_data.get('error', {}).get('message', 'Unknown error')
                return {
                    'success': False,
                    'error': f'Failed to create media container: {error_message}',
                    'error_code': 'CONTAINER_CREATION_FAILED',
                    'container_id': None
                }
                
        except Exception as e:
            logger.error(f"Error creating Instagram media container: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'error_code': 'CONTAINER_ERROR',
                'container_id': None
            }
    
    def _create_carousel_container(self, account: SocialAccount, caption: str, 
                                  container_ids: List[str]) -> Dict[str, Any]:
        """Create a carousel container for multiple media items"""
        try:
            url = f"{self.base_url}/{account.account_id}/media"
            
            data = {
                'access_token': account.access_token,
                'media_type': 'CAROUSEL',
                'children': ','.join(container_ids)
            }
            
            if caption:
                data['caption'] = caption
            
            response = requests.post(url, data=data)
            
            if response.status_code == 200:
                result = response.json()
                return {
                    'success': True,
                    'container_id': result.get('id'),
                    'error': None,
                    'error_code': None
                }
            else:
                error_data = response.json()
                error_message = error_data.get('error', {}).get('message', 'Unknown error')
                return {
                    'success': False,
                    'error': f'Failed to create carousel container: {error_message}',
                    'error_code': 'CAROUSEL_CREATION_FAILED',
                    'container_id': None
                }
                
        except Exception as e:
            logger.error(f"Error creating Instagram carousel container: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'error_code': 'CAROUSEL_CONTAINER_ERROR',
                'container_id': None
            }
    
    def _publish_media_container(self, account: SocialAccount, container_id: str) -> Dict[str, Any]:
        """Publish a media container to Instagram"""
        try:
            url = f"{self.base_url}/{account.account_id}/media_publish"
            
            data = {
                'access_token': account.access_token,
                'creation_id': container_id
            }
            
            response = requests.post(url, data=data)
            
            if response.status_code == 200:
                result = response.json()
                return {
                    'success': True,
                    'post_id': result.get('id'),
                    'error': None,
                    'error_code': None
                }
            else:
                error_data = response.json()
                error_message = error_data.get('error', {}).get('message', 'Unknown error')
                return {
                    'success': False,
                    'error': f'Failed to publish media: {error_message}',
                    'error_code': 'PUBLISH_FAILED',
                    'post_id': None
                }
                
        except Exception as e:
            logger.error(f"Error publishing Instagram media container: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'error_code': 'PUBLISH_ERROR',
                'post_id': None
            }
    
    def _add_comment(self, account: SocialAccount, post_id: str, comment_text: str) -> bool:
        """Add a comment to an Instagram post"""
        try:
            url = f"{self.base_url}/{post_id}/comments"
            
            data = {
                'access_token': account.access_token,
                'message': comment_text
            }
            
            response = requests.post(url, data=data)
            
            if response.status_code == 200:
                logger.info(f"Successfully added comment to Instagram post {post_id}")
                return True
            else:
                logger.warning(f"Failed to add comment to Instagram post {post_id}: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error adding comment to Instagram post {post_id}: {str(e)}")
            return False
    
    def _get_media_type(self, media_url: str) -> str:
        """Determine media type from URL"""
        url_lower = media_url.lower()
        
        # Image extensions
        image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
        if any(url_lower.endswith(ext) for ext in image_extensions):
            return 'image'
        
        # Video extensions
        video_extensions = ['.mp4', '.mov', '.avi', '.mkv', '.webm']
        if any(url_lower.endswith(ext) for ext in video_extensions):
            return 'video'
        
        # Default to image if uncertain
        return 'image'
    
    def _get_shortcode_from_id(self, post_id: str) -> str:
        """Convert Instagram post ID to shortcode for URL"""
        # This is a simplified version - in production you might want to
        # make an API call to get the actual shortcode
        return post_id.replace('_', '/')
    
    def get_account_info(self, account: SocialAccount) -> Dict[str, Any]:
        """Get Instagram account information"""
        try:
            url = f"{self.base_url}/{account.account_id}"
            params = {
                'fields': 'id,username,account_type,media_count,followers_count',
                'access_token': account.access_token
            }
            
            response = requests.get(url, params=params)
            
            if response.status_code == 200:
                return {
                    'success': True,
                    'data': response.json(),
                    'error': None
                }
            else:
                return {
                    'success': False,
                    'data': None,
                    'error': response.text
                }
                
        except Exception as e:
            logger.error(f"Error getting Instagram account info: {str(e)}")
            return {
                'success': False,
                'data': None,
                'error': str(e)
            }
    
    def get_media_insights(self, account: SocialAccount, media_id: str) -> Dict[str, Any]:
        """Get insights for a specific Instagram media post"""
        try:
            url = f"{self.base_url}/{media_id}/insights"
            params = {
                'metric': 'impressions,reach,engagement,likes,comments,saves,shares',
                'access_token': account.access_token
            }
            
            response = requests.get(url, params=params)
            
            if response.status_code == 200:
                insights_data = response.json().get('data', [])
                
                # Convert insights to dictionary
                insights = {}
                for insight in insights_data:
                    metric_name = insight.get('name')
                    metric_values = insight.get('values', [])
                    if metric_values:
                        insights[metric_name] = metric_values[0].get('value', 0)
                
                return {
                    'success': True,
                    'insights': insights,
                    'error': None
                }
            else:
                return {
                    'success': False,
                    'insights': {},
                    'error': response.text
                }
                
        except Exception as e:
            logger.error(f"Error getting Instagram media insights: {str(e)}")
            return {
                'success': False,
                'insights': {},
                'error': str(e)
            }