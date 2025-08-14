from rest_framework import serializers
from .models import (
    SocialPlatform, SocialAccount, SocialPost, SocialPostTarget,
    SocialAnalytics, SocialComment, SocialIdea, SocialHashtag,
    SocialQueue, SocialMediaFile
)


class SocialPlatformSerializer(serializers.ModelSerializer):
    """Serializer for social media platforms"""
    
    class Meta:
        model = SocialPlatform
        fields = [
            'id', 'name', 'display_name', 'icon_class', 'color_hex',
            'is_active', 'api_version', 'max_text_length', 'max_image_count',
            'max_video_size_mb', 'supports_scheduling', 'supports_hashtags',
            'supports_first_comment', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class SocialAccountSerializer(serializers.ModelSerializer):
    """Serializer for connected social media accounts"""
    platform = SocialPlatformSerializer(read_only=True)
    platform_id = serializers.PrimaryKeyRelatedField(
        queryset=SocialPlatform.objects.all(),
        source='platform',
        write_only=True
    )
    is_token_expired = serializers.ReadOnlyField()
    
    class Meta:
        model = SocialAccount
        fields = [
            'id', 'platform', 'platform_id', 'account_id', 'account_name',
            'account_username', 'profile_picture_url', 'status', 'last_sync',
            'error_message', 'permissions', 'connection_type', 'is_active', 'auto_publish',
            'timezone', 'is_token_expired', 'posting_enabled', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'access_token', 'refresh_token', 'token_expires_at',
            'last_sync', 'error_message', 'created_at', 'updated_at',
            'is_token_expired'
        ]


class SocialPostTargetSerializer(serializers.ModelSerializer):
    """Serializer for post targets"""
    account = SocialAccountSerializer(read_only=True)
    account_id = serializers.PrimaryKeyRelatedField(
        queryset=SocialAccount.objects.all(),
        source='account',
        write_only=True
    )
    
    class Meta:
        model = SocialPostTarget
        fields = [
            'id', 'account', 'account_id', 'content_override', 'hashtags_override',
            'platform_post_id', 'platform_url', 'status', 'error_message',
            'published_at', 'retry_count', 'max_retries', 'next_retry_at',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'platform_post_id', 'platform_url', 'published_at',
            'retry_count', 'next_retry_at', 'created_at', 'updated_at'
        ]


class SocialPostSerializer(serializers.ModelSerializer):
    """Serializer for social media posts"""
    targets = SocialPostTargetSerializer(many=True, read_only=True)
    target_accounts = serializers.ListField(
        child=serializers.UUIDField(),
        write_only=True,
        required=False,
        help_text="List of account IDs to target for this post"
    )
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    character_count = serializers.SerializerMethodField()
    
    class Meta:
        model = SocialPost
        fields = [
            'id', 'content', 'post_type', 'hashtags', 'mentions', 'first_comment',
            'media_files', 'thumbnail_url', 'status', 'scheduled_at', 'published_at',
            'original_content', 'ai_suggestions', 'ai_generated', 'targets',
            'target_accounts', 'created_by_name', 'character_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['published_at', 'created_at', 'updated_at']
    
    def get_character_count(self, obj):
        """Get character count of content"""
        return len(obj.content) if obj.content else 0
    
    def create(self, validated_data):
        """Create post and associated targets"""
        target_accounts = validated_data.pop('target_accounts', [])
        post = super().create(validated_data)
        
        # Create post targets
        for account_id in target_accounts:
            try:
                account = SocialAccount.objects.get(
                    id=account_id,
                    created_by=post.created_by
                )
                SocialPostTarget.objects.create(post=post, account=account)
            except SocialAccount.DoesNotExist:
                continue
        
        return post


class SocialAnalyticsSerializer(serializers.ModelSerializer):
    """Serializer for analytics data"""
    post_target = SocialPostTargetSerializer(read_only=True)
    engagement_rate = serializers.SerializerMethodField()
    total_engagement = serializers.SerializerMethodField()
    
    class Meta:
        model = SocialAnalytics
        fields = [
            'id', 'post_target', 'likes', 'comments', 'shares', 'saves',
            'impressions', 'reach', 'clicks', 'video_views', 'video_completion_rate',
            'platform_metrics', 'engagement_rate', 'total_engagement',
            'last_updated', 'created_at'
        ]
        read_only_fields = ['created_at', 'last_updated']
    
    def get_engagement_rate(self, obj):
        """Calculate engagement rate"""
        if obj.reach > 0:
            total_engagements = obj.likes + obj.comments + obj.shares + obj.saves
            return round((total_engagements / obj.reach) * 100, 2)
        return 0.0
    
    def get_total_engagement(self, obj):
        """Get total engagement count"""
        return obj.likes + obj.comments + obj.shares + obj.saves


class SocialCommentSerializer(serializers.ModelSerializer):
    """Serializer for social comments"""
    post_target = SocialPostTargetSerializer(read_only=True)
    account = SocialAccountSerializer(read_only=True)
    replied_by_name = serializers.CharField(source='replied_by.get_full_name', read_only=True)
    time_since_created = serializers.SerializerMethodField()
    
    class Meta:
        model = SocialComment
        fields = [
            'id', 'post_target', 'account', 'platform_comment_id', 'comment_type',
            'content', 'author_name', 'author_username', 'author_profile_url',
            'author_avatar_url', 'sentiment', 'ai_tags', 'priority_score',
            'is_replied', 'is_flagged', 'is_hidden', 'replied_at', 'replied_by_name',
            'platform_created_at', 'time_since_created', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'platform_comment_id', 'platform_created_at', 'platform_data',
            'created_at', 'updated_at', 'time_since_created'
        ]
    
    def get_time_since_created(self, obj):
        """Get human-readable time since comment was created"""
        from django.utils.timesince import timesince
        return timesince(obj.platform_created_at)


class SocialIdeaSerializer(serializers.ModelSerializer):
    """Serializer for content ideas"""
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    related_post = SocialPostSerializer(read_only=True)
    
    class Meta:
        model = SocialIdea
        fields = [
            'id', 'title', 'description', 'content_draft', 'tags', 'category',
            'target_platforms', 'status', 'priority', 'ai_generated', 'ai_prompt',
            'related_post', 'inspiration_urls', 'reference_images',
            'created_by_name', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class SocialHashtagSerializer(serializers.ModelSerializer):
    """Serializer for hashtags"""
    
    class Meta:
        model = SocialHashtag
        fields = [
            'id', 'tag', 'display_tag', 'usage_count', 'avg_engagement',
            'last_used', 'category', 'relevance_score', 'platform_performance',
            'is_trending', 'is_favorite', 'is_blocked', 'created_at', 'updated_at'
        ]
        read_only_fields = ['usage_count', 'last_used', 'created_at', 'updated_at']


class SocialQueueSerializer(serializers.ModelSerializer):
    """Serializer for publishing queues"""
    account = SocialAccountSerializer(read_only=True)
    account_id = serializers.PrimaryKeyRelatedField(
        queryset=SocialAccount.objects.all(),
        source='account',
        write_only=True
    )
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    
    class Meta:
        model = SocialQueue
        fields = [
            'id', 'account', 'account_id', 'name', 'is_active', 'timezone',
            'schedule_times', 'posts_per_day', 'min_interval_hours',
            'optimize_timing', 'best_times', 'created_by_name',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class SocialMediaFileSerializer(serializers.ModelSerializer):
    """Serializer for media files"""
    uploaded_by_name = serializers.CharField(source='uploaded_by.get_full_name', read_only=True)
    file_size_mb = serializers.ReadOnlyField()
    file_url = serializers.SerializerMethodField()
    
    class Meta:
        model = SocialMediaFile
        fields = [
            'id', 'file', 'file_name', 'file_type', 'file_size', 'file_size_mb',
            'mime_type', 'width', 'height', 'duration', 'alt_text', 'ai_tags',
            'is_appropriate', 'usage_count', 'last_used', 'file_url',
            'uploaded_by_name', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'file_size', 'file_size_mb', 'mime_type', 'width', 'height',
            'duration', 'usage_count', 'last_used', 'created_at', 'updated_at'
        ]
    
    def get_file_url(self, obj):
        """Get full URL for the file"""
        request = self.context.get('request')
        if request and obj.file:
            return request.build_absolute_uri(obj.file.url)
        return None


# Specialized serializers for specific use cases
class PostPublishingSerializer(serializers.Serializer):
    """Serializer for post publishing requests"""
    target_accounts = serializers.ListField(
        child=serializers.UUIDField(),
        min_length=1,
        help_text="List of account IDs to publish to"
    )
    publish_now = serializers.BooleanField(default=True)
    scheduled_at = serializers.DateTimeField(required=False)
    
    def validate(self, data):
        if not data.get('publish_now') and not data.get('scheduled_at'):
            raise serializers.ValidationError(
                "Either publish_now must be True or scheduled_at must be provided"
            )
        return data


class AIContentRequestSerializer(serializers.Serializer):
    """Serializer for AI content generation requests"""
    content = serializers.CharField(max_length=10000)
    platform = serializers.ChoiceField(
        choices=['facebook', 'instagram', 'twitter', 'linkedin'],
        default='facebook'
    )
    action = serializers.ChoiceField(
        choices=['improve', 'shorten', 'expand', 'rewrite'],
        default='improve'
    )


class AIIdeaRequestSerializer(serializers.Serializer):
    """Serializer for AI idea generation requests"""
    topics = serializers.ListField(
        child=serializers.CharField(max_length=100),
        required=False
    )
    business_type = serializers.CharField(max_length=200, required=False)
    platform = serializers.ChoiceField(
        choices=['facebook', 'instagram', 'twitter', 'linkedin'],
        default='facebook'
    )
    count = serializers.IntegerField(min_value=1, max_value=10, default=5)
    
    def validate(self, data):
        if not data.get('topics') and not data.get('business_type'):
            raise serializers.ValidationError(
                "Either topics or business_type must be provided"
            )
        return data


class CalendarPostSerializer(serializers.ModelSerializer):
    """Simplified serializer for calendar view"""
    platform_names = serializers.SerializerMethodField()
    
    class Meta:
        model = SocialPost
        fields = [
            'id', 'content', 'post_type', 'status', 'scheduled_at',
            'published_at', 'platform_names', 'created_at'
        ]
    
    def get_platform_names(self, obj):
        """Get list of platform names for this post"""
        return [target.account.platform.display_name for target in obj.targets.all()]


class AnalyticsSummarySerializer(serializers.Serializer):
    """Serializer for analytics summary data"""
    total_posts = serializers.IntegerField()
    total_likes = serializers.IntegerField()
    total_comments = serializers.IntegerField()
    total_shares = serializers.IntegerField()
    total_reach = serializers.IntegerField()
    total_impressions = serializers.IntegerField()
    avg_engagement_rate = serializers.FloatField()
    top_performing_post = SocialPostSerializer()
    platform_breakdown = serializers.DictField()
    recent_performance = serializers.ListField()


class EngagementInboxSerializer(serializers.Serializer):
    """Serializer for engagement inbox data"""
    total_comments = serializers.IntegerField()
    unreplied_count = serializers.IntegerField()
    flagged_count = serializers.IntegerField()
    negative_sentiment_count = serializers.IntegerField()
    high_priority_count = serializers.IntegerField()
    recent_comments = SocialCommentSerializer(many=True)


class MediaUploadSerializer(serializers.Serializer):
    """Serializer for media upload requests"""
    file = serializers.FileField()
    analyze_content = serializers.BooleanField(default=True)
    generate_alt_text = serializers.BooleanField(default=True)
    
    def validate_file(self, value):
        """Validate uploaded file"""
        # Check file size (max 100MB)
        if value.size > 100 * 1024 * 1024:
            raise serializers.ValidationError("File size cannot exceed 100MB")
        
        # Check file type
        allowed_types = [
            'image/jpeg', 'image/png', 'image/gif', 'image/webp',
            'video/mp4', 'video/avi', 'video/mov', 'video/wmv'
        ]
        
        if value.content_type not in allowed_types:
            raise serializers.ValidationError(
                f"File type {value.content_type} is not supported"
            )
        
        return value