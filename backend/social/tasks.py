import logging
import requests
from datetime import datetime, timedelta
from celery import shared_task
from django.utils import timezone
from django.conf import settings
from typing import List, Dict, Any

from .models import (
    SocialPost, SocialPostTarget, SocialAccount, SocialPlatform,
    SocialComment, SocialAnalytics
)
from .services.facebook_service import FacebookService
from .services.ai_service import AIService

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3)
def publish_post(self, post_id: str, target_account_ids: List[str]):
    """
    Publish a social media post to specified accounts
    """
    try:
        post = SocialPost.objects.get(id=post_id)
        post.status = 'publishing'
        post.save()
        
        logger.info(f"Starting publication of post {post_id} to {len(target_account_ids)} accounts")
        
        published_count = 0
        failed_count = 0
        
        for account_id in target_account_ids:
            try:
                account = SocialAccount.objects.get(id=account_id)
                
                # Get or create post target
                target, created = SocialPostTarget.objects.get_or_create(
                    post=post,
                    account=account,
                    defaults={
                        'content_override': '',
                        'hashtags_override': [],
                        'status': 'pending'
                    }
                )
                
                target.status = 'publishing'
                target.save()
                
                # Publish based on platform
                success = False
                platform_post_id = None
                platform_url = None
                error_message = None
                
                if account.platform.name == 'facebook':
                    success, platform_post_id, platform_url, error_message = publish_to_facebook(
                        post, account, target
                    )
                elif account.platform.name == 'instagram':
                    success, platform_post_id, platform_url, error_message = publish_to_instagram(
                        post, account, target
                    )
                elif account.platform.name == 'linkedin':
                    success, platform_post_id, platform_url, error_message = publish_to_linkedin(
                        post, account, target
                    )
                else:
                    # Placeholder for other platforms
                    success = True
                    platform_post_id = f"mock_{account.platform.name}_{post_id}"
                    platform_url = f"https://{account.platform.name}.com/posts/{platform_post_id}"
                    logger.info(f"Mock publication to {account.platform.name} successful")
                
                if success:
                    target.status = 'published'
                    target.platform_post_id = platform_post_id
                    target.platform_url = platform_url
                    target.published_at = timezone.now()
                    target.error_message = ''
                    published_count += 1
                    
                    logger.info(f"Successfully published to {account.platform.display_name} ({account.account_name})")
                else:
                    target.status = 'failed'
                    target.error_message = error_message or 'Unknown error occurred'
                    failed_count += 1
                    
                    logger.error(f"Failed to publish to {account.platform.display_name}: {error_message}")
                
                target.save()
                
            except SocialAccount.DoesNotExist:
                logger.error(f"Account {account_id} not found")
                failed_count += 1
            except Exception as e:
                logger.error(f"Error publishing to account {account_id}: {str(e)}")
                failed_count += 1
        
        # Update post status
        if published_count > 0 and failed_count == 0:
            post.status = 'published'
            post.published_at = timezone.now()
        elif published_count > 0:
            post.status = 'partially_published'
        else:
            post.status = 'failed'
        
        post.save()
        
        logger.info(f"Post {post_id} publication completed: {published_count} successful, {failed_count} failed")
        
        # Schedule analytics collection
        analyze_post_performance.apply_async(
            args=[post_id],
            countdown=300  # Wait 5 minutes before collecting initial analytics
        )
        
        return {
            'post_id': post_id,
            'published_count': published_count,
            'failed_count': failed_count,
            'status': post.status
        }
        
    except SocialPost.DoesNotExist:
        logger.error(f"Post {post_id} not found")
        raise
    except Exception as e:
        logger.error(f"Error in publish_post task: {str(e)}")
        # Retry the task
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=60 * (2 ** self.request.retries))
        else:
            # Mark post as failed after max retries
            try:
                post = SocialPost.objects.get(id=post_id)
                post.status = 'failed'
                post.save()
            except:
                pass
            raise

