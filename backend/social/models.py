from django.db import models
from django.contrib.auth import get_user_model
import uuid
from datetime import datetime
import json

User = get_user_model()

# Standalone social media app without organization dependencies

class SocialPlatform(models.Model):
    """Available social media platforms"""
    PLATFORM_CHOICES = [
        ('facebook', 'Facebook'),
        ('instagram', 'Instagram'),
        ('linkedin', 'LinkedIn'),
        ('twitter', 'Twitter/X'),
        ('youtube', 'YouTube'),
        ('pinterest', 'Pinterest'),
        ('google_business', 'Google My Business'),
        ('tiktok', 'TikTok'),
    ]
    
    name = models.CharField(max_length=50, choices=PLATFORM_CHOICES, unique=True)
    display_name = models.CharField(max_length=100)
    icon_class = models.CharField(max_length=50, blank=True)
    color_hex = models.CharField(max_length=7)  # #1877F2 for Facebook
    is_active = models.BooleanField(default=True)
    api_version = models.CharField(max_length=20, blank=True)
    
    # Platform-specific limits
    max_text_length = models.IntegerField(default=280)
    max_image_count = models.IntegerField(default=10)
    max_video_size_mb = models.IntegerField(default=100)
    supports_scheduling = models.BooleanField(default=True)
    supports_hashtags = models.BooleanField(default=True)
    supports_first_comment = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'social_platforms'
        ordering = ['display_name']
    
    def __str__(self):
        return self.display_name
