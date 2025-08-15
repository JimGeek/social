from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'platforms', views.SocialPlatformViewSet)
router.register(r'accounts', views.SocialAccountViewSet)
router.register(r'posts', views.SocialPostViewSet)
router.register(r'post-targets', views.SocialPostTargetViewSet)
router.register(r'analytics-data', views.SocialAnalyticsViewSet)
router.register(r'comments', views.SocialCommentViewSet)
router.register(r'ideas', views.SocialIdeaViewSet)
router.register(r'hashtags', views.SocialHashtagViewSet)
router.register(r'queues', views.SocialQueueViewSet)
router.register(r'media-files', views.SocialMediaFileViewSet)

urlpatterns = [
    path('', include(router.urls)),
    
    # User authentication endpoints
    path('auth/login/', views.LoginView.as_view(), name='auth-login'),
    path('auth/register/', views.RegisterView.as_view(), name='auth-register'),
    path('auth/profile/', views.ProfileView.as_view(), name='auth-profile'),
    
    # OAuth and authentication endpoints
    path('auth/facebook/connect/', views.FacebookConnectView.as_view(), name='facebook-connect'),
    path('auth/facebook/callback/', views.FacebookCallbackView.as_view(), name='facebook-callback'),
    path('auth/instagram/connect/', views.InstagramConnectView.as_view(), name='instagram-connect'),
    path('auth/instagram/callback/', views.InstagramCallbackView.as_view(), name='instagram-callback'),
    path('auth/instagram-direct/connect/', views.InstagramDirectConnectView.as_view(), name='instagram-direct-connect'),
    path('auth/instagram-direct/callback/', views.InstagramDirectCallbackView.as_view(), name='instagram-direct-callback'),
    path('auth/linkedin/connect/', views.LinkedInConnectView.as_view(), name='linkedin-connect'),
    path('auth/linkedin/callback/', views.LinkedInCallbackView.as_view(), name='linkedin-callback'),
    path('auth/disconnect/<uuid:account_id>/', views.DisconnectAccountView.as_view(), name='disconnect-account'),
    
    # Post publishing endpoints
    path('posts/<uuid:post_id>/publish/', views.PublishPostView.as_view(), name='publish-post'),
    path('posts/<uuid:post_id>/schedule/', views.SchedulePostView.as_view(), name='schedule-post'),
    path('posts/<uuid:post_id>/cancel/', views.CancelPostView.as_view(), name='cancel-post'),
    
    # AI assistance endpoints
    path('ai/content-suggestions/', views.AIContentSuggestionsView.as_view(), name='ai-content-suggestions'),
    path('ai/hashtag-suggestions/', views.AIHashtagSuggestionsView.as_view(), name='ai-hashtag-suggestions'),
    path('ai/generate-ideas/', views.AIGenerateIdeasView.as_view(), name='ai-generate-ideas'),
    path('ai/analyze-content/', views.AIAnalyzeContentView.as_view(), name='ai-analyze-content'),
    
    # Analytics endpoints
    path('analytics/summary/', views.AnalyticsSummaryView.as_view(), name='analytics-summary'),
    path('analytics/platform/<str:platform>/', views.PlatformAnalyticsView.as_view(), name='platform-analytics'),
    path('analytics/sync/', views.SyncAnalyticsView.as_view(), name='sync-analytics'),
    path('analytics/export/', views.ExportAnalyticsView.as_view(), name='export-analytics'),
    
    # Advanced Analytics endpoints
    path('analytics/post-performance/', views.PostPerformanceView.as_view(), name='post-performance'),
    path('analytics/engagement-analysis/', views.EngagementAnalysisView.as_view(), name='engagement-analysis'),
    path('analytics/auto-sync/', views.AutoSyncView.as_view(), name='auto-sync'),
    
    # Engagement endpoints
    path('engagement/inbox/', views.EngagementInboxView.as_view(), name='engagement-inbox'),
    path('engagement/reply/', views.ReplyToCommentView.as_view(), name='reply-comment'),
    path('engagement/flag/<uuid:comment_id>/', views.FlagCommentView.as_view(), name='flag-comment'),
    
    # Calendar and scheduling
    path('calendar/posts/', views.CalendarPostsView.as_view(), name='calendar-posts'),
    path('calendar/optimal-times/', views.OptimalTimesView.as_view(), name='optimal-times'),
    
    # Media management
    path('media/upload/', views.MediaUploadView.as_view(), name='media-upload'),
    path('media/validate/', views.MediaValidationView.as_view(), name='media-validate'),
    path('media/analyze/', views.MediaAnalysisView.as_view(), name='media-analyze'),
    
    # Platform capabilities
    path('platforms/capabilities/', views.PlatformCapabilitiesView.as_view(), name='platform-capabilities'),
    
    # Live data collection endpoints
    path('live-data/collect/', views.LiveDataCollectionView.as_view(), name='live-data-collect'),
    path('live-data/trending/', views.TrendingContentView.as_view(), name='trending-content'),
    path('live-data/connection-status/', views.AccountConnectionStatusView.as_view(), name='account-connection-status'),
    
    # Diagnostics endpoints
    path('diagnostics/', views.SocialMediaDiagnosticsView.as_view(), name='social-media-diagnostics'),
    
    # Sentry Monitoring endpoints
    path('log/', views.SentryLogsView.as_view(), name='sentry-logs'),
    path('log/test/', views.SentryTestView.as_view(), name='sentry-test'),
    path('metrics/', views.ApplicationMetricsView.as_view(), name='app-metrics'),
]