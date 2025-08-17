import requests
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from django.conf import settings
from django.utils import timezone

from ..models import SocialAccount

logger = logging.getLogger(__name__)

class FacebookService:
    """
    Service for Facebook Graph API interactions
    """
    
    def __init__(self):
        self.app_id = settings.FACEBOOK_APP_ID
        self.app_secret = settings.FACEBOOK_APP_SECRET
        self.base_url = "https://graph.facebook.com/v18.0"
    
    def get_auth_url(self, redirect_uri: str, state: str = None) -> str:
        """
        Generate Facebook OAuth authorization URL
        """
        params = {
            'client_id': self.app_id,
            'redirect_uri': redirect_uri,
            'scope': 'pages_manage_posts,pages_read_engagement,pages_show_list,public_profile,email',
            'response_type': 'code',
        }
        
        if state:
            params['state'] = state
        
        query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
        return f"https://www.facebook.com/v18.0/dialog/oauth?{query_string}"
    
    def exchange_code_for_token(self, code: str, redirect_uri: str) -> Dict[str, Any]:
        """
        Exchange authorization code for access token
        """
        try:
            url = f"{self.base_url}/oauth/access_token"
            params = {
                'client_id': self.app_id,
                'client_secret': self.app_secret,
                'redirect_uri': redirect_uri,
                'code': code,
            }
            
            response = requests.get(url, params=params)
            response.raise_for_status()
            
            token_data = response.json()
            
            # Get long-lived token
            long_lived_token = self.get_long_lived_token(token_data['access_token'])
            
            return {
                'success': True,
                'access_token': long_lived_token,
                'token_type': token_data.get('token_type', 'bearer'),
                'expires_in': token_data.get('expires_in')
            }
            
        except requests.RequestException as e:
            logger.error(f"Error exchanging Facebook code for token: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_long_lived_token(self, short_lived_token: str) -> str:
        """
        Exchange short-lived token for long-lived token (60 days)
        """
        try:
            url = f"{self.base_url}/oauth/access_token"
            params = {
                'grant_type': 'fb_exchange_token',
                'client_id': self.app_id,
                'client_secret': self.app_secret,
                'fb_exchange_token': short_lived_token,
            }
            
            response = requests.get(url, params=params)
            response.raise_for_status()
            
            token_data = response.json()
            return token_data['access_token']
            
        except requests.RequestException as e:
            logger.error(f"Error getting long-lived Facebook token: {str(e)}")
            return short_lived_token  # Return original token if exchange fails
    
    def get_user_info(self, access_token: str) -> Dict[str, Any]:
        """
        Get user information from Facebook
        """
        try:
            url = f"{self.base_url}/me"
            params = {
                'access_token': access_token,
                'fields': 'id,name,email,picture'
            }
            
            response = requests.get(url, params=params)
            response.raise_for_status()
            
            return {
                'success': True,
                'user': response.json()
            }
            
        except requests.RequestException as e:
            logger.error(f"Error getting Facebook user info: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_user_pages(self, access_token: str) -> Dict[str, Any]:
        """
        Get pages managed by the user
        """
        try:
            url = f"{self.base_url}/me/accounts"
            params = {
                'access_token': access_token,
                'fields': 'id,name,access_token,picture,category,about'
            }
            
            response = requests.get(url, params=params)
            response.raise_for_status()
            
            return {
                'success': True,
                'pages': response.json().get('data', [])
            }
            
        except requests.RequestException as e:
            logger.error(f"Error getting Facebook pages: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def publish_post(self, account: SocialAccount, content: str, 
                    media_urls: List[str] = None, first_comment: str = None, post_type: str = 'image') -> Dict[str, Any]:
        """
        Publish a post to Facebook page
        """
        try:
            page_id = account.account_id
            access_token = account.access_token
            
            # Handle Facebook Stories differently
            if post_type == 'story':
                return self._publish_facebook_story(account, content, media_urls)
            
            # Handle Facebook Reels differently
            if post_type == 'reel':
                return self._publish_facebook_reel(account, content, media_urls)
            
            url = f"{self.base_url}/{page_id}/feed"
            
            data = {
                'message': content,
                'access_token': access_token,
            }
            
            # Handle media attachments
            if media_urls:
                # Check if we have videos - Facebook videos need different handling
                has_video = any(self._is_video_file(url) for url in media_urls)
                
                if has_video and len(media_urls) == 1:
                    # Single video post - use different endpoint
                    return self._publish_video_post(account, content, media_urls[0])
                elif has_video:
                    # Mixed media or multiple videos not supported in single post
                    logger.warning("Mixed media or multiple videos not supported in single Facebook post")
                
                # Handle image uploads
                media_fbids = []
                for media_url in media_urls[:10]:  # Facebook supports up to 10 images
                    if not self._is_video_file(media_url):  # Only images for regular posts
                        fbid = self._upload_media_to_facebook(account, media_url)
                        if fbid:
                            media_fbids.append(fbid)
                
                if media_fbids:
                    # Facebook expects attached_media as JSON string
                    import json
                    if len(media_fbids) == 1:
                        # Single image post
                        data['attached_media'] = json.dumps([{'media_fbid': media_fbids[0]}])
                    else:
                        # Multiple images - create album
                        data['attached_media'] = json.dumps([{'media_fbid': fbid} for fbid in media_fbids])
            
            response = requests.post(url, data=data)
            response.raise_for_status()
            
            result = response.json()
            post_id = result.get('id')
            
            # Add first comment if provided
            if first_comment and post_id:
                self.add_comment(account, post_id, first_comment)
            
            return {
                'success': True,
                'post_id': post_id,
                'post_url': f"https://facebook.com/{post_id.replace('_', '/posts/')}"
            }
            
        except requests.RequestException as e:
            error_details = str(e)
            # Try to get more detailed error from response
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_json = e.response.json()
                    if 'error' in error_json:
                        error_details = f"{error_json['error'].get('message', str(e))} (Code: {error_json['error'].get('code', 'unknown')})"
                except:
                    error_details = f"{str(e)} - Response: {e.response.text[:200]}"
            
            logger.error(f"Error publishing Facebook post: {error_details}")
            return {
                'success': False,
                'error': error_details
            }
    
    def add_comment(self, account: SocialAccount, post_id: str, comment_text: str) -> bool:
        """
        Add a comment to a Facebook post
        """
        try:
            url = f"{self.base_url}/{post_id}/comments"
            data = {
                'message': comment_text,
                'access_token': account.access_token,
            }
            
            response = requests.post(url, data=data)
            response.raise_for_status()
            
            logger.info(f"Added first comment to Facebook post {post_id}")
            return True
            
        except requests.RequestException as e:
            logger.error(f"Error adding Facebook comment: {str(e)}")
            return False
    
    def get_post_insights(self, account: SocialAccount, post_id: str) -> Dict[str, Any]:
        """
        Get insights/analytics for a Facebook post
        """
        try:
            url = f"{self.base_url}/{post_id}/insights"
            params = {
                'access_token': account.access_token,
                'metric': 'post_impressions,post_engaged_users,post_clicks,post_reactions_like_total,post_comments,post_shares'
            }
            
            response = requests.get(url, params=params)
            response.raise_for_status()
            
            insights_data = response.json().get('data', [])
            
            # Parse insights into a readable format
            insights = {}
            for insight in insights_data:
                metric = insight['name']
                values = insight.get('values', [])
                if values:
                    insights[metric] = values[0].get('value', 0)
            
            # Map Facebook metrics to our standardized format
            standardized = {
                'impressions': insights.get('post_impressions', 0),
                'reach': insights.get('post_impressions', 0),  # Approximation
                'engagement': insights.get('post_engaged_users', 0),
                'clicks': insights.get('post_clicks', 0),
                'likes': insights.get('post_reactions_like_total', 0),
                'comments': insights.get('post_comments', 0),
                'shares': insights.get('post_shares', 0),
            }
            
            return standardized
            
        except requests.RequestException as e:
            logger.error(f"Error getting Facebook post insights: {str(e)}")
            return {}
    
    def get_recent_comments(self, account: SocialAccount, days: int = 7) -> List[Dict[str, Any]]:
        """
        Get recent comments on all posts for a page
        """
        try:
            page_id = account.account_id
            access_token = account.access_token
            
            # First get recent posts
            posts_url = f"{self.base_url}/{page_id}/posts"
            since_date = (timezone.now() - timedelta(days=days)).isoformat()
            
            posts_params = {
                'access_token': access_token,
                'fields': 'id,created_time',
                'since': since_date,
                'limit': 50
            }
            
            posts_response = requests.get(posts_url, params=posts_params)
            posts_response.raise_for_status()
            
            posts = posts_response.json().get('data', [])
            
            # Get comments for each post
            all_comments = []
            for post in posts:
                post_id = post['id']
                
                comments_url = f"{self.base_url}/{post_id}/comments"
                comments_params = {
                    'access_token': access_token,
                    'fields': 'id,message,from,created_time,like_count',
                    'limit': 20
                }
                
                try:
                    comments_response = requests.get(comments_url, params=comments_params)
                    comments_response.raise_for_status()
                    
                    comments = comments_response.json().get('data', [])
                    all_comments.extend(comments)
                    
                except requests.RequestException as e:
                    logger.warning(f"Error getting comments for post {post_id}: {str(e)}")
                    continue
            
            return all_comments
            
        except requests.RequestException as e:
            logger.error(f"Error getting Facebook comments: {str(e)}")
            return []
    
    def refresh_page_token(self, account: SocialAccount) -> bool:
        """
        Refresh the page access token
        """
        try:
            # Get user's long-lived token first
            user_token_url = f"{self.base_url}/oauth/access_token"
            user_token_params = {
                'grant_type': 'fb_exchange_token',
                'client_id': self.app_id,
                'client_secret': self.app_secret,
                'fb_exchange_token': account.access_token,
            }
            
            user_response = requests.get(user_token_url, params=user_token_params)
            user_response.raise_for_status()
            user_token_data = user_response.json()
            user_token = user_token_data['access_token']
            
            # Get new page token
            pages_url = f"{self.base_url}/me/accounts"
            pages_params = {
                'access_token': user_token,
                'fields': 'id,access_token'
            }
            
            pages_response = requests.get(pages_url, params=pages_params)
            pages_response.raise_for_status()
            
            pages = pages_response.json().get('data', [])
            page = next((p for p in pages if p['id'] == account.account_id), None)
            
            if page:
                account.access_token = page['access_token']
                account.is_token_expired = False
                account.save()
                
                logger.info(f"Refreshed Facebook page token for {account.account_name}")
                return True
            else:
                logger.error(f"Page {account.account_id} not found in user's pages")
                return False
                
        except requests.RequestException as e:
            logger.error(f"Error refreshing Facebook page token: {str(e)}")
            return False
    
    def validate_token(self, access_token: str) -> Dict[str, Any]:
        """
        Validate a Facebook access token
        """
        try:
            url = f"{self.base_url}/me"
            params = {
                'access_token': access_token,
                'fields': 'id'
            }
            
            response = requests.get(url, params=params)
            
            if response.status_code == 200:
                return {
                    'valid': True,
                    'data': response.json()
                }
            else:
                return {
                    'valid': False,
                    'error': response.json().get('error', {}).get('message', 'Unknown error')
                }
                
        except requests.RequestException as e:
            return {
                'valid': False,
                'error': str(e)
            }
    
    def _upload_media_to_facebook(self, account: SocialAccount, media_url: str) -> Optional[str]:
        """
        Upload media to Facebook page and return media FBID
        """
        import os
        
        try:
            page_id = account.account_id
            access_token = account.access_token
            
            # Check if media_url is a local file path or URL
            if media_url.startswith('http'):
                # Remote URL - download first
                media_response = requests.get(media_url)
                if media_response.status_code != 200:
                    logger.error(f"Failed to download media from {media_url}")
                    return None
                media_data = media_response.content
                filename = media_url.split('/')[-1] if '/' in media_url else 'image.jpg'
            else:
                # Local file path
                if not os.path.exists(media_url):
                    logger.error(f"Media file not found: {media_url}")
                    return None
                
                with open(media_url, 'rb') as f:
                    media_data = f.read()
                filename = os.path.basename(media_url)
            
            # Upload to Facebook page photos endpoint
            upload_url = f"{self.base_url}/{page_id}/photos"
            
            # Determine proper content type
            if filename.lower().endswith('.png'):
                content_type = 'image/png'
            elif filename.lower().endswith('.gif'):
                content_type = 'image/gif'
            else:
                content_type = 'image/jpeg'
            
            files = {
                'source': (filename, media_data, content_type)
            }
            
            data = {
                'access_token': access_token,
                'published': 'false'  # Upload unpublished to get FBID for later use
            }
            
            response = requests.post(upload_url, files=files, data=data)
            
            if response.status_code == 200:
                result = response.json()
                fbid = result.get('id')
                logger.info(f"Successfully uploaded media to Facebook: {fbid}")
                return fbid
            else:
                error_detail = response.text
                try:
                    error_json = response.json()
                    if 'error' in error_json:
                        error_detail = f"{error_json['error'].get('message', error_detail)} (Code: {error_json['error'].get('code', response.status_code)})"
                except:
                    pass
                logger.error(f"Facebook media upload failed (Status {response.status_code}): {error_detail}")
                return None
                
        except Exception as e:
            logger.error(f"Facebook media upload error: {str(e)}")
            return None
    
    def _is_video_file(self, media_url: str) -> bool:
        """Check if the media file is a video"""
        url_lower = media_url.lower()
        video_extensions = ['.mp4', '.mov', '.avi', '.mkv', '.webm']
        return any(url_lower.endswith(ext) for ext in video_extensions)
    
    def _publish_video_post(self, account: SocialAccount, content: str, video_url: str) -> Dict[str, Any]:
        """Publish a video post to Facebook page"""
        import os
        
        try:
            page_id = account.account_id
            access_token = account.access_token
            
            # Check if video_url is a local file path or URL
            if video_url.startswith('http'):
                # Remote URL - download first
                video_response = requests.get(video_url)
                if video_response.status_code != 200:
                    logger.error(f"Failed to download video from {video_url}")
                    return {'success': False, 'error': f'Failed to download video from {video_url}'}
                video_data = video_response.content
                filename = video_url.split('/')[-1] if '/' in video_url else 'video.mp4'
            else:
                # Local file path
                if not os.path.exists(video_url):
                    logger.error(f"Video file not found: {video_url}")
                    return {'success': False, 'error': f'Video file not found: {video_url}'}
                
                with open(video_url, 'rb') as f:
                    video_data = f.read()
                filename = os.path.basename(video_url)
            
            # Upload video to Facebook page
            upload_url = f"{self.base_url}/{page_id}/videos"
            
            files = {
                'source': (filename, video_data, 'video/mp4')
            }
            
            data = {
                'access_token': access_token,
                'description': content
            }
            
            response = requests.post(upload_url, files=files, data=data)
            
            if response.status_code == 200:
                result = response.json()
                post_id = result.get('id')
                logger.info(f"Successfully uploaded video to Facebook: {post_id}")
                return {
                    'success': True,
                    'post_id': post_id,
                    'post_url': f"https://facebook.com/{post_id.replace('_', '/posts/')}"
                }
            else:
                logger.error(f"Facebook video upload failed: {response.text}")
                return {'success': False, 'error': f'Facebook video upload failed: {response.text}'}
                
        except Exception as e:
            logger.error(f"Facebook video upload error: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def publish_instagram_post(self, account: SocialAccount, content: str, 
                             media_urls: List[str] = None, first_comment: str = None, post_type: str = 'image') -> Dict[str, Any]:
        """
        Publish a post to Instagram Business account via Facebook Graph API
        """
        try:
            instagram_account_id = account.account_id
            access_token = account.access_token
            
            # For Instagram posts via Facebook, we need to use the Instagram Content Publishing API
            # Step 1: Create media container
            
            if not media_urls or len(media_urls) == 0:
                return {
                    'success': False,
                    'error': 'Instagram requires at least one image or video. Text-only posts are not supported.',
                    'error_code': 'MEDIA_REQUIRED'
                }
            
            # Handle Stories differently
            if post_type == 'story':
                return self._publish_instagram_story(instagram_account_id, access_token, content, media_urls[0])
            
            # Handle single media vs multiple media
            if len(media_urls) == 1:
                media_url = media_urls[0]
                
                # Determine if it's video or image
                if self._is_video_file(media_url):
                    # For videos, use REELS
                    container_data = {
                        'media_type': 'REELS',
                        'video_url': media_url,
                        'caption': content,
                        'access_token': access_token
                    }
                else:
                    # For images
                    container_data = {
                        'image_url': media_url,
                        'caption': content,
                        'access_token': access_token
                    }
                
                # Create container
                container_url = f"{self.base_url}/{instagram_account_id}/media"
                container_response = requests.post(container_url, data=container_data)
                
                if container_response.status_code != 200:
                    error_data = container_response.json()
                    error_message = error_data.get('error', {}).get('message', 'Container creation failed')
                    return {
                        'success': False,
                        'error': f'Failed to create Instagram media container: {error_message}'
                    }
                
                container_result = container_response.json()
                container_id = container_result.get('id')
                
                # For videos (REELS), we need to wait for processing
                if self._is_video_file(media_url):
                    # Wait for container to be ready
                    ready = self._wait_for_instagram_container(instagram_account_id, container_id, access_token)
                    if not ready:
                        return {
                            'success': False,
                            'error': 'Instagram video container not ready for publishing'
                        }
                
                # Step 2: Publish the container
                publish_url = f"{self.base_url}/{instagram_account_id}/media_publish"
                publish_data = {
                    'creation_id': container_id,
                    'access_token': access_token
                }
                
                publish_response = requests.post(publish_url, data=publish_data)
                
                if publish_response.status_code == 200:
                    publish_result = publish_response.json()
                    post_id = publish_result.get('id')
                    
                    # Create Instagram URL
                    if self._is_video_file(media_url):
                        post_url = f"https://www.instagram.com/reel/{post_id}/"
                    else:
                        post_url = f"https://www.instagram.com/p/{post_id}/"
                    
                    return {
                        'success': True,
                        'post_id': post_id,
                        'post_url': post_url
                    }
                else:
                    error_data = publish_response.json()
                    error_message = error_data.get('error', {}).get('message', 'Publishing failed')
                    return {
                        'success': False,
                        'error': f'Failed to publish Instagram post: {error_message}'
                    }
            else:
                # Multiple media - carousel post
                return self._publish_instagram_carousel(instagram_account_id, access_token, content, media_urls)
                
        except Exception as e:
            logger.error(f"Error publishing Instagram post via Facebook: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _wait_for_instagram_container(self, instagram_account_id: str, container_id: str, 
                                    access_token: str, max_wait_seconds: int = 60) -> bool:
        """Wait for Instagram container to be ready for publishing"""
        import time
        
        try:
            start_time = time.time()
            
            while time.time() - start_time < max_wait_seconds:
                # Check container status
                status_url = f"{self.base_url}/{container_id}"
                params = {
                    'access_token': access_token,
                    'fields': 'status_code'
                }
                
                response = requests.get(status_url, params=params)
                
                if response.status_code == 200:
                    result = response.json()
                    status_code = result.get('status_code', 'UNKNOWN')
                    
                    logger.info(f"Instagram container {container_id} status: {status_code}")
                    
                    if status_code == 'FINISHED':
                        return True
                    elif status_code == 'ERROR':
                        logger.error(f"Instagram container {container_id} processing failed")
                        return False
                    elif status_code in ['IN_PROGRESS', 'PUBLISHED']:
                        time.sleep(2)
                        continue
                else:
                    logger.warning(f"Failed to check Instagram container status: {response.text}")
                    time.sleep(2)
                    continue
            
            logger.error(f"Instagram container {container_id} not ready after {max_wait_seconds} seconds")
            return False
            
        except Exception as e:
            logger.error(f"Error waiting for Instagram container: {str(e)}")
            return False
    
    def _publish_instagram_carousel(self, instagram_account_id: str, access_token: str, 
                                   content: str, media_urls: List[str]) -> Dict[str, Any]:
        """Publish a carousel post to Instagram Business account via Facebook Graph API"""
        try:
            # Step 1: Create media containers for each item
            container_ids = []
            
            for media_url in media_urls[:10]:  # Instagram supports max 10 items in carousel
                # Check if media is video or image
                if self._is_video_file(media_url):
                    # Videos in carousel are not supported by Instagram
                    logger.warning(f"Skipping video {media_url} - videos not supported in Instagram carousel")
                    continue
                
                # Create container for image
                container_data = {
                    'image_url': media_url,
                    'is_carousel_item': 'true',
                    'access_token': access_token
                }
                
                container_url = f"{self.base_url}/{instagram_account_id}/media"
                response = requests.post(container_url, data=container_data)
                
                if response.status_code == 200:
                    result = response.json()
                    container_ids.append(result.get('id'))
                    logger.info(f"Created carousel item container: {result.get('id')}")
                else:
                    error_data = response.json()
                    error_message = error_data.get('error', {}).get('message', 'Container creation failed')
                    logger.error(f"Failed to create carousel item container: {error_message}")
                    return {
                        'success': False,
                        'error': f'Failed to create carousel item container: {error_message}'
                    }
            
            if len(container_ids) == 0:
                return {
                    'success': False,
                    'error': 'No valid media items for carousel (videos not supported in carousel)'
                }
            
            # Step 2: Create carousel container
            carousel_data = {
                'media_type': 'CAROUSEL',
                'children': ','.join(container_ids),
                'caption': content,
                'access_token': access_token
            }
            
            carousel_url = f"{self.base_url}/{instagram_account_id}/media"
            carousel_response = requests.post(carousel_url, data=carousel_data)
            
            if carousel_response.status_code != 200:
                error_data = carousel_response.json()
                error_message = error_data.get('error', {}).get('message', 'Carousel creation failed')
                return {
                    'success': False,
                    'error': f'Failed to create carousel container: {error_message}'
                }
            
            carousel_result = carousel_response.json()
            carousel_container_id = carousel_result.get('id')
            
            # Step 3: Publish the carousel
            publish_url = f"{self.base_url}/{instagram_account_id}/media_publish"
            publish_data = {
                'creation_id': carousel_container_id,
                'access_token': access_token
            }
            
            publish_response = requests.post(publish_url, data=publish_data)
            
            if publish_response.status_code == 200:
                publish_result = publish_response.json()
                post_id = publish_result.get('id')
                post_url = f"https://www.instagram.com/p/{post_id}/"
                
                logger.info(f"Successfully published Instagram carousel with {len(container_ids)} items")
                
                return {
                    'success': True,
                    'post_id': post_id,
                    'post_url': post_url
                }
            else:
                error_data = publish_response.json()
                error_message = error_data.get('error', {}).get('message', 'Publishing failed')
                return {
                    'success': False,
                    'error': f'Failed to publish Instagram carousel: {error_message}'
                }
                
        except Exception as e:
            logger.error(f"Error publishing Instagram carousel: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _publish_instagram_story(self, instagram_account_id: str, access_token: str, 
                                content: str, media_url: str) -> Dict[str, Any]:
        """
        Publish an Instagram Story via Facebook Graph API
        """
        try:
            # Step 1: Create story media container
            container_url = f"{self.base_url}/{instagram_account_id}/media"
            
            # Determine media type
            if self._is_video_file(media_url):
                container_data = {
                    'media_type': 'STORIES',
                    'video_url': media_url,
                    'access_token': access_token
                }
            else:
                container_data = {
                    'media_type': 'STORIES',
                    'image_url': media_url,
                    'access_token': access_token
                }
            
            # Stories don't support captions in the same way
            # Text overlays would need to be added via other methods
            
            container_response = requests.post(container_url, data=container_data)
            
            if container_response.status_code != 200:
                error_data = container_response.json()
                error_message = error_data.get('error', {}).get('message', 'Story container creation failed')
                return {
                    'success': False,
                    'error': f'Failed to create Instagram Story container: {error_message}'
                }
            
            container_result = container_response.json()
            container_id = container_result.get('id')
            
            # Step 2: Publish the story
            publish_url = f"{self.base_url}/{instagram_account_id}/media_publish"
            publish_data = {
                'creation_id': container_id,
                'access_token': access_token
            }
            
            publish_response = requests.post(publish_url, data=publish_data)
            
            if publish_response.status_code == 200:
                publish_result = publish_response.json()
                story_id = publish_result.get('id')
                
                # Stories don't have permanent URLs, they're temporary
                story_url = f"https://www.instagram.com/stories/{instagram_account_id}/"
                
                return {
                    'success': True,
                    'post_id': story_id,
                    'post_url': story_url
                }
            else:
                error_data = publish_response.json()
                error_message = error_data.get('error', {}).get('message', 'Story publishing failed')
                return {
                    'success': False,
                    'error': f'Failed to publish Instagram Story: {error_message}'
                }
                
        except Exception as e:
            logger.error(f"Error publishing Instagram Story via Facebook: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _publish_facebook_story(self, account: SocialAccount, content: str, media_urls: List[str]) -> Dict[str, Any]:
        """
        Publish a Facebook Story to a Facebook Page
        """
        try:
            if not media_urls or len(media_urls) == 0:
                return {
                    'success': False,
                    'error': 'Facebook Stories require at least one image or video'
                }
            
            page_id = account.account_id
            access_token = account.access_token
            media_url = media_urls[0]  # Facebook Stories support one media item
            
            # Determine if it's a photo or video story
            if self._is_video_file(media_url):
                return self._publish_facebook_video_story(page_id, access_token, content, media_url)
            else:
                return self._publish_facebook_photo_story(page_id, access_token, content, media_url)
                
        except Exception as e:
            logger.error(f"Error publishing Facebook Story: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _publish_facebook_photo_story(self, page_id: str, access_token: str, content: str, photo_url: str) -> Dict[str, Any]:
        """Publish a Facebook Photo Story"""
        try:
            # Step 1: Upload photo to get photo_id
            fbid = self._upload_media_to_facebook_for_story(page_id, access_token, photo_url)
            if not fbid:
                return {
                    'success': False,
                    'error': 'Failed to upload photo for Facebook Story'
                }
            
            # Step 2: Publish as photo story
            story_url = f"{self.base_url}/{page_id}/photo_stories"
            story_data = {
                'photo_id': fbid,
                'access_token': access_token
            }
            
            response = requests.post(story_url, data=story_data)
            
            if response.status_code == 200:
                result = response.json()
                story_id = result.get('id')
                
                return {
                    'success': True,
                    'post_id': story_id,
                    'post_url': f"https://facebook.com/stories/{page_id}/"
                }
            else:
                error_data = response.json()
                error_message = error_data.get('error', {}).get('message', 'Photo story publishing failed')
                return {
                    'success': False,
                    'error': f'Failed to publish Facebook photo story: {error_message}'
                }
                
        except Exception as e:
            logger.error(f"Error publishing Facebook photo story: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _publish_facebook_video_story(self, page_id: str, access_token: str, content: str, video_url: str) -> Dict[str, Any]:
        """Publish a Facebook Video Story using three-phase upload process"""
        try:
            # Phase 1: Start upload and get video_id and upload_url
            start_response = self._start_video_story_upload(page_id, access_token)
            if not start_response['success']:
                return start_response
            
            video_id = start_response['video_id']
            upload_url = start_response['upload_url']
            
            # Phase 2: Upload video file to upload_url
            upload_response = self._upload_video_to_story_url(upload_url, video_url, access_token)
            if not upload_response['success']:
                return upload_response
            
            # Phase 3: Finish upload and publish story
            finish_response = self._finish_video_story_upload(page_id, access_token, video_id)
            if not finish_response['success']:
                return finish_response
            
            return {
                'success': True,
                'post_id': finish_response.get('post_id'),
                'post_url': f"https://facebook.com/stories/{page_id}/"
            }
                
        except Exception as e:
            logger.error(f"Error publishing Facebook video story: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _upload_media_to_facebook_for_story(self, page_id: str, access_token: str, media_url: str) -> Optional[str]:
        """Upload media to Facebook for Story use"""
        import os
        
        try:
            # Check if media_url is a local file path or URL
            if media_url.startswith('http'):
                # Remote URL - download first
                media_response = requests.get(media_url)
                if media_response.status_code != 200:
                    logger.error(f"Failed to download media from {media_url}")
                    return None
                media_data = media_response.content
                filename = media_url.split('/')[-1] if '/' in media_url else 'image.jpg'
            else:
                # Local file path
                if not os.path.exists(media_url):
                    logger.error(f"Media file not found: {media_url}")
                    return None
                
                with open(media_url, 'rb') as f:
                    media_data = f.read()
                filename = os.path.basename(media_url)
            
            # Upload to Facebook page photos endpoint for Story
            upload_url = f"{self.base_url}/{page_id}/photos"
            
            # Determine proper content type
            if filename.lower().endswith('.png'):
                content_type = 'image/png'
            elif filename.lower().endswith('.gif'):
                content_type = 'image/gif'
            else:
                content_type = 'image/jpeg'
            
            files = {
                'source': (filename, media_data, content_type)
            }
            
            data = {
                'access_token': access_token,
                'published': 'false',  # Upload unpublished to get FBID for Story use
                'temporary': 'true'     # For Story use
            }
            
            response = requests.post(upload_url, files=files, data=data)
            
            if response.status_code == 200:
                result = response.json()
                fbid = result.get('id')
                logger.info(f"Successfully uploaded media to Facebook for Story: {fbid}")
                return fbid
            else:
                logger.error(f"Facebook media upload for Story failed: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Facebook media upload for Story error: {str(e)}")
            return None
    
    def _start_video_story_upload(self, page_id: str, access_token: str) -> Dict[str, Any]:
        """Phase 1: Start video story upload and get video_id and upload_url"""
        try:
            url = f"{self.base_url}/{page_id}/video_stories"
            data = {
                'upload_phase': 'start',
                'access_token': access_token
            }
            
            response = requests.post(url, data=data)
            
            if response.status_code == 200:
                result = response.json()
                video_id = result.get('video_id')
                upload_url = result.get('upload_url')
                
                if video_id and upload_url:
                    logger.info(f"Started Facebook video story upload: video_id={video_id}")
                    return {
                        'success': True,
                        'video_id': video_id,
                        'upload_url': upload_url
                    }
                else:
                    return {
                        'success': False,
                        'error': 'Missing video_id or upload_url in start response'
                    }
            else:
                error_data = response.json()
                error_message = error_data.get('error', {}).get('message', 'Start upload failed')
                return {
                    'success': False,
                    'error': f'Failed to start video story upload: {error_message}'
                }
                
        except Exception as e:
            logger.error(f"Error starting video story upload: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _upload_video_to_story_url(self, upload_url: str, video_url: str, access_token: str) -> Dict[str, Any]:
        """Phase 2: Upload video file to the provided upload_url"""
        import os
        
        try:
            # Check if video_url is a local file path or URL
            if video_url.startswith('http'):
                # Remote URL - download first
                video_response = requests.get(video_url)
                if video_response.status_code != 200:
                    logger.error(f"Failed to download video from {video_url}")
                    return {
                        'success': False,
                        'error': f'Failed to download video from {video_url}'
                    }
                video_data = video_response.content
                filename = video_url.split('/')[-1] if '/' in video_url else 'video.mp4'
            else:
                # Local file path
                if not os.path.exists(video_url):
                    logger.error(f"Video file not found: {video_url}")
                    return {
                        'success': False,
                        'error': f'Video file not found: {video_url}'
                    }
                
                with open(video_url, 'rb') as f:
                    video_data = f.read()
                filename = os.path.basename(video_url)
            
            # Upload video to the provided upload_url
            files = {
                'video_file_chunk': (filename, video_data, 'video/mp4')
            }
            
            headers = {
                'Authorization': f'OAuth {access_token}',
                'file_url': video_url
            }
            
            # Set longer timeout for video uploads
            response = requests.post(upload_url, files=files, headers=headers, timeout=300)
            
            if response.status_code == 200:
                result = response.json()
                success = result.get('success', False)
                
                if success:
                    logger.info(f"Successfully uploaded video to Facebook story upload URL")
                    return {
                        'success': True
                    }
                else:
                    return {
                        'success': False,
                        'error': 'Upload reported failure in response'
                    }
            else:
                logger.error(f"Video upload to story URL failed (Status {response.status_code}): {response.text}")
                return {
                    'success': False,
                    'error': f'Video upload failed with status {response.status_code}'
                }
                
        except Exception as e:
            logger.error(f"Error uploading video to story URL: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _finish_video_story_upload(self, page_id: str, access_token: str, video_id: str) -> Dict[str, Any]:
        """Phase 3: Finish video story upload and publish"""
        try:
            url = f"{self.base_url}/{page_id}/video_stories"
            data = {
                'upload_phase': 'finish',
                'video_id': video_id,
                'access_token': access_token
            }
            
            response = requests.post(url, data=data)
            
            if response.status_code == 200:
                result = response.json()
                success = result.get('success', False)
                post_id = result.get('post_id')
                
                if success:
                    logger.info(f"Successfully finished Facebook video story upload: post_id={post_id}")
                    return {
                        'success': True,
                        'post_id': post_id
                    }
                else:
                    return {
                        'success': False,
                        'error': 'Finish upload reported failure in response'
                    }
            else:
                error_data = response.json()
                error_message = error_data.get('error', {}).get('message', 'Finish upload failed')
                return {
                    'success': False,
                    'error': f'Failed to finish video story upload: {error_message}'
                }
                
        except Exception as e:
            logger.error(f"Error finishing video story upload: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _publish_facebook_reel(self, account: SocialAccount, content: str, media_urls: List[str]) -> Dict[str, Any]:
        """
        Publish a Facebook Reel to a Facebook Page
        Uses the Facebook video_reels API endpoint
        """
        try:
            if not media_urls or len(media_urls) == 0:
                return {
                    'success': False,
                    'error': 'Facebook Reels require exactly one video file'
                }
            
            if len(media_urls) > 1:
                return {
                    'success': False,
                    'error': 'Facebook Reels support only one video file'
                }
            
            page_id = account.account_id
            access_token = account.access_token
            video_url = media_urls[0]
            
            # Validate that it's a video file
            if not self._is_video_file(video_url):
                return {
                    'success': False,
                    'error': 'Facebook Reels require a video file, not an image'
                }
            
            # Use three-phase upload process for Facebook Reels
            # Phase 1: Start upload and get video_id and upload_url
            start_response = self._start_facebook_reel_upload(page_id, access_token)
            if not start_response['success']:
                return start_response
            
            video_id = start_response['video_id']
            upload_url = start_response['upload_url']
            
            # Phase 2: Upload video file to upload_url
            upload_response = self._upload_video_to_reel_url(upload_url, video_url, access_token)
            if not upload_response['success']:
                return upload_response
            
            # Phase 3: Finish upload and publish reel
            finish_response = self._finish_facebook_reel_upload(page_id, access_token, video_id, content)
            if not finish_response['success']:
                return finish_response
            
            return {
                'success': True,
                'post_id': finish_response.get('post_id'),
                'post_url': f"https://facebook.com/{page_id}/videos/{video_id}/"
            }
                
        except Exception as e:
            logger.error(f"Error publishing Facebook Reel: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _start_facebook_reel_upload(self, page_id: str, access_token: str) -> Dict[str, Any]:
        """Phase 1: Start Facebook Reel upload and get video_id and upload_url"""
        try:
            url = f"{self.base_url}/{page_id}/video_reels"
            data = {
                'upload_phase': 'start',
                'access_token': access_token
            }
            
            response = requests.post(url, data=data)
            
            if response.status_code == 200:
                result = response.json()
                video_id = result.get('video_id')
                upload_url = result.get('upload_url')
                
                if video_id and upload_url:
                    logger.info(f"Started Facebook Reel upload: video_id={video_id}")
                    return {
                        'success': True,
                        'video_id': video_id,
                        'upload_url': upload_url
                    }
                else:
                    return {
                        'success': False,
                        'error': 'Missing video_id or upload_url in start response'
                    }
            else:
                error_data = response.json()
                error_message = error_data.get('error', {}).get('message', 'Start upload failed')
                return {
                    'success': False,
                    'error': f'Failed to start Facebook Reel upload: {error_message}'
                }
                
        except Exception as e:
            logger.error(f"Error starting Facebook Reel upload: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _upload_video_to_reel_url(self, upload_url: str, video_url: str, access_token: str) -> Dict[str, Any]:
        """Phase 2: Upload video file to the provided upload_url for Reel"""
        import os
        
        try:
            # Check if video_url is a local file path or URL
            if video_url.startswith('http'):
                # Remote URL - download first
                video_response = requests.get(video_url)
                if video_response.status_code != 200:
                    logger.error(f"Failed to download video from {video_url}")
                    return {
                        'success': False,
                        'error': f'Failed to download video from {video_url}'
                    }
                video_data = video_response.content
                filename = video_url.split('/')[-1] if '/' in video_url else 'reel.mp4'
            else:
                # Local file path
                if not os.path.exists(video_url):
                    logger.error(f"Video file not found: {video_url}")
                    return {
                        'success': False,
                        'error': f'Video file not found: {video_url}'
                    }
                
                with open(video_url, 'rb') as f:
                    video_data = f.read()
                filename = os.path.basename(video_url)
            
            # Upload video to the provided upload_url
            files = {
                'video_file_chunk': (filename, video_data, 'video/mp4')
            }
            
            headers = {
                'Authorization': f'OAuth {access_token}',
                'file_url': video_url
            }
            
            # Set longer timeout for video uploads
            response = requests.post(upload_url, files=files, headers=headers, timeout=300)
            
            if response.status_code == 200:
                result = response.json()
                success = result.get('success', False)
                
                if success:
                    logger.info(f"Successfully uploaded video to Facebook Reel upload URL")
                    return {
                        'success': True
                    }
                else:
                    return {
                        'success': False,
                        'error': 'Upload reported failure in response'
                    }
            else:
                logger.error(f"Video upload to Reel URL failed (Status {response.status_code}): {response.text}")
                return {
                    'success': False,
                    'error': f'Video upload failed with status {response.status_code}'
                }
                
        except Exception as e:
            logger.error(f"Error uploading video to Reel URL: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _finish_facebook_reel_upload(self, page_id: str, access_token: str, video_id: str, description: str = '') -> Dict[str, Any]:
        """Phase 3: Finish Facebook Reel upload and publish"""
        try:
            url = f"{self.base_url}/{page_id}/video_reels"
            data = {
                'upload_phase': 'finish',
                'video_id': video_id,
                'video_state': 'PUBLISHED',
                'access_token': access_token
            }
            
            # Add description if provided
            if description:
                data['description'] = description
            
            response = requests.post(url, data=data)
            
            if response.status_code == 200:
                result = response.json()
                success = result.get('success', False)
                post_id = result.get('id') or result.get('post_id')
                
                if success:
                    logger.info(f"Successfully finished Facebook Reel upload: post_id={post_id}")
                    return {
                        'success': True,
                        'post_id': post_id
                    }
                else:
                    return {
                        'success': False,
                        'error': 'Finish upload reported failure in response'
                    }
            else:
                error_data = response.json()
                error_message = error_data.get('error', {}).get('message', 'Finish upload failed')
                return {
                    'success': False,
                    'error': f'Failed to finish Facebook Reel upload: {error_message}'
                }
                
        except Exception as e:
            logger.error(f"Error finishing Facebook Reel upload: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }