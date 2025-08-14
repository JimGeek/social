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
                    media_urls: List[str] = None, first_comment: str = None) -> Dict[str, Any]:
        """
        Publish a post to Facebook page
        """
        try:
            page_id = account.account_id
            access_token = account.access_token
            
            url = f"{self.base_url}/{page_id}/feed"
            
            data = {
                'message': content,
                'access_token': access_token,
            }
            
            # Handle media attachments
            if media_urls:
                # For now, just use the first image
                # In production, you'd handle multiple media properly
                data['link'] = media_urls[0] if media_urls[0].startswith('http') else None
            
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
            logger.error(f"Error publishing Facebook post: {str(e)}")
            return {
                'success': False,
                'error': str(e)
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