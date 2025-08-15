"""
Analytics Service for Social Media Platforms
Handles real data collection from Facebook and Instagram Insights APIs
"""
import requests
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from django.utils import timezone
from django.conf import settings
from django.db import transaction
from ..models import SocialAccount, SocialPost, SocialPostTarget, SocialAnalytics, SocialComment

logger = logging.getLogger(__name__)


class AnalyticsService:
    """Main service for collecting and processing social media analytics"""
    
    def __init__(self, user=None):
        self.user = user
        self.facebook_service = FacebookAnalyticsService()
        self.instagram_service = InstagramAnalyticsService()
        self.linkedin_service = LinkedInAnalyticsService()
    
    def sync_all_analytics(self, user_id: str, days_back: int = 7) -> Dict[str, Any]:
        """Sync analytics for all connected accounts for a user"""
        results = {
            'facebook': {'success': 0, 'failed': 0, 'errors': []},
            'instagram': {'success': 0, 'failed': 0, 'errors': []},
            'linkedin': {'success': 0, 'failed': 0, 'errors': []},
            'total_posts_updated': 0,
            'sync_timestamp': timezone.now().isoformat()
        }
        
        try:
            # Get all connected accounts for user
            accounts = SocialAccount.objects.filter(
                created_by_id=user_id,
                status='connected'
            ).select_related('platform')
            
            logger.info(f"Starting analytics sync for {accounts.count()} accounts")
            
            for account in accounts:
                platform_name = account.platform.name.lower()
                
                try:
                    if platform_name == 'facebook':
                        sync_result = self.facebook_service.sync_account_analytics(account, days_back)
                        results['facebook']['success'] += sync_result.get('posts_updated', 0)
                    
                    elif platform_name == 'instagram':
                        sync_result = self.instagram_service.sync_account_analytics(account, days_back)
                        results['instagram']['success'] += sync_result.get('posts_updated', 0)
                    
                    elif platform_name == 'linkedin':
                        # LinkedIn analytics temporarily disabled due to API permission requirements
                        logger.info(f"LinkedIn analytics skipped for {account.account_name} - requires Marketing Developer Platform")
                        results['linkedin']['success'] += 0
                        sync_result = {'posts_updated': 0}  # Dummy result for LinkedIn
                    
                    results['total_posts_updated'] += sync_result.get('posts_updated', 0)
                    
                except Exception as e:
                    error_msg = f"Failed to sync {platform_name} account {account.account_name}: {str(e)}"
                    logger.error(error_msg)
                    results[platform_name]['failed'] += 1
                    results[platform_name]['errors'].append(error_msg)
            
            logger.info(f"Analytics sync completed. Updated {results['total_posts_updated']} posts")
            return results
            
        except Exception as e:
            logger.error(f"Analytics sync failed: {str(e)}")
            raise
    
    def get_account_insights(self, account_id: str, date_range: Dict[str, str]) -> Dict[str, Any]:
        """Get comprehensive insights for a specific account"""
        try:
            from datetime import datetime
            account = SocialAccount.objects.get(id=account_id)
            platform_name = account.platform.name.lower()
            
            if platform_name == 'facebook':
                return self.facebook_service.get_account_insights(account, date_range)
            elif platform_name == 'instagram':
                return self.instagram_service.get_account_insights(account, date_range)
            elif platform_name == 'linkedin':
                return {
                    'account_name': account.account_name,
                    'platform': 'LinkedIn',
                    'message': 'LinkedIn analytics temporarily disabled - requires Marketing Developer Platform access',
                    'summary': {'total_posts': 0, 'total_impressions': 0, 'total_reach': 0, 'total_engagement': 0}
                }
            else:
                return {'error': f'Analytics not supported for platform: {platform_name}'}
                
        except SocialAccount.DoesNotExist:
            return {'error': 'Account not found'}
        except Exception as e:
            logger.error(f"Failed to get account insights: {str(e)}")
            return {'error': str(e)}


