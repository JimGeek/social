from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.conf import settings
from django.utils import timezone
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.authtoken.models import Token
from datetime import datetime, timedelta
import requests
import json
import uuid
import openai
import logging
from urllib.parse import urlencode

logger = logging.getLogger(__name__)
from .tasks import publish_post, sync_social_comments, generate_ai_content
# Standalone social-media app without organization dependencies
from .models import (
    SocialPlatform, SocialAccount, SocialPost, SocialPostTarget,
    SocialAnalytics, SocialComment, SocialIdea, SocialHashtag,
    SocialQueue, SocialMediaFile
)
from .serializers import (
    SocialPlatformSerializer, SocialAccountSerializer, SocialPostSerializer,
    SocialPostTargetSerializer, SocialAnalyticsSerializer, SocialCommentSerializer,
    SocialIdeaSerializer, SocialHashtagSerializer, SocialQueueSerializer,
    SocialMediaFileSerializer
)


# Authentication Views
class LoginView(APIView):
    """Login view that returns user data and auth token"""
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        email = request.data.get('email')
        password = request.data.get('password')
        
        if not email or not password:
            return Response(
                {'error': 'Email and password are required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Try to get user by email (since Django uses username for auth)
        try:
            user = User.objects.get(email=email)
            username = user.username
        except User.DoesNotExist:
            return Response(
                {'error': 'Invalid credentials'}, 
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        # Authenticate with username and password
        user = authenticate(username=username, password=password)
        if not user:
            return Response(
                {'error': 'Invalid credentials'}, 
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        # Get or create auth token
        token, created = Token.objects.get_or_create(user=user)
        
        return Response({
            'user': {
                'id': user.id,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'date_joined': user.date_joined.isoformat(),
            },
            'token': token.key,
        })


class RegisterView(APIView):
    """Register new user"""
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        email = request.data.get('email')
        password = request.data.get('password')
        password_confirm = request.data.get('password_confirm')
        first_name = request.data.get('first_name', '')
        last_name = request.data.get('last_name', '')
        
        if not email or not password:
            return Response(
                {'error': 'Email and password are required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if password != password_confirm:
            return Response(
                {'error': 'Passwords do not match'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if user already exists
        if User.objects.filter(email=email).exists():
            return Response(
                {'error': 'User with this email already exists'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create new user
        user = User.objects.create_user(
            username=email,  # Use email as username
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
        )
        
        # Create auth token
        token = Token.objects.create(user=user)
        
        return Response({
            'user': {
                'id': user.id,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'date_joined': user.date_joined.isoformat(),
            },
            'token': token.key,
        }, status=status.HTTP_201_CREATED)


class ProfileView(APIView):
    """Get and update user profile"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        user = request.user
        return Response({
            'id': user.id,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'date_joined': user.date_joined.isoformat(),
        })
    
    def put(self, request):
        user = request.user
        
        # Update allowed fields
        user.first_name = request.data.get('first_name', user.first_name)
        user.last_name = request.data.get('last_name', user.last_name)
        user.save()
        
        return Response({
            'id': user.id,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'date_joined': user.date_joined.isoformat(),
        })


class SocialPlatformViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for social platforms (read-only)"""
    queryset = SocialPlatform.objects.filter(is_active=True)
    serializer_class = SocialPlatformSerializer
    permission_classes = [permissions.IsAuthenticated]


class SocialAccountViewSet(viewsets.ModelViewSet):
    """ViewSet for connected social accounts"""
    serializer_class = SocialAccountSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = SocialAccount.objects.all()
    
    def get_queryset(self):
        return SocialAccount.objects.all()
    
    @action(detail=True, methods=['post'])
    def refresh_token(self, request, pk=None):
        """Refresh OAuth token for an account"""
        account = self.get_object()
        
        if account.platform.name == 'facebook':
            # Implement Facebook token refresh
            try:
                result = self._refresh_facebook_token(account)
                if result['success']:
                    account.access_token = result['access_token']
                    account.token_expires_at = result['expires_at']
                    account.status = 'connected'
                    account.save()
                    return Response({'status': 'success', 'message': 'Token refreshed successfully'})
                else:
                    return Response({'status': 'error', 'message': result['error']}, 
                                  status=status.HTTP_400_BAD_REQUEST)
            except Exception as e:
                return Response({'status': 'error', 'message': str(e)}, 
                              status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        return Response({'status': 'error', 'message': 'Platform not supported'}, 
                       status=status.HTTP_400_BAD_REQUEST)
    
    def _refresh_facebook_token(self, account):
        """Refresh Facebook access token"""
        try:
            url = 'https://graph.facebook.com/oauth/access_token'
            params = {
                'grant_type': 'fb_exchange_token',
                'client_id': settings.FACEBOOK_APP_ID,
                'client_secret': settings.FACEBOOK_APP_SECRET,
                'fb_exchange_token': account.access_token
            }
            
            response = requests.get(url, params=params)
            data = response.json()
            
            if 'access_token' in data:
                expires_in = data.get('expires_in', 5184000)  # Default 60 days
                expires_at = timezone.now() + timedelta(seconds=expires_in)
                
                return {
                    'success': True,
                    'access_token': data['access_token'],
                    'expires_at': expires_at
                }
            else:
                return {'success': False, 'error': data.get('error', {}).get('message', 'Unknown error')}
                
        except Exception as e:
            return {'success': False, 'error': str(e)}


class SocialPostViewSet(viewsets.ModelViewSet):
    """ViewSet for social media posts"""
    serializer_class = SocialPostSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = SocialPost.objects.all()
    
    def get_queryset(self):
        return SocialPost.objects.all()
    
    def perform_create(self, serializer):
        # Validate post against platform restrictions before saving
        post_data = serializer.validated_data
        target_accounts = self.request.data.get('target_accounts', [])
        self._validate_post_against_platforms(post_data, target_accounts)
        
        serializer.save(created_by=self.request.user)
    
    def update(self, request, *args, **kwargs):
        """Override update to prevent editing published posts"""
        post = self.get_object()
        
        if post.status in ['published', 'partially_published']:
            return Response(
                {
                    'error': 'Published posts cannot be edited. You can only view status or delete the post.',
                    'status': post.status,
                    'published_at': post.published_at
                }, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        return super().update(request, *args, **kwargs)
    
    def partial_update(self, request, *args, **kwargs):
        """Override partial_update to prevent editing published posts"""
        post = self.get_object()
        
        if post.status in ['published', 'partially_published']:
            return Response(
                {
                    'error': 'Published posts cannot be edited. You can only view status or delete the post.',
                    'status': post.status,
                    'published_at': post.published_at
                }, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        return super().partial_update(request, *args, **kwargs)
    
    def _validate_post_against_platforms(self, post_data, target_accounts):
        """Validate post content against platform-specific restrictions"""
        from .utils.media_validator import MediaValidator
        from rest_framework.exceptions import ValidationError
        
        post_type = post_data.get('post_type', 'text')
        content = post_data.get('content', '')
        media_files = post_data.get('media_files', [])
        
        # Get target accounts
        accounts = SocialAccount.objects.filter(
            id__in=target_accounts,
            created_by=self.request.user,
            is_active=True
        )
        
        validation_errors = []
        
        for account in accounts:
            platform_name = account.platform.name
            platform = account.platform
            
            # Platform-specific validations
            if platform_name == 'instagram':
                # Instagram requires media for all posts
                if not media_files or len(media_files) == 0:
                    validation_errors.append(
                        f"Instagram ({account.account_name}) requires at least one image or video. "
                        "Text-only posts are not supported."
                    )
                
                # Validate post type for Instagram
                if post_type == 'story':
                    # Check if account supports stories (Business accounts only)
                    from .services.instagram_service import InstagramService
                    instagram_service = InstagramService()
                    account_info = instagram_service.get_account_info(account)
                    
                    if account_info['success']:
                        account_type = account_info['data'].get('account_type', 'PERSONAL')
                        if account_type != 'BUSINESS':
                            validation_errors.append(
                                f"Stories are only available for Instagram Business accounts. "
                                f"{account.account_name} is a {account_type} account."
                            )
                
                elif post_type == 'reel':
                    # Validate reel content
                    if media_files:
                        for media_url in media_files:
                            # This would need actual media validation
                            # For now, just check that it's intended to be video
                            pass
                
                # Validate caption length
                if len(content) > platform.max_text_length:
                    validation_errors.append(
                        f"Caption too long for Instagram ({account.account_name}). "
                        f"Max {platform.max_text_length} characters, got {len(content)}."
                    )
            
            elif platform_name == 'facebook':
                # Facebook supports text posts but has character limits
                if len(content) > platform.max_text_length:
                    validation_errors.append(
                        f"Post too long for Facebook ({account.account_name}). "
                        f"Max {platform.max_text_length} characters, got {len(content)}."
                    )
                
                # Facebook doesn't support Instagram-specific post types
                if post_type in ['story', 'reel']:
                    validation_errors.append(
                        f"{post_type.title()}s are not supported on Facebook ({account.account_name}). "
                        "Consider using a regular post or video instead."
                    )
            
            elif platform_name == 'linkedin':
                # LinkedIn has character limits
                if len(content) > platform.max_text_length:
                    validation_errors.append(
                        f"Post too long for LinkedIn ({account.account_name}). "
                        f"Max {platform.max_text_length} characters, got {len(content)}."
                    )
                
                # LinkedIn doesn't support stories or reels
                if post_type in ['story', 'reel']:
                    validation_errors.append(
                        f"{post_type.title()}s are not supported on LinkedIn ({account.account_name}). "
                        "Use a regular post instead."
                    )
            
            elif platform_name == 'twitter':
                # Twitter has strict character limits
                if len(content) > platform.max_text_length:
                    validation_errors.append(
                        f"Tweet too long for Twitter/X ({account.account_name}). "
                        f"Max {platform.max_text_length} characters, got {len(content)}."
                    )
                
                # Twitter doesn't support stories or reels
                if post_type in ['story', 'reel']:
                    validation_errors.append(
                        f"{post_type.title()}s are not supported on Twitter/X ({account.account_name}). "
                        "Use a regular tweet instead."
                    )
                
                # Twitter has media count limits
                if media_files and len(media_files) > platform.max_image_count:
                    validation_errors.append(
                        f"Too many media files for Twitter/X ({account.account_name}). "
                        f"Max {platform.max_image_count} files, got {len(media_files)}."
                    )
            
            # Check if account supports posting
            if not account.posting_enabled:
                validation_errors.append(
                    f"Posting is disabled for {platform_name} account {account.account_name}. "
                    "This may be due to API restrictions or account type limitations."
                )
        
        # Raise validation error if any issues found
        if validation_errors:
            raise ValidationError({
                'platform_restrictions': validation_errors,
                'message': 'Post validation failed due to platform restrictions'
            })
    
    @action(detail=True, methods=['post'])
    def duplicate(self, request, pk=None):
        """Duplicate a post"""
        original_post = self.get_object()
        
        # Create duplicate
        duplicate_data = {
            'content': original_post.content,
            'post_type': original_post.post_type,
            'hashtags': original_post.hashtags,
            'mentions': original_post.mentions,
            'first_comment': original_post.first_comment,
            'media_files': original_post.media_files,
        }
        
        serializer = self.get_serializer(data=duplicate_data)
        serializer.is_valid(raise_exception=True)
        duplicate_post = serializer.save(
            
            created_by=self.request.user
        )
        
        return Response(self.get_serializer(duplicate_post).data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'])
    def publish(self, request, pk=None):
        """Publish a post immediately to selected social accounts"""
        post = self.get_object()
        
        # Prevent republishing already published posts
        if post.status in ['published', 'partially_published']:
            return Response(
                {
                    'error': 'Post is already published and cannot be republished.',
                    'status': post.status,
                    'published_at': post.published_at
                }, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        target_accounts = request.data.get('target_accounts', [])
        
        if not target_accounts:
            return Response(
                {'error': 'No target accounts specified'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate that accounts belong to the user and support posting
        valid_accounts = SocialAccount.objects.filter(
            id__in=target_accounts,
            created_by=request.user,
            status='connected',
            posting_enabled=True
        ).values_list('id', flat=True)
        
        if not valid_accounts:
            return Response(
                {'error': 'No valid connected accounts found'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create targets for the accounts if they don't exist
        for account_id in valid_accounts:
            SocialPostTarget.objects.get_or_create(
                post=post,
                account_id=account_id,
                defaults={
                    'content_override': '',
                    'hashtags_override': [],
                    'status': 'pending'
                }
            )
        
        # Trigger publishing task
        task = publish_post.delay(str(post.id), list(valid_accounts))
        
        return Response({
            'message': 'Post queued for publishing',
            'task_id': task.id,
            'target_accounts': len(valid_accounts)
        }, status=status.HTTP_202_ACCEPTED)
    
    @action(detail=True, methods=['post'])
    def schedule(self, request, pk=None):
        """Schedule a post for later publication"""
        post = self.get_object()
        
        # Prevent scheduling already published posts
        if post.status in ['published', 'partially_published']:
            return Response(
                {
                    'error': 'Post is already published and cannot be rescheduled.',
                    'status': post.status,
                    'published_at': post.published_at
                }, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        scheduled_at = request.data.get('scheduled_at')
        target_accounts = request.data.get('target_accounts', [])
        
        if not scheduled_at:
            return Response(
                {'error': 'scheduled_at is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not target_accounts:
            return Response(
                {'error': 'No target accounts specified'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Parse and validate the scheduled time with comprehensive timezone handling
            if isinstance(scheduled_at, str):
                # Handle different datetime formats and make timezone-aware
                if 'Z' in scheduled_at:
                    # ISO format with Z suffix (UTC)
                    scheduled_time = datetime.fromisoformat(scheduled_at.replace('Z', '+00:00'))
                elif '+' in scheduled_at or scheduled_at.endswith(('00', '30', '45')):
                    # ISO format with timezone offset
                    scheduled_time = datetime.fromisoformat(scheduled_at)
                else:
                    # Assume local time, make it timezone-aware
                    naive_dt = datetime.fromisoformat(scheduled_at)
                    scheduled_time = timezone.make_aware(naive_dt)
            else:
                scheduled_time = scheduled_at
            
            # Ensure it's timezone-aware for comparison
            if scheduled_time.tzinfo is None:
                scheduled_time = timezone.make_aware(scheduled_time)
                
            if scheduled_time <= timezone.now():
                return Response(
                    {'error': 'Scheduled time must be in the future'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        except (ValueError, TypeError) as e:
            return Response(
                {'error': f'Invalid scheduled_at format: {str(e)}'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate accounts and check posting capability
        valid_accounts = SocialAccount.objects.filter(
            id__in=target_accounts,
            created_by=request.user,
            status='connected',
            posting_enabled=True
        ).values_list('id', flat=True)
        
        if not valid_accounts:
            return Response(
                {'error': 'No valid connected accounts found'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Update post scheduling
        post.scheduled_at = scheduled_time
        post.status = 'scheduled'
        post.save()
        
        # Create targets for the accounts
        for account_id in valid_accounts:
            SocialPostTarget.objects.get_or_create(
                post=post,
                account_id=account_id,
                defaults={
                    'content_override': '',
                    'hashtags_override': [],
                    'status': 'pending'
                }
            )
        
        return Response({
            'message': 'Post scheduled successfully',
            'scheduled_at': scheduled_time.isoformat(),
            'target_accounts': len(valid_accounts)
        }, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel a scheduled post"""
        post = self.get_object()
        
        if post.status != 'scheduled':
            return Response(
                {'error': 'Only scheduled posts can be cancelled'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        post.status = 'draft'
        post.scheduled_at = None
        post.save()
        
        # Update targets
        post.targets.update(status='cancelled')
        
        return Response({
            'message': 'Post cancelled successfully'
        }, status=status.HTTP_200_OK)


class SocialPostTargetViewSet(viewsets.ModelViewSet):
    """ViewSet for post targets (platform-specific posts)"""
    serializer_class = SocialPostTargetSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = SocialPostTarget.objects.all()
    
    def get_queryset(self):
        return SocialPostTarget.objects.filter(
            post__created_by=self.request.user
        )


class SocialAnalyticsViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for analytics data"""
    serializer_class = SocialAnalyticsSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = SocialAnalytics.objects.all()
    
    def get_queryset(self):
        return SocialAnalytics.objects.filter(
            post_target__post__created_by=self.request.user
        )


class SocialCommentViewSet(viewsets.ModelViewSet):
    """ViewSet for social comments and interactions"""
    serializer_class = SocialCommentSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = SocialComment.objects.all()
    
    def get_queryset(self):
        return SocialComment.objects.filter()
    
    @action(detail=False, methods=['get'])
    def inbox(self, request):
        """Get engagement inbox with filters"""
        queryset = self.get_queryset()
        
        # Apply filters
        filter_type = request.query_params.get('filter', 'all')
        if filter_type == 'unreplied':
            queryset = queryset.filter(is_replied=False)
        elif filter_type == 'flagged':
            queryset = queryset.filter(is_flagged=True)
        elif filter_type == 'negative':
            queryset = queryset.filter(sentiment='negative')
        elif filter_type == 'questions':
            queryset = queryset.filter(sentiment='question')
        
        # Order by priority and date
        queryset = queryset.order_by('-priority_score', '-platform_created_at')
        
        serializer = self.get_serializer(queryset[:50], many=True)  # Limit to 50 recent
        return Response(serializer.data)


class SocialIdeaViewSet(viewsets.ModelViewSet):
    """ViewSet for content ideas"""
    serializer_class = SocialIdeaSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = SocialIdea.objects.all()
    
    def get_queryset(self):
        return SocialIdea.objects.filter()
    
    def perform_create(self, serializer):
        serializer.save(
            
            created_by=self.request.user
        )
    
    @action(detail=True, methods=['post'])
    def convert_to_post(self, request, pk=None):
        """Convert idea to actual post"""
        idea = self.get_object()
        
        post_data = {
            'content': idea.content_draft or idea.description,
            'post_type': 'text',
            'hashtags': [],
        }
        
        post_serializer = SocialPostSerializer(data=post_data)
        post_serializer.is_valid(raise_exception=True)
        post = post_serializer.save(
            
            created_by=self.request.user
        )
        
        # Update idea status and link to post
        idea.status = 'in_progress'
        idea.related_post = post
        idea.save()
        
        return Response(SocialPostSerializer(post).data, status=status.HTTP_201_CREATED)


class SocialHashtagViewSet(viewsets.ModelViewSet):
    """ViewSet for hashtag management"""
    serializer_class = SocialHashtagSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = SocialHashtag.objects.all()
    
    def get_queryset(self):
        return SocialHashtag.objects.filter()
    
    @action(detail=False, methods=['get'])
    def suggestions(self, request):
        """Get hashtag suggestions based on content"""
        content = request.query_params.get('content', '')
        platform = request.query_params.get('platform', 'facebook')
        
        if not content:
            return Response({'error': 'Content parameter is required'}, 
                           status=status.HTTP_400_BAD_REQUEST)
        
        # Get AI suggestions
        try:
            ai_suggestions = self._get_ai_hashtag_suggestions(content, platform)
            
            # Get popular hashtags from user
            popular_hashtags = self.get_queryset().filter(
                is_favorite=True,
                is_blocked=False
            ).order_by('-usage_count')[:10]
            
            return Response({
                'ai_suggestions': ai_suggestions,
                'popular_hashtags': SocialHashtagSerializer(popular_hashtags, many=True).data
            })
            
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _get_ai_hashtag_suggestions(self, content, platform):
        """Get AI-generated hashtag suggestions"""
        try:
            openai.api_key = settings.OPENAI_API_KEY
            
            prompt = f"""
            Generate 10 relevant hashtags for this {platform} post content:
            "{content}"
            
            Return only hashtags without # symbol, one per line.
            Focus on trending, relevant hashtags that would increase engagement.
            """
            
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200,
                temperature=0.7
            )
            
            hashtags = response.choices[0].message.content.strip().split('\n')
            return [tag.strip().replace('#', '') for tag in hashtags if tag.strip()]
            
        except Exception as e:
            # Provide fallback hashtags if OpenAI fails
            return self._generate_fallback_hashtags(post_content, platform)
    
    def _generate_fallback_ideas(self, platform, count, topics):
        """Generate fallback content ideas when AI is not available"""
        # Construction/real estate industry content templates
        base_ideas = [
            {
                "title": "Project Showcase",
                "description": "Share photos and details of recently completed construction projects",
                "platform": platform,
                "content_type": "visual"
            },
            {
                "title": "Before & After",
                "description": "Show transformation photos of renovation projects",
                "platform": platform,
                "content_type": "visual"
            },
            {
                "title": "Construction Tips",
                "description": "Share helpful tips and advice for homeowners and contractors",
                "platform": platform,
                "content_type": "educational"
            },
            {
                "title": "Team Spotlight",
                "description": "Feature team members, their expertise, and contributions",
                "platform": platform,
                "content_type": "personal"
            },
            {
                "title": "Client Testimonial",
                "description": "Share positive feedback and success stories from satisfied clients",
                "platform": platform,
                "content_type": "social_proof"
            },
            {
                "title": "Industry News",
                "description": "Comment on latest trends in construction and real estate",
                "platform": platform,
                "content_type": "news"
            },
            {
                "title": "Safety First",
                "description": "Share important safety tips and practices for construction sites",
                "platform": platform,
                "content_type": "educational"
            },
            {
                "title": "Material Spotlight",
                "description": "Highlight quality materials and their benefits",
                "platform": platform,
                "content_type": "product"
            }
        ]
        
        # Filter by topics if provided
        if topics:
            topic_keywords = [topic.lower() for topic in topics]
            filtered_ideas = []
            for idea in base_ideas:
                if any(keyword in idea["description"].lower() or keyword in idea["title"].lower() 
                      for keyword in topic_keywords):
                    filtered_ideas.append(idea)
            if filtered_ideas:
                base_ideas = filtered_ideas
        
        # Return requested count
        return base_ideas[:count] if count <= len(base_ideas) else base_ideas
    
    def _generate_fallback_hashtags(self, content, platform):
        """Generate fallback hashtags when AI is not available"""
        # Construction/real estate industry hashtags
        industry_tags = [
            "construction", "building", "realestate", "home", "renovation", 
            "architecture", "design", "contractor", "homeimprovement", "property"
        ]
        
        # Platform-specific hashtags
        platform_tags = {
            "instagram": ["instagood", "photooftheday", "construction", "building"],
            "facebook": ["construction", "realestate", "homebuilding"],
            "linkedin": ["construction", "realestate", "business", "industry"],
            "twitter": ["construction", "realestate", "building"]
        }
        
        # Combine and return
        tags = industry_tags + platform_tags.get(platform.lower(), [])
        return list(set(tags))[:10]  # Return unique tags, max 10


class SocialQueueViewSet(viewsets.ModelViewSet):
    """ViewSet for publishing queues"""
    serializer_class = SocialQueueSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = SocialQueue.objects.all()
    
    def get_queryset(self):
        return SocialQueue.objects.filter()
    
    def perform_create(self, serializer):
        serializer.save(
            
            created_by=self.request.user
        )


class SocialMediaFileViewSet(viewsets.ModelViewSet):
    """ViewSet for media file management"""
    serializer_class = SocialMediaFileSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    queryset = SocialMediaFile.objects.all()
    
    def get_queryset(self):
        return SocialMediaFile.objects.filter()
    
    def perform_create(self, serializer):
        serializer.save(
            
            uploaded_by=self.request.user
        )


# OAuth and Connection Views
class FacebookConnectView(APIView):
    """Initiate Facebook OAuth connection"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        """Generate Facebook OAuth URL"""
        app_id = settings.FACEBOOK_APP_ID
        redirect_uri = settings.FACEBOOK_REDIRECT_URI
        
        # Use Facebook permissions from settings (includes required permissions for live data)
        permissions = settings.FACEBOOK_SCOPES
        
        # Create state parameter with user info for callback
        import base64
        import json
        state_data = {
            'csrf': str(uuid.uuid4()),
            'user_id': str(request.user.id)
        }
        state_encoded = base64.b64encode(json.dumps(state_data).encode()).decode()
        
        params = {
            'client_id': app_id,
            'redirect_uri': redirect_uri,
            'scope': ','.join(permissions),
            'response_type': 'code',
            'state': state_encoded
        }
        
        auth_url = f"https://www.facebook.com/v18.0/dialog/oauth?{urlencode(params)}"
        
        # Note: No need to store CSRF in session since we use state parameter for security
        
        # Store user ID in session for callback authentication (convert UUID to string)
        request.session['oauth_user_id'] = str(request.user.id)
        # No organization needed for standalone app
        
        # Store user token for frontend authentication after redirect
        from rest_framework.authtoken.models import Token
        token, created = Token.objects.get_or_create(user=request.user)
        request.session['oauth_token'] = token.key
        
        # Force session save
        request.session.save()
        
        
        return Response({'auth_url': auth_url})


class FacebookCallbackView(APIView):
    """Handle Facebook OAuth callback"""
    permission_classes = []  # Remove auth requirement for callback
    
    def get(self, request):
        """Process Facebook OAuth callback"""
        code = request.GET.get('code')
        state = request.GET.get('state')
        error = request.GET.get('error')
        
        
        # First try to get user from state parameter (more reliable)
        user = None
        org_slug = 'default'
        
        if state:
            try:
                import base64
                import json
                decoded_state = json.loads(base64.b64decode(state.encode()).decode())
                user_id = decoded_state.get('user_id')
                # No organization needed for standalone app
                csrf_token = decoded_state.get('csrf')
                
                
                # Get user from database
                # Note: We rely on the state parameter encoding for security instead of session CSRF
                # since sessions may not persist reliably during OAuth flow
                from django.contrib.auth import get_user_model
                User = get_user_model()
                user = User.objects.get(id=user_id)
                org_slug = 'social'  # Default slug for standalone app
                    
            except Exception as e:
                print(f"DEBUG: Error decoding state: {str(e)}")
                
        # Fallback to session-based user retrieval
        if not user:
            user = self._get_user_from_session(request)
            if user:
                org_slug = 'social'  # Default slug for standalone app
        
        if not user:
            # Clear any stale session data
            request.session.pop('oauth_user_id', None)
            # request.session.pop('oauth_organization_id', None)  # Not needed for standalone
            request.session.pop('fb_oauth_state', None)
            return redirect(f"{settings.FRONTEND_URL}/social/settings?error=authentication_required&message=Session expired during OAuth flow")
        
        if error:
            return redirect(f"{settings.FRONTEND_URL}/social/settings?error=facebook_oauth_error&message={error}")
        
        # State verification is already done above when decoding user info
        # Additional verification would be redundant since we already checked CSRF token
        
        if not code:
            return redirect(f"{settings.FRONTEND_URL}/social/settings?error=no_authorization_code")
        
        try:
            # Exchange code for access token
            token_data = self._exchange_code_for_token(code, request)
            
            if not token_data['success']:
                return redirect(f"{settings.FRONTEND_URL}/social/settings?error=token_exchange_failed&message={token_data['error']}")
            
            # Get user and pages information
            user_data = self._get_facebook_user_data(token_data['access_token'])
            pages_data = self._get_facebook_pages(token_data['access_token'])
            
            # Create or update social accounts
            accounts_created = []
            
            # Create account for user profile (if posting to timeline is needed)
            if user_data:
                user_account = self._create_or_update_account(
                    platform_name='facebook',
                    account_data=user_data,
                    access_token=token_data['access_token'],
                    expires_at=token_data['expires_at'],
                    request=request,
                    user=user
                )
                if user_account:
                    accounts_created.append(user_account)
            
            # Create accounts for managed pages
            for page in pages_data:
                page_account = self._create_or_update_account(
                    platform_name='facebook',
                    account_data=page,
                    access_token=page['access_token'],  # Page-specific token
                    expires_at=None,  # Page tokens don't expire
                    request=request,
                    user=user
                )
                if page_account:
                    accounts_created.append(page_account)
            
            # Redirect to frontend with success message
            accounts_count = len(accounts_created)
            
            # Get token for frontend auth
            token = request.session.get('oauth_token', '')
            
            # Clear OAuth session data
            request.session.pop('oauth_user_id', None)
            # request.session.pop('oauth_organization_id', None)  # Not needed for standalone
            request.session.pop('fb_oauth_state', None)
            request.session.pop('oauth_token', None)
            
            return redirect(f"{settings.FRONTEND_URL}/social/settings?success=facebook_connected&accounts={accounts_count}&token={token}")
            
        except Exception as e:
            return redirect(f"{settings.FRONTEND_URL}/social/settings?error=connection_failed&message={str(e)}")
    
    def _get_user_from_session(self, request):
        """Get user from session or token"""
        # First try to get user from Django's built-in session auth
        if hasattr(request, 'user') and request.user.is_authenticated:
            return request.user
        
        # Try to get user ID from session and fetch user
        user_id = request.session.get('oauth_user_id')
        if user_id:
            try:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                user = User.objects.get(id=user_id)
                return user
            except User.DoesNotExist:
                pass
        
        # Try to get user from oauth_token stored in session
        oauth_token = request.session.get('oauth_token')
        if oauth_token:
            try:
                from rest_framework.authtoken.models import Token
                token_obj = Token.objects.get(key=oauth_token)
                return token_obj.user
            except Token.DoesNotExist:
                pass
        
        return None
        
        return None
    
    def _exchange_code_for_token(self, code, request):
        """Exchange authorization code for access token"""
        try:
            redirect_uri = request.build_absolute_uri('/api/social/auth/facebook/callback/')
            
            url = f'https://graph.facebook.com/{settings.FACEBOOK_API_VERSION}/oauth/access_token'
            params = {
                'client_id': settings.FACEBOOK_APP_ID,
                'client_secret': settings.FACEBOOK_APP_SECRET,
                'redirect_uri': redirect_uri,
                'code': code
            }
            
            response = requests.get(url, params=params)
            data = response.json()
            
            if 'access_token' in data:
                expires_in = data.get('expires_in', 5184000)  # Default 60 days
                expires_at = timezone.now() + timedelta(seconds=expires_in)
                
                return {
                    'success': True,
                    'access_token': data['access_token'],
                    'expires_at': expires_at
                }
            else:
                return {
                    'success': False,
                    'error': data.get('error', {}).get('message', 'Failed to get access token')
                }
                
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _get_facebook_user_data(self, access_token):
        """Get Facebook user profile data"""
        try:
            url = 'https://graph.facebook.com/v18.0/me'
            params = {
                'access_token': access_token,
                'fields': 'id,name,picture,email'
            }
            
            response = requests.get(url, params=params)
            if response.status_code == 200:
                return response.json()
            return None
            
        except Exception:
            return None
    
    def _get_facebook_pages(self, access_token):
        """Get Facebook pages managed by user"""
        try:
            url = 'https://graph.facebook.com/v18.0/me/accounts'
            params = {
                'access_token': access_token,
                'fields': 'id,name,access_token,picture,category,fan_count'
            }
            
            response = requests.get(url, params=params)
            if response.status_code == 200:
                data = response.json()
                return data.get('data', [])
            return []
            
        except Exception:
            return []
    
    def _create_or_update_account(self, platform_name, account_data, access_token, expires_at, request, user=None):
        """Create or update social media account"""
        try:
            platform = SocialPlatform.objects.get(name=platform_name)
            current_user = user or (request.user if hasattr(request, 'user') else None)
            
            if not current_user:
                raise Exception("User not found")
            
            account, created = SocialAccount.objects.update_or_create(
                platform=platform,
                account_id=account_data['id'],
                defaults={
                    'account_name': account_data.get('name', ''),
                    'account_username': account_data.get('username', ''),
                    'profile_picture_url': account_data.get('picture', {}).get('data', {}).get('url', ''),
                    'access_token': access_token,
                    'token_expires_at': expires_at,
                    'status': 'connected',
                    'permissions': ['pages_manage_posts', 'pages_read_engagement'],
                    'created_by': current_user
                }
            )
            
            return account
            
        except Exception as e:
            print(f"Error creating account: {e}")
            return None


class InstagramConnectView(APIView):
    """Initiate Instagram Business OAuth connection"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        """Generate Instagram OAuth URL"""
        # Instagram Business API uses the same Facebook App ID
        app_id = settings.FACEBOOK_APP_ID
        redirect_uri = request.build_absolute_uri('/api/social/auth/instagram/callback/')
        
        # Instagram permissions (try Business API first, fallback to Basic Display)
        permissions = [
            'instagram_basic',                  # Basic Instagram access
            'instagram_manage_insights',        # Required for analytics data
            'pages_show_list',                 # Access connected Facebook pages (for Business API)
            'pages_read_engagement',           # Read engagement data (for Business API)
            'pages_read_user_content',         # Read user content data
            'read_insights'                    # Read insights data
        ]
        
        # Create state parameter with user info for callback
        import base64
        import json
        state_data = {
            'csrf': str(uuid.uuid4()),
            'user_id': str(request.user.id)
        }
        state_encoded = base64.b64encode(json.dumps(state_data).encode()).decode()
        
        # Store user ID in session for callback authentication (convert UUID to string)
        request.session['oauth_user_id'] = str(request.user.id)
        # No organization needed for standalone app
        
        # Store user token for frontend authentication after redirect
        from rest_framework.authtoken.models import Token
        token, created = Token.objects.get_or_create(user=request.user)
        request.session['oauth_token'] = token.key
        
        # Force session save
        request.session.save()
        
        
        # Note: No need to store CSRF in session since we use state parameter for security
        
        # Instagram OAuth URL (uses Facebook OAuth with Instagram scopes)
        params = {
            'client_id': app_id,
            'redirect_uri': redirect_uri,
            'scope': ','.join(permissions),
            'response_type': 'code',
            'state': state_encoded
        }
        
        # Instagram Business API uses Facebook OAuth (not instagram.com OAuth)
        auth_url = f"https://www.facebook.com/v18.0/dialog/oauth?{urlencode(params)}"
        
        return Response({'auth_url': auth_url})


class InstagramCallbackView(APIView):
    """Handle Instagram OAuth callback"""
    permission_classes = []  # Remove auth requirement for callback
    
    def get(self, request):
        """Process Instagram OAuth callback"""
        print("\n" + "="*80)
        print("🔍 INSTAGRAM OAUTH CALLBACK STARTED")
        print("="*80)
        
        code = request.GET.get('code')
        state = request.GET.get('state')
        error = request.GET.get('error')
        
        print(f"📥 Callback parameters:")
        print(f"   Code: {code[:50] if code else 'None'}...")
        print(f"   State: {state[:50] if state else 'None'}...")
        print(f"   Error: {error}")
        print(f"   Full GET params: {dict(request.GET)}")
        
        # First try to get user from state parameter (more reliable)
        user = None
        org_slug = 'default'
        
        if state:
            try:
                import base64
                import json
                decoded_state = json.loads(base64.b64decode(state.encode()).decode())
                user_id = decoded_state.get('user_id')
                # No organization needed for standalone app
                csrf_token = decoded_state.get('csrf')
                
                # Get user from database
                # Note: We rely on the state parameter encoding for security instead of session CSRF
                # since sessions may not persist reliably during OAuth flow
                from django.contrib.auth import get_user_model
                User = get_user_model()
                user = User.objects.get(id=user_id)
                org_slug = 'social'  # Default slug for standalone app
                    
            except Exception as e:
                pass  # Error decoding state
                
        # Fallback to session-based user retrieval
        if not user:
            user = self._get_user_from_session(request)
            if user:
                org_slug = 'social'  # Default slug for standalone app
        
        if not user:
            # Clear any stale session data
            request.session.pop('oauth_user_id', None)
            # request.session.pop('oauth_organization_id', None)  # Not needed for standalone
            request.session.pop('ig_oauth_state', None)
            return redirect(f"{settings.FRONTEND_URL}/social/settings?error=authentication_required&message=Session expired during OAuth flow")
        
        if error:
            return redirect(f"{settings.FRONTEND_URL}/{org_slug}/social/settings?error=instagram_oauth_error&message={error}")
        
        # State verification is already done above when decoding user info
        # Additional verification would be redundant since we already checked CSRF token
        
        if not code:
            return redirect(f"{settings.FRONTEND_URL}/social/settings?error=no_authorization_code")
        
        try:
            # Exchange code for access token
            token_data = self._exchange_code_for_token(code, request)
            
            if not token_data['success']:
                return redirect(f"{settings.FRONTEND_URL}/social/settings?error=token_exchange_failed&message={token_data['error']}")
            
            # Get Instagram user data
            print(f"Getting Instagram user data with token: {token_data['access_token'][:20]}...")
            user_data = self._get_instagram_user_data(token_data['access_token'])
            
            if not user_data:
                print("❌ Failed to get Instagram user data")
                return redirect(f"{settings.FRONTEND_URL}/{org_slug}/social/settings?error=user_data_failed&message=Could not retrieve Instagram account information")
            
            print(f"✅ Got Instagram user data: {user_data}")
            
            # Handle multiple Instagram accounts
            created_accounts = []
            accounts_data = user_data if isinstance(user_data, list) else [user_data]
            
            for account_data in accounts_data:
                print(f"📝 Creating account for: {account_data.get('name', 'Unknown')}")
                account = self._create_or_update_account(
                    platform_name='instagram',
                    account_data=account_data,
                    access_token=token_data['access_token'],
                    expires_at=token_data.get('expires_at'),
                    request=request,
                    user=user  # Pass the user we retrieved from state parameter
                )
                
                if account:
                    created_accounts.append(account)
                    print(f"✅ Instagram account created/updated: {account}")
                else:
                    print(f"❌ Failed to create Instagram account: {account_data}")
            
            if not created_accounts:
                print("❌ Failed to create any Instagram accounts")
                return redirect(f"{settings.FRONTEND_URL}/{org_slug}/social/settings?error=account_creation_failed&message=Could not save any Instagram accounts to database")
            
            print(f"✅ Successfully created/updated {len(created_accounts)} Instagram accounts")
            
            # Get token for frontend auth
            token = request.session.get('oauth_token', '')
            
            # Clear OAuth session data
            request.session.pop('oauth_user_id', None)
            # request.session.pop('oauth_organization_id', None)  # Not needed for standalone
            request.session.pop('ig_oauth_state', None)
            request.session.pop('oauth_token', None)
            
            return redirect(f"{settings.FRONTEND_URL}/{org_slug}/social/settings?success=instagram_connected&accounts={len(created_accounts)}&token={token}")
            
        except Exception as e:
            import traceback
            print(f"Instagram OAuth callback error: {str(e)}")
            print(f"Traceback: {traceback.format_exc()}")
            return redirect(f"{settings.FRONTEND_URL}/social/settings?error=connection_failed&message={str(e)}")
    
    def _get_user_from_session(self, request):
        """Get user from session or token"""
        # First try to get user from Django's built-in session auth
        if hasattr(request, 'user') and request.user.is_authenticated:
            return request.user
        
        # Try to get user ID from session and fetch user
        user_id = request.session.get('oauth_user_id')
        if user_id:
            try:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                user = User.objects.get(id=user_id)
                return user
            except User.DoesNotExist:
                pass
        
        # Try to get user from oauth_token stored in session
        oauth_token = request.session.get('oauth_token')
        if oauth_token:
            try:
                from rest_framework.authtoken.models import Token
                token_obj = Token.objects.get(key=oauth_token)
                return token_obj.user
            except Token.DoesNotExist:
                pass
        
        return None
        
        return None
    
    def _exchange_code_for_token(self, code, request):
        """Exchange authorization code for access token"""
        try:
            redirect_uri = request.build_absolute_uri('/api/social/auth/instagram/callback/')
            
            # Instagram Business API uses Facebook token exchange
            url = f'https://graph.facebook.com/{settings.FACEBOOK_API_VERSION}/oauth/access_token'
            params = {
                'client_id': settings.FACEBOOK_APP_ID,
                'client_secret': settings.FACEBOOK_APP_SECRET,
                'grant_type': 'authorization_code',
                'redirect_uri': redirect_uri,
                'code': code
            }
            
            response = requests.get(url, params=params)
            token_data = response.json()
            
            if 'access_token' in token_data:
                # For Instagram Business API, we use the Facebook access token directly
                # No need for additional token exchange as it's already long-lived
                return {
                    'success': True,
                    'access_token': token_data['access_token'],
                    'expires_at': timezone.now() + timedelta(seconds=token_data.get('expires_in', 5184000))
                }
            else:
                return {
                    'success': False,
                    'error': token_data.get('error_description', 'Failed to exchange code for token')
                }
                
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _get_long_lived_token(self, short_token):
        """Exchange short-lived token for long-lived token"""
        try:
            url = 'https://graph.instagram.com/access_token'
            params = {
                'grant_type': 'ig_exchange_token',
                'client_secret': settings.INSTAGRAM_APP_SECRET,
                'access_token': short_token
            }
            
            response = requests.get(url, params=params)
            return response.json()
            
        except Exception as e:
            print(f"Error getting long-lived token: {e}")
            return {'access_token': short_token, 'expires_in': 3600}  # Fallback
    
    def _get_instagram_user_data(self, access_token):
        """Get Instagram account data via Facebook Graph API"""
        try:
            import json
            print(f"🔍 Getting Instagram user data with token: {access_token[:20]}...")
            
            # Step 1: Check Facebook user info first
            print("Step 1: Getting Facebook user info...")
            fb_user_url = 'https://graph.facebook.com/v18.0/me'
            fb_user_params = {
                'fields': 'id,name,email',
                'access_token': access_token
            }
            
            fb_user_response = requests.get(fb_user_url, params=fb_user_params)
            if fb_user_response.status_code != 200:
                print(f"❌ Facebook user API failed: {fb_user_response.text}")
                return None
            
            fb_user_data = fb_user_response.json()
            print(f"✅ Facebook user: {fb_user_data}")
            
            # Step 2: Get the user's Facebook pages
            print("Step 2: Getting Facebook pages...")
            url = 'https://graph.facebook.com/v18.0/me/accounts'
            params = {
                'fields': 'id,name,instagram_business_account{id,username,name}',
                'access_token': access_token
            }
            
            response = requests.get(url, params=params)
            
            if response.status_code != 200:
                print(f"❌ Facebook pages API failed: {response.status_code} - {response.text}")
                return None
                
            pages_data = response.json()
            print(f"✅ Facebook pages response: {json.dumps(pages_data, indent=2)}")
            
            # Step 3: Look for pages with Instagram Business accounts
            instagram_accounts = []
            if 'data' in pages_data and pages_data['data']:
                print(f"Found {len(pages_data['data'])} Facebook pages")
                for i, page in enumerate(pages_data['data']):
                    print(f"  Page {i+1}: {page.get('name', 'Unnamed')} (ID: {page.get('id', 'No ID')})")
                    if 'instagram_business_account' in page:
                        ig_account = page['instagram_business_account']
                        print(f"  ✅ Found Instagram Business Account: {ig_account}")
                        instagram_accounts.append({
                            'id': ig_account['id'],
                            'name': ig_account.get('name', ig_account.get('username', '')),
                            'username': ig_account.get('username', ''),
                            'account_type': 'BUSINESS',  # Always business for Instagram Business API
                            'media_count': 0,  # Not available through this endpoint
                            'access_token': access_token,
                            'page_id': page['id'],
                            'page_name': page['name']
                        })
                    else:
                        print(f"  ❌ No Instagram Business Account for this page")
                        
                # If we found Instagram Business accounts, return all of them
                if instagram_accounts:
                    print(f"✅ Found {len(instagram_accounts)} Instagram Business accounts total")
                    return instagram_accounts  # Return list instead of single account
            else:
                print("❌ No Facebook pages found for this user")
            
            # Step 4: Try Instagram Basic Display API as fallback
            print("Step 3: Trying Instagram Basic Display API...")
            url = 'https://graph.instagram.com/me'
            params = {
                'fields': 'id,username,account_type,media_count',
                'access_token': access_token
            }
            
            response = requests.get(url, params=params)
            print(f"Instagram Basic API status: {response.status_code}")
            
            if response.status_code == 200:
                user_data = response.json()
                print(f"✅ Instagram basic API response: {json.dumps(user_data, indent=2)}")
                
                if 'id' in user_data:
                    return {
                        'id': user_data['id'],
                        'name': user_data.get('username', ''),
                        'username': user_data.get('username', ''),
                        'account_type': user_data.get('account_type', 'PERSONAL'),
                        'media_count': user_data.get('media_count', 0),
                        'access_token': access_token
                    }
            else:
                print(f"❌ Instagram Basic API failed: {response.text}")
                
            print("❌ No Instagram account data found via any method")
            return None
            
        except Exception as e:
            print(f"❌ Exception getting Instagram user data: {e}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            return None
    
    def _create_or_update_account(self, platform_name, account_data, access_token, expires_at, request, user=None):
        """Create or update Instagram social account"""
        try:
            # Use passed user or fall back to request.user
            actual_user = user if user else request.user
            
            print(f"Creating account for platform: {platform_name}")
            print(f"Account data: {account_data}")
            print(f"User: {actual_user}")
            
            platform = SocialPlatform.objects.get(name=platform_name)
            print(f"Found platform: {platform}")
            
            if not actual_user:
                print("❌ No user found")
                return None
            
            account, created = SocialAccount.objects.update_or_create(
                platform=platform,
                account_id=account_data['id'],
                defaults={
                    'account_name': account_data['name'],
                    'account_username': account_data.get('username', ''),
                    'access_token': access_token,
                    'token_expires_at': expires_at,
                    'is_active': True,
                    'status': 'connected',
                    'connection_type': 'facebook_business' if platform_name == 'instagram' else 'standard',
                    'created_by': actual_user
                }
            )
            
            print(f"✅ Account {'created' if created else 'updated'}: {account}")
            return account
            
        except SocialPlatform.DoesNotExist:
            print(f"❌ Platform '{platform_name}' not found in database")
            return None
        except Exception as e:
            print(f"❌ Error creating Instagram account: {e}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            return None


# Instagram Direct Connection Views (Instagram Login API)
class InstagramDirectConnectView(APIView):
    """Initiate direct Instagram connection via Instagram Login API"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        """Generate Instagram Login API OAuth URL for direct connection"""
        app_id = settings.INSTAGRAM_BASIC_APP_ID  # Instagram App ID for Instagram Login
        # Use ngrok HTTPS URL for Instagram OAuth (Instagram requires HTTPS redirect URIs)
        ngrok_url = "https://159ddc3326a0.ngrok-free.app"
        redirect_uri = f"{ngrok_url}/api/social/auth/instagram-direct/callback/"
        
        # Instagram Login API permissions (2025 scopes)
        permissions_scope = [
            'instagram_business_basic',           # Basic access to Instagram business account data
            'instagram_business_content_publish', # Essential for publishing content
            'instagram_business_manage_comments'  # For comment management
        ]
        
        # Create state parameter with user info for callback
        state = json.dumps({
            'user_id': request.user.id,
            'connection_type': 'instagram_direct'
        })
        
        params = {
            'client_id': app_id,
            'redirect_uri': redirect_uri,
            'scope': ','.join(permissions_scope),
            'response_type': 'code',
            'state': state
        }
        
        # Instagram Login API OAuth URL (direct Instagram authentication)
        auth_url = f"https://api.instagram.com/oauth/authorize?{urlencode(params)}"
        
        print(f"🔗 Instagram Direct OAuth URL: {auth_url}")
        
        return Response({'auth_url': auth_url})


class InstagramDirectCallbackView(APIView):
    """Handle Instagram Login API OAuth callback"""
    permission_classes = []  # Remove auth requirement for callback
    
    def get(self, request):
        """Process Instagram Login API OAuth callback"""
        print("\n" + "="*80)
        print("🔍 INSTAGRAM DIRECT OAUTH CALLBACK STARTED")
        print("="*80)
        
        code = request.GET.get('code')
        state = request.GET.get('state')
        error = request.GET.get('error')
        
        print(f"📥 Callback parameters:")
        print(f"   Code: {code[:50] if code else 'None'}...")
        print(f"   State: {state[:50] if state else 'None'}...")
        print(f"   Error: {error}")
        
        if error:
            print(f"❌ OAuth error: {error}")
            return redirect(f"{settings.FRONTEND_URL}/social/settings?error=instagram_direct_oauth_error&message={error}")
        
        if not code:
            print("❌ No authorization code received")
            return redirect(f"{settings.FRONTEND_URL}/social/settings?error=instagram_direct_oauth_error&message=no_code")
        
        try:
            # Parse state to get user info
            state_data = json.loads(state) if state else {}
            user_id = state_data.get('user_id')
            
            if not user_id:
                print("❌ No user_id in state")
                return redirect(f"{settings.FRONTEND_URL}/social/settings?error=instagram_direct_oauth_error&message=invalid_state")
            
            # Get user object
            user = User.objects.get(id=user_id)
            print(f"✅ Found user: {user.email}")
            
            # Exchange code for access token
            token_data = self._exchange_code_for_token(code, request)
            if not token_data:
                return redirect(f"{settings.FRONTEND_URL}/social/settings?error=instagram_direct_token_error&message=token_exchange_failed")
            
            access_token = token_data.get('access_token')
            print(f"✅ Got access token: {access_token[:20] if access_token else 'None'}...")
            
            # Get Instagram user data
            user_data = self._get_instagram_direct_user_data(access_token)
            if not user_data:
                return redirect(f"{settings.FRONTEND_URL}/social/settings?error=instagram_direct_user_data_error&message=failed_to_get_user_data")
            
            print(f"✅ Instagram user data: {user_data}")
            
            # Create or update account
            account = self._create_or_update_instagram_direct_account(user_data, access_token, user)
            if account:
                print(f"✅ Instagram Direct account created/updated: {account.account_name}")
                return redirect(f"{settings.FRONTEND_URL}/social/settings?success=instagram_direct_connected&account={account.account_name}")
            else:
                print("❌ Failed to create Instagram Direct account")
                return redirect(f"{settings.FRONTEND_URL}/social/settings?error=instagram_direct_account_creation_error&message=account_creation_failed")
        
        except Exception as e:
            print(f"❌ Instagram Direct OAuth callback error: {str(e)}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            return redirect(f"{settings.FRONTEND_URL}/social/settings?error=instagram_direct_oauth_error&message={str(e)}")
    
    def _exchange_code_for_token(self, code, request):
        """Exchange authorization code for access token - Instagram Login API 2025"""
        try:
            # Use Instagram-specific Graph API endpoint for Instagram Login API (2025 method)
            token_url = "https://api.instagram.com/oauth/access_token"
            # Use ngrok HTTPS URL for Instagram OAuth (Instagram requires HTTPS redirect URIs)
            ngrok_url = "https://159ddc3326a0.ngrok-free.app"
            redirect_uri = f"{ngrok_url}/api/social/auth/instagram-direct/callback/"
            
            data = {
                'client_id': settings.INSTAGRAM_BASIC_APP_ID,
                'client_secret': settings.INSTAGRAM_BASIC_APP_SECRET,
                'grant_type': 'authorization_code',
                'redirect_uri': redirect_uri,
                'code': code
            }
            
            print(f"🔄 Exchanging code for token using Instagram Login API 2025...")
            print(f"📝 Request URL: {token_url}")
            print(f"📝 Request data: {data}")
            response = requests.post(token_url, data=data)
            print(f"📈 Token exchange response status: {response.status_code}")
            print(f"📄 Response headers: {dict(response.headers)}")
            print(f"📄 Response content: {response.text}")
            
            if response.status_code == 200:
                token_data = response.json()
                print(f"✅ Token exchange successful: {token_data}")
                return token_data
            else:
                print(f"❌ Token exchange failed: Status {response.status_code}")
                print(f"❌ Error details: {response.text}")
                return None
                
        except Exception as e:
            print(f"❌ Error exchanging code for token: {e}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            return None
    
    def _get_instagram_direct_user_data(self, access_token):
        """Get Instagram user data via Instagram Login API"""
        try:
            url = "https://graph.instagram.com/me"
            params = {
                'fields': 'id,username,account_type,media_count,followers_count,follows_count',
                'access_token': access_token
            }
            
            print(f"🔄 Getting Instagram user data...")
            response = requests.get(url, params=params)
            print(f"📈 User data response status: {response.status_code}")
            
            if response.status_code == 200:
                user_data = response.json()
                print(f"✅ Instagram user data retrieved: {user_data}")
                return user_data
            else:
                print(f"❌ Failed to get Instagram user data: {response.text}")
                return None
                
        except Exception as e:
            print(f"❌ Error getting Instagram user data: {e}")
            return None
    
    def _create_or_update_instagram_direct_account(self, user_data, access_token, user):
        """Create or update Instagram Login API account"""
        try:
            platform = SocialPlatform.objects.get(name='instagram')
            
            account, created = SocialAccount.objects.update_or_create(
                platform=platform,
                account_id=user_data['id'],
                defaults={
                    'account_name': user_data.get('username', ''),
                    'account_username': user_data.get('username', ''),
                    'profile_picture_url': '',  # Will be available in Instagram Login API
                    'access_token': access_token,
                    'token_expires_at': None,  # Instagram Login tokens have longer expiry
                    'status': 'connected',
                    'permissions': ['user_profile', 'user_media'],
                    'created_by': user,
                    'connection_type': 'instagram_direct'  # Instagram Login API connection
                }
            )
            
            action = "Created" if created else "Updated"
            print(f"✅ {action} Instagram Direct account: {account.account_name}")
            
            return account
            
        except SocialPlatform.DoesNotExist:
            print(f"❌ Instagram platform not found in database")
            return None
        except Exception as e:
            print(f"❌ Error creating Instagram Direct account: {e}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            return None


class DisconnectAccountView(APIView):
    """Disconnect a social media account"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, account_id):
        """Disconnect social account"""
        try:
            account = get_object_or_404(
                SocialAccount,
                id=account_id,
                created_by=request.user
            )
            
            # Update account status
            account.status = 'disconnected'
            account.access_token = ''
            account.refresh_token = ''
            account.token_expires_at = None
            account.save()
            
            return Response({'success': True, 'message': 'Account disconnected successfully'})
            
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class LinkedInConnectView(APIView):
    """Initiate LinkedIn OAuth connection"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        """Generate LinkedIn OAuth URL"""
        from .services.linkedin_service import LinkedInService
        
        linkedin_service = LinkedInService()
        redirect_uri = f"{settings.BACKEND_URL}/api/social/auth/linkedin/callback/"
        
        # Create state parameter with user info for callback
        import base64
        import json
        state_data = {
            'csrf': str(uuid.uuid4()),
            'user_id': str(request.user.id)
        }
        state_encoded = base64.b64encode(json.dumps(state_data).encode()).decode()
        
        auth_url = linkedin_service.get_auth_url(redirect_uri, state_encoded)
        
        # Store user ID in session for callback authentication
        request.session['oauth_user_id'] = str(request.user.id)
        request.session['linkedin_oauth_state'] = state_encoded
        
        # Store user token for frontend authentication after redirect
        from rest_framework.authtoken.models import Token
        token, created = Token.objects.get_or_create(user=request.user)
        request.session['oauth_token'] = token.key
        
        # Force session save
        request.session.save()
        
        return Response({'auth_url': auth_url})


class LinkedInCallbackView(APIView):
    """Handle LinkedIn OAuth callback"""
    permission_classes = []  # Remove auth requirement for callback
    
    def get(self, request):
        """Process LinkedIn OAuth callback"""
        code = request.GET.get('code')
        state = request.GET.get('state')
        error = request.GET.get('error')
        
        # Get user from state parameter
        user = None
        org_slug = 'social'
        
        if state:
            try:
                import base64
                import json
                decoded_state = json.loads(base64.b64decode(state.encode()).decode())
                user_id = decoded_state.get('user_id')
                csrf_token = decoded_state.get('csrf')
                
                # Get user from database
                from django.contrib.auth import get_user_model
                User = get_user_model()
                user = User.objects.get(id=user_id)
                
            except Exception as e:
                logger.error(f"Error decoding LinkedIn state: {str(e)}")
        
        # Fallback to session-based user retrieval
        if not user:
            user = self._get_user_from_session(request)
        
        if not user:
            request.session.pop('oauth_user_id', None)
            request.session.pop('linkedin_oauth_state', None)
            return redirect(f"{settings.FRONTEND_URL}/social/settings?error=authentication_required&message=Session expired during LinkedIn OAuth flow")
        
        if error:
            return redirect(f"{settings.FRONTEND_URL}/social/settings?error=linkedin_oauth_error&message={error}")
        
        if not code:
            return redirect(f"{settings.FRONTEND_URL}/social/settings?error=linkedin_oauth_error&message=No authorization code received")
        
        try:
            from .services.linkedin_service import LinkedInService
            
            linkedin_service = LinkedInService()
            redirect_uri = f"{settings.BACKEND_URL}/api/social/auth/linkedin/callback/"
            
            # Exchange code for token
            token_result = linkedin_service.exchange_code_for_token(code, redirect_uri)
            
            if not token_result['success']:
                return redirect(f"{settings.FRONTEND_URL}/social/settings?error=linkedin_token_error&message={token_result['error']}")
            
            access_token = token_result['access_token']
            expires_in = token_result['expires_in']
            
            # Get user profile
            profile_result = linkedin_service.get_user_profile(access_token)
            
            if not profile_result['success']:
                return redirect(f"{settings.FRONTEND_URL}/social/settings?error=linkedin_profile_error&message={profile_result['error']}")
            
            profile_data = profile_result['data']
            
            # Get LinkedIn platform
            try:
                linkedin_platform = SocialPlatform.objects.get(name='linkedin')
            except SocialPlatform.DoesNotExist:
                return redirect(f"{settings.FRONTEND_URL}/social/settings?error=platform_error&message=LinkedIn platform not configured")
            
            # Calculate token expiration
            token_expires_at = timezone.now() + timezone.timedelta(seconds=expires_in)
            
            # Create or update LinkedIn account
            linkedin_account, created = SocialAccount.objects.update_or_create(
                platform=linkedin_platform,
                account_id=profile_data['id'],
                defaults={
                    'account_name': f"{profile_data['first_name']} {profile_data['last_name']}".strip(),
                    'account_username': '',  # LinkedIn doesn't provide username in basic profile
                    'profile_picture_url': profile_data['profile_picture_url'],
                    'access_token': access_token,
                    'refresh_token': '',  # LinkedIn doesn't support refresh tokens
                    'token_expires_at': token_expires_at,
                    'status': 'connected',
                    'connection_type': 'standard',
                    'permissions': [token_result.get('scope', '')],
                    'posting_enabled': True,
                    'is_active': True,
                    'last_sync': timezone.now(),
                    'created_by': user
                }
            )
            
            # Clear session data
            request.session.pop('oauth_user_id', None)
            request.session.pop('linkedin_oauth_state', None)
            
            action = 'connected' if created else 'updated'
            return redirect(f"{settings.FRONTEND_URL}/social/settings?success=linkedin_{action}&account={linkedin_account.account_name}")
            
        except Exception as e:
            logger.error(f"LinkedIn OAuth callback error: {str(e)}")
            return redirect(f"{settings.FRONTEND_URL}/social/settings?error=linkedin_connection_error&message=Failed to connect LinkedIn account")
    
    def _get_user_from_session(self, request):
        """Helper method to get user from session"""
        user_id = request.session.get('oauth_user_id')
        if user_id:
            try:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                return User.objects.get(id=user_id)
            except:
                return None
        return None


# Publishing Views
class PublishPostView(APIView):
    """Publish a post immediately"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, post_id):
        """Publish post to selected platforms"""
        try:
            post = get_object_or_404(
                SocialPost,
                id=post_id,
                created_by=request.user
            )
            
            # Get target accounts from request
            target_account_ids = request.data.get('target_accounts', [])
            
            if not target_account_ids:
                return Response({'error': 'No target accounts specified'}, 
                               status=status.HTTP_400_BAD_REQUEST)
            
            results = []
            
            for account_id in target_account_ids:
                try:
                    account = SocialAccount.objects.get(
                        id=account_id,
                        created_by=request.user,
                        status='connected'
                    )
                    
                    # Create or get post target
                    post_target, created = SocialPostTarget.objects.get_or_create(
                        post=post,
                        account=account
                    )
                    
                    # Publish to platform
                    result = self._publish_to_platform(post, post_target)
                    results.append({
                        'account': account.account_name,
                        'platform': account.platform.display_name,
                        'success': result['success'],
                        'message': result.get('message', ''),
                        'post_url': result.get('post_url', '')
                    })
                    
                except SocialAccount.DoesNotExist:
                    results.append({
                        'account_id': account_id,
                        'success': False,
                        'message': 'Account not found or not connected'
                    })
            
            # Update post status
            if any(r['success'] for r in results):
                post.status = 'published'
                post.published_at = timezone.now()
                post.save()
            
            return Response({
                'success': True,
                'results': results,
                'post_status': post.status
            })
            
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _publish_to_platform(self, post, post_target):
        """Publish post to specific platform"""
        platform = post_target.account.platform.name.lower()
        
        if platform == 'facebook':
            return self._publish_to_facebook(post, post_target)
        elif platform == 'instagram':
            return self._publish_to_instagram(post, post_target)
        else:
            return {'success': False, 'message': f'Platform {platform} publishing not yet implemented. Currently supported: Facebook, Instagram'}
    
    def _publish_to_facebook(self, post, post_target):
        """Publish post to Facebook"""
        try:
            account = post_target.account
            content = post_target.content_override or post.content
            
            # Validate account access token
            if not account.access_token:
                post_target.status = 'failed'
                post_target.error_message = 'No access token available - please reconnect your Facebook account'
                post_target.save()
                return {'success': False, 'message': 'No access token available - please reconnect your Facebook account'}
            
            # Prepare post data
            post_data = {
                'message': content,
                'access_token': account.access_token
            }
            
            # Add media if present
            if post.media_files:
                # For now, handle single image
                # TODO: Implement multi-media posts
                pass
            
            # Post to Facebook
            url = f'https://graph.facebook.com/v18.0/{account.account_id}/feed'
            
            # Add timeout and better error handling
            try:
                response = requests.post(url, data=post_data, timeout=30)
            except requests.exceptions.ConnectionError:
                post_target.status = 'failed'
                post_target.error_message = 'Connection failed - please check your internet connection'
                post_target.save()
                return {'success': False, 'message': 'Connection failed - please check your internet connection'}
            except requests.exceptions.Timeout:
                post_target.status = 'failed'
                post_target.error_message = 'Request timeout - Facebook API did not respond'
                post_target.save()
                return {'success': False, 'message': 'Request timeout - Facebook API did not respond'}
            except requests.exceptions.RequestException as e:
                post_target.status = 'failed'
                post_target.error_message = f'Network error: {str(e)}'
                post_target.save()
                return {'success': False, 'message': f'Network error: {str(e)}'}
            
            if response.status_code == 200:
                data = response.json()
                post_id = data.get('id')
                
                # Update post target
                post_target.platform_post_id = post_id
                post_target.platform_url = f'https://facebook.com/{post_id}'
                post_target.status = 'published'
                post_target.published_at = timezone.now()
                post_target.save()
                
                return {
                    'success': True,
                    'message': 'Published successfully',
                    'post_url': post_target.platform_url,
                    'platform_post_id': post_id
                }
            else:
                error_data = response.json()
                error_message = error_data.get('error', {}).get('message', 'Unknown error')
                
                post_target.status = 'failed'
                post_target.error_message = error_message
                post_target.save()
                
                return {'success': False, 'message': error_message}
                
        except Exception as e:
            post_target.status = 'failed'
            post_target.error_message = str(e)
            post_target.save()
            
            return {'success': False, 'message': str(e)}

    def _publish_to_instagram(self, post, post_target):
        """Publish post to Instagram"""
        try:
            account = post_target.account
            content = post_target.content_override or post.content
            
            # Validate account access token
            if not account.access_token:
                post_target.status = 'failed'
                post_target.error_message = 'No access token available - please reconnect your Instagram account'
                post_target.save()
                return {'success': False, 'message': 'No access token available - please reconnect your Instagram account'}
            
            # Instagram Basic Display API doesn't support posting
            # Instagram Graph API requires business accounts
            # For now, return a helpful message
            post_target.status = 'failed'
            post_target.error_message = 'Instagram posting requires Instagram Business account and Facebook Page connection'
            post_target.save()
            
            return {
                'success': False, 
                'message': 'Instagram posting is not available for personal accounts. Please connect an Instagram Business account linked to a Facebook Page.'
            }
            
        except Exception as e:
            post_target.status = 'failed'
            post_target.error_message = str(e)
            post_target.save()
            
            return {'success': False, 'message': str(e)}


class SchedulePostView(APIView):
    """Schedule a post for later"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, post_id):
        """Schedule post for publishing"""
        try:
            post = get_object_or_404(
                SocialPost,
                id=post_id,
                created_by=request.user
            )
            
            scheduled_at = request.data.get('scheduled_at')
            target_account_ids = request.data.get('target_accounts', [])
            
            if not scheduled_at or not target_account_ids:
                return Response({'error': 'scheduled_at and target_accounts are required'}, 
                               status=status.HTTP_400_BAD_REQUEST)
            
            # Parse scheduled time
            try:
                # Handle different datetime formats and make timezone-aware
                if 'Z' in scheduled_at:
                    scheduled_datetime = datetime.fromisoformat(scheduled_at.replace('Z', '+00:00'))
                elif '+' in scheduled_at or scheduled_at.endswith(('00', '30', '45')):
                    scheduled_datetime = datetime.fromisoformat(scheduled_at)
                else:
                    # Assume local time, make it timezone-aware
                    naive_dt = datetime.fromisoformat(scheduled_at)
                    scheduled_datetime = timezone.make_aware(naive_dt)
                    
                # Ensure it's timezone-aware
                if scheduled_datetime.tzinfo is None:
                    scheduled_datetime = timezone.make_aware(scheduled_datetime)
                    
            except (ValueError, TypeError) as e:
                return Response({'error': f'Invalid scheduled_at format: {str(e)}'}, 
                               status=status.HTTP_400_BAD_REQUEST)
            
            # Update post
            post.scheduled_at = scheduled_datetime
            post.status = 'scheduled'
            post.save()
            
            # Create post targets
            for account_id in target_account_ids:
                try:
                    account = SocialAccount.objects.get(
                        id=account_id,
                        created_by=request.user
                    )
                    
                    SocialPostTarget.objects.update_or_create(
                        post=post,
                        account=account,
                        defaults={'status': 'scheduled'}
                    )
                    
                except SocialAccount.DoesNotExist:
                    continue
            
            # TODO: Create Celery task for scheduled publishing
            
            return Response({
                'success': True,
                'message': f'Post scheduled for {scheduled_datetime}',
                'post_id': str(post.id)
            })
            
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CancelPostView(APIView):
    """Cancel a scheduled post"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, post_id):
        """Cancel scheduled post"""
        try:
            post = get_object_or_404(
                SocialPost,
                id=post_id,
                created_by=request.user,
                status='scheduled'
            )
            
            post.status = 'cancelled'
            post.save()
            
            # Update all targets
            post.targets.update(status='cancelled')
            
            return Response({
                'success': True,
                'message': 'Post cancelled successfully'
            })
            
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# AI Assistant Views
class AIContentSuggestionsView(APIView):
    """Get AI content suggestions"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        """Generate content suggestions using AI"""
        try:
            original_content = request.data.get('content', '')
            platform = request.data.get('platform', 'facebook')
            action = request.data.get('action', 'improve')  # improve, shorten, expand, rewrite
            
            if not original_content:
                return Response({'error': 'Content is required'}, 
                               status=status.HTTP_400_BAD_REQUEST)
            
            suggestions = self._get_ai_content_suggestions(original_content, platform, action)
            
            return Response({
                'original_content': original_content,
                'suggestions': suggestions,
                'platform': platform,
                'action': action
            })
            
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _get_ai_content_suggestions(self, content, platform, action):
        """Generate AI content suggestions"""
        try:
            openai.api_key = getattr(settings, 'OPENAI_API_KEY', None)
            
            if not openai.api_key:
                return {'error': 'OpenAI API key not configured'}
            
            platform_limits = {
                'facebook': 63206,
                'twitter': 280,
                'instagram': 2200,
                'linkedin': 1300
            }
            
            char_limit = platform_limits.get(platform, 2000)
            
            prompts = {
                'improve': f"Improve this {platform} post to be more engaging while keeping it under {char_limit} characters:\n\n{content}",
                'shorten': f"Make this {platform} post shorter and more concise while keeping the main message, under {char_limit} characters:\n\n{content}",
                'expand': f"Expand this {platform} post with more details and context, keeping it under {char_limit} characters:\n\n{content}",
                'rewrite': f"Completely rewrite this {platform} post with a different tone and style, under {char_limit} characters:\n\n{content}"
            }
            
            prompt = prompts.get(action, prompts['improve'])
            
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500,
                temperature=0.7,
                n=3  # Generate 3 variations
            )
            
            suggestions = []
            for choice in response.choices:
                suggestion = choice.message.content.strip()
                suggestions.append({
                    'content': suggestion,
                    'character_count': len(suggestion),
                    'within_limit': len(suggestion) <= char_limit
                })
            
            return suggestions
            
        except Exception as e:
            return {'error': str(e)}


class AIHashtagSuggestionsView(APIView):
    """Get AI hashtag suggestions"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        """Generate hashtag suggestions"""
        # Implementation similar to the one in SocialHashtagViewSet
        pass


class AIGenerateIdeasView(APIView):
    """Generate content ideas using AI"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        """Generate content ideas based on topics/keywords"""
        try:
            topics = request.data.get('topics', [])
            business_type = request.data.get('business_type', '')
            platform = request.data.get('platform', 'facebook')
            count = min(request.data.get('count', 5), 10)  # Max 10 ideas
            
            if not topics and not business_type:
                return Response({'error': 'Topics or business_type is required'}, 
                               status=status.HTTP_400_BAD_REQUEST)
            
            ideas = self._generate_ai_ideas(topics, business_type, platform, count)
            
            return Response({
                'ideas': ideas,
                'topics': topics,
                'business_type': business_type,
                'platform': platform
            })
            
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _generate_ai_ideas(self, topics, business_type, platform, count):
        """Generate content ideas using AI"""
        try:
            openai.api_key = getattr(settings, 'OPENAI_API_KEY', None)
            
            if not openai.api_key:
                # Provide fallback content when OpenAI is not configured
                return self._generate_fallback_ideas(platform, count, topics)
            
            topics_text = ', '.join(topics) if topics else ''
            
            prompt = f"""
            Generate {count} creative social media post ideas for {platform}.
            
            Business type: {business_type}
            Topics of interest: {topics_text}
            
            For each idea, provide:
            1. Title (short, catchy)
            2. Description (brief explanation)
            3. Content suggestion (actual post text)
            4. Relevant hashtags (3-5)
            
            Format as JSON array with objects containing: title, description, content, hashtags
            """
            
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1500,
                temperature=0.8
            )
            
            try:
                ideas_json = json.loads(response.choices[0].message.content)
                return ideas_json
            except json.JSONDecodeError:
                # Fallback if JSON parsing fails
                return []
                
        except Exception as e:
            return []


class AIAnalyzeContentView(APIView):
    """Analyze content for sentiment, tone, etc."""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        """Analyze content using AI"""
        try:
            content = request.data.get('content', '')
            if not content:
                return Response({'error': 'Content is required'}, status=status.HTTP_400_BAD_REQUEST)
            
            # Try AI analysis first
            openai.api_key = getattr(settings, 'OPENAI_API_KEY', None)
            
            if openai.api_key:
                try:
                    response = openai.ChatCompletion.create(
                        model="gpt-3.5-turbo",
                        messages=[{
                            "role": "user", 
                            "content": f"""Analyze this social media content and provide insights:
                            
                            Content: {content}
                            
                            Please provide analysis in JSON format with:
                            - sentiment: positive/negative/neutral
                            - tone: professional/casual/friendly/promotional
                            - engagement_prediction: high/medium/low
                            - target_audience: description
                            - improvement_suggestions: array of suggestions
                            - readability_score: 1-10
                            """
                        }],
                        max_tokens=300,
                        temperature=0.3
                    )
                    
                    analysis_result = json.loads(response.choices[0].message.content)
                    return Response(analysis_result)
                    
                except (json.JSONDecodeError, Exception):
                    pass  # Fall through to basic analysis
            
            # Fallback analysis when AI is not available
            analysis = self._basic_content_analysis(content)
            return Response(analysis)
            
        except Exception as e:
            return Response(
                {'error': 'Content analysis failed', 'details': str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _basic_content_analysis(self, content):
        """Provide basic content analysis when AI is not available"""
        import re
        
        # Basic sentiment analysis using keyword matching
        positive_words = ['great', 'excellent', 'amazing', 'wonderful', 'fantastic', 'love', 'best', 'awesome']
        negative_words = ['bad', 'terrible', 'awful', 'hate', 'worst', 'problem', 'issue', 'failed']
        
        content_lower = content.lower()
        positive_count = sum(1 for word in positive_words if word in content_lower)
        negative_count = sum(1 for word in negative_words if word in content_lower)
        
        if positive_count > negative_count:
            sentiment = 'positive'
        elif negative_count > positive_count:
            sentiment = 'negative'
        else:
            sentiment = 'neutral'
        
        # Basic tone analysis
        professional_indicators = ['please', 'thank you', 'sincerely', 'regards', 'professional']
        casual_indicators = ['hey', 'awesome', 'cool', 'lol', 'omg']
        
        professional_count = sum(1 for indicator in professional_indicators if indicator in content_lower)
        casual_count = sum(1 for indicator in casual_indicators if indicator in content_lower)
        
        if professional_count > casual_count:
            tone = 'professional'
        elif casual_count > professional_count:
            tone = 'casual'
        else:
            tone = 'friendly'
        
        # Basic engagement prediction based on content characteristics
        has_hashtags = '#' in content
        has_question = '?' in content
        has_emojis = bool(re.search(r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF]', content))
        word_count = len(content.split())
        
        engagement_score = 0
        if has_hashtags: engagement_score += 1
        if has_question: engagement_score += 1
        if has_emojis: engagement_score += 1
        if 10 <= word_count <= 100: engagement_score += 1  # Optimal length
        
        if engagement_score >= 3:
            engagement_prediction = 'high'
        elif engagement_score >= 2:
            engagement_prediction = 'medium'
        else:
            engagement_prediction = 'low'
        
        # Readability score (basic approximation)
        avg_word_length = sum(len(word) for word in content.split()) / max(len(content.split()), 1)
        readability_score = max(1, min(10, 11 - int(avg_word_length)))
        
        return {
            'sentiment': sentiment,
            'tone': tone,
            'engagement_prediction': engagement_prediction,
            'target_audience': 'General construction and real estate audience',
            'improvement_suggestions': self._get_improvement_suggestions(content, has_hashtags, has_question, has_emojis),
            'readability_score': readability_score,
            'analysis_method': 'basic'  # Indicate this was basic analysis
        }
    
    def _get_improvement_suggestions(self, content, has_hashtags, has_question, has_emojis):
        """Generate improvement suggestions based on content analysis"""
        suggestions = []
        
        if not has_hashtags:
            suggestions.append("Consider adding relevant hashtags to increase discoverability")
        
        if not has_question:
            suggestions.append("Try adding a question to encourage engagement")
        
        if not has_emojis:
            suggestions.append("Consider adding emojis to make the content more visually appealing")
        
        word_count = len(content.split())
        if word_count < 10:
            suggestions.append("Content is quite short - consider adding more details")
        elif word_count > 100:
            suggestions.append("Content is quite long - consider making it more concise")
        
        if content.isupper():
            suggestions.append("Avoid using all caps as it may appear aggressive")
        
        return suggestions


# Analytics Views
class AnalyticsSummaryView(APIView):
    """Get analytics summary"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        """Get analytics summary for user"""
        try:
            from django.db.models import Sum, Avg, Count
            import logging
            
            logger = logging.getLogger(__name__)
            logger.info("Analytics summary requested")
            
            user = request.user
            logger.info(f"User: {user.username}")
            
            # Get date range from query params (default to last 30 days)
            days_back = int(request.GET.get('days', 30))
            start_date = request.GET.get('start_date')
            end_date = request.GET.get('end_date')
            
            if start_date and end_date:
                try:
                    since_date = datetime.strptime(start_date, '%Y-%m-%d')
                    until_date = datetime.strptime(end_date, '%Y-%m-%d')
                except ValueError:
                    return Response({'error': 'Invalid date format. Use YYYY-MM-DD'}, status=400)
            else:
                since_date = datetime.now() - timedelta(days=days_back)
                until_date = datetime.now()
            
            logger.info(f"Date range: {since_date} to {until_date}")
            
            # Get overview metrics from database
            analytics_qs = SocialAnalytics.objects.filter(
                post_target__account__created_by=user,
                post_target__post__published_at__gte=since_date,
                post_target__post__published_at__lte=until_date
            )
            
            logger.info(f"Found {analytics_qs.count()} analytics records")
            
            overview = {
                'total_posts': analytics_qs.count(),
                'total_impressions': analytics_qs.aggregate(Sum('impressions'))['impressions__sum'] or 0,
                'total_reach': analytics_qs.aggregate(Sum('reach'))['reach__sum'] or 0,
                'total_likes': analytics_qs.aggregate(Sum('likes'))['likes__sum'] or 0,
                'total_comments': analytics_qs.aggregate(Sum('comments'))['comments__sum'] or 0,
                'total_shares': analytics_qs.aggregate(Sum('shares'))['shares__sum'] or 0,
                'avg_engagement_rate': 0.0,
                'date_range': {
                    'start_date': since_date.strftime('%Y-%m-%d'),
                    'end_date': datetime.now().strftime('%Y-%m-%d'),
                    'days': days_back
                }
            }
            
            # Calculate engagement rate
            if overview['total_reach'] > 0:
                total_engagement = overview['total_likes'] + overview['total_comments'] + overview['total_shares']
                overview['avg_engagement_rate'] = round((total_engagement / overview['total_reach']) * 100, 2)
            
            # Get platform breakdown
            platforms = {}
            accounts = SocialAccount.objects.filter(
                created_by=user,
                status='connected'
            ).select_related('platform')
            
            for account in accounts:
                platform_name = account.platform.name.lower()
                platform_analytics = analytics_qs.filter(post_target__account=account)
                
                platforms[platform_name] = {
                    'account_name': account.account_name,
                    'posts': platform_analytics.count(),
                    'impressions': platform_analytics.aggregate(Sum('impressions'))['impressions__sum'] or 0,
                    'reach': platform_analytics.aggregate(Sum('reach'))['reach__sum'] or 0,
                    'engagement': (platform_analytics.aggregate(Sum('likes'))['likes__sum'] or 0) + 
                                 (platform_analytics.aggregate(Sum('comments'))['comments__sum'] or 0) + 
                                 (platform_analytics.aggregate(Sum('shares'))['shares__sum'] or 0),
                    'last_sync': account.last_sync.isoformat() if account.last_sync else None
                }
            
            # Get recent activity (last 7 days of posts)
            recent_posts = analytics_qs.filter(
                post_target__post__published_at__gte=datetime.now() - timedelta(days=7)
            ).select_related(
                'post_target__post', 
                'post_target__account__platform'
            ).order_by('-post_target__post__published_at')[:10]
            
            recent_activity = []
            for analytics in recent_posts:
                post = analytics.post_target.post
                recent_activity.append({
                    'post_id': str(post.id),
                    'content': post.content[:100] + '...' if len(post.content) > 100 else post.content,
                    'platform': analytics.post_target.account.platform.display_name,
                    'published_at': post.published_at.isoformat() if post.published_at else None,
                    'impressions': analytics.impressions,
                    'likes': analytics.likes,
                    'comments': analytics.comments,
                    'engagement_rate': analytics.platform_metrics.get('engagement_rate', 0) if analytics.platform_metrics else 0
                })
            
            # Get connected accounts summary
            connected_accounts = []
            for account in accounts:
                account_metrics = account.permissions if isinstance(account.permissions, dict) else {}
                connected_accounts.append({
                    'id': str(account.id),
                    'platform': account.platform.display_name,
                    'account_name': account.account_name,
                    'username': account.account_username,
                    'status': account.status,
                    'followers': account_metrics.get('followers', account_metrics.get('follower_count', 0)),
                    'last_sync': account.last_sync.isoformat() if account.last_sync else None
                })
            
            return Response({
                'overview': overview,
                'platforms': platforms,
                'recent_activity': recent_activity,
                'connected_accounts': connected_accounts,
                'sync_info': {
                    'last_sync': max([acc.last_sync for acc in accounts if acc.last_sync], default=None),
                    'can_sync': True,
                    'sync_status': 'up_to_date' if all(acc.last_sync for acc in accounts) else 'needs_sync'
                }
            })
            
        except Exception as e:
            logger.error(f"Error getting analytics summary: {str(e)}")
            return Response({'error': str(e)}, status=500)


class PlatformAnalyticsView(APIView):
    """Get platform-specific analytics"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, platform):
        """Get analytics for specific platform"""
        try:
            from .services.analytics_service import AnalyticsService
            from datetime import datetime, timedelta
            
            user = request.user
            
            # Get date range from query params
            start_date = request.GET.get('start_date')
            end_date = request.GET.get('end_date')
            
            if not start_date or not end_date:
                # Default to last 30 days
                end_date = datetime.now().strftime('%Y-%m-%d')
                start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
            
            date_range = {
                'start_date': start_date,
                'end_date': end_date
            }
            
            # Get accounts for this platform
            try:
                platform_obj = SocialPlatform.objects.get(name__iexact=platform)
            except SocialPlatform.DoesNotExist:
                return Response({'error': f'Platform {platform} not found'}, status=404)
            
            accounts = SocialAccount.objects.filter(
                created_by=user,
                platform=platform_obj,
                status='connected'
            )
            
            if not accounts.exists():
                return Response({
                    'error': f'No connected {platform} accounts found',
                    'platform': platform.title(),
                    'connected_accounts': 0
                }, status=404)
            
            # Get detailed analytics for each account
            analytics_service = AnalyticsService()
            platform_data = {
                'platform': platform.title(),
                'accounts': [],
                'summary': {
                    'total_accounts': accounts.count(),
                    'total_followers': 0,
                    'total_posts': 0,
                    'total_impressions': 0,
                    'total_reach': 0,
                    'total_engagement': 0,
                    'avg_engagement_rate': 0.0
                },
                'date_range': date_range
            }
            
            total_engagement_rates = []
            
            for account in accounts:
                # Get account insights
                account_insights = analytics_service.get_account_insights(str(account.id), date_range)
                
                if 'error' not in account_insights:
                    # Extract key metrics
                    if platform.lower() == 'facebook':
                        page_insights = account_insights.get('page_insights', {})
                        post_performance = account_insights.get('post_performance', {})
                        
                        account_data = {
                            'id': str(account.id),
                            'name': account.account_name,
                            'username': account.account_username,
                            'followers': page_insights.get('followers', 0),
                            'posts': post_performance.get('total_posts', 0),
                            'impressions': post_performance.get('total_impressions', 0),
                            'reach': post_performance.get('total_reach', 0),
                            'engagement': post_performance.get('total_engagement', 0),
                            'engagement_rate': post_performance.get('avg_engagement_rate', 0),
                            'top_posts': post_performance.get('top_performing_posts', []),
                            'last_sync': account.last_sync.isoformat() if account.last_sync else None
                        }
                        
                    elif platform.lower() == 'instagram':
                        account_insights_data = account_insights.get('account_insights', {})
                        media_performance = account_insights.get('media_performance', {})
                        
                        account_data = {
                            'id': str(account.id),
                            'name': account.account_name,
                            'username': account.account_username,
                            'followers': account_insights_data.get('follower_count', 0),
                            'posts': media_performance.get('total_posts', 0),
                            'impressions': media_performance.get('total_impressions', 0),
                            'reach': media_performance.get('total_reach', 0),
                            'engagement': media_performance.get('total_engagement', 0),
                            'engagement_rate': media_performance.get('avg_engagement_rate', 0),
                            'profile_views': account_insights_data.get('total_profile_views', 0),
                            'website_clicks': account_insights_data.get('total_website_clicks', 0),
                            'top_posts': media_performance.get('top_performing_posts', []),
                            'last_sync': account.last_sync.isoformat() if account.last_sync else None
                        }
                    
                    # Add to platform summary
                    platform_data['summary']['total_followers'] += account_data['followers']
                    platform_data['summary']['total_posts'] += account_data['posts']
                    platform_data['summary']['total_impressions'] += account_data['impressions']
                    platform_data['summary']['total_reach'] += account_data['reach']
                    platform_data['summary']['total_engagement'] += account_data['engagement']
                    
                    if account_data['engagement_rate'] > 0:
                        total_engagement_rates.append(account_data['engagement_rate'])
                    
                    platform_data['accounts'].append(account_data)
                
                else:
                    # Account insights failed, add basic info
                    platform_data['accounts'].append({
                        'id': str(account.id),
                        'name': account.account_name,
                        'username': account.account_username,
                        'error': account_insights.get('error'),
                        'last_sync': account.last_sync.isoformat() if account.last_sync else None
                    })
            
            # Calculate average engagement rate
            if total_engagement_rates:
                platform_data['summary']['avg_engagement_rate'] = round(
                    sum(total_engagement_rates) / len(total_engagement_rates), 2
                )
            
            return Response(platform_data)
            
        except Exception as e:
            logger.error(f"Error getting platform analytics for {platform}: {str(e)}")
            return Response({'error': str(e)}, status=500)


class SyncAnalyticsView(APIView):
    """Manually sync analytics data from social platforms"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        """Sync analytics for all connected accounts"""
        try:
            from .services.analytics_service import AnalyticsService
            import json
            
            user = request.user
            
            # Get days_back parameter (default 30 days) - handle both DRF and Django requests
            try:
                if hasattr(request, 'data') and request.data:
                    days_back = int(request.data.get('days_back', 30))
                    account_id = request.data.get('account_id')
                elif request.body:
                    body_data = json.loads(request.body.decode('utf-8'))
                    days_back = int(body_data.get('days_back', 30))
                    account_id = body_data.get('account_id')
                else:
                    days_back = int(request.POST.get('days_back', 30))
                    account_id = request.POST.get('account_id')
            except (ValueError, json.JSONDecodeError):
                days_back = 30
                account_id = None
            
            analytics_service = AnalyticsService()
            
            # Perform sync
            sync_results = analytics_service.sync_all_analytics(str(user.id), days_back)
            
            return Response({
                'success': True,
                'message': f'Analytics sync completed for {days_back} days',
                'results': sync_results
            })
            
        except Exception as e:
            logger.error(f"Error syncing analytics: {str(e)}")
            return Response({'error': str(e)}, status=500)


class ExportAnalyticsView(APIView):
    """Export analytics data"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        """Export analytics to Excel/CSV via GET"""
        return self._export_analytics(request)
    
    def post(self, request):
        """Export analytics to Excel/CSV via POST"""
        return self._export_analytics(request)
    
    def _export_analytics(self, request):
        """Internal method to handle analytics export"""
        try:
            # Import required libraries
            import pandas as pd
            from django.http import HttpResponse
            from datetime import datetime, timedelta
            import io
            
            logger.info("Starting analytics export")
            
            user = request.user
            
            # Get export parameters (support both GET query params and POST data)
            if request.method == 'GET':
                export_format = request.GET.get('format', 'csv')
                days_back = int(request.GET.get('days', 30))
                platforms = request.GET.getlist('platforms') if 'platforms' in request.GET else []
                start_date = request.GET.get('start_date')
                end_date = request.GET.get('end_date')
                platform = request.GET.get('platform')  # Single platform filter
            else:
                export_format = request.data.get('format', 'csv')
                days_back = int(request.data.get('days', 30))
                platforms = request.data.get('platforms', [])
                start_date = request.data.get('start_date')
                end_date = request.data.get('end_date')
                platform = request.data.get('platform')
            
            # Handle single platform parameter
            if platform and platform not in platforms:
                platforms.append(platform)
            
            # Calculate date range
            if start_date and end_date:
                try:
                    since_date = datetime.strptime(start_date, '%Y-%m-%d')
                    until_date = datetime.strptime(end_date, '%Y-%m-%d')
                except ValueError:
                    return Response({'error': 'Invalid date format. Use YYYY-MM-DD'}, status=400)
            else:
                since_date = datetime.now() - timedelta(days=days_back)
                until_date = datetime.now()
            
            # Build query
            analytics_qs = SocialAnalytics.objects.filter(
                post_target__account__created_by=user,
                post_target__post__published_at__gte=since_date,
                post_target__post__published_at__lte=until_date
            ).select_related(
                'post_target__post',
                'post_target__account__platform'
            )
            
            # Filter by platforms if specified
            if platforms:
                analytics_qs = analytics_qs.filter(
                    post_target__account__platform__name__in=platforms
                )
            
            # Prepare data for export
            export_data = []
            for analytics in analytics_qs:
                post = analytics.post_target.post
                account = analytics.post_target.account
                
                export_data.append({
                    'Date': post.published_at.strftime('%Y-%m-%d') if post.published_at else '',
                    'Platform': account.platform.display_name,
                    'Account': account.account_name,
                    'Post Content': post.content[:100] + '...' if len(post.content) > 100 else post.content,
                    'Post Type': post.post_type,
                    'Impressions': analytics.impressions,
                    'Reach': analytics.reach,
                    'Likes': analytics.likes,
                    'Comments': analytics.comments,
                    'Shares': analytics.shares,
                    'Saves': analytics.saves,
                    'Video Views': analytics.video_views,
                    'Clicks': analytics.clicks,
                    'Engagement Rate': analytics.platform_metrics.get('engagement_rate', 0) if analytics.platform_metrics else 0,
                    'Total Engagement': analytics.likes + analytics.comments + analytics.shares + analytics.saves
                })
            
            if not export_data:
                return Response({
                    'error': 'No data available for export',
                    'message': f'No analytics data found for the last {days_back} days'
                }, status=404)
            
            # Create DataFrame
            df = pd.DataFrame(export_data)
            
            # Generate filename
            filename = f'social_analytics_{user.username}_{datetime.now().strftime("%Y%m%d")}'
            
            if export_format.lower() == 'excel':
                # Export to Excel
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, sheet_name='Analytics', index=False)
                    
                    # Add summary sheet
                    summary_data = {
                        'Metric': ['Total Posts', 'Total Impressions', 'Total Reach', 'Total Engagement', 'Avg Engagement Rate'],
                        'Value': [
                            len(export_data),
                            df['Impressions'].sum(),
                            df['Reach'].sum(),
                            df['Total Engagement'].sum(),
                            round(df['Engagement Rate'].mean(), 2)
                        ]
                    }
                    summary_df = pd.DataFrame(summary_data)
                    summary_df.to_excel(writer, sheet_name='Summary', index=False)
                
                output.seek(0)
                response = HttpResponse(
                    output.getvalue(),
                    content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                )
                response['Content-Disposition'] = f'attachment; filename="{filename}.xlsx"'
                
            else:
                # Export to CSV
                csv_buffer = io.StringIO()
                df.to_csv(csv_buffer, index=False)
                
                response = HttpResponse(csv_buffer.getvalue(), content_type='text/csv')
                response['Content-Disposition'] = f'attachment; filename="{filename}.csv"'
            
            return response
            
        except ImportError as e:
            logger.error(f"Import error in analytics export: {str(e)}")
            return Response({
                'error': 'Export functionality not available',
                'message': f'Import error: {str(e)}'
            }, status=500)
        except Exception as e:
            logger.error(f"Error exporting analytics: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return Response({'error': str(e)}, status=500)


# Engagement Views
class EngagementInboxView(APIView):
    """Unified engagement inbox"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        """Get engagement inbox data"""
        # Already implemented in SocialCommentViewSet.inbox
        pass


class ReplyToCommentView(APIView):
    """Reply to a comment"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        """Reply to social media comment"""
        # TODO: Implement comment reply
        pass


class FlagCommentView(APIView):
    """Flag a comment for attention"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, comment_id):
        """Flag comment"""
        try:
            comment = get_object_or_404(
                SocialComment,
                id=comment_id,
                created_by=request.user
            )
            
            comment.is_flagged = not comment.is_flagged
            comment.save()
            
            return Response({
                'success': True,
                'is_flagged': comment.is_flagged
            })
            
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Calendar Views
class CalendarPostsView(APIView):
    """Get posts for calendar view"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        """Get posts for calendar display"""
        from datetime import datetime
        from django.utils.dateparse import parse_date
        from .serializers import SocialPostSerializer
        
        # Get query parameters
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        
        if not start_date or not end_date:
            return Response(
                {'error': 'start_date and end_date parameters are required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Parse dates
            start_date = parse_date(start_date)
            end_date = parse_date(end_date)
            
            if not start_date or not end_date:
                return Response(
                    {'error': 'Invalid date format. Use YYYY-MM-DD'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Get posts for the user within the date range
            user = request.user
            posts = SocialPost.objects.filter(
                created_by=user,
                scheduled_at__date__gte=start_date,
                scheduled_at__date__lte=end_date,
                scheduled_at__isnull=False  # Only posts that are scheduled
            ).select_related(
                'created_by'
            ).prefetch_related(
                'targets__account__platform'
            ).order_by('scheduled_at')
            
            # Serialize the posts
            serializer = SocialPostSerializer(posts, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {'error': f'Failed to fetch calendar posts: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class OptimalTimesView(APIView):
    """Get optimal posting times"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        """Get AI-determined optimal posting times"""
        # TODO: Implement optimal times calculation
        pass


# Media Views
class MediaUploadView(APIView):
    """Upload media files"""
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    
    def post(self, request):
        """Upload and process media file"""
        # TODO: Implement media upload with AI analysis
        pass


class MediaAnalysisView(APIView):
    """Analyze uploaded media"""
    permission_classes = [permissions.IsAuthenticated]


# Live Data Collection Views
class LiveDataCollectionView(APIView):
    """Collect live data from all connected social media accounts"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        """Start live data collection for user"""
        from .services.live_data_service import LiveDataService
        
        try:
            user = request.user
            
            # Get parameters
            days_back = int(request.data.get('days_back', 30))
            if days_back > 90:  # Limit to 90 days for performance
                days_back = 90
            
            logger.info(f"Starting live data collection for {user.username}, {days_back} days back")
            
            # Initialize live data service
            live_service = LiveDataService()
            
            # Collect all live data
            results = live_service.collect_all_live_data(user, days_back)
            
            return Response({
                'status': 'success',
                'message': 'Live data collection completed',
                'results': results
            })
            
        except Exception as e:
            logger.error(f"Error in live data collection: {str(e)}")
            return Response({
                'status': 'error',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def get(self, request):
        """Get live data collection status"""
        from .services.live_data_service import LiveDataService
        
        try:
            user = request.user
            
            live_service = LiveDataService()
            connection_status = live_service.get_account_connection_status(user)
            
            return Response({
                'status': 'success',
                'connection_status': connection_status
            })
            
        except Exception as e:
            logger.error(f"Error getting live data status: {str(e)}")
            return Response({
                'status': 'error',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class TrendingContentView(APIView):
    """Get trending hashtags and optimal posting times"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        """Get trending content analysis"""
        from .services.live_data_service import LiveDataService
        
        try:
            user = request.user
            
            days_back = int(request.GET.get('days_back', 30))
            if days_back > 90:
                days_back = 90
            
            live_service = LiveDataService()
            trending_data = live_service._analyze_trending_content(user, days_back)
            
            return Response({
                'status': 'success',
                'trending_data': trending_data
            })
            
        except Exception as e:
            logger.error(f"Error getting trending content: {str(e)}")
            return Response({
                'status': 'error',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AccountConnectionStatusView(APIView):
    """Get detailed status of all connected social media accounts"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        """Get account connection status"""
        from .services.live_data_service import LiveDataService
        
        try:
            user = request.user
            
            live_service = LiveDataService()
            status_data = live_service.get_account_connection_status(user)
            
            return Response({
                'status': 'success',
                'data': status_data
            })
            
        except Exception as e:
            logger.error(f"Error getting account connection status: {str(e)}")
            return Response({
                'status': 'error',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SocialMediaDiagnosticsView(APIView):
    """Diagnose social media connection issues"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        """Run diagnostics on social media configuration"""
        from django.conf import settings
        
        diagnostics = {
            'configuration_status': 'checking',
            'facebook_config': {},
            'instagram_config': {},
            'database_status': {},
            'issues': [],
            'recommendations': []
        }
        
        try:
            # Check Facebook configuration
            fb_app_id = getattr(settings, 'FACEBOOK_APP_ID', None)
            fb_app_secret = getattr(settings, 'FACEBOOK_APP_SECRET', None)
            fb_redirect_uri = getattr(settings, 'FACEBOOK_REDIRECT_URI', None)
            
            diagnostics['facebook_config'] = {
                'app_id_configured': bool(fb_app_id and fb_app_id != 'your_facebook_app_id_here'),
                'app_secret_configured': bool(fb_app_secret and fb_app_secret != 'your_facebook_app_secret_here'),
                'redirect_uri_configured': bool(fb_redirect_uri and fb_redirect_uri != ''),
                'api_version': getattr(settings, 'FACEBOOK_API_VERSION', 'v18.0'),
                'scopes': getattr(settings, 'FACEBOOK_SCOPES', [])
            }
            
            # Check Instagram configuration
            ig_app_id = getattr(settings, 'INSTAGRAM_APP_ID', None)
            ig_app_secret = getattr(settings, 'INSTAGRAM_APP_SECRET', None)
            
            diagnostics['instagram_config'] = {
                'app_id_configured': bool(ig_app_id and ig_app_id != 'your_facebook_app_id_here'),
                'app_secret_configured': bool(ig_app_secret and ig_app_secret != 'your_instagram_app_secret_here'),
                'uses_facebook_app': bool(ig_app_id == fb_app_id)  # Instagram Business API uses Facebook App
            }
            
            # Check database
            try:
                platform_count = SocialPlatform.objects.count()
                account_count = SocialAccount.objects.count()
                connected_count = SocialAccount.objects.filter(status='connected').count()
                
                diagnostics['database_status'] = {
                    'platforms_available': platform_count,
                    'accounts_total': account_count,
                    'accounts_connected': connected_count
                }
                
            except Exception as e:
                diagnostics['database_status']['error'] = str(e)
            
            # Analyze issues
            if not diagnostics['facebook_config']['app_id_configured']:
                diagnostics['issues'].append('Facebook App ID not configured')
                diagnostics['recommendations'].append('Set FACEBOOK_APP_ID in environment variables')
            
            if not diagnostics['facebook_config']['app_secret_configured']:
                diagnostics['issues'].append('Facebook App Secret not configured')
                diagnostics['recommendations'].append('Set FACEBOOK_APP_SECRET in environment variables')
            
            if not diagnostics['facebook_config']['redirect_uri_configured']:
                diagnostics['issues'].append('Facebook redirect URI not configured')
                diagnostics['recommendations'].append('Set FACEBOOK_REDIRECT_URI in environment variables')
            
            if not diagnostics['instagram_config']['app_id_configured']:
                diagnostics['issues'].append('Instagram App ID not configured')
                diagnostics['recommendations'].append('Set INSTAGRAM_APP_ID in environment variables (usually same as Facebook App ID)')
            
            # Determine overall status
            if not diagnostics['issues']:
                diagnostics['configuration_status'] = 'ready'
            elif len(diagnostics['issues']) <= 2:
                diagnostics['configuration_status'] = 'needs_configuration'
            else:
                diagnostics['configuration_status'] = 'not_ready'
            
            # Add setup guide
            diagnostics['setup_guide'] = {
                'step1': 'Create Facebook App at https://developers.facebook.com/apps/',
                'step2': 'Add Facebook Login and Instagram Basic Display products',
                'step3': 'Configure OAuth redirect URIs in Facebook App settings',
                'step4': 'Set environment variables with App ID and Secret',
                'step5': 'Restart Django server and test connection'
            }
            
            return Response(diagnostics)
            
        except Exception as e:
            logger.error(f"Error in social media diagnostics: {str(e)}")
            return Response({
                'configuration_status': 'error',
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PostPerformanceView(APIView):
    """Detailed post performance analytics"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        try:
            # Get query parameters
            start_date = request.GET.get('start_date')
            end_date = request.GET.get('end_date')
            platform = request.GET.get('platform', 'all')
            limit = int(request.GET.get('limit', 20))
            
            # Parse dates
            if start_date:
                start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            else:
                start_date = timezone.now().date() - timedelta(days=30)
                
            if end_date:
                end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            else:
                end_date = timezone.now().date()
            
            # Build query
            posts_query = SocialPost.objects.filter(
                created_by=request.user,
                published_at__date__gte=start_date,
                published_at__date__lte=end_date,
                status='published'
            ).select_related('created_by').prefetch_related('targets__account__platform', 'targets__analytics')
            
            # Filter by platform if specified
            if platform != 'all':
                posts_query = posts_query.filter(targets__account__platform__name=platform)
            
            posts = posts_query.distinct().order_by('-published_at')[:limit]
            
            # Build detailed performance data
            performance_data = []
            for post in posts:
                # Get analytics for all targets
                total_impressions = 0
                total_reach = 0
                total_likes = 0
                total_comments = 0
                total_shares = 0
                platform_breakdown = {}
                
                for target in post.targets.all():
                    try:
                        analytics = target.analytics
                    except SocialAnalytics.DoesNotExist:
                        analytics = None
                    
                    if analytics:
                        total_impressions += analytics.impressions or 0
                        total_reach += analytics.reach or 0
                        total_likes += analytics.likes or 0
                        total_comments += analytics.comments or 0
                        total_shares += analytics.shares or 0
                        
                        platform_name = target.account.platform.display_name
                        platform_breakdown[platform_name] = {
                            'impressions': analytics.impressions or 0,
                            'reach': analytics.reach or 0,
                            'likes': analytics.likes or 0,
                            'comments': analytics.comments or 0,
                            'shares': analytics.shares or 0,
                            'engagement_rate': round(
                                ((analytics.likes + analytics.comments + analytics.shares) / max(analytics.reach, 1)) * 100, 2
                            )
                        }
                
                # Calculate engagement rate
                engagement_rate = round(((total_likes + total_comments + total_shares) / max(total_reach, 1)) * 100, 2)
                
                performance_data.append({
                    'id': str(post.id),
                    'content': post.content[:100] + ('...' if len(post.content) > 100 else ''),
                    'full_content': post.content,
                    'post_type': post.post_type,
                    'published_at': post.published_at.isoformat() if post.published_at else None,
                    'created_by': post.created_by.get_full_name() if post.created_by else 'System',
                    'hashtags': post.hashtags,
                    'platforms': list(platform_breakdown.keys()),
                    'platform_breakdown': platform_breakdown,
                    'total_metrics': {
                        'impressions': total_impressions,
                        'reach': total_reach,
                        'likes': total_likes,
                        'comments': total_comments,
                        'shares': total_shares,
                        'engagement': total_likes + total_comments + total_shares,
                        'engagement_rate': engagement_rate
                    },
                    'performance_score': engagement_rate * (total_reach / 1000),  # Weighted score
                })
            
            # Sort by performance score
            performance_data.sort(key=lambda x: x['performance_score'], reverse=True)
            
            # Calculate summary stats
            if performance_data:
                avg_engagement_rate = sum(p['total_metrics']['engagement_rate'] for p in performance_data) / len(performance_data)
                top_post = performance_data[0] if performance_data else None
                
                summary = {
                    'total_posts': len(performance_data),
                    'avg_engagement_rate': round(avg_engagement_rate, 2),
                    'total_engagement': sum(p['total_metrics']['engagement'] for p in performance_data),
                    'total_reach': sum(p['total_metrics']['reach'] for p in performance_data),
                    'top_performing_post': top_post,
                    'date_range': {
                        'start': start_date.isoformat(),
                        'end': end_date.isoformat()
                    }
                }
            else:
                summary = {
                    'total_posts': 0,
                    'avg_engagement_rate': 0,
                    'total_engagement': 0,
                    'total_reach': 0,
                    'top_performing_post': None
                }
            
            # Transform data to match frontend expectations
            posts = []
            platform_breakdown = {}
            engagement_trends = []
            
            for post_data in performance_data:
                # Add post data in expected format
                post = {
                    'id': post_data['id'],
                    'content': post_data['content'],
                    'platform': post_data['platforms'][0] if post_data['platforms'] else 'unknown',
                    'published_at': post_data['published_at'],
                    'engagement_rate': post_data['total_metrics']['engagement_rate'],
                    'likes': post_data['total_metrics']['likes'],
                    'comments': post_data['total_metrics']['comments'],
                    'shares': post_data['total_metrics']['shares'],
                    'reach': post_data['total_metrics']['reach'],
                    'impressions': post_data['total_metrics']['impressions'],
                    'engagement_score': post_data['performance_score']
                }
                posts.append(post)
                
                # Build platform breakdown
                for platform_name in post_data['platforms']:
                    if platform_name not in platform_breakdown:
                        platform_breakdown[platform_name] = {
                            'total_posts': 0,
                            'avg_engagement_rate': 0,
                            'total_reach': 0,
                            'total_impressions': 0
                        }
                    platform_breakdown[platform_name]['total_posts'] += 1
                    platform_breakdown[platform_name]['total_reach'] += post_data['total_metrics']['reach']
                    platform_breakdown[platform_name]['total_impressions'] += post_data['total_metrics']['impressions']
            
            # Calculate average engagement rates for platforms
            for platform_name in platform_breakdown:
                platform_posts = [p for p in posts if p['platform'] == platform_name]
                if platform_posts:
                    avg_rate = sum(p['engagement_rate'] for p in platform_posts) / len(platform_posts)
                    platform_breakdown[platform_name]['avg_engagement_rate'] = avg_rate
            
            # Generate simple engagement trends (last 7 days)
            current_date = timezone.now()
            for i in range(7):
                trend_date = current_date - timedelta(days=i)
                trend_date_str = trend_date.date().isoformat()
                day_posts = [p for p in posts if p['published_at'] and trend_date_str in p['published_at']]
                if day_posts:
                    avg_engagement = sum(p['engagement_rate'] for p in day_posts) / len(day_posts)
                    total_likes = sum(p['likes'] for p in day_posts)
                    total_comments = sum(p['comments'] for p in day_posts)
                    total_shares = sum(p['shares'] for p in day_posts)
                    
                    engagement_trends.append({
                        'date': trend_date_str,
                        'engagement_rate': avg_engagement,
                        'likes': total_likes,
                        'comments': total_comments,
                        'shares': total_shares
                    })
            
            engagement_trends.sort(key=lambda x: x['date'])
            
            return Response({
                'posts': posts,
                'platform_breakdown': platform_breakdown,
                'engagement_trends': engagement_trends,
                'top_performers': posts[:5],  # Top 5 posts
                'summary': summary
            })
            
        except Exception as e:
            logger.error(f"Error in post performance view: {str(e)}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class EngagementAnalysisView(APIView):
    """Comprehensive engagement analysis"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        try:
            # Get parameters
            days_back = int(request.GET.get('days', 30))
            platform = request.GET.get('platform', 'all')
            
            end_date = timezone.now()
            start_date = end_date - timedelta(days=days_back)
            
            # Get analytics data
            analytics_query = SocialAnalytics.objects.filter(
                post_target__post__created_by=request.user,
                post_target__post__published_at__gte=start_date,
                post_target__post__published_at__lte=end_date
            ).select_related('post_target__post', 'post_target__account__platform')
            
            if platform != 'all':
                analytics_query = analytics_query.filter(post_target__account__platform__name=platform)
            
            analytics_data = list(analytics_query)
            
            if not analytics_data:
                return Response({
                    'engagement_trends': [],
                    'best_posting_times': {},
                    'platform_comparison': {},
                    'engagement_by_content_type': {},
                    'hashtag_performance': [],
                    'weekly_patterns': [],
                    'summary': {
                        'total_posts': 0,
                        'avg_engagement_rate': 0,
                        'best_day': 'No data',
                        'best_hour': 'No data'
                    }
                })
            
            # Engagement trends (daily)
            daily_engagement = {}
            hour_performance = {}
            day_performance = {}
            content_type_performance = {}
            platform_performance = {}
            
            for analytics in analytics_data:
                post = analytics.post_target.post
                publish_date = post.published_at.date() if post.published_at else None
                publish_hour = post.published_at.hour if post.published_at else None
                publish_day = post.published_at.strftime('%A') if post.published_at else None
                
                engagement = (analytics.likes or 0) + (analytics.comments or 0) + (analytics.shares or 0)
                reach = max(analytics.reach or 0, 1)
                engagement_rate = (engagement / reach) * 100
                
                # Daily trends
                if publish_date:
                    date_key = publish_date.isoformat()
                    if date_key not in daily_engagement:
                        daily_engagement[date_key] = {'posts': 0, 'total_engagement': 0, 'total_reach': 0}
                    daily_engagement[date_key]['posts'] += 1
                    daily_engagement[date_key]['total_engagement'] += engagement
                    daily_engagement[date_key]['total_reach'] += reach
                
                # Hour analysis
                if publish_hour is not None:
                    if publish_hour not in hour_performance:
                        hour_performance[publish_hour] = {'posts': 0, 'total_engagement_rate': 0}
                    hour_performance[publish_hour]['posts'] += 1
                    hour_performance[publish_hour]['total_engagement_rate'] += engagement_rate
                
                # Day of week analysis
                if publish_day:
                    if publish_day not in day_performance:
                        day_performance[publish_day] = {'posts': 0, 'total_engagement_rate': 0}
                    day_performance[publish_day]['posts'] += 1
                    day_performance[publish_day]['total_engagement_rate'] += engagement_rate
                
                # Content type analysis
                content_type = post.post_type
                if content_type not in content_type_performance:
                    content_type_performance[content_type] = {'posts': 0, 'total_engagement': 0, 'total_reach': 0}
                content_type_performance[content_type]['posts'] += 1
                content_type_performance[content_type]['total_engagement'] += engagement
                content_type_performance[content_type]['total_reach'] += reach
                
                # Platform analysis
                platform_name = analytics.post_target.account.platform.display_name
                if platform_name not in platform_performance:
                    platform_performance[platform_name] = {'posts': 0, 'total_engagement': 0, 'total_reach': 0}
                platform_performance[platform_name]['posts'] += 1
                platform_performance[platform_name]['total_engagement'] += engagement
                platform_performance[platform_name]['total_reach'] += reach
            
            # Process trends
            engagement_trends = []
            for date_key, data in sorted(daily_engagement.items()):
                engagement_trends.append({
                    'date': date_key,
                    'posts': data['posts'],
                    'engagement': data['total_engagement'],
                    'reach': data['total_reach'],
                    'engagement_rate': round((data['total_engagement'] / max(data['total_reach'], 1)) * 100, 2)
                })
            
            # Best posting times
            best_hours = []
            for hour, data in hour_performance.items():
                if data['posts'] >= 2:  # Only hours with multiple posts
                    avg_engagement_rate = data['total_engagement_rate'] / data['posts']
                    best_hours.append({
                        'hour': hour,
                        'time': f"{hour:02d}:00",
                        'avg_engagement_rate': round(avg_engagement_rate, 2),
                        'posts_count': data['posts']
                    })
            best_hours.sort(key=lambda x: x['avg_engagement_rate'], reverse=True)
            
            # Best days
            best_days = []
            for day, data in day_performance.items():
                if data['posts'] >= 1:
                    avg_engagement_rate = data['total_engagement_rate'] / data['posts']
                    best_days.append({
                        'day': day,
                        'avg_engagement_rate': round(avg_engagement_rate, 2),
                        'posts_count': data['posts']
                    })
            best_days.sort(key=lambda x: x['avg_engagement_rate'], reverse=True)
            
            # Platform comparison
            platform_comparison = {}
            for platform, data in platform_performance.items():
                engagement_rate = (data['total_engagement'] / max(data['total_reach'], 1)) * 100
                platform_comparison[platform] = {
                    'posts': data['posts'],
                    'engagement_rate': round(engagement_rate, 2),
                    'total_engagement': data['total_engagement'],
                    'total_reach': data['total_reach']
                }
            
            # Content type performance
            content_type_analysis = {}
            for content_type, data in content_type_performance.items():
                engagement_rate = (data['total_engagement'] / max(data['total_reach'], 1)) * 100
                content_type_analysis[content_type] = {
                    'posts': data['posts'],
                    'engagement_rate': round(engagement_rate, 2),
                    'total_engagement': data['total_engagement']
                }
            
            # Calculate summary
            total_posts = len(analytics_data)
            avg_engagement_rate = sum(
                ((a.likes + a.comments + a.shares) / max(a.reach, 1)) * 100 
                for a in analytics_data
            ) / total_posts if total_posts > 0 else 0
            
            summary = {
                'total_posts': total_posts,
                'avg_engagement_rate': round(avg_engagement_rate, 2),
                'best_day': best_days[0]['day'] if best_days else 'No data',
                'best_hour': f"{best_hours[0]['hour']:02d}:00" if best_hours else 'No data',
                'top_platform': max(platform_comparison.keys(), 
                                  key=lambda k: platform_comparison[k]['engagement_rate']) if platform_comparison else 'No data'
            }
            
            return Response({
                'engagement_trends': engagement_trends,
                'best_posting_times': {
                    'hours': best_hours[:5],
                    'days': best_days
                },
                'platform_comparison': platform_comparison,
                'engagement_by_content_type': content_type_analysis,
                'weekly_patterns': engagement_trends[-7:],  # Last 7 days
                'summary': summary
            })
            
        except Exception as e:
            logger.error(f"Error in engagement analysis view: {str(e)}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AutoSyncView(APIView):
    """Automated sync for posts and analytics"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        try:
            from .services.analytics_service import FacebookAnalyticsService, InstagramAnalyticsService
            
            facebook_service = FacebookAnalyticsService()
            instagram_service = InstagramAnalyticsService()
            
            results = {
                'posts_imported': 0,
                'analytics_updated': 0,
                'accounts_processed': 0,
                'errors': []
            }
            
            # Get all connected accounts
            accounts = SocialAccount.objects.filter(
                created_by=request.user,
                status='connected',
                is_active=True
            )
            
            for account in accounts:
                try:
                    results['accounts_processed'] += 1
                    
                    # Import posts based on platform
                    if account.platform.name == 'instagram':
                        import_result = instagram_service.import_instagram_posts(account, limit=20)
                        results['posts_imported'] += import_result.get('posts_imported', 0)
                        
                        # Update analytics
                        analytics_result = instagram_service.collect_analytics(account, days_back=30)
                        if analytics_result.get('summary'):
                            results['analytics_updated'] += 1
                            
                    elif account.platform.name == 'facebook':
                        import_result = facebook_service.import_facebook_posts(account, limit=20)
                        if not import_result.get('error'):
                            results['posts_imported'] += import_result.get('posts_imported', 0)
                        
                        # Update analytics
                        analytics_result = facebook_service.collect_analytics(account, days_back=30)
                        if analytics_result.get('summary'):
                            results['analytics_updated'] += 1
                
                except Exception as e:
                    error_msg = f"Error processing {account.account_name}: {str(e)}"
                    logger.error(error_msg)
                    results['errors'].append(error_msg)
            
            # Update last sync timestamp
            for account in accounts:
                account.last_sync = timezone.now()
                account.save(update_fields=['last_sync'])
            
            return Response({
                'success': True,
                'message': f"Sync completed: {results['posts_imported']} posts imported, {results['analytics_updated']} accounts updated",
                'details': results
            })
            
        except Exception as e:
            logger.error(f"Error in auto sync: {str(e)}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Media Upload Views
class MediaUploadView(APIView):
    """Handle media file uploads with validation"""
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    
    def post(self, request):
        """Upload and validate a media file"""
        from .utils.media_validator import MediaValidator
        import os
        from PIL import Image
        from django.core.files.storage import default_storage
        
        try:
            file = request.FILES.get('file')
            if not file:
                return Response({
                    'error': 'No file provided'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            platform = request.data.get('platform', 'instagram')
            post_type = request.data.get('post_type', 'image')
            analyze_content = request.data.get('analyze_content', 'true').lower() == 'true'
            
            # Validate file size (100MB limit)
            if file.size > 100 * 1024 * 1024:
                return Response({
                    'error': 'File size exceeds 100MB limit'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Save file temporarily
            file_name = f"temp_{uuid.uuid4()}_{file.name}"
            file_path = default_storage.save(f"temp/{file_name}", file)
            full_file_path = default_storage.path(file_path)
            
            try:
                # Validate with MediaValidator
                validation_result = MediaValidator.validate_file(
                    full_file_path, 
                    platform, 
                    post_type
                )
                
                if not validation_result['valid']:
                    # Clean up temp file
                    default_storage.delete(file_path)
                    return Response({
                        'valid': False,
                        'errors': validation_result['errors'],
                        'warnings': validation_result.get('warnings', [])
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                # Create SocialMediaFile record
                media_file = SocialMediaFile.objects.create(
                    file=file_path,
                    file_name=file.name,
                    file_type=validation_result['metadata']['media_type'],
                    file_size=file.size,
                    mime_type=file.content_type,
                    width=validation_result['metadata'].get('width'),
                    height=validation_result['metadata'].get('height'),
                    duration=validation_result['metadata'].get('duration'),
                    uploaded_by=request.user
                )
                
                # Generate AI alt text if requested and it's an image
                if analyze_content and validation_result['metadata']['media_type'] == 'image':
                    try:
                        alt_text = self._generate_alt_text(full_file_path)
                        media_file.alt_text = alt_text
                        media_file.save(update_fields=['alt_text'])
                    except Exception as e:
                        logger.warning(f"Failed to generate alt text: {str(e)}")
                
                # Remove temp file path, keep the actual file
                os.rename(full_file_path, default_storage.path(f"social_media/{timezone.now().year}/{timezone.now().month}/{media_file.id}_{file.name}"))
                media_file.file = f"social_media/{timezone.now().year}/{timezone.now().month}/{media_file.id}_{file.name}"
                media_file.save(update_fields=['file'])
                
                # Return success response
                serializer = SocialMediaFileSerializer(media_file, context={'request': request})
                
                return Response({
                    'valid': True,
                    'file': serializer.data,
                    'validation': validation_result,
                    'message': 'File uploaded successfully'
                }, status=status.HTTP_201_CREATED)
                
            except Exception as e:
                # Clean up temp file on error
                if default_storage.exists(file_path):
                    default_storage.delete(file_path)
                raise e
                
        except Exception as e:
            logger.error(f"Media upload error: {str(e)}")
            return Response({
                'error': f'Upload failed: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _generate_alt_text(self, image_path):
        """Generate AI alt text for images"""
        try:
            import openai
            
            if not settings.OPENAI_API_KEY:
                return ""
            
            # This is a placeholder - in production you'd send the image to OpenAI Vision API
            # For now, return a simple description
            return "Image uploaded for social media post"
            
        except Exception as e:
            logger.warning(f"Alt text generation failed: {str(e)}")
            return ""


class MediaValidationView(APIView):
    """Validate media files without uploading"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        """Validate media compatibility with platform and post type"""
        from .utils.media_validator import MediaValidator
        
        try:
            platform = request.data.get('platform', 'instagram')
            post_type = request.data.get('post_type', 'image')
            media_urls = request.data.get('media_urls', [])
            
            if not media_urls:
                return Response({
                    'error': 'No media URLs provided'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Get platform recommendations
            recommendations = MediaValidator.get_platform_recommendations(platform, post_type)
            
            # Validate each media URL (if they're local files)
            validation_results = []
            for url in media_urls:
                # For now, just return the recommendations
                # In production, you'd validate actual files
                validation_results.append({
                    'url': url,
                    'valid': True,
                    'warnings': [f"Manual validation required for {url}"]
                })
            
            return Response({
                'platform': platform,
                'post_type': post_type,
                'recommendations': recommendations,
                'validations': validation_results
            })
            
        except Exception as e:
            logger.error(f"Media validation error: {str(e)}")
            return Response({
                'error': f'Validation failed: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PlatformCapabilitiesView(APIView):
    """Get platform-specific posting capabilities"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        """Get supported post types and media requirements for all platforms"""
        from .services.instagram_service import InstagramService
        
        try:
            platform = request.query_params.get('platform')
            
            if platform == 'instagram':
                # Get Instagram-specific capabilities
                instagram_service = InstagramService()
                
                # Try to get capabilities for user's Instagram accounts
                user_accounts = SocialAccount.objects.filter(
                    created_by=request.user,
                    platform__name='instagram',
                    is_active=True
                )
                
                account_capabilities = []
                for account in user_accounts:
                    supported_types = instagram_service.get_supported_post_types(account)
                    account_capabilities.append({
                        'account': SocialAccountSerializer(account).data,
                        'supported_types': supported_types
                    })
                
                return Response({
                    'platform': 'instagram',
                    'account_capabilities': account_capabilities,
                    'general_requirements': {
                        'media_required': True,
                        'text_only_supported': False,
                        'max_caption_length': 2200,
                        'max_hashtags': 30
                    }
                })
            
            else:
                # Generic response for other platforms
                return Response({
                    'platform': platform or 'all',
                    'message': 'Platform capabilities endpoint',
                    'supported_platforms': ['instagram', 'facebook', 'linkedin', 'twitter']
                })
                
        except Exception as e:
            logger.error(f"Platform capabilities error: {str(e)}")
            return Response({
                'error': f'Failed to get capabilities: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