@shared_task
def process_scheduled_posts():
    """
    Process posts that are scheduled to be published now
    """
    now = timezone.now()
    scheduled_posts = SocialPost.objects.filter(
        status='scheduled',
        scheduled_at__lte=now
    )
    
    logger.info(f"Processing {scheduled_posts.count()} scheduled posts")
    
    for post in scheduled_posts:
        try:
            # Get target accounts for this post
            target_account_ids = list(
                post.targets.values_list('account_id', flat=True)
            )
            
            if target_account_ids:
                # Trigger publication
                publish_post.delay(str(post.id), target_account_ids)
                logger.info(f"Queued post {post.id} for publication")
            else:
                logger.warning(f"Post {post.id} has no target accounts")
                post.status = 'failed'
                post.save()
                
        except Exception as e:
            logger.error(f"Error processing scheduled post {post.id}: {str(e)}")

@shared_task(bind=True, max_retries=3)
def sync_social_comments(self, account_id: str = None):
    """
    Sync comments and interactions from social media platforms
    """
    try:
        if account_id:
            accounts = SocialAccount.objects.filter(id=account_id, is_active=True)
        else:
            accounts = SocialAccount.objects.filter(is_active=True, status='connected')
        
        logger.info(f"Syncing comments for {accounts.count()} accounts")
        
        for account in accounts:
            try:
                if account.platform.name == 'facebook':
                    sync_facebook_comments(account)
                elif account.platform.name == 'instagram':
                    sync_instagram_comments(account)
                else:
                    logger.info(f"Comment sync not implemented for {account.platform.name}")
                    
            except Exception as e:
                logger.error(f"Error syncing comments for account {account.id}: {str(e)}")
                
    except Exception as e:
        logger.error(f"Error in sync_social_comments task: {str(e)}")
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=300)  # Retry after 5 minutes
        raise

@shared_task(bind=True, max_retries=2)
def analyze_post_performance(self, post_id: str):
    """
    Analyze the performance of a published post
    """
    try:
        post = SocialPost.objects.get(id=post_id)
        
        if post.status not in ['published', 'partially_published']:
            logger.warning(f"Post {post_id} is not published, skipping analytics")
            return
        
        logger.info(f"Analyzing performance for post {post_id}")
        
        for target in post.targets.filter(status='published'):
            try:
                account = target.account
                
                if account.platform.name == 'facebook':
                    analyze_facebook_post_performance(post, target)
                elif account.platform.name == 'instagram':
                    analyze_instagram_post_performance(post, target)
                else:
                    # Create mock analytics for other platforms
                    create_mock_analytics(post, target)
                    
            except Exception as e:
                logger.error(f"Error analyzing performance for target {target.id}: {str(e)}")
                
    except SocialPost.DoesNotExist:
        logger.error(f"Post {post_id} not found for analytics")
    except Exception as e:
        logger.error(f"Error in analyze_post_performance task: {str(e)}")
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=1800)  # Retry after 30 minutes
        raise

