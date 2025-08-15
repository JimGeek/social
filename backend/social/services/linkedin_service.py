"""
LinkedIn API v2 Service for Social Media Manager

Implements LinkedIn API v2 for:
- OAuth 2.0 authentication
- Publishing posts (text and media)
- User profile information
- Analytics and insights

LinkedIn API v2 Requirements 2025:
- Uses OAuth 2.0 with specific scopes
- Requires app approval for advanced features
- Rate limiting enforced
- LinkedIn-Version and X-Restli-Protocol-Version headers required
"""

import logging
import requests
from typing import Dict, List, Any, Optional
from django.conf import settings
from django.utils import timezone
from urllib.parse import urlencode

from ..models import SocialAccount

logger = logging.getLogger(__name__)


class LinkedInService:
    """LinkedIn API v2 service for posting and account management"""
    
    def __init__(self):
        self.base_url = "https://api.linkedin.com/v2"
        self.oauth_url = "https://www.linkedin.com/oauth/v2"
        self.client_id = getattr(settings, 'LINKEDIN_CLIENT_ID', '')
        self.client_secret = getattr(settings, 'LINKEDIN_CLIENT_SECRET', '')
        
        # Required headers for LinkedIn API v2
        self.api_headers = {
            'LinkedIn-Version': '202210',
            'X-Restli-Protocol-Version': '2.0.0',
            'Content-Type': 'application/json'
        }
    
    def get_auth_url(self, redirect_uri: str, state: str = None) -> str:
        """
        Generate LinkedIn OAuth authorization URL
        
        Required scopes for posting:
        - openid: Basic profile access
        - profile: Profile information
        - w_member_social: Write access for social posts
        """
        params = {
            'response_type': 'code',
            'client_id': self.client_id,
            'redirect_uri': redirect_uri,
            'scope': 'openid profile w_member_social',
        }
        
        if state:
            params['state'] = state
        
        return f"{self.oauth_url}/authorization?{urlencode(params)}"
    
    def exchange_code_for_token(self, code: str, redirect_uri: str) -> Dict[str, Any]:
        """
        Exchange authorization code for access token
        """
        try:
            url = f"{self.oauth_url}/accessToken"
            
            data = {
                'grant_type': 'authorization_code',
                'code': code,
                'redirect_uri': redirect_uri,
                'client_id': self.client_id,
                'client_secret': self.client_secret,
            }
            
            headers = {'Content-Type': 'application/x-www-form-urlencoded'}
            
            response = requests.post(url, data=data, headers=headers)
            
            logger.info(f"LinkedIn token exchange response: {response.status_code}")
            logger.debug(f"Response content: {response.text}")
            
            if response.status_code == 200:
                token_data = response.json()
                logger.info(f"Token exchange successful, scope: {token_data.get('scope', 'none')}")
                return {
                    'success': True,
                    'access_token': token_data.get('access_token'),
                    'expires_in': token_data.get('expires_in', 5184000),  # Default 60 days
                    'scope': token_data.get('scope', ''),
                    'error': None
                }
            else:
                try:
                    error_data = response.json()
                    error_msg = error_data.get('error_description', error_data.get('error', 'Token exchange failed'))
                except:
                    error_msg = response.text
                logger.error(f"LinkedIn token exchange failed: {error_msg}")
                return {
                    'success': False,
                    'access_token': None,
                    'error': error_msg
                }
                
        except Exception as e:
            logger.error(f"LinkedIn token exchange error: {str(e)}")
            return {
                'success': False,
                'access_token': None,
                'error': str(e)
            }
    
    def get_user_profile(self, access_token: str) -> Dict[str, Any]:
        """
        Get LinkedIn user profile information using OpenID Connect userinfo endpoint
        """
        try:
            # Use OpenID Connect userinfo endpoint for basic profile info
            url = "https://api.linkedin.com/v2/userinfo"
            params = {}
            
            headers = {
                **self.api_headers,
                'Authorization': f'Bearer {access_token}'
            }
            
            response = requests.get(url, params=params, headers=headers)
            
            logger.info(f"LinkedIn profile fetch response: {response.status_code}")
            logger.debug(f"Profile response content: {response.text}")
            
            if response.status_code == 200:
                profile_data = response.json()
                logger.info(f"Profile data keys: {list(profile_data.keys())}")
                
                # Extract data from OpenID Connect userinfo response
                # Expected fields: sub, name, given_name, family_name, picture, email, etc.
                user_id = profile_data.get('sub', '')
                full_name = profile_data.get('name', '')
                first_name = profile_data.get('given_name', '')
                last_name = profile_data.get('family_name', '')
                profile_picture_url = profile_data.get('picture', '')
                
                # Fallback: split full name if given_name/family_name not available
                if not first_name and not last_name and full_name:
                    name_parts = full_name.split(' ', 1)
                    first_name = name_parts[0] if len(name_parts) > 0 else ''
                    last_name = name_parts[1] if len(name_parts) > 1 else ''
                
                logger.info(f"Extracted profile: ID={user_id}, Name={first_name} {last_name}")
                
                return {
                    'success': True,
                    'data': {
                        'id': user_id,
                        'first_name': first_name,
                        'last_name': last_name,
                        'profile_picture_url': profile_picture_url
                    },
                    'error': None
                }
            else:
                logger.error(f"LinkedIn profile fetch failed: {response.status_code} - {response.text}")
                return {
                    'success': False,
                    'data': None,
                    'error': f"Profile fetch failed: {response.text}"
                }
                
        except Exception as e:
            logger.error(f"LinkedIn profile fetch error: {str(e)}")
            return {
                'success': False,
                'data': None,
                'error': str(e)
            }
    
    def publish_post(self, account: SocialAccount, content: str, media_urls: List[str] = None) -> Dict[str, Any]:
        """
        Publish a post to LinkedIn using UGC Posts API
        
        Args:
            account: SocialAccount instance for LinkedIn
            content: Post text content
            media_urls: Optional list of media URLs (images/videos)
            
        Returns:
            Dict with success status, post_id, post_url, and error info
        """
        try:
            if not content.strip():
                return {
                    'success': False,
                    'error': 'Content is required for LinkedIn posts',
                    'error_code': 'CONTENT_REQUIRED',
                    'post_id': None,
                    'post_url': None
                }
            
            # Prepare post data
            post_data = {
                "author": f"urn:li:person:{account.account_id}",
                "lifecycleState": "PUBLISHED",
                "specificContent": {
                    "com.linkedin.ugc.ShareContent": {
                        "shareCommentary": {
                            "text": content
                        },
                        "shareMediaCategory": "NONE"
                    }
                },
                "visibility": {
                    "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
                }
            }
            
            # Add media if provided
            if media_urls and len(media_urls) > 0:
                if len(media_urls) == 1:
                    # Single media
                    media_urn = self._upload_media(account, media_urls[0])
                    if media_urn:
                        # Determine media category based on file type
                        media_category = self._get_media_category(media_urls[0])
                        post_data["specificContent"]["com.linkedin.ugc.ShareContent"]["shareMediaCategory"] = media_category
                        post_data["specificContent"]["com.linkedin.ugc.ShareContent"]["media"] = [
                            {
                                "status": "READY",
                                "description": {
                                    "text": content[:200] if len(content) > 200 else content
                                },
                                "media": media_urn,
                                "title": {
                                    "text": "Social Media Post"
                                }
                            }
                        ]
                else:
                    # Multiple media - LinkedIn supports multiple images
                    media_list = []
                    for media_url in media_urls[:9]:  # LinkedIn supports up to 9 images
                        media_urn = self._upload_media(account, media_url)
                        if media_urn:
                            media_list.append({
                                "status": "READY",
                                "description": {
                                    "text": content[:200] if len(content) > 200 else content
                                },
                                "media": media_urn,
                                "title": {
                                    "text": "Social Media Post"
                                }
                            })
                    
                    if media_list:
                        # Use IMAGE for multiple media (LinkedIn doesn't support mixed media types)
                        post_data["specificContent"]["com.linkedin.ugc.ShareContent"]["shareMediaCategory"] = "IMAGE"
                        post_data["specificContent"]["com.linkedin.ugc.ShareContent"]["media"] = media_list
            
            # Make API request
            url = f"{self.base_url}/ugcPosts"
            headers = {
                **self.api_headers,
                'Authorization': f'Bearer {account.access_token}'
            }
            
            response = requests.post(url, json=post_data, headers=headers)
            
            if response.status_code in [200, 201]:
                post_id = response.headers.get('x-restli-id', '')
                
                # LinkedIn post URLs are typically in the format:
                # https://www.linkedin.com/feed/update/urn:li:ugcPost:{id}
                post_url = f"https://www.linkedin.com/feed/update/urn:li:ugcPost:{post_id}" if post_id else ""
                
                return {
                    'success': True,
                    'post_id': post_id,
                    'post_url': post_url,
                    'error': None,
                    'error_code': None
                }
            else:
                error_data = response.json() if response.content else {}
                error_message = error_data.get('message', response.text)
                
                return {
                    'success': False,
                    'error': f'LinkedIn post failed: {error_message}',
                    'error_code': 'POST_FAILED',
                    'post_id': None,
                    'post_url': None
                }
                
        except Exception as e:
            logger.error(f"LinkedIn post error: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'error_code': 'POST_ERROR',
                'post_id': None,
                'post_url': None
            }
    
    def _upload_media(self, account: SocialAccount, media_url: str) -> Optional[str]:
        """
        Upload media to LinkedIn using Vector API
        """
        import requests
        import os
        from django.conf import settings
        
        try:
            # Check if media_url is a local file path or URL
            if media_url.startswith('http'):
                # Remote URL - download first
                media_response = requests.get(media_url)
                if media_response.status_code != 200:
                    logger.error(f"Failed to download media from {media_url}")
                    return None
                media_data = media_response.content
                # Get filename from URL or use default
                filename = media_url.split('/')[-1] if '/' in media_url else 'image.jpg'
            else:
                # Local file path
                if not os.path.exists(media_url):
                    logger.error(f"Media file not found: {media_url}")
                    return None
                
                with open(media_url, 'rb') as f:
                    media_data = f.read()
                filename = os.path.basename(media_url)
            
            # Determine media category and recipe
            media_category = self._get_media_category(media_url)
            
            if media_category == 'VIDEO':
                recipe = "urn:li:digitalmediaRecipe:feedshare-video"
            else:
                recipe = "urn:li:digitalmediaRecipe:feedshare-image"
            
            # Step 1: Register upload with LinkedIn
            register_url = "https://api.linkedin.com/v2/assets?action=registerUpload"
            register_data = {
                "registerUploadRequest": {
                    "recipes": [recipe],
                    "owner": f"urn:li:person:{account.account_id}",
                    "serviceRelationships": [
                        {
                            "relationshipType": "OWNER",
                            "identifier": "urn:li:userGeneratedContent"
                        }
                    ]
                }
            }
            
            headers = {
                'Authorization': f'Bearer {account.access_token}',
                'Content-Type': 'application/json'
            }
            
            register_response = requests.post(register_url, json=register_data, headers=headers)
            
            if register_response.status_code != 200:
                logger.error(f"LinkedIn register upload failed: {register_response.text}")
                return None
            
            register_result = register_response.json()
            upload_url = register_result['value']['uploadMechanism']['com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest']['uploadUrl']
            asset_id = register_result['value']['asset']
            
            # Step 2: Upload the actual media data
            upload_headers = {
                'Authorization': f'Bearer {account.access_token}',
            }
            
            # Set appropriate content type
            if media_category == 'VIDEO':
                content_type = 'video/mp4'
            else:
                content_type = 'image/jpeg'
            
            files = {'file': (filename, media_data, content_type)}
            upload_response = requests.post(upload_url, headers=upload_headers, files=files)
            
            if upload_response.status_code not in [200, 201]:
                logger.error(f"LinkedIn media upload failed: {upload_response.text}")
                return None
            
            logger.info(f"Successfully uploaded media to LinkedIn: {asset_id}")
            return asset_id
            
        except Exception as e:
            logger.error(f"LinkedIn media upload error: {str(e)}")
            return None
    
    def _get_media_category(self, media_url: str) -> str:
        """
        Determine LinkedIn media category from file URL/path
        LinkedIn supports: NONE, IMAGE, VIDEO, ARTICLE
        """
        url_lower = media_url.lower()
        
        # Video extensions
        video_extensions = ['.mp4', '.mov', '.avi', '.mkv', '.webm']
        if any(url_lower.endswith(ext) for ext in video_extensions):
            return 'VIDEO'
        
        # Image extensions (default)
        image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
        if any(url_lower.endswith(ext) for ext in image_extensions):
            return 'IMAGE'
        
        # Default to image if uncertain
        return 'IMAGE'
    
    def get_post_analytics(self, account: SocialAccount, post_id: str) -> Dict[str, Any]:
        """
        Get analytics for a LinkedIn post
        Note: Requires special permissions and app approval
        """
        try:
            # LinkedIn analytics require special permissions
            # This is a placeholder for future implementation
            
            return {
                'success': False,
                'analytics': {},
                'error': 'LinkedIn analytics require special app permissions'
            }
            
        except Exception as e:
            logger.error(f"LinkedIn analytics error: {str(e)}")
            return {
                'success': False,
                'analytics': {},
                'error': str(e)
            }
    
    def validate_token(self, access_token: str) -> bool:
        """
        Validate LinkedIn access token by making a simple API call
        """
        try:
            url = f"{self.base_url}/people/~"
            headers = {
                **self.api_headers,
                'Authorization': f'Bearer {access_token}'
            }
            
            response = requests.get(url, headers=headers)
            return response.status_code == 200
            
        except Exception as e:
            logger.error(f"LinkedIn token validation error: {str(e)}")
            return False
    
    def refresh_token(self, account: SocialAccount) -> Dict[str, Any]:
        """
        LinkedIn doesn't support token refresh. Tokens expire and require re-authorization.
        """
        return {
            'success': False,
            'error': 'LinkedIn tokens cannot be refreshed. User must re-authorize the application.',
            'requires_reauth': True
        }