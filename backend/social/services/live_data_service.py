"""
Live Data Collection Service

This service orchestrates live data collection from connected Facebook and Instagram accounts,
providing real-time analytics and insights for the social media management system.
"""

import logging
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from django.conf import settings
from django.utils import timezone
from django.db.models import Q

from ..models import SocialAccount, SocialAnalytics, SocialPost, SocialPostTarget
from .analytics_service import FacebookAnalyticsService, InstagramAnalyticsService

logger = logging.getLogger(__name__)


class LiveDataService:
    """Service for collecting and processing live data from social media accounts"""
    
    def __init__(self):
        self.facebook_service = FacebookAnalyticsService()
        self.instagram_service = InstagramAnalyticsService()
    
    def collect_all_live_data(self, user, days_back: int = 30) -> Dict[str, Any]:
        """Collect live data from all connected accounts for a user"""
        logger.info(f"Starting live data collection for user: {user.username}")
        
        results = {
            'user': user.username,
            'collection_started': timezone.now().isoformat(),
            'facebook_results': [],
            'instagram_results': [],
            'summary': {
                'total_accounts': 0,
                'successful_collections': 0,
                'failed_collections': 0,
                'data_points_collected': 0
            },
            'errors': []
        }
        
        try:
            # Collect Facebook data
            facebook_results = self._collect_facebook_data(user, days_back)
            results['facebook_results'] = facebook_results
            
            # Collect Instagram data
            instagram_results = self._collect_instagram_data(user, days_back)
            results['instagram_results'] = instagram_results
            
            # Update summary
            self._update_summary(results)
            
            # Generate trending hashtags and optimal times
            trending_data = self._analyze_trending_content(user, days_back)
            results['trending_analysis'] = trending_data
            
            results['collection_completed'] = timezone.now().isoformat()
            logger.info(f"Live data collection completed for {user.username}")
            
            return results
            
        except Exception as e:
            error_msg = f"Error in live data collection: {str(e)}"
            logger.error(error_msg)
            results['errors'].append(error_msg)
            results['collection_failed'] = timezone.now().isoformat()
            return results
    
    def _collect_facebook_data(self, user, days_back: int) -> List[Dict[str, Any]]:
        """Collect live data from Facebook accounts"""
        results = []
        
        facebook_accounts = SocialAccount.objects.filter(
            created_by=user,
            platform__name='facebook',
            status='connected',
            is_active=True
        )
        
        logger.info(f"Found {facebook_accounts.count()} Facebook accounts to process")
        
        for account in facebook_accounts:
            result = {
                'account_id': account.account_id,
                'account_name': account.account_name,
                'platform': 'Facebook',
                'status': 'processing'
            }
            
            try:
                # Collect comprehensive analytics
                analytics_data = self.facebook_service.collect_analytics(account, days_back)
                
                if analytics_data.get('error'):
                    result['status'] = 'error'
                    result['error'] = analytics_data['error']
                else:
                    result['status'] = 'success'
                    result['data'] = analytics_data
                    
                    # Sync account-level analytics
                    sync_result = self.facebook_service.sync_account_analytics(account, days_back)
                    result['sync_result'] = sync_result
                    
                    # Extract key metrics for summary
                    result['metrics'] = {
                        'total_posts': analytics_data.get('summary', {}).get('total_posts', 0),
                        'total_impressions': analytics_data.get('summary', {}).get('total_impressions', 0),
                        'total_reach': analytics_data.get('summary', {}).get('total_reach', 0),
                        'total_engagement': analytics_data.get('summary', {}).get('total_engagement', 0),
                        'avg_engagement_rate': analytics_data.get('summary', {}).get('avg_engagement_rate', 0)
                    }
                
            except Exception as e:
                result['status'] = 'error'
                result['error'] = str(e)
                logger.error(f"Error collecting Facebook data for {account.account_name}: {str(e)}")
            
            results.append(result)
        
        return results
    
    def _collect_instagram_data(self, user, days_back: int) -> List[Dict[str, Any]]:
        """Collect live data from Instagram accounts"""
        results = []
        
        instagram_accounts = SocialAccount.objects.filter(
            created_by=user,
            platform__name='instagram',
            status='connected',
            is_active=True
        )
        
        logger.info(f"Found {instagram_accounts.count()} Instagram accounts to process")
        
        for account in instagram_accounts:
            result = {
                'account_id': account.account_id,
                'account_name': account.account_name,
                'username': account.account_username,
                'platform': 'Instagram',
                'status': 'processing'
            }
            
            try:
                # Collect comprehensive analytics
                analytics_data = self.instagram_service.collect_analytics(account, days_back)
                
                if analytics_data.get('error'):
                    result['status'] = 'error'
                    result['error'] = analytics_data['error']
                elif not analytics_data.get('has_insights_access'):
                    result['status'] = 'limited'
                    result['message'] = analytics_data.get('message', 'No insights access')
                    result['verification'] = analytics_data.get('verification', {})
                else:
                    result['status'] = 'success'
                    result['data'] = analytics_data
                    
                    # Sync account-level analytics
                    sync_result = self.instagram_service.sync_account_analytics(account, days_back)
                    result['sync_result'] = sync_result
                    
                    # Extract key metrics for summary
                    result['metrics'] = {
                        'total_posts': analytics_data.get('summary', {}).get('total_posts', 0),
                        'total_impressions': analytics_data.get('summary', {}).get('total_impressions', 0),
                        'total_reach': analytics_data.get('summary', {}).get('total_reach', 0),
                        'total_engagement': analytics_data.get('summary', {}).get('total_engagement', 0),
                        'avg_engagement_rate': analytics_data.get('summary', {}).get('avg_engagement_rate', 0)
                    }
                
            except Exception as e:
                result['status'] = 'error'
                result['error'] = str(e)
                logger.error(f"Error collecting Instagram data for {account.account_name}: {str(e)}")
            
            results.append(result)
        
        return results
    
    def _update_summary(self, results: Dict[str, Any]):
        """Update the summary statistics"""
        facebook_results = results.get('facebook_results', [])
        instagram_results = results.get('instagram_results', [])
        all_results = facebook_results + instagram_results
        
        results['summary']['total_accounts'] = len(all_results)
        results['summary']['successful_collections'] = len([r for r in all_results if r.get('status') == 'success'])
        results['summary']['failed_collections'] = len([r for r in all_results if r.get('status') == 'error'])
        
        # Count data points collected
        data_points = 0
        for result in all_results:
            if result.get('status') == 'success' and result.get('metrics'):
                data_points += sum(result['metrics'].values())
        
        results['summary']['data_points_collected'] = data_points
    
    def _analyze_trending_content(self, user, days_back: int) -> Dict[str, Any]:
        """Analyze trending hashtags and optimal posting times from live data"""
        logger.info(f"Analyzing trending content for {user.username}")
        
        try:
            # Get recent posts with analytics
            end_date = timezone.now().date()
            start_date = end_date - timedelta(days=days_back)
            
            posts_with_analytics = SocialAnalytics.objects.filter(
                post_target__post__created_by=user,
                post_target__post__published_at__date__gte=start_date,
                post_target__post__published_at__date__lte=end_date
            ).select_related('post_target__post')
            
            if not posts_with_analytics.exists():
                return {
                    'message': 'No recent posts with analytics data found',
                    'trending_hashtags': [],
                    'optimal_times': {},
                    'top_performing_content': []
                }
            
            # Analyze hashtags performance
            trending_hashtags = self._analyze_hashtag_performance(posts_with_analytics)
            
            # Analyze optimal posting times
            optimal_times = self._analyze_optimal_posting_times(posts_with_analytics)
            
            # Get top performing content
            top_content = self._get_top_performing_content(posts_with_analytics)
            
            return {
                'trending_hashtags': trending_hashtags,
                'optimal_times': optimal_times,
                'top_performing_content': top_content,
                'analysis_date': timezone.now().isoformat(),
                'posts_analyzed': posts_with_analytics.count()
            }
            
        except Exception as e:
            logger.error(f"Error analyzing trending content: {str(e)}")
            return {
                'error': str(e),
                'trending_hashtags': [],
                'optimal_times': {},
                'top_performing_content': []
            }
    
    def _analyze_hashtag_performance(self, analytics_queryset) -> List[Dict[str, Any]]:
        """Analyze hashtag performance from posts with analytics"""
        hashtag_performance = {}
        
        for analytics in analytics_queryset:
            post = analytics.post_target.post
            hashtags = post.hashtags if post.hashtags else []
            
            # Calculate engagement score for this post
            engagement_score = analytics.likes + analytics.comments + analytics.shares
            reach = max(analytics.reach, 1)  # Avoid division by zero
            engagement_rate = (engagement_score / reach) * 100
            
            for hashtag in hashtags:
                hashtag = hashtag.lower().strip()
                if hashtag not in hashtag_performance:
                    hashtag_performance[hashtag] = {
                        'hashtag': hashtag,
                        'usage_count': 0,
                        'total_engagement': 0,
                        'total_reach': 0,
                        'total_impressions': 0,
                        'posts': []
                    }
                
                hashtag_performance[hashtag]['usage_count'] += 1
                hashtag_performance[hashtag]['total_engagement'] += engagement_score
                hashtag_performance[hashtag]['total_reach'] += analytics.reach
                hashtag_performance[hashtag]['total_impressions'] += analytics.impressions
                hashtag_performance[hashtag]['posts'].append({
                    'post_id': str(post.id),
                    'engagement_rate': engagement_rate,
                    'published_at': post.published_at.isoformat() if post.published_at else None
                })
        
        # Calculate average performance and sort
        trending_hashtags = []
        for hashtag_data in hashtag_performance.values():
            if hashtag_data['usage_count'] >= 2:  # Only include hashtags used multiple times
                avg_engagement_rate = sum(p['engagement_rate'] for p in hashtag_data['posts']) / len(hashtag_data['posts'])
                trending_hashtags.append({
                    'hashtag': hashtag_data['hashtag'],
                    'usage_count': hashtag_data['usage_count'],
                    'avg_engagement_rate': round(avg_engagement_rate, 2),
                    'total_reach': hashtag_data['total_reach'],
                    'performance_score': avg_engagement_rate * hashtag_data['usage_count']
                })
        
        # Sort by performance score and return top 10
        trending_hashtags.sort(key=lambda x: x['performance_score'], reverse=True)
        return trending_hashtags[:10]
    
    def _analyze_optimal_posting_times(self, analytics_queryset) -> Dict[str, Any]:
        """Analyze optimal posting times based on engagement data"""
        time_performance = {}
        
        for analytics in analytics_queryset:
            post = analytics.post_target.post
            if not post.published_at:
                continue
            
            # Extract hour and day of week
            hour = post.published_at.hour
            day_of_week = post.published_at.strftime('%A')
            
            # Calculate engagement rate
            reach = max(analytics.reach, 1)
            engagement_score = analytics.likes + analytics.comments + analytics.shares
            engagement_rate = (engagement_score / reach) * 100
            
            # Track by hour
            if hour not in time_performance:
                time_performance[hour] = {'posts': 0, 'total_engagement_rate': 0}
            time_performance[hour]['posts'] += 1
            time_performance[hour]['total_engagement_rate'] += engagement_rate
        
        # Calculate optimal hours
        optimal_hours = []
        for hour, data in time_performance.items():
            if data['posts'] >= 2:  # Only consider hours with multiple posts
                avg_engagement_rate = data['total_engagement_rate'] / data['posts']
                optimal_hours.append({
                    'hour': hour,
                    'time': f"{hour:02d}:00",
                    'posts_count': data['posts'],
                    'avg_engagement_rate': round(avg_engagement_rate, 2)
                })
        
        # Sort by engagement rate and get top 5
        optimal_hours.sort(key=lambda x: x['avg_engagement_rate'], reverse=True)
        
        return {
            'best_hours': optimal_hours[:5],
            'recommendation': optimal_hours[0]['time'] if optimal_hours else '09:00',
            'analysis_note': f'Based on {analytics_queryset.count()} posts with analytics data'
        }
    
    def _get_top_performing_content(self, analytics_queryset, limit: int = 5) -> List[Dict[str, Any]]:
        """Get top performing content based on engagement metrics"""
        top_content = []
        
        for analytics in analytics_queryset.order_by('-likes', '-comments', '-shares')[:limit]:
            post = analytics.post_target.post
            engagement_score = analytics.likes + analytics.comments + analytics.shares
            reach = max(analytics.reach, 1)
            engagement_rate = (engagement_score / reach) * 100
            
            top_content.append({
                'post_id': str(post.id),
                'content_preview': post.content[:100] + '...' if len(post.content) > 100 else post.content,
                'platform': analytics.post_target.account.platform.display_name,
                'published_at': post.published_at.isoformat() if post.published_at else None,
                'metrics': {
                    'impressions': analytics.impressions,
                    'reach': analytics.reach,
                    'likes': analytics.likes,
                    'comments': analytics.comments,
                    'shares': analytics.shares,
                    'engagement_rate': round(engagement_rate, 2)
                },
                'hashtags': post.hashtags[:5] if post.hashtags else []
            })
        
        return top_content
    
    def get_account_connection_status(self, user) -> Dict[str, Any]:
        """Get detailed connection status for all social media accounts"""
        try:
            facebook_accounts = SocialAccount.objects.filter(
                created_by=user,
                platform__name='facebook'
            )
            
            instagram_accounts = SocialAccount.objects.filter(
                created_by=user,
                platform__name='instagram'
            )
            
            # Test token validity
            facebook_status = []
            for account in facebook_accounts:
                status = self._test_account_connection(account, 'facebook')
                facebook_status.append(status)
            
            instagram_status = []
            for account in instagram_accounts:
                status = self._test_account_connection(account, 'instagram')
                instagram_status.append(status)
            
            return {
                'user': user.username,
                'facebook_accounts': facebook_status,
                'instagram_accounts': instagram_status,
                'summary': {
                    'total_accounts': len(facebook_status) + len(instagram_status),
                    'connected_accounts': len([s for s in facebook_status + instagram_status if s['is_connected']]),
                    'accounts_with_insights': len([s for s in facebook_status + instagram_status if s.get('has_insights_access', False)])
                },
                'last_checked': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting account connection status: {str(e)}")
            return {'error': str(e)}
    
    def _test_account_connection(self, account: SocialAccount, platform: str) -> Dict[str, Any]:
        """Test individual account connection and capabilities"""
        result = {
            'account_id': account.account_id,
            'account_name': account.account_name,
            'platform': platform,
            'status': account.status,
            'is_connected': False,
            'has_insights_access': False,
            'last_sync': account.last_sync.isoformat() if account.last_sync else None
        }
        
        try:
            if platform == 'facebook':
                # Test Facebook page access
                verification = self.facebook_service._verify_page_account(account)
                result['is_page'] = verification.get('is_page', False)
                result['is_connected'] = verification.get('is_page', False)
                result['has_insights_access'] = verification.get('has_page_token', False)
                
                if verification.get('name'):
                    result['verified_name'] = verification['name']
                if verification.get('fan_count') is not None:
                    result['followers'] = verification['fan_count']
                    
            else:  # Instagram
                # Test Instagram account access
                verification = self.instagram_service._verify_business_account(account)
                result['is_connected'] = True  # Basic connection test passed if no exception
                result['has_insights_access'] = verification.get('is_business', False)
                result['is_business_account'] = verification.get('is_business', False)
                
                if verification.get('username'):
                    result['verified_username'] = verification['username']
            
        except Exception as e:
            result['error'] = str(e)
            logger.error(f"Error testing {platform} account connection: {str(e)}")
        
        return result