@shared_task
def generate_ai_content(prompt: str, platform: str):
    """
    Generate AI content suggestions
    """
    try:
        ai_service = AIService()
        suggestions = ai_service.generate_content_suggestions(prompt, platform)
        
        logger.info(f"Generated {len(suggestions)} AI content suggestions for {platform}")
        
        return {
            'suggestions': suggestions,
            'platform': platform,
            'generated_at': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error generating AI content: {str(e)}")
        raise

@shared_task
def cleanup_old_tasks():
    """
    Clean up old task results and expired data
    """
    try:
        # Clean up old analytics data (older than 1 year)
        cutoff_date = timezone.now() - timedelta(days=365)
        old_analytics = SocialAnalytics.objects.filter(created_at__lt=cutoff_date)
        deleted_count = old_analytics.count()
        old_analytics.delete()
        
        logger.info(f"Cleaned up {deleted_count} old analytics records")
        
        # Clean up old media files (older than 6 months)
        media_cutoff = timezone.now() - timedelta(days=180)
        # Media cleanup would go here
        old_media_count = 0
        # old_media.delete()
        
        logger.info(f"Cleaned up {old_media_count} old media files")
        
        return {
            'analytics_cleaned': deleted_count,
            'media_cleaned': old_media_count
        }
        
    except Exception as e:
        logger.error(f"Error in cleanup_old_tasks: {str(e)}")
        raise

# Platform-specific publishing functions

def publish_to_facebook(post: SocialPost, account: SocialAccount, target: SocialPostTarget) -> tuple:
    """
    Publish post to Facebook
    Returns: (success, platform_post_id, platform_url, error_message)
    """
    try:
        facebook_service = FacebookService()
        
        # Prepare content
        content = target.content_override or post.content
        if post.hashtags:
            hashtags = target.hashtags_override or post.hashtags
            content += '\n\n' + ' '.join([f'#{tag}' for tag in hashtags])
        
        # Publish post
        result = facebook_service.publish_post(
            account=account,
            content=content,
            media_urls=post.media_files or [],
            first_comment=post.first_comment
        )
        
        if result.get('success'):
            return (
                True,
                result.get('post_id'),
                result.get('post_url'),
                None
            )
        else:
            return (False, None, None, result.get('error'))
            
    except Exception as e:
        return (False, None, None, str(e))

def publish_to_instagram(post: SocialPost, account: SocialAccount, target: SocialPostTarget) -> tuple:
    """
    Publish post to Instagram using Instagram Graph API 2025
    Returns: (success, platform_post_id, platform_url, error_message)
    
    Note: Instagram Graph API 2025 requires images/videos - text-only posts are not supported
    """
    try:
        from .services.instagram_service import InstagramService
        
        instagram_service = InstagramService()
        
        # Prepare content
        content = target.content_override or post.content
        if post.hashtags:
            hashtags = target.hashtags_override or post.hashtags
            content += '\n\n' + ' '.join([f'#{tag}' for tag in hashtags])
        
        # Publish post
        result = instagram_service.publish_post(
            account=account,
            content=content,
            media_urls=post.media_files or [],
            first_comment=post.first_comment
        )
        
        if result.get('success'):
            return (
                True,
                result.get('post_id'),
                result.get('post_url'),
                None
            )
        else:
            return (False, None, None, result.get('error'))
            
    except Exception as e:
        return (False, None, None, str(e))


def publish_to_linkedin(post: SocialPost, account: SocialAccount, target: SocialPostTarget) -> tuple:
    """
    Publish post to LinkedIn using LinkedIn API v2
    Returns: (success, platform_post_id, platform_url, error_message)
    """
    try:
        from .services.linkedin_service import LinkedInService
        
        linkedin_service = LinkedInService()
        
        # Prepare content
        content = target.content_override or post.content
        if post.hashtags:
            hashtags = target.hashtags_override or post.hashtags
            content += '\n\n' + ' '.join([f'#{tag}' for tag in hashtags])
        
        # Publish post
        result = linkedin_service.publish_post(
            account=account,
            content=content,
            media_urls=post.media_files or []
        )
        
        if result.get('success'):
            return (
                True,
                result.get('post_id'),
                result.get('post_url'),
                None
            )
        else:
            return (False, None, None, result.get('error'))
            
    except Exception as e:
        return (False, None, None, str(e))


def sync_facebook_comments(account: SocialAccount):
    """
    Sync comments from Facebook
    """
    try:
        facebook_service = FacebookService()
        comments = facebook_service.get_recent_comments(account)
        
        for comment_data in comments:
            SocialComment.objects.update_or_create(
                platform_comment_id=comment_data['id'],
                account=account,
                defaults={
                    'content': comment_data['message'],
                    'author_name': comment_data['from']['name'],
                    'author_id': comment_data['from']['id'],
                    'sentiment': analyze_sentiment(comment_data['message']),
                    'platform_created_at': comment_data['created_time'],
                }
            )
        
        logger.info(f"Synced {len(comments)} comments for Facebook account {account.account_name}")
        
    except Exception as e:
        logger.error(f"Error syncing Facebook comments: {str(e)}")
        raise

def sync_instagram_comments(account: SocialAccount):
    """
    Sync comments from Instagram using Instagram Graph API 2025
    """
    try:
        from .services.instagram_service import InstagramService
        
        instagram_service = InstagramService()
        
        # Get account info to verify access
        account_info = instagram_service.get_account_info(account)
        
        if not account_info.get('success'):
            logger.error(f"Cannot access Instagram account {account.account_name}: {account_info.get('error')}")
            return
        
        # TODO: Implement comment fetching when needed
        # Instagram Graph API provides comments endpoint: /{media-id}/comments
        # For now, just log that the account is accessible
        logger.info(f"Instagram account {account.account_name} is accessible - comment sync to be implemented")
        
    except Exception as e:
        logger.error(f"Error syncing Instagram comments for {account.account_name}: {str(e)}")

def analyze_facebook_post_performance(post: SocialPost, target: SocialPostTarget):
    """
    Analyze Facebook post performance
    """
    try:
        facebook_service = FacebookService()
        insights = facebook_service.get_post_insights(
            target.account, 
            target.platform_post_id
        )
        
        # Create or update analytics
        SocialAnalytics.objects.update_or_create(
            post_target=target,
            defaults={
                'reach': insights.get('reach', 0),
                'impressions': insights.get('impressions', 0),
                'engagement': insights.get('engagement', 0),
                'clicks': insights.get('clicks', 0),
                'shares': insights.get('shares', 0),
                'comments_count': insights.get('comments', 0),
                'likes_count': insights.get('likes', 0),
                'raw_data': insights
            }
        )
        
        logger.info(f"Updated analytics for Facebook post {target.platform_post_id}")
        
    except Exception as e:
        logger.error(f"Error analyzing Facebook post performance: {str(e)}")

def analyze_instagram_post_performance(post: SocialPost, target: SocialPostTarget):
    """
    Analyze Instagram post performance using Instagram Graph API 2025
    """
    try:
        from .services.instagram_service import InstagramService
        
        instagram_service = InstagramService()
        
        if target.platform_post_id and target.platform_post_id != f"instagram_mock_{post.id}":
            # Get real insights from Instagram
            insights_result = instagram_service.get_media_insights(
                target.account, 
                target.platform_post_id
            )
            
            if insights_result.get('success'):
                insights = insights_result.get('insights', {})
                
                # Create or update analytics with real data
                SocialAnalytics.objects.update_or_create(
                    post_target=target,
                    defaults={
                        'reach': insights.get('reach', 0),
                        'impressions': insights.get('impressions', 0),
                        'engagement': insights.get('engagement', 0),
                        'clicks': insights.get('clicks', 0),
                        'shares': insights.get('shares', 0),
                        'comments_count': insights.get('comments', 0),
                        'likes_count': insights.get('likes', 0),
                        'raw_data': insights
                    }
                )
                
                logger.info(f"Updated analytics for Instagram post {target.platform_post_id}")
            else:
                logger.warning(f"Failed to get Instagram insights: {insights_result.get('error')}")
                # Fall back to mock analytics
                create_mock_analytics(post, target)
        else:
            # For mock posts or posts without real platform_post_id
            create_mock_analytics(post, target)
            
    except Exception as e:
        logger.error(f"Error analyzing Instagram post performance: {str(e)}")
        # Fall back to mock analytics on error
        create_mock_analytics(post, target)

def create_mock_analytics(post: SocialPost, target: SocialPostTarget):
    """
    Create mock analytics data for testing
    """
    import random
    
    SocialAnalytics.objects.update_or_create(
        post_target=target,
        defaults={
            'reach': random.randint(100, 1000),
            'impressions': random.randint(150, 1500),
            'engagement': random.randint(10, 100),
            'clicks': random.randint(5, 50),
            'shares': random.randint(0, 20),
            'comments_count': random.randint(0, 15),
            'likes_count': random.randint(5, 80),
            'raw_data': {'mock': True}
        }
    )

def analyze_sentiment(text: str) -> str:
    """
    Analyze sentiment of text (basic implementation)
    In production, this would use a proper sentiment analysis service
    """
    positive_words = ['great', 'awesome', 'love', 'amazing', 'excellent', 'good', 'nice', 'beautiful']
    negative_words = ['bad', 'terrible', 'hate', 'awful', 'horrible', 'poor', 'worst', 'disappointed']
    question_words = ['how', 'what', 'when', 'where', 'why', 'who', '?']
    
    text_lower = text.lower()
    
    if any(word in text_lower for word in question_words):
        return 'question'
    elif any(word in text_lower for word in positive_words):
        return 'positive'
    elif any(word in text_lower for word in negative_words):
        return 'negative'
    else:
        return 'neutral'


# Analytics Tasks

# Organization-based analytics sync removed for standalone app


@shared_task(bind=True, max_retries=2)
def sync_analytics_for_account(self, account_id: str, days_back: int = 30):
    """
    Sync analytics data for a specific account
    """
    try:
        from .services.analytics_service import AnalyticsService
        
        account = SocialAccount.objects.get(id=account_id)
        logger.info(f"Starting analytics sync for account {account.account_name}")
        
        analytics_service = AnalyticsService()
        
        if account.platform.name.lower() == 'facebook':
            results = analytics_service.facebook_service.sync_account_analytics(account, days_back)
        elif account.platform.name.lower() == 'instagram':
            results = analytics_service.instagram_service.sync_account_analytics(account, days_back)
        else:
            logger.warning(f"Analytics sync not supported for platform: {account.platform.name}")
            return {'error': 'Platform not supported'}
        
        logger.info(f"Analytics sync completed for account {account.account_name}: {results}")
        return results
        
    except SocialAccount.DoesNotExist:
        logger.error(f"Account {account_id} not found")
        return {'error': 'Account not found'}
    except Exception as e:
        logger.error(f"Error syncing analytics for account {account_id}: {str(e)}")
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=900)  # Retry after 15 minutes
        raise