class SocialAccount(models.Model):
    """Connected social media accounts per user"""
    STATUS_CHOICES = [
        ('connected', 'Connected'),
        ('expired', 'Token Expired'),
        ('disconnected', 'Disconnected'),
        ('error', 'Connection Error'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    platform = models.ForeignKey(SocialPlatform, on_delete=models.CASCADE)
    
    # Account details
    account_id = models.CharField(max_length=100)  # Platform-specific account ID
    account_name = models.CharField(max_length=200)
    account_username = models.CharField(max_length=100, blank=True)
    profile_picture_url = models.URLField(blank=True)
    
    # OAuth tokens
    access_token = models.TextField()
    refresh_token = models.TextField(blank=True)
    token_expires_at = models.DateTimeField(null=True, blank=True)
    
    # Connection status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='connected')
    last_sync = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    
    # Permissions
    permissions = models.JSONField(default=list)  # List of granted permissions
    
    # Connection type (for Instagram: facebook_business vs instagram_direct)
    CONNECTION_TYPE_CHOICES = [
        ('standard', 'Standard'),
        ('facebook_business', 'Facebook Business'),
        ('instagram_direct', 'Instagram Direct'),
    ]
    connection_type = models.CharField(max_length=20, choices=CONNECTION_TYPE_CHOICES, default='standard')
    
    # Settings
    is_active = models.BooleanField(default=True)
    auto_publish = models.BooleanField(default=True)
    timezone = models.CharField(max_length=50, default='UTC')
    
    # Posting capability (False for personal Facebook profiles)
    posting_enabled = models.BooleanField(default=True, help_text="Whether this account supports API posting")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    class Meta:
        db_table = 'social_accounts'
        unique_together = ['platform', 'account_id']
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.platform.display_name} - {self.account_name}"
    
    @property
    def is_token_expired(self):
        if not self.token_expires_at:
            return False
        return datetime.now() > self.token_expires_at.replace(tzinfo=None)
class SocialPost(models.Model):
    """Social media posts"""
    POST_TYPES = [
        ('text', 'Text Only'),
        ('image', 'Image Post'),
        ('video', 'Video Post'),
        ('carousel', 'Carousel/Album'),
        ('story', 'Story'),
        ('reel', 'Reel/Short'),
    ]
    
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('scheduled', 'Scheduled'),
        ('publishing', 'Publishing'),
        ('published', 'Published'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    
    # Content
    content = models.TextField()
    post_type = models.CharField(max_length=20, choices=POST_TYPES, default='text')
    hashtags = models.JSONField(default=list)
    mentions = models.JSONField(default=list)
    first_comment = models.TextField(blank=True)  # For Instagram/Facebook
    
    # Media
    media_files = models.JSONField(default=list)  # List of media file paths/URLs
    thumbnail_url = models.URLField(blank=True)
    
    # Scheduling
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    scheduled_at = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    
    # AI assistance
    original_content = models.TextField(blank=True)  # Original before AI modifications
    ai_suggestions = models.JSONField(default=dict)  # AI-generated variations
    ai_generated = models.BooleanField(default=False)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    
    class Meta:
        db_table = 'social_posts'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.post_type.title()} - {self.content[:50]}..."
class SocialPostTarget(models.Model):
    """Platform-specific post targets"""
    post = models.ForeignKey(SocialPost, on_delete=models.CASCADE, related_name='targets')
    account = models.ForeignKey(SocialAccount, on_delete=models.CASCADE)
    
    # Platform-specific content variations
    content_override = models.TextField(blank=True)  # Platform-specific content
    hashtags_override = models.JSONField(default=list)
    
    # Publishing details
    platform_post_id = models.CharField(max_length=200, blank=True)  # ID from platform API
    platform_url = models.URLField(blank=True)  # Direct link to post
    
    # Status tracking
    status = models.CharField(max_length=20, choices=SocialPost.STATUS_CHOICES, default='draft')
    error_message = models.TextField(blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    
    # Retry mechanism
    retry_count = models.IntegerField(default=0)
    max_retries = models.IntegerField(default=3)
    next_retry_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'social_post_targets'
        unique_together = ['post', 'account']
        ordering = ['-created_at']
class SocialAnalytics(models.Model):
    """Analytics data for social posts"""
    post_target = models.OneToOneField(SocialPostTarget, on_delete=models.CASCADE, related_name='analytics')
    
    # Engagement metrics
    likes = models.IntegerField(default=0)
    comments = models.IntegerField(default=0)
    shares = models.IntegerField(default=0)
    saves = models.IntegerField(default=0)
    
    # Reach metrics
    impressions = models.IntegerField(default=0)
    reach = models.IntegerField(default=0)
    clicks = models.IntegerField(default=0)
    
    # Video metrics (if applicable)
    video_views = models.IntegerField(default=0)
    video_completion_rate = models.FloatField(default=0.0)
    
    # Platform-specific metrics
    platform_metrics = models.JSONField(default=dict)  # Store platform-specific data
    
    # Tracking
    last_updated = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'social_analytics'
class SocialComment(models.Model):
    """Comments and interactions from social platforms"""
    COMMENT_TYPES = [
        ('comment', 'Comment'),
        ('reply', 'Reply'),
        ('mention', 'Mention'),
        ('dm', 'Direct Message'),
    ]
    
    SENTIMENT_CHOICES = [
        ('positive', 'Positive'),
        ('neutral', 'Neutral'),
        ('negative', 'Negative'),
        ('question', 'Question'),
        ('complaint', 'Complaint'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    post_target = models.ForeignKey(SocialPostTarget, on_delete=models.CASCADE, null=True, blank=True, related_name='comments')
    account = models.ForeignKey(SocialAccount, on_delete=models.CASCADE)
    
    # Comment details
    platform_comment_id = models.CharField(max_length=200)
    comment_type = models.CharField(max_length=20, choices=COMMENT_TYPES, default='comment')
    content = models.TextField()
    
    # Author info
    author_name = models.CharField(max_length=200)
    author_username = models.CharField(max_length=100, blank=True)
    author_profile_url = models.URLField(blank=True)
    author_avatar_url = models.URLField(blank=True)
    
    # AI analysis
    sentiment = models.CharField(max_length=20, choices=SENTIMENT_CHOICES, default='neutral')
    ai_tags = models.JSONField(default=list)  # AI-generated tags
    priority_score = models.IntegerField(default=0)  # 0-100 priority
    
    # Management
    is_replied = models.BooleanField(default=False)
    is_flagged = models.BooleanField(default=False)
    is_hidden = models.BooleanField(default=False)
    replied_at = models.DateTimeField(null=True, blank=True)
    replied_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Platform data
    platform_created_at = models.DateTimeField()
    platform_data = models.JSONField(default=dict)  # Raw platform data
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'social_comments'
        unique_together = ['account', 'platform_comment_id']
        ordering = ['-platform_created_at']
    
    def __str__(self):
        return f"{self.author_name}: {self.content[:50]}..."
class SocialIdea(models.Model):
    """Content ideas board"""
    STATUS_CHOICES = [
        ('idea', 'Idea'),
        ('in_progress', 'In Progress'),
        ('scheduled', 'Scheduled'),
        ('published', 'Published'),
        ('archived', 'Archived'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    
    # Content
    title = models.CharField(max_length=200)
    description = models.TextField()
    content_draft = models.TextField(blank=True)
    
    # Categorization
    tags = models.JSONField(default=list)
    category = models.CharField(max_length=100, blank=True)
    target_platforms = models.JSONField(default=list)  # List of platform names
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='idea')
    priority = models.IntegerField(default=3)  # 1-5 priority
    
    # AI generated
    ai_generated = models.BooleanField(default=False)
    ai_prompt = models.TextField(blank=True)  # Original AI prompt
    
    # Links
    related_post = models.ForeignKey(SocialPost, on_delete=models.SET_NULL, null=True, blank=True)
    inspiration_urls = models.JSONField(default=list)  # URLs for inspiration
    
    # Media
    reference_images = models.JSONField(default=list)  # Image URLs/paths
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    
    class Meta:
        db_table = 'social_ideas'
        ordering = ['-priority', '-created_at']
    
    def __str__(self):
        return self.title
class SocialHashtag(models.Model):
    """Hashtag management and suggestions"""
    
    
    tag = models.CharField(max_length=100)  # Without #
    display_tag = models.CharField(max_length=100)  # With proper casing
    
    # Analytics
    usage_count = models.IntegerField(default=0)
    avg_engagement = models.FloatField(default=0.0)
    last_used = models.DateTimeField(null=True, blank=True)
    
    # AI categorization
    category = models.CharField(max_length=100, blank=True)
    relevance_score = models.FloatField(default=0.0)  # 0-1 relevance to business
    
    # Platform performance
    platform_performance = models.JSONField(default=dict)  # Per-platform stats
    
    is_trending = models.BooleanField(default=False)
    is_favorite = models.BooleanField(default=False)
    is_blocked = models.BooleanField(default=False)  # Don't suggest
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'social_hashtags'
        unique_together = ['tag']
        ordering = ['-usage_count', 'tag']
    
    def __str__(self):
        return f"#{self.display_tag}"
class SocialQueue(models.Model):
    """Publishing queue management"""
    
    account = models.ForeignKey(SocialAccount, on_delete=models.CASCADE)
    
    # Queue settings
    name = models.CharField(max_length=200)
    is_active = models.BooleanField(default=True)
    
    # Scheduling settings
    timezone = models.CharField(max_length=50, default='UTC')
    schedule_times = models.JSONField(default=list)  # List of time slots
    
    # Queue limits
    posts_per_day = models.IntegerField(default=5)
    min_interval_hours = models.IntegerField(default=2)
    
    # Auto-optimization
    optimize_timing = models.BooleanField(default=False)
    best_times = models.JSONField(default=list)  # AI-determined best times
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    
    class Meta:
        db_table = 'social_queues'
        unique_together = ['account', 'name']
        ordering = ['name']
    
    def __str__(self):
        return f"{self.account} - {self.name}"
class SocialMediaFile(models.Model):
    """Media file storage for social posts"""
    FILE_TYPES = [
        ('image', 'Image'),
        ('video', 'Video'),
        ('gif', 'GIF'),
        ('document', 'Document'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    
    # File details
    file = models.FileField(upload_to='social_media/%Y/%m/')
    file_name = models.CharField(max_length=255)
    file_type = models.CharField(max_length=20, choices=FILE_TYPES)
    file_size = models.BigIntegerField()  # Size in bytes
    mime_type = models.CharField(max_length=100)
    
    # Image/Video metadata
    width = models.IntegerField(null=True, blank=True)
    height = models.IntegerField(null=True, blank=True)
    duration = models.FloatField(null=True, blank=True)  # Video duration in seconds
    
    # AI analysis
    alt_text = models.TextField(blank=True)  # AI-generated alt text
    ai_tags = models.JSONField(default=list)  # AI-detected objects/themes
    is_appropriate = models.BooleanField(default=True)  # Content moderation
    
    # Usage tracking
    usage_count = models.IntegerField(default=0)
    last_used = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE)
    
    class Meta:
        db_table = 'social_media_files'
        ordering = ['-created_at']
    
    def __str__(self):
        return self.file_name
    
    @property
    def file_size_mb(self):
        return round(self.file_size / (1024 * 1024), 2)