class FacebookAnalyticsService:
    """Facebook-specific analytics collection"""
    
    def __init__(self):
        self.base_url = "https://graph.facebook.com/v18.0"
    
    def sync_account_analytics(self, account: SocialAccount, days_back: int = 7) -> Dict[str, Any]:
        """Sync analytics for a Facebook account"""
        logger.info(f"Syncing Facebook analytics for account: {account.account_name}")
        
        results = {
            'posts_updated': 0,
            'page_insights_updated': False,
            'errors': []
        }
        
        try:
            # First, sync page-level insights
            page_insights = self._get_page_insights(account, days_back)
            if page_insights:
                # Store page insights in account's platform_metrics
                self._update_account_metrics(account, page_insights)
                results['page_insights_updated'] = True
            
            # Then sync post-level analytics
            post_results = self._sync_post_analytics(account, days_back)
            results['posts_updated'] = post_results['posts_updated']
            results['errors'].extend(post_results['errors'])
            
            return results
            
        except Exception as e:
            logger.error(f"Facebook analytics sync failed for {account.account_name}: {str(e)}")
            results['errors'].append(str(e))
            return results
    
    def _is_facebook_page(self, account: SocialAccount) -> bool:
        """Check if the Facebook account is a Page (not a personal User account)"""
        try:
            # Try to get basic page information - this will fail for personal accounts
            url = f"{self.base_url}/{account.account_id}"
            params = {
                'fields': 'id,name,category',  # Page-specific fields
                'access_token': account.access_token
            }
            
            response = requests.get(url, params=params)
            
            if response.status_code == 200:
                data = response.json()
                # If it has a 'category' field, it's a Page
                # Personal profiles don't have a 'category' field
                if 'category' in data:
                    logger.debug(f"Account {account.account_name} is a Facebook Page")
                    return True
                else:
                    logger.info(f"Account {account.account_name} is a personal Facebook account, not a Page")
                    return False
            else:
                logger.warning(f"Could not verify account type for {account.account_name}: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Error checking if account is Facebook Page: {str(e)}")
            return False
    
    def import_facebook_posts(self, account: SocialAccount, limit: int = 25) -> Dict[str, Any]:
        """Import Facebook posts from API into database"""
        results = {
            'posts_imported': 0,
            'posts_updated': 0,
            'errors': []
        }
        
        try:
            # Check if this is a Facebook Page (not personal profile)
            if not self._is_facebook_page(account):
                return {
                    'error': 'Account is not a Facebook Page - cannot import posts',
                    'posts_imported': 0
                }
            
            # Fetch Facebook posts from API
            url = f"{self.base_url}/{account.account_id}/posts"
            params = {
                'fields': 'id,message,story,created_time,permalink_url,type',
                'limit': limit,
                'access_token': account.access_token
            }
            
            response = requests.get(url, params=params)
            
            if response.status_code == 200:
                data = response.json()
                posts_data = data.get('data', [])
                
                logger.info(f"Found {len(posts_data)} Facebook posts for {account.account_name}")
                
                # Get system user for API imports
                from django.contrib.auth import get_user_model
                User = get_user_model()
                system_user = account.created_by
                
                for post_data in posts_data:
                    try:
                        # Check if this post already exists
                        existing_target = SocialPostTarget.objects.filter(
                            account=account,
                            platform_post_id=post_data.get('id')
                        ).first()
                        
                        # Extract content (message or story)
                        content = post_data.get('message') or post_data.get('story') or ''
                        
                        if existing_target:
                            # Update existing
                            post = existing_target.post
                            post.content = content
                            post.save()
                            post_target = existing_target
                            created = False
                        else:
                            # Create new post
                            post = SocialPost.objects.create(
                                created_by=account.created_by,
                                content=content,
                                post_type='image' if post_data.get('type') == 'photo' else 'text',
                                status='published',
                                published_at=post_data.get('created_time')
                            )
                            
                            # Create new post target
                            post_target = SocialPostTarget.objects.create(
                                post=post,
                                account=account,
                                platform_post_id=post_data.get('id'),
                                status='published',
                                published_at=post_data.get('created_time'),
                                platform_url=post_data.get('permalink_url', '')
                            )
                            
                            created = True
                        
                        # Create basic analytics (we'll get engagement data separately)
                        analytics, _ = SocialAnalytics.objects.get_or_create(
                            post_target=post_target,
                            defaults={
                                'impressions': 0,
                                'reach': 0,
                                'likes': 0,  # Will be updated when we fetch post insights
                                'comments': 0,  # Will be updated when we fetch post insights
                                'shares': 0,  # Will be updated when we fetch post insights
                                'video_views': 0,
                                'platform_metrics': post_data
                            }
                        )
                        
                        if created:
                            results['posts_imported'] += 1
                        else:
                            results['posts_updated'] += 1
                            
                    except Exception as e:
                        error_msg = f"Error importing Facebook post {post_data.get('id')}: {str(e)}"
                        logger.error(error_msg)
                        results['errors'].append(error_msg)
                
            else:
                error_msg = f"Failed to fetch Facebook posts: {response.status_code} - {response.text}"
                logger.error(error_msg)
                results['errors'].append(error_msg)
                
        except Exception as e:
            error_msg = f"Error importing Facebook posts: {str(e)}"
            logger.error(error_msg)
            results['errors'].append(error_msg)
            
        return results
    
    def _get_page_insights(self, account: SocialAccount, days_back: int) -> Dict[str, Any]:
        """Get Facebook page-level insights with improved error handling"""
        try:
            # First, verify this is a Page account by checking the account directly
            if not self._is_facebook_page(account):
                logger.warning(f"Account {account.account_name} is not a Facebook Page - skipping insights")
                return {}
            
            since_date = (timezone.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')
            until_date = timezone.now().strftime('%Y-%m-%d')
            
            # Start with basic metrics that are always available
            basic_metrics = ['page_fans', 'page_impressions']
            
            # Try basic metrics first
            insights_data = self._fetch_page_metrics(account, basic_metrics, since_date, until_date)
            
            if insights_data:
                # If basic metrics work, try additional supported metrics
                # Note: Removed deprecated metrics page_reach, page_engaged_users, page_post_engagements
                additional_metrics = ['page_impressions_unique']  # Use supported metrics only
                additional_data = self._fetch_page_metrics(account, additional_metrics, since_date, until_date)
                if additional_data:
                    insights_data['data'].extend(additional_data['data'])
                
                return self._process_page_insights(insights_data)
            else:
                logger.warning(f"No insights data available for Facebook page {account.account_name}")
                return {}
                
        except Exception as e:
            logger.error(f"Error getting Facebook page insights: {str(e)}")
            return {}
    
    def _verify_page_account(self, account: SocialAccount) -> Dict[str, Any]:
        """Verify if account is a Facebook Page and has necessary permissions"""
        try:
            url = f"{self.base_url}/{account.account_id}"
            # Try basic fields first that work for both pages and users
            params = {
                'fields': 'id,name',
                'access_token': account.access_token
            }
            
            response = requests.get(url, params=params)
            
            if response.status_code == 200:
                data = response.json()
                
                # Test if this is a page by trying to access page-specific fields
                is_page = self._test_page_access(account)
                
                return {
                    'is_page': is_page,
                    'name': data.get('name'),
                    'fan_count': 0,  # Will be fetched separately if it's a page
                    'has_page_token': is_page
                }
            else:
                logger.error(f"Facebook account verification failed: {response.status_code} - {response.text}")
                return {'is_page': False}
                
        except Exception as e:
            logger.error(f"Error verifying Facebook account: {str(e)}")
            return {'is_page': False}
    
    def _test_page_access(self, account: SocialAccount) -> bool:
        """Test if account has page-level access by trying to fetch page insights"""
        try:
            url = f"{self.base_url}/{account.account_id}/insights"
            params = {
                'metric': 'page_fans',
                'access_token': account.access_token
            }
            
            response = requests.get(url, params=params)
            
            # If we get 200 or specific error codes that indicate a page but permission issues
            if response.status_code == 200:
                return True
            elif response.status_code == 400:
                error_data = response.json()
                error_code = error_data.get('error', {}).get('code', 0)
                # Code 100 often means insufficient permissions but valid page
                if error_code == 100:
                    return True
            
            return False
            
        except Exception:
            return False
    
    def _fetch_page_metrics(self, account: SocialAccount, metrics: list, since_date: str, until_date: str) -> Dict[str, Any]:
        """Fetch specific metrics with error handling"""
        try:
            url = f"{self.base_url}/{account.account_id}/insights"
            params = {
                'metric': ','.join(metrics),
                'since': since_date,
                'until': until_date,
                'period': 'day',
                'access_token': account.access_token
            }
            
            response = requests.get(url, params=params)
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Facebook metrics API error for {metrics}: {response.status_code} - {response.text}")
                return {}
                
        except Exception as e:
            logger.error(f"Error fetching Facebook metrics {metrics}: {str(e)}")
            return {}
    
    def _process_page_insights(self, insights_data: Dict) -> Dict[str, Any]:
        """Process raw Facebook page insights data"""
        processed = {
            'followers': 0,
            'total_impressions': 0,
            'total_reach': 0,
            'total_engagements': 0,
            'daily_metrics': [],
            'last_updated': timezone.now().isoformat()
        }
        
        try:
            for metric in insights_data.get('data', []):
                metric_name = metric.get('name')
                values = metric.get('values', [])
                
                if metric_name == 'page_fans':
                    # Get most recent follower count
                    if values:
                        processed['followers'] = values[-1].get('value', 0)
                
                elif metric_name in ['page_impressions', 'page_reach', 'page_engaged_users']:
                    # Sum daily values
                    total = sum(item.get('value', 0) for item in values)
                    if metric_name == 'page_impressions':
                        processed['total_impressions'] = total
                    elif metric_name == 'page_reach':
                        processed['total_reach'] = total
                    elif metric_name == 'page_engaged_users':
                        processed['total_engagements'] = total
                
                # Store daily breakdown
                for value_item in values:
                    date_str = value_item.get('end_time', '').split('T')[0]
                    if date_str:
                        daily_metric = {
                            'date': date_str,
                            'metric': metric_name,
                            'value': value_item.get('value', 0)
                        }
                        processed['daily_metrics'].append(daily_metric)
            
            return processed
            
        except Exception as e:
            logger.error(f"Error processing Facebook page insights: {str(e)}")
            return processed
    
    def _sync_post_analytics(self, account: SocialAccount, days_back: int) -> Dict[str, Any]:
        """Sync analytics for Facebook posts"""
        results = {
            'posts_updated': 0,
            'errors': []
        }
        
        try:
            # Get posts published to this account in the last N days
            since_date = timezone.now() - timedelta(days=days_back)
            post_targets = SocialPostTarget.objects.filter(
                account=account,
                post__published_at__gte=since_date,
                platform_post_id__isnull=False  # Only posts that were actually published
            ).select_related('post')
            
            logger.info(f"Found {post_targets.count()} Facebook posts to sync analytics for")
            
            for post_target in post_targets:
                try:
                    analytics_data = self._get_post_insights(account, post_target.platform_post_id)
                    if analytics_data:
                        self._update_post_analytics(post_target, analytics_data)
                        results['posts_updated'] += 1
                        
                except Exception as e:
                    error_msg = f"Failed to sync post {post_target.platform_post_id}: {str(e)}"
                    logger.error(error_msg)
                    results['errors'].append(error_msg)
            
            return results
            
        except Exception as e:
            logger.error(f"Error syncing Facebook post analytics: {str(e)}")
            results['errors'].append(str(e))
            return results
    
    def _get_post_insights(self, account: SocialAccount, platform_post_id: str) -> Dict[str, Any]:
        """Get insights for a specific Facebook post"""
        try:
            # Facebook post insights metrics
            metrics = [
                'post_impressions',  # Total impressions
                'post_reach',  # Unique reach
                'post_engaged_users',  # Engaged users
                'post_clicks',  # Link clicks
                'post_reactions_like_total',  # Likes
                'post_reactions_love_total',  # Love reactions
                'post_reactions_wow_total',  # Wow reactions
                'post_reactions_haha_total',  # Haha reactions
                'post_reactions_sorry_total',  # Sorry reactions
                'post_reactions_anger_total',  # Angry reactions
                'post_comments',  # Comments
                'post_shares',  # Shares
                'post_video_views'  # Video views (if applicable)
            ]
            
            url = f"{self.base_url}/{platform_post_id}/insights"
            params = {
                'metric': ','.join(metrics),
                'access_token': account.access_token
            }
            
            response = requests.get(url, params=params)
            
            if response.status_code == 200:
                data = response.json()
                return self._process_post_insights(data)
            else:
                logger.warning(f"Facebook post insights API error for post {platform_post_id}: {response.status_code}")
                return {}
                
        except Exception as e:
            logger.error(f"Error getting Facebook post insights: {str(e)}")
            return {}
    
    def _process_post_insights(self, insights_data: Dict) -> Dict[str, Any]:
        """Process raw Facebook post insights data"""
        processed = {
            'impressions': 0,
            'reach': 0,
            'clicks': 0,
            'likes': 0,
            'comments': 0,
            'shares': 0,
            'video_views': 0,
            'total_reactions': 0,
            'reaction_breakdown': {},
            'engagement_rate': 0.0
        }
        
        try:
            for metric in insights_data.get('data', []):
                metric_name = metric.get('name')
                values = metric.get('values', [])
                value = values[0].get('value', 0) if values else 0
                
                if metric_name == 'post_impressions':
                    processed['impressions'] = value
                elif metric_name == 'post_reach':
                    processed['reach'] = value
                elif metric_name == 'post_clicks':
                    processed['clicks'] = value
                elif metric_name == 'post_comments':
                    processed['comments'] = value
                elif metric_name == 'post_shares':
                    processed['shares'] = value
                elif metric_name == 'post_video_views':
                    processed['video_views'] = value
                elif metric_name.startswith('post_reactions_'):
                    reaction_type = metric_name.replace('post_reactions_', '').replace('_total', '')
                    processed['reaction_breakdown'][reaction_type] = value
                    if reaction_type == 'like':
                        processed['likes'] = value
            
            # Calculate total reactions
            processed['total_reactions'] = sum(processed['reaction_breakdown'].values())
            
            # Calculate engagement rate
            if processed['reach'] > 0:
                total_engagement = (processed['total_reactions'] + 
                                  processed['comments'] + 
                                  processed['shares'])
                processed['engagement_rate'] = (total_engagement / processed['reach']) * 100
            
            return processed
            
        except Exception as e:
            logger.error(f"Error processing Facebook post insights: {str(e)}")
            return processed
    
    def _update_post_analytics(self, post_target: SocialPostTarget, analytics_data: Dict):
        """Update SocialAnalytics record with Facebook data"""
        try:
            analytics, created = SocialAnalytics.objects.get_or_create(
                post_target=post_target,
                defaults={
                    'impressions': analytics_data.get('impressions', 0),
                    'reach': analytics_data.get('reach', 0),
                    'clicks': analytics_data.get('clicks', 0),
                    'likes': analytics_data.get('likes', 0),
                    'comments': analytics_data.get('comments', 0),
                    'shares': analytics_data.get('shares', 0),
                    'video_views': analytics_data.get('video_views', 0),
                    'platform_metrics': analytics_data
                }
            )
            
            if not created:
                # Update existing record
                analytics.impressions = analytics_data.get('impressions', 0)
                analytics.reach = analytics_data.get('reach', 0)
                analytics.clicks = analytics_data.get('clicks', 0)
                analytics.likes = analytics_data.get('likes', 0)
                analytics.comments = analytics_data.get('comments', 0)
                analytics.shares = analytics_data.get('shares', 0)
                analytics.video_views = analytics_data.get('video_views', 0)
                analytics.platform_metrics = analytics_data
                analytics.save()
            
            logger.debug(f"Updated analytics for post {post_target.platform_post_id}")
            
        except Exception as e:
            logger.error(f"Error updating post analytics: {str(e)}")
            raise
    
    def _update_account_metrics(self, account: SocialAccount, page_insights: Dict):
        """Update account with page-level metrics"""
        try:
            # Store page insights in account's permissions field (repurpose as metrics)
            # Or create a new field for this - for now using a JSON field approach
            account.permissions = page_insights
            account.last_sync = timezone.now()
            account.save()
            
            logger.debug(f"Updated page metrics for account {account.account_name}")
            
        except Exception as e:
            logger.error(f"Error updating account metrics: {str(e)}")
            raise
    
    def get_account_insights(self, account: SocialAccount, date_range: Dict[str, str]) -> Dict[str, Any]:
        """Get comprehensive Facebook account insights"""
        try:
            # Get page insights for the date range
            days_back = (datetime.now() - datetime.strptime(date_range['start_date'], '%Y-%m-%d')).days
            page_insights = self._get_page_insights(account, days_back)
            
            # Get post performance summary
            post_analytics = self._get_post_performance_summary(account, date_range)
            
            return {
                'account_name': account.account_name,
                'platform': 'Facebook',
                'page_insights': page_insights,
                'post_performance': post_analytics,
                'date_range': date_range
            }
            
        except Exception as e:
            logger.error(f"Error getting Facebook account insights: {str(e)}")
            return {'error': str(e)}
    
    def _get_post_performance_summary(self, account: SocialAccount, date_range: Dict[str, str]) -> Dict[str, Any]:
        """Get summary of post performance for date range"""
        try:
            start_date = datetime.strptime(date_range['start_date'], '%Y-%m-%d').date()
            end_date = datetime.strptime(date_range['end_date'], '%Y-%m-%d').date()
            
            # Get analytics for posts in date range
            analytics = SocialAnalytics.objects.filter(
                post_target__account=account,
                post_target__post__published_at__date__gte=start_date,
                post_target__post__published_at__date__lte=end_date
            )
            
            if not analytics.exists():
                return {'message': 'No post data available for this date range'}
            
            # Calculate aggregated metrics
            total_posts = analytics.count()
            total_impressions = sum(a.impressions for a in analytics)
            total_reach = sum(a.reach for a in analytics)
            total_engagement = sum(a.likes + a.comments + a.shares for a in analytics)
            
            avg_engagement_rate = sum(
                a.platform_metrics.get('engagement_rate', 0) for a in analytics
            ) / total_posts if total_posts > 0 else 0
            
            return {
                'total_posts': total_posts,
                'total_impressions': total_impressions,
                'total_reach': total_reach,
                'total_engagement': total_engagement,
                'avg_engagement_rate': round(avg_engagement_rate, 2),
                'top_performing_posts': self._get_top_posts(analytics, limit=5)
            }
            
        except Exception as e:
            logger.error(f"Error getting post performance summary: {str(e)}")
            return {'error': str(e)}
    
    def _get_top_posts(self, analytics_queryset, limit: int = 5) -> List[Dict]:
        """Get top performing posts by engagement"""
        try:
            top_posts = []
            
            for analytics in analytics_queryset.order_by('-likes', '-comments', '-shares')[:limit]:
                post = analytics.post_target.post
                top_posts.append({
                    'post_id': str(post.id),
                    'content': post.content[:100] + '...' if len(post.content) > 100 else post.content,
                    'published_at': post.published_at.isoformat() if post.published_at else None,
                    'likes': analytics.likes,
                    'comments': analytics.comments,
                    'shares': analytics.shares,
                    'impressions': analytics.impressions,
                    'engagement_rate': analytics.platform_metrics.get('engagement_rate', 0)
                })
            
            return top_posts
            
        except Exception as e:
            logger.error(f"Error getting top posts: {str(e)}")
            return []
    
    def collect_analytics(self, account: SocialAccount, days_back: int = 7) -> Dict[str, Any]:
        """Collect comprehensive Facebook analytics data"""
        logger.info(f"Collecting Facebook analytics for account: {account.account_name}")
        
        try:
            # Check if this is a Facebook Page (not a personal profile)
            is_page = self._is_facebook_page(account)
            
            if not is_page:
                logger.warning(f"Account {account.account_name} is not a Facebook Page")
                return {
                    'account_name': account.account_name,
                    'platform': 'Facebook',
                    'verification': {'is_page': False, 'account_type': 'personal'},
                    'has_insights_access': False,
                    'message': 'This Facebook account is not a Page. Only Facebook Pages can provide analytics insights.',
                    'summary': {'total_posts': 0, 'total_impressions': 0, 'total_reach': 0, 'total_engagement': 0, 'avg_engagement_rate': 0}
                }
            
            # Get page insights
            page_insights = self._get_page_insights(account, days_back)
            
            # Get post performance summary
            date_range = {
                'start_date': (timezone.now() - timedelta(days=days_back)).strftime('%Y-%m-%d'),
                'end_date': timezone.now().strftime('%Y-%m-%d')
            }
            post_performance = self._get_post_performance_summary(account, date_range)
            
            return {
                'account_name': account.account_name,
                'platform': 'Facebook',
                'verification': {'is_page': True, 'account_type': 'page'},
                'has_insights_access': True,
                'page_insights': page_insights,
                'post_performance': post_performance,
                'date_range': date_range,
                'summary': {
                    'total_posts': post_performance.get('total_posts', 0),
                    'total_impressions': page_insights.get('total_impressions', 0),
                    'total_reach': page_insights.get('total_reach', 0),
                    'total_engagement': page_insights.get('total_engagements', 0),
                    'avg_engagement_rate': post_performance.get('avg_engagement_rate', 0),
                    'followers': page_insights.get('followers', 0)
                }
            }
            
        except Exception as e:
            logger.error(f"Error collecting Facebook analytics for {account.account_name}: {str(e)}")
            return {
                'account_name': account.account_name,
                'platform': 'Facebook',
                'error': str(e),
                'has_insights_access': False
            }
    
    def _get_post_performance_summary(self, account: SocialAccount, date_range: Dict[str, str]) -> Dict[str, Any]:
        """Get summary of post performance for date range"""
        try:
            start_date = datetime.strptime(date_range['start_date'], '%Y-%m-%d').date()
            end_date = datetime.strptime(date_range['end_date'], '%Y-%m-%d').date()
            
            # Get analytics for posts in date range
            analytics = SocialAnalytics.objects.filter(
                post_target__account=account,
                post_target__post__published_at__date__gte=start_date,
                post_target__post__published_at__date__lte=end_date
            )
            
            if not analytics.exists():
                return {'message': 'No post data available for this date range'}
            
            # Calculate aggregated metrics
            total_posts = analytics.count()
            total_impressions = sum(a.impressions for a in analytics)
            total_reach = sum(a.reach for a in analytics)
            total_engagement = sum(a.likes + a.comments + a.shares for a in analytics)
            
            avg_engagement_rate = sum(
                a.platform_metrics.get('engagement_rate', 0) for a in analytics
            ) / total_posts if total_posts > 0 else 0
            
            return {
                'total_posts': total_posts,
                'total_impressions': total_impressions,
                'total_reach': total_reach,
                'total_engagement': total_engagement,
                'avg_engagement_rate': round(avg_engagement_rate, 2),
                'top_performing_posts': self._get_top_posts(analytics, limit=5)
            }
            
        except Exception as e:
            logger.error(f"Error getting Facebook post performance summary: {str(e)}")
            return {'error': str(e)}


class InstagramAnalyticsService:
    """Instagram-specific analytics collection"""
    
    def __init__(self):
        self.base_url = "https://graph.facebook.com/v18.0"
    
    def sync_account_analytics(self, account: SocialAccount, days_back: int = 7) -> Dict[str, Any]:
        """Sync analytics for an Instagram Business account"""
        logger.info(f"Syncing Instagram analytics for account: {account.account_name}")
        
        results = {
            'posts_updated': 0,
            'account_insights_updated': False,
            'errors': []
        }
        
        try:
            # First, sync account-level insights
            account_insights = self._get_account_insights(account, days_back)
            if account_insights:
                self._update_account_metrics(account, account_insights)
                results['account_insights_updated'] = True
            
            # Then sync media-level analytics
            media_results = self._sync_media_analytics(account, days_back)
            results['posts_updated'] = media_results['posts_updated']
            results['errors'].extend(media_results['errors'])
            
            return results
            
        except Exception as e:
            logger.error(f"Instagram analytics sync failed for {account.account_name}: {str(e)}")
            results['errors'].append(str(e))
            return results
    
    def _get_account_insights(self, account: SocialAccount, days_back: int) -> Dict[str, Any]:
        """Get Instagram account-level insights with business account verification"""
        try:
            # First, verify this is a Business account
            account_info = self._verify_business_account(account)
            if not account_info.get('is_business'):
                logger.warning(f"Account {account.account_name} is not an Instagram Business account - skipping insights")
                return {}
            
            since_date = (timezone.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')
            until_date = timezone.now().strftime('%Y-%m-%d')
            
            # Start with basic metrics that are actually supported by Instagram API
            # Fixed: Use only supported metrics, but handle follower_count separately
            basic_metrics = ['reach', 'website_clicks']  # Remove profile_views and follower_count for now
            
            insights_data = self._fetch_instagram_metrics(account, basic_metrics, since_date, until_date)
            
            if insights_data:
                return self._process_account_insights(insights_data)
            else:
                # Try fallback approach with follower count only
                follower_data = self._get_follower_count(account)
                if follower_data:
                    return {'follower_count': follower_data.get('followers_count', 0)}
                return {}
                
        except Exception as e:
            logger.error(f"Error getting Instagram account insights: {str(e)}")
            return {}
    
    def _verify_business_account(self, account: SocialAccount) -> Dict[str, Any]:
        """Verify if account is an Instagram Business account"""
        try:
            url = f"{self.base_url}/{account.account_id}"
            # Try basic fields first that are available for all Instagram accounts
            params = {
                'fields': 'id,username',
                'access_token': account.access_token
            }
            
            response = requests.get(url, params=params)
            
            if response.status_code == 200:
                data = response.json()
                
                # Test if we can access insights endpoint - this is only available for Business accounts
                insights_test = self._test_insights_access(account)
                
                return {
                    'is_business': insights_test,
                    'username': data.get('username'),
                    'has_insights_access': insights_test
                }
            else:
                logger.error(f"Instagram account verification failed: {response.status_code} - {response.text}")
                return {'is_business': False}
                
        except Exception as e:
            logger.error(f"Error verifying Instagram account: {str(e)}")
            return {'is_business': False}
    
    def _test_insights_access(self, account: SocialAccount) -> bool:
        """Test if account has insights access (Business accounts only)"""
        try:
            url = f"{self.base_url}/{account.account_id}/insights"
            params = {
                'metric': 'impressions',
                'period': 'day',
                'since': (timezone.now() - timedelta(days=1)).strftime('%Y-%m-%d'),
                'until': timezone.now().strftime('%Y-%m-%d'),
                'access_token': account.access_token
            }
            
            response = requests.get(url, params=params)
            
            # If we get 200 or specific error codes that indicate permission issues
            # rather than account type issues, consider it a business account
            if response.status_code == 200:
                return True
            elif response.status_code == 400:
                error_data = response.json()
                error_code = error_data.get('error', {}).get('code', 0)
                # Code 100 often means insufficient permissions but valid business account
                if error_code == 100:
                    return True
            
            return False
            
        except Exception:
            return False
    
    def _get_follower_count(self, account: SocialAccount) -> Dict[str, Any]:
        """Get basic follower count as fallback"""
        try:
            url = f"{self.base_url}/{account.account_id}"
            params = {
                'fields': 'followers_count',
                'access_token': account.access_token
            }
            
            response = requests.get(url, params=params)
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Instagram follower count API error: {response.status_code} - {response.text}")
                return {}
                
        except Exception as e:
            logger.error(f"Error getting Instagram follower count: {str(e)}")
            return {}
    
    def _fetch_instagram_metrics(self, account: SocialAccount, metrics: list, since_date: str, until_date: str) -> Dict[str, Any]:
        """Fetch specific Instagram metrics with error handling"""
        try:
            url = f"{self.base_url}/{account.account_id}/insights"
            params = {
                'metric': ','.join(metrics),
                'period': 'day',
                'since': since_date,
                'until': until_date,
                'access_token': account.access_token
            }
            
            # Add metric_type parameter for specific metrics that require it
            # These metrics require metric_type=total_value
            total_value_metrics = ['profile_views', 'website_clicks']
            if any(metric in total_value_metrics for metric in metrics):
                params['metric_type'] = 'total_value'
            
            response = requests.get(url, params=params)
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Instagram metrics API error for {metrics}: {response.status_code} - {response.text}")
                return {}
                
        except Exception as e:
            logger.error(f"Error fetching Instagram metrics {metrics}: {str(e)}")
            return {}
    
    def _process_account_insights(self, insights_data: Dict) -> Dict[str, Any]:
        """Process raw Instagram account insights data"""
        processed = {
            'follower_count': 0,
            'total_impressions': 0,
            'total_reach': 0,
            'total_profile_views': 0,
            'total_website_clicks': 0,
            'daily_metrics': [],
            'last_updated': timezone.now().isoformat()
        }
        
        try:
            for metric in insights_data.get('data', []):
                metric_name = metric.get('name')
                values = metric.get('values', [])
                
                if metric_name == 'follower_count':
                    # Get most recent follower count
                    if values:
                        processed['follower_count'] = values[-1].get('value', 0)
                
                elif metric_name in ['impressions', 'reach', 'profile_views', 'website_clicks']:
                    # Sum daily values
                    total = sum(item.get('value', 0) for item in values)
                    processed[f'total_{metric_name}'] = total
                
                # Store daily breakdown
                for value_item in values:
                    date_str = value_item.get('end_time', '').split('T')[0]
                    if date_str:
                        daily_metric = {
                            'date': date_str,
                            'metric': metric_name,
                            'value': value_item.get('value', 0)
                        }
                        processed['daily_metrics'].append(daily_metric)
            
            return processed
            
        except Exception as e:
            logger.error(f"Error processing Instagram account insights: {str(e)}")
            return processed
    
    def _sync_media_analytics(self, account: SocialAccount, days_back: int) -> Dict[str, Any]:
        """Sync analytics for Instagram media/posts"""
        results = {
            'posts_updated': 0,
            'errors': []
        }
        
        try:
            # Get posts published to this account in the last N days
            since_date = timezone.now() - timedelta(days=days_back)
            post_targets = SocialPostTarget.objects.filter(
                account=account,
                post__published_at__gte=since_date,
                platform_post_id__isnull=False  # Only posts that were actually published
            ).select_related('post')
            
            logger.info(f"Found {post_targets.count()} Instagram posts to sync analytics for")
            
            for post_target in post_targets:
                try:
                    analytics_data = self._get_media_insights(account, post_target.platform_post_id)
                    if analytics_data:
                        self._update_post_analytics(post_target, analytics_data)
                        results['posts_updated'] += 1
                        
                except Exception as e:
                    error_msg = f"Failed to sync media {post_target.platform_post_id}: {str(e)}"
                    logger.error(error_msg)
                    results['errors'].append(error_msg)
            
            return results
            
        except Exception as e:
            logger.error(f"Error syncing Instagram media analytics: {str(e)}")
            results['errors'].append(str(e))
            return results
    
    def import_instagram_posts(self, account: SocialAccount, limit: int = 25) -> Dict[str, Any]:
        """Import Instagram posts/media from API into database"""
        results = {
            'posts_imported': 0,
            'posts_updated': 0,
            'errors': []
        }
        
        try:
            # First verify this is a business account
            if not self._verify_business_account(account).get('is_business'):
                return {
                    'error': 'Account is not a business account - cannot import media',
                    'posts_imported': 0
                }
            
            # Fetch Instagram media from API
            url = f"{self.base_url}/{account.account_id}/media"
            params = {
                'fields': 'id,media_type,media_url,permalink,thumbnail_url,timestamp,caption,like_count,comments_count',
                'limit': limit,
                'access_token': account.access_token
            }
            
            response = requests.get(url, params=params)
            
            if response.status_code == 200:
                data = response.json()
                media_items = data.get('data', [])
                
                logger.info(f"Found {len(media_items)} Instagram media items for {account.account_name}")
                
                for media in media_items:
                    try:
                        # Get a system user for API imports
                        from django.contrib.auth import get_user_model
                        User = get_user_model()
                        system_user = account.created_by
                        
                        # Check if this media already exists as a post target
                        existing_target = SocialPostTarget.objects.filter(
                            account=account,
                            platform_post_id=media.get('id')
                        ).first()
                        
                        if existing_target:
                            # Update existing post and target
                            post = existing_target.post
                            post.content = media.get('caption', '')
                            post.post_type = 'image' if media.get('media_type') == 'IMAGE' else 'video'
                            post.save()
                            
                            post_target = existing_target
                            created = False
                            target_created = False
                        else:
                            # Create new post
                            post = SocialPost.objects.create(
                                created_by=account.created_by,
                                content=media.get('caption', ''),
                                post_type='image' if media.get('media_type') == 'IMAGE' else 'video',
                                status='published',
                                published_at=media.get('timestamp')
                            )
                            
                            # Create new post target
                            post_target = SocialPostTarget.objects.create(
                                post=post,
                                account=account,
                                platform_post_id=media.get('id'),
                                status='published',
                                published_at=media.get('timestamp'),
                                platform_url=media.get('permalink', '')
                            )
                            
                            created = True
                            target_created = True
                        
                        # Create basic analytics record with available data
                        # We'll get detailed insights separately
                        analytics, analytics_created = SocialAnalytics.objects.get_or_create(
                            post_target=post_target,
                            defaults={
                                'impressions': 0,  # Will be updated when we fetch insights
                                'reach': 0,  # Will be updated when we fetch insights
                                'likes': media.get('like_count', 0),
                                'comments': media.get('comments_count', 0),
                                'shares': 0,
                                'saves': 0,
                                'video_views': 0,
                                'platform_metrics': media  # Store the full media data
                            }
                        )
                        
                        if created:
                            results['posts_imported'] += 1
                        else:
                            results['posts_updated'] += 1
                            
                    except Exception as e:
                        error_msg = f"Error importing media {media.get('id')}: {str(e)}"
                        logger.error(error_msg)
                        results['errors'].append(error_msg)
                
                logger.info(f"Instagram import complete: {results['posts_imported']} imported, {results['posts_updated']} updated")
                
            else:
                error_msg = f"Failed to fetch Instagram media: {response.status_code} - {response.text}"
                logger.error(error_msg)
                results['errors'].append(error_msg)
                
        except Exception as e:
            error_msg = f"Error importing Instagram posts: {str(e)}"
            logger.error(error_msg)
            results['errors'].append(error_msg)
            
        return results
    
    def _get_media_insights(self, account: SocialAccount, media_id: str) -> Dict[str, Any]:
        """Get insights for a specific Instagram media"""
        try:
            # Instagram media insights metrics
            metrics = [
                'impressions',  # Total impressions
                'reach',  # Unique reach
                'engagement',  # Total engagement
                'likes',  # Likes
                'comments',  # Comments
                'saves',  # Saves
                'video_views'  # Video views (if applicable)
            ]
            
            url = f"{self.base_url}/{media_id}/insights"
            params = {
                'metric': ','.join(metrics),
                'access_token': account.access_token
            }
            
            response = requests.get(url, params=params)
            
            if response.status_code == 200:
                data = response.json()
                return self._process_media_insights(data)
            else:
                logger.warning(f"Instagram media insights API error for media {media_id}: {response.status_code}")
                return {}
                
        except Exception as e:
            logger.error(f"Error getting Instagram media insights: {str(e)}")
            return {}
    
    def _process_media_insights(self, insights_data: Dict) -> Dict[str, Any]:
        """Process raw Instagram media insights data"""
        processed = {
            'impressions': 0,
            'reach': 0,
            'likes': 0,
            'comments': 0,
            'saves': 0,
            'video_views': 0,
            'total_engagement': 0,
            'engagement_rate': 0.0
        }
        
        try:
            for metric in insights_data.get('data', []):
                metric_name = metric.get('name')
                values = metric.get('values', [])
                value = values[0].get('value', 0) if values else 0
                
                if metric_name in processed:
                    processed[metric_name] = value
                elif metric_name == 'engagement':
                    processed['total_engagement'] = value
            
            # Calculate engagement rate
            if processed['reach'] > 0:
                processed['engagement_rate'] = (processed['total_engagement'] / processed['reach']) * 100
            
            return processed
            
        except Exception as e:
            logger.error(f"Error processing Instagram media insights: {str(e)}")
            return processed
    
    def _update_post_analytics(self, post_target: SocialPostTarget, analytics_data: Dict):
        """Update SocialAnalytics record with Instagram data"""
        try:
            analytics, created = SocialAnalytics.objects.get_or_create(
                post_target=post_target,
                defaults={
                    'impressions': analytics_data.get('impressions', 0),
                    'reach': analytics_data.get('reach', 0),
                    'likes': analytics_data.get('likes', 0),
                    'comments': analytics_data.get('comments', 0),
                    'saves': analytics_data.get('saves', 0),
                    'video_views': analytics_data.get('video_views', 0),
                    'platform_metrics': analytics_data
                }
            )
            
            if not created:
                # Update existing record
                analytics.impressions = analytics_data.get('impressions', 0)
                analytics.reach = analytics_data.get('reach', 0)
                analytics.likes = analytics_data.get('likes', 0)
                analytics.comments = analytics_data.get('comments', 0)
                analytics.saves = analytics_data.get('saves', 0)
                analytics.video_views = analytics_data.get('video_views', 0)
                analytics.platform_metrics = analytics_data
                analytics.save()
            
            logger.debug(f"Updated Instagram analytics for media {post_target.platform_post_id}")
            
        except Exception as e:
            logger.error(f"Error updating Instagram post analytics: {str(e)}")
            raise
    
    def _update_account_metrics(self, account: SocialAccount, account_insights: Dict):
        """Update account with Instagram-level metrics"""
        try:
            # Store account insights in account's permissions field (repurpose as metrics)
            account.permissions = account_insights
            account.last_sync = timezone.now()
            account.save()
            
            logger.debug(f"Updated Instagram account metrics for {account.account_name}")
            
        except Exception as e:
            logger.error(f"Error updating Instagram account metrics: {str(e)}")
            raise
    
    def get_account_insights(self, account: SocialAccount, date_range: Dict[str, str]) -> Dict[str, Any]:
        """Get comprehensive Instagram account insights"""
        try:
            # Get account insights for the date range
            days_back = (datetime.now() - datetime.strptime(date_range['start_date'], '%Y-%m-%d')).days
            account_insights = self._get_account_insights(account, days_back)
            
            # Get media performance summary
            media_analytics = self._get_media_performance_summary(account, date_range)
            
            return {
                'account_name': account.account_name,
                'platform': 'Instagram',
                'account_insights': account_insights,
                'media_performance': media_analytics,
                'date_range': date_range
            }
            
        except Exception as e:
            logger.error(f"Error getting Instagram account insights: {str(e)}")
            return {'error': str(e)}
    
    def _get_media_performance_summary(self, account: SocialAccount, date_range: Dict[str, str]) -> Dict[str, Any]:
        """Get summary of media performance for date range"""
        try:
            start_date = datetime.strptime(date_range['start_date'], '%Y-%m-%d').date()
            end_date = datetime.strptime(date_range['end_date'], '%Y-%m-%d').date()
            
            # Get analytics for media in date range
            analytics = SocialAnalytics.objects.filter(
                post_target__account=account,
                post_target__post__published_at__date__gte=start_date,
                post_target__post__published_at__date__lte=end_date
            )
            
            if not analytics.exists():
                return {'message': 'No media data available for this date range'}
            
            # Calculate aggregated metrics
            total_posts = analytics.count()
            total_impressions = sum(a.impressions for a in analytics)
            total_reach = sum(a.reach for a in analytics)
            total_engagement = sum(a.likes + a.comments + a.saves for a in analytics)
            
            avg_engagement_rate = sum(
                a.platform_metrics.get('engagement_rate', 0) for a in analytics
            ) / total_posts if total_posts > 0 else 0
            
            return {
                'total_posts': total_posts,
                'total_impressions': total_impressions,
                'total_reach': total_reach,
                'total_engagement': total_engagement,
                'avg_engagement_rate': round(avg_engagement_rate, 2),
                'top_performing_posts': self._get_top_media(analytics, limit=5)
            }
            
        except Exception as e:
            logger.error(f"Error getting Instagram media performance summary: {str(e)}")
            return {'error': str(e)}
    
    def _get_top_media(self, analytics_queryset, limit: int = 5) -> List[Dict]:
        """Get top performing media by engagement"""
        try:
            top_media = []
            
            for analytics in analytics_queryset.order_by('-likes', '-comments', '-saves')[:limit]:
                post = analytics.post_target.post
                top_media.append({
                    'post_id': str(post.id),
                    'content': post.content[:100] + '...' if len(post.content) > 100 else post.content,
                    'published_at': post.published_at.isoformat() if post.published_at else None,
                    'likes': analytics.likes,
                    'comments': analytics.comments,
                    'saves': analytics.saves,
                    'impressions': analytics.impressions,
                    'engagement_rate': analytics.platform_metrics.get('engagement_rate', 0)
                })
            
            return top_media
            
        except Exception as e:
            logger.error(f"Error getting top Instagram media: {str(e)}")
            return []
    
    def collect_analytics(self, account: SocialAccount, days_back: int = 7) -> Dict[str, Any]:
        """Collect comprehensive Instagram analytics data"""
        logger.info(f"Collecting Instagram analytics for account: {account.account_name}")
        
        try:
            # Get account verification info
            verification = self._verify_business_account(account)
            
            if not verification.get('is_business'):
                logger.warning(f"Account {account.account_name} doesn't have business insights access")
                return {
                    'account_name': account.account_name,
                    'platform': 'Instagram',
                    'verification': verification,
                    'has_insights_access': False,
                    'message': 'This Instagram account does not have business insights access. Convert to Business account to enable analytics.'
                }
            
            # Get account insights
            account_insights = self._get_account_insights(account, days_back)
            
            # Get media performance summary
            date_range = {
                'start_date': (timezone.now() - timedelta(days=days_back)).strftime('%Y-%m-%d'),
                'end_date': timezone.now().strftime('%Y-%m-%d')
            }
            media_performance = self._get_media_performance_summary(account, date_range)
            
            return {
                'account_name': account.account_name,
                'platform': 'Instagram',
                'verification': verification,
                'has_insights_access': True,
                'account_insights': account_insights,
                'media_performance': media_performance,
                'date_range': date_range,
                'summary': {
                    'total_posts': media_performance.get('total_posts', 0),
                    'total_impressions': media_performance.get('total_impressions', 0),
                    'total_reach': media_performance.get('total_reach', 0),
                    'total_engagement': media_performance.get('total_engagement', 0),
                    'avg_engagement_rate': media_performance.get('avg_engagement_rate', 0)
                }
            }
            
        except Exception as e:
            logger.error(f"Error collecting Instagram analytics for {account.account_name}: {str(e)}")
            return {
                'account_name': account.account_name,
                'platform': 'Instagram',
                'error': str(e),
                'has_insights_access': False
            }


class LinkedInAnalyticsService:
    """LinkedIn Analytics API service for collecting social media analytics"""
    
    def __init__(self):
        self.base_url = "https://api.linkedin.com/v2"
        # LinkedIn analytics API headers
        self.api_headers = {
            'LinkedIn-Version': '202210',
            'X-Restli-Protocol-Version': '2.0.0',
            'Content-Type': 'application/json'
        }
    
    def sync_account_analytics(self, account: SocialAccount, days_back: int = 7) -> Dict[str, Any]:
        """Sync LinkedIn analytics for an account"""
        results = {
            'account_name': account.account_name,
            'platform': 'LinkedIn',
            'posts_imported': 0,
            'posts_updated': 0,
            'errors': []
        }
        
        try:
            logger.info(f"Starting LinkedIn analytics sync for account: {account.account_name}")
            
            # Import posts from LinkedIn first
            import_result = self._import_linkedin_posts(account, days_back)
            results.update(import_result)
            
            # Get account insights
            account_insights = self._get_account_insights(account, days_back)
            if account_insights:
                self._update_account_metrics(account, account_insights)
            
            # Always update individual post analytics for existing posts, even if API calls failed
            # This ensures existing posts have analytics records
            self._update_posts_analytics(account, days_back)
            
            logger.info(f"LinkedIn sync complete: {results['posts_imported']} imported, {results['posts_updated']} updated")
            
        except Exception as e:
            error_msg = f"Error syncing LinkedIn analytics: {str(e)}"
            logger.error(error_msg)
            results['errors'].append(error_msg)
        
        return results
    
    def _import_linkedin_posts(self, account: SocialAccount, days_back: int) -> Dict[str, Any]:
        """Import LinkedIn posts for the account"""
        from django.utils import timezone as django_timezone
        from datetime import timedelta
        
        results = {
            'posts_imported': 0,
            'posts_updated': 0,
            'errors': []
        }
        
        try:
            # Get LinkedIn posts/shares
            since_date = (django_timezone.now() - timedelta(days=days_back)).isoformat()
            
            # LinkedIn Share API endpoint for user posts
            url = f"{self.base_url}/shares"
            headers = {
                **self.api_headers,
                'Authorization': f'Bearer {account.access_token}'
            }
            
            params = {
                'q': 'owners',
                'owners': f'urn:li:person:{account.account_id}',
                'sortBy': 'CREATED',
                'start': 0,
                'count': 50  # LinkedIn API limit
            }
            
            response = requests.get(url, headers=headers, params=params)
            
            if response.status_code == 200:
                data = response.json()
                shares = data.get('elements', [])
                
                for share in shares:
                    try:
                        share_id = share.get('id')
                        share_urn = f"urn:li:share:{share_id}"
                        
                        # Check if this post already exists
                        existing_target = SocialPostTarget.objects.filter(
                            account=account,
                            platform_post_id=share_id
                        ).select_related('post').first()
                        
                        if existing_target:
                            # Update existing post
                            post = existing_target.post
                            post.content = self._extract_share_text(share)
                            post.save()
                            
                            post_target = existing_target
                            created = False
                            target_created = False
                        else:
                            # Create new post
                            post = SocialPost.objects.create(
                                created_by=account.created_by,
                                content=self._extract_share_text(share),
                                post_type='text',  # LinkedIn shares are typically text-based
                                status='published',
                                published_at=self._parse_linkedin_date(share.get('created', {}))
                            )
                            
                            # Create new post target
                            post_target = SocialPostTarget.objects.create(
                                post=post,
                                account=account,
                                platform_post_id=share_id,
                                status='published',
                                published_at=self._parse_linkedin_date(share.get('created', {})),
                                platform_url=f"https://www.linkedin.com/feed/update/{share_urn}"
                            )
                            
                            created = True
                            target_created = True
                        
                        # Create analytics record with basic data
                        analytics, analytics_created = SocialAnalytics.objects.get_or_create(
                            post_target=post_target,
                            defaults={
                                'impressions': 0,  # Will be updated via insights API
                                'reach': 0,
                                'likes': 0,
                                'comments': 0,
                                'shares': 0,
                                'saves': 0,
                                'video_views': 0,
                                'platform_metrics': share  # Store the full share data
                            }
                        )
                        
                        if created:
                            results['posts_imported'] += 1
                        else:
                            results['posts_updated'] += 1
                            
                    except Exception as e:
                        error_msg = f"Error importing LinkedIn share {share.get('id')}: {str(e)}"
                        logger.error(error_msg)
                        results['errors'].append(error_msg)
                
                logger.info(f"LinkedIn import complete: {results['posts_imported']} imported, {results['posts_updated']} updated")
                
            else:
                error_msg = f"Failed to fetch LinkedIn shares: {response.status_code} - {response.text}"
                logger.error(error_msg)
                results['errors'].append(error_msg)
                
                # Check if token is revoked and update account status
                if response.status_code == 401 and 'REVOKED_ACCESS_TOKEN' in response.text:
                    from django.utils import timezone as django_timezone
                    from datetime import timedelta
                    # Set token as expired so UI shows reconnect option
                    account.token_expires_at = django_timezone.now() - timedelta(days=1)
                    account.save()
                    logger.info(f"LinkedIn token revoked for {account.account_name} - updated expiration date")
                
        except Exception as e:
            error_msg = f"Error importing LinkedIn posts: {str(e)}"
            logger.error(error_msg)
            results['errors'].append(error_msg)
            
        return results
    
    def _extract_share_text(self, share: Dict) -> str:
        """Extract text content from LinkedIn share object"""
        try:
            # LinkedIn share text can be in different locations
            text = share.get('text', {}).get('text', '')
            if not text:
                # Try alternative text location
                text = share.get('commentary', '')
            return text[:2000]  # Limit content length
        except Exception:
            return 'LinkedIn post content'
    
    def _parse_linkedin_date(self, created_obj: Dict) -> Optional[datetime]:
        """Parse LinkedIn created timestamp"""
        try:
            from django.utils import timezone as django_timezone
            import pytz
            timestamp = created_obj.get('time', 0)
            if timestamp:
                return datetime.fromtimestamp(timestamp / 1000, tz=pytz.UTC)
            return django_timezone.now()
        except Exception:
            from django.utils import timezone as django_timezone
            return django_timezone.now()
    
    def _get_account_insights(self, account: SocialAccount, days_back: int) -> Dict[str, Any]:
        """Get LinkedIn account-level insights"""
        from django.utils import timezone as django_timezone
        
        try:
            # LinkedIn doesn't provide comprehensive account insights like Facebook/Instagram
            # We'll focus on profile metrics and engagement
            
            # Get profile information
            profile_url = f"{self.base_url}/people/(id:{account.account_id})"
            headers = {
                **self.api_headers,
                'Authorization': f'Bearer {account.access_token}'
            }
            
            params = {
                'projection': '(id,firstName,lastName,headline,numConnections,numConnectionsDisplay)'
            }
            
            response = requests.get(profile_url, headers=headers, params=params)
            
            if response.status_code == 200:
                profile_data = response.json()
                
                return {
                    'profile_id': profile_data.get('id'),
                    'name': f"{profile_data.get('firstName', {}).get('localized', {}).get('en_US', '')} {profile_data.get('lastName', {}).get('localized', {}).get('en_US', '')}",
                    'headline': profile_data.get('headline', {}).get('localized', {}).get('en_US', ''),
                    'connections': profile_data.get('numConnections', 0),
                    'connections_display': profile_data.get('numConnectionsDisplay', ''),
                    'data_collected_at': django_timezone.now().isoformat()
                }
            else:
                logger.warning(f"LinkedIn profile API error: {response.status_code}")
                
                # Check if token is revoked and update account status
                if response.status_code == 401:
                    from django.utils import timezone as django_timezone
                    from datetime import timedelta
                    # Set token as expired so UI shows reconnect option
                    account.token_expires_at = django_timezone.now() - timedelta(days=1)
                    account.save()
                    logger.info(f"LinkedIn token invalid for {account.account_name} - updated expiration date")
                
                return {}
                
        except Exception as e:
            logger.error(f"Error getting LinkedIn account insights: {str(e)}")
            return {}
    
    def _update_posts_analytics(self, account: SocialAccount, days_back: int):
        """Update LinkedIn post analytics with available metrics"""
        from django.utils import timezone as django_timezone
        from datetime import timedelta
        
        try:
            # Get recent posts for this account
            since_date = django_timezone.now() - timedelta(days=days_back)
            post_targets = SocialPostTarget.objects.filter(
                account=account,
                post__published_at__gte=since_date
            ).select_related('post')
            
            for post_target in post_targets:
                try:
                    # For now, LinkedIn doesn't provide detailed post analytics via public API
                    # We'll update with basic engagement data if available
                    analytics, created = SocialAnalytics.objects.get_or_create(
                        post_target=post_target,
                        defaults={
                            'impressions': 0,
                            'reach': 0,
                            'likes': 0,
                            'comments': 0,
                            'shares': 0,
                            'saves': 0,
                            'video_views': 0,
                            'platform_metrics': {'note': 'LinkedIn analytics require enterprise API access'}
                        }
                    )
                    
                    if not created:
                        # Update with any available metrics
                        analytics.platform_metrics = {
                            **analytics.platform_metrics,
                            'last_updated': django_timezone.now().isoformat(),
                            'note': 'LinkedIn analytics require enterprise API access'
                        }
                        analytics.save()
                        
                except Exception as e:
                    logger.error(f"Error updating LinkedIn post analytics for {post_target.platform_post_id}: {str(e)}")
                    
        except Exception as e:
            logger.error(f"Error updating LinkedIn posts analytics: {str(e)}")
    
    def _update_account_metrics(self, account: SocialAccount, account_insights: Dict):
        """Update account with LinkedIn-level metrics"""
        from django.utils import timezone as django_timezone
        
        try:
            # Store account insights in account's permissions field
            account.permissions = account_insights
            account.last_sync = django_timezone.now()
            account.save()
            
            logger.debug(f"Updated LinkedIn account metrics for {account.account_name}")
            
        except Exception as e:
            logger.error(f"Error updating LinkedIn account metrics: {str(e)}")
    
    def collect_analytics(self, account: SocialAccount, days_back: int = 7) -> Dict[str, Any]:
        """Collect comprehensive LinkedIn analytics data directly from API"""
        logger.info(f"Collecting LinkedIn analytics for account: {account.account_name}")
        
        try:
            # First, import/sync LinkedIn posts from API to ensure we have current data
            import_result = self._import_linkedin_posts(account, days_back)
            logger.info(f"LinkedIn sync result: {import_result['posts_imported']} imported, {import_result['posts_updated']} updated")
            
            # Get account insights
            account_insights = self._get_account_insights(account, days_back)
            
            # Get posts performance summary (this will now include API-synced posts)
            from django.utils import timezone as django_timezone
            from datetime import timedelta
            date_range = {
                'start_date': (django_timezone.now() - timedelta(days=days_back)).strftime('%Y-%m-%d'),
                'end_date': django_timezone.now().strftime('%Y-%m-%d')
            }
            posts_summary = self._get_posts_performance_summary(account, date_range)
            
            return {
                'account_name': account.account_name,
                'platform': 'LinkedIn',
                'account_insights': account_insights,
                'posts_performance': posts_summary,
                'date_range': date_range,
                'sync_result': import_result,
                'summary': {
                    'total_posts': posts_summary.get('total_posts', 0),
                    'total_impressions': posts_summary.get('total_impressions', 0),
                    'total_reach': posts_summary.get('total_reach', 0),
                    'total_engagement': posts_summary.get('total_engagement', 0),
                    'avg_engagement_rate': posts_summary.get('avg_engagement_rate', 0)
                },
                'note': 'LinkedIn analytics fetched directly from API'
            }
            
        except Exception as e:
            logger.error(f"Error collecting LinkedIn analytics for {account.account_name}: {str(e)}")
            return {
                'account_name': account.account_name,
                'platform': 'LinkedIn',
                'error': str(e),
                'has_insights_access': False
            }
    
    def _get_posts_performance_summary(self, account: SocialAccount, date_range: Dict[str, str]) -> Dict[str, Any]:
        """Get summary of LinkedIn posts performance for date range"""
        try:
            start_date = datetime.strptime(date_range['start_date'], '%Y-%m-%d').date()
            end_date = datetime.strptime(date_range['end_date'], '%Y-%m-%d').date()
            
            # Get analytics for posts in date range
            analytics = SocialAnalytics.objects.filter(
                post_target__account=account,
                post_target__post__published_at__date__gte=start_date,
                post_target__post__published_at__date__lte=end_date
            )
            
            if not analytics.exists():
                return {'message': 'No LinkedIn posts data available for this date range'}
            
            # Calculate aggregated metrics
            total_posts = analytics.count()
            total_impressions = sum(a.impressions for a in analytics)
            total_reach = sum(a.reach for a in analytics)
            total_engagement = sum(a.likes + a.comments + a.shares for a in analytics)
            
            return {
                'total_posts': total_posts,
                'total_impressions': total_impressions,
                'total_reach': total_reach,
                'total_engagement': total_engagement,
                'avg_engagement_rate': 0.0,  # LinkedIn doesn't provide this via basic API
                'top_performing_posts': self._get_top_posts(analytics, limit=5)
            }
            
        except Exception as e:
            logger.error(f"Error getting LinkedIn posts performance summary: {str(e)}")
            return {'error': str(e)}
    
    def _get_top_posts(self, analytics_queryset, limit: int = 5) -> List[Dict]:
        """Get top performing LinkedIn posts by engagement"""
        try:
            top_posts = []
            
            for analytics in analytics_queryset.order_by('-likes', '-comments', '-shares')[:limit]:
                post = analytics.post_target.post
                top_posts.append({
                    'post_id': str(post.id),
                    'content': post.content[:100] + '...' if len(post.content) > 100 else post.content,
                    'published_at': post.published_at.isoformat() if post.published_at else None,
                    'likes': analytics.likes,
                    'comments': analytics.comments,
                    'shares': analytics.shares,
                    'impressions': analytics.impressions
                })
            
            return top_posts
            
        except Exception as e:
            logger.error(f"Error getting top LinkedIn posts: {str(e)}")
            return []