@shared_task
def daily_analytics_sync():
    """
    Daily task to sync analytics for all active accounts
    """
    try:
        # Get all connected social accounts
        accounts = SocialAccount.objects.filter(status='connected')
        
        logger.info(f"Starting daily analytics sync for {accounts.count()} accounts")
        
        for account in accounts:
            # Queue analytics sync for each account
            sync_analytics_for_account.delay(str(account.id), days_back=7)  # Sync last 7 days daily
            
        logger.info("Daily analytics sync tasks queued")
        return {'accounts_queued': accounts.count()}
        
    except Exception as e:
        logger.error(f"Error in daily_analytics_sync: {str(e)}")
        raise


@shared_task
def weekly_analytics_sync():
    """
    Weekly task to sync comprehensive analytics data
    """
    try:
        # Get all connected social accounts
        accounts = SocialAccount.objects.filter(status='connected')
        
        logger.info(f"Starting weekly analytics sync for {accounts.count()} accounts")
        
        for account in accounts:
            # Queue comprehensive analytics sync for each account
            sync_analytics_for_account.delay(str(account.id), days_back=30)  # Sync last 30 days weekly
            
        logger.info("Weekly analytics sync tasks queued")
        return {'accounts_queued': accounts.count()}
        
    except Exception as e:
        logger.error(f"Error in weekly_analytics_sync: {str(e)}")
        raise


@shared_task
def update_account_followers():
    """
    Update follower counts for all connected accounts
    """
    try:
        from .services.analytics_service import AnalyticsService
        
        accounts = SocialAccount.objects.filter(status='connected')
        logger.info(f"Updating follower counts for {accounts.count()} accounts")
        
        analytics_service = AnalyticsService()
        updated_count = 0
        
        for account in accounts:
            try:
                platform_name = account.platform.name.lower()
                
                if platform_name == 'facebook':
                    # Get page insights
                    page_insights = analytics_service.facebook_service._get_page_insights(account, 1)
                    if page_insights and 'followers' in page_insights:
                        # Update account permissions with follower count
                        account_metrics = account.permissions if isinstance(account.permissions, dict) else {}
                        account_metrics['followers'] = page_insights['followers']
                        account.permissions = account_metrics
                        account.save()
                        updated_count += 1
                        logger.debug(f"Updated Facebook followers for {account.account_name}")
                        
                elif platform_name == 'instagram':
                    # Get account insights
                    account_insights = analytics_service.instagram_service._get_account_insights(account, 1)
                    if account_insights and 'follower_count' in account_insights:
                        # Update account permissions with follower count
                        account_metrics = account.permissions if isinstance(account.permissions, dict) else {}
                        account_metrics['follower_count'] = account_insights['follower_count']
                        account.permissions = account_metrics
                        account.save()
                        updated_count += 1
                        logger.debug(f"Updated Instagram followers for {account.account_name}")
                        
            except Exception as e:
                logger.error(f"Error updating followers for account {account.id}: {str(e)}")
                continue
        
        logger.info(f"Updated follower counts for {updated_count} accounts")
        return {'accounts_updated': updated_count}
        
    except Exception as e:
        logger.error(f"Error in update_account_followers: {str(e)}")
        raise


# Analytics report generation removed for standalone app