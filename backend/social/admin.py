from django.contrib import admin
from .models import (
    SocialPlatform, SocialAccount, SocialPost, SocialPostTarget,
    SocialAnalytics, SocialComment, SocialIdea, SocialHashtag,
    SocialQueue, SocialMediaFile
)


@admin.register(SocialPlatform)
class SocialPlatformAdmin(admin.ModelAdmin):
    list_display = ['display_name', 'name', 'is_active', 'supports_scheduling', 'max_text_length']
    list_filter = ['is_active', 'supports_scheduling', 'supports_hashtags']
    search_fields = ['display_name', 'name']
    ordering = ['display_name']


@admin.register(SocialAccount)
class SocialAccountAdmin(admin.ModelAdmin):
    list_display = ['account_name', 'platform', 'status', 'is_active', 'created_at']
    list_filter = ['platform', 'status', 'is_active', 'created_at']
    search_fields = ['account_name', 'account_username']
    readonly_fields = ['access_token', 'refresh_token', 'created_at', 'updated_at']
    ordering = ['-created_at']
    
    fieldsets = (
        ('Account Info', {
            'fields': ('platform', 'account_id', 'account_name', 'account_username', 'profile_picture_url')
        }),
        ('Connection', {
            'fields': ('status', 'access_token', 'refresh_token', 'token_expires_at', 'permissions')
        }),
        ('Settings', {
            'fields': ('is_active', 'auto_publish', 'timezone')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )


@admin.register(SocialPost)
class SocialPostAdmin(admin.ModelAdmin):
    list_display = ['content_preview', 'post_type', 'status', 'scheduled_at', 'created_by', 'created_at']
    list_filter = ['post_type', 'status', 'ai_generated', 'created_at']
    search_fields = ['content', 'hashtags', 'created_by__email']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']
    
    def content_preview(self, obj):
        return obj.content[:100] + "..." if len(obj.content) > 100 else obj.content
    content_preview.short_description = 'Content Preview'
    
    fieldsets = (
        ('Content', {
            'fields': ('content', 'post_type', 'hashtags', 'mentions', 'first_comment')
        }),
        ('Media', {
            'fields': ('media_files', 'thumbnail_url')
        }),
        ('Scheduling', {
            'fields': ('status', 'scheduled_at', 'published_at')
        }),
        ('AI Assistance', {
            'fields': ('ai_generated', 'original_content', 'ai_suggestions'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )


@admin.register(SocialPostTarget)
class SocialPostTargetAdmin(admin.ModelAdmin):
    list_display = ['post_content_preview', 'account', 'status', 'published_at', 'retry_count']
    list_filter = ['status', 'account__platform', 'published_at', 'created_at']
    search_fields = ['post__content', 'account__account_name', 'platform_post_id']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']
    
    def post_content_preview(self, obj):
        content = obj.content_override or obj.post.content
        return content[:50] + "..." if len(content) > 50 else content
    post_content_preview.short_description = 'Content Preview'


@admin.register(SocialAnalytics)
class SocialAnalyticsAdmin(admin.ModelAdmin):
    list_display = ['post_target', 'likes', 'comments', 'shares', 'impressions', 'reach', 'last_updated']
    list_filter = ['last_updated', 'post_target__account__platform']
    search_fields = ['post_target__post__content', 'post_target__account__account_name']
    readonly_fields = ['created_at', 'last_updated']
    ordering = ['-last_updated']


@admin.register(SocialComment)
class SocialCommentAdmin(admin.ModelAdmin):
    list_display = ['author_name', 'content_preview', 'account', 'comment_type', 'sentiment', 'is_replied', 'platform_created_at']
    list_filter = ['comment_type', 'sentiment', 'is_replied', 'is_flagged', 'account__platform', 'platform_created_at']
    search_fields = ['content', 'author_name', 'author_username', 'account__account_name']
    readonly_fields = ['platform_comment_id', 'platform_created_at', 'created_at', 'updated_at']
    ordering = ['-platform_created_at']
    
    def content_preview(self, obj):
        return obj.content[:100] + "..." if len(obj.content) > 100 else obj.content
    content_preview.short_description = 'Content Preview'
    
    fieldsets = (
        ('Comment Info', {
            'fields': ('account', 'post_target', 'platform_comment_id', 'comment_type', 'content')
        }),
        ('Author', {
            'fields': ('author_name', 'author_username', 'author_profile_url', 'author_avatar_url')
        }),
        ('AI Analysis', {
            'fields': ('sentiment', 'ai_tags', 'priority_score')
        }),
        ('Management', {
            'fields': ('is_replied', 'is_flagged', 'is_hidden', 'replied_at', 'replied_by')
        }),
        ('Timestamps', {
            'fields': ('platform_created_at', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )


@admin.register(SocialIdea)
class SocialIdeaAdmin(admin.ModelAdmin):
    list_display = ['title', 'category', 'status', 'priority', 'ai_generated', 'created_by', 'created_at']
    list_filter = ['status', 'priority', 'ai_generated', 'category', 'created_at']
    search_fields = ['title', 'description', 'content_draft', 'tags']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-priority', '-created_at']
    
    fieldsets = (
        ('Content', {
            'fields': ('title', 'description', 'content_draft')
        }),
        ('Categorization', {
            'fields': ('category', 'tags', 'target_platforms', 'priority')
        }),
        ('Status & AI', {
            'fields': ('status', 'ai_generated', 'ai_prompt')
        }),
        ('Links & Media', {
            'fields': ('related_post', 'inspiration_urls', 'reference_images'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )


@admin.register(SocialHashtag)
class SocialHashtagAdmin(admin.ModelAdmin):
    list_display = ['display_tag', 'usage_count', 'avg_engagement', 'category', 'is_trending', 'is_favorite']
    list_filter = ['is_trending', 'is_favorite', 'is_blocked', 'category']
    search_fields = ['tag', 'display_tag', 'category']
    readonly_fields = ['usage_count', 'last_used', 'created_at', 'updated_at']
    ordering = ['-usage_count', 'tag']


@admin.register(SocialQueue)
class SocialQueueAdmin(admin.ModelAdmin):
    list_display = ['name', 'account', 'is_active', 'posts_per_day', 'optimize_timing']
    list_filter = ['is_active', 'optimize_timing', 'account__platform']
    search_fields = ['name', 'account__account_name']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['name']


@admin.register(SocialMediaFile)
class SocialMediaFileAdmin(admin.ModelAdmin):
    list_display = ['file_name', 'file_type', 'file_size_mb', 'usage_count', 'uploaded_by', 'created_at']
    list_filter = ['file_type', 'is_appropriate', 'created_at']
    search_fields = ['file_name', 'alt_text', 'ai_tags', 'uploaded_by__email']
    readonly_fields = ['file_size', 'width', 'height', 'duration', 'usage_count', 'last_used', 'created_at', 'updated_at']
    ordering = ['-created_at']
    
    def file_size_mb(self, obj):
        return f"{obj.file_size_mb} MB"
    file_size_mb.short_description = 'File Size'
    
    fieldsets = (
        ('File Info', {
            'fields': ('file', 'file_name', 'file_type', 'file_size', 'mime_type')
        }),
        ('Media Properties', {
            'fields': ('width', 'height', 'duration')
        }),
        ('AI Analysis', {
            'fields': ('alt_text', 'ai_tags', 'is_appropriate')
        }),
        ('Usage', {
            'fields': ('usage_count', 'last_used')
        }),
        ('Metadata', {
            'fields': ('uploaded_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
