"""
Media validation utilities for social media platforms
Handles platform-specific media requirements and restrictions
"""

import os
import mimetypes
from PIL import Image
from moviepy.editor import VideoFileClip
from django.core.exceptions import ValidationError
from typing import Dict, List, Tuple, Optional


class MediaValidator:
    """
    Validates media files against platform-specific requirements
    """
    
    # Platform-specific media requirements
    PLATFORM_REQUIREMENTS = {
        'instagram': {
            'images': {
                'formats': ['JPEG', 'JPG', 'PNG'],  # Support common image formats
                'max_size_mb': 30,
                'min_width': 320,
                'max_width': 2048,  # More flexible width limit
                'min_height': 320,
                'max_height': 2048,  # More flexible height limit
                'aspect_ratios': [(1, 1), (4, 5), (16, 9)],  # Square, portrait, landscape
                'max_count': 10  # Carousel limit
            },
            'videos': {
                'formats': ['MOV', 'MP4'],
                'max_size_mb': 100,
                'min_duration': 3,  # seconds
                'max_duration': 90,  # Instagram Reels max
                'min_width': 320,
                'max_width': 1080,
                'min_height': 320,
                'max_height': 1920,
                'codecs': ['H.264', 'H.265'],
                'frame_rate_max': 60
            },
            'stories': {
                'aspect_ratio': (9, 16),  # Vertical only
                'duration_max': 15,  # seconds
                'formats': ['JPEG', 'MOV', 'MP4']
            },
            'reels': {
                'aspect_ratio': (9, 16),  # Vertical only
                'duration_min': 3,
                'duration_max': 90,  # seconds
                'formats': ['MOV', 'MP4']
            }
        },
        'facebook': {
            'images': {
                'formats': ['JPEG', 'PNG', 'GIF', 'BMP', 'TIFF'],
                'max_size_mb': 30,
                'min_width': 320,
                'max_width': 2048,
                'min_height': 320,
                'max_height': 2048,
                'max_count': 10
            },
            'videos': {
                'formats': ['MOV', 'MP4', 'AVI', 'WMV', 'FLV', '3GP'],
                'max_size_mb': 4000,  # 4GB
                'min_duration': 1,
                'max_duration': 240,  # 4 minutes
                'min_width': 320,
                'max_width': 1920,
                'min_height': 240,
                'max_height': 1080
            }
        },
        'linkedin': {
            'images': {
                'formats': ['JPEG', 'PNG', 'GIF'],  # LinkedIn supports common image formats
                'max_size_mb': 20,  # Standard for professional platform
                'min_width': 400,  # Minimum for good quality
                'max_width': 7680,  # High resolution support
                'min_height': 400,
                'max_height': 4320,
                'max_count': 20,  # LinkedIn supports multiple images in carousel posts
                'aspect_ratios': [(16, 9), (4, 3), (1, 1), (3, 4)]  # Standard business ratios
            },
            'videos': {
                'formats': ['MOV', 'MP4', 'AVI', 'WMV', 'FLV', 'ASF', 'MKV'],
                'max_size_mb': 200,  # LinkedIn's enterprise video limit
                'min_duration': 3,
                'max_duration': 600,  # 10 minutes for professional content
                'min_width': 256,
                'max_width': 4096,
                'min_height': 144,
                'max_height': 2304,
                'codecs': ['H.264', 'H.265'],  # Standard video codecs
                'frame_rate_max': 60
            },
            'text': {
                'max_length': 3000,  # LinkedIn UGC Posts API confirmed limit
                'supports_hashtags': True,
                'supports_mentions': True,
                'supports_links': True
            }
        },
        'twitter': {
            'images': {
                'formats': ['JPEG', 'PNG', 'GIF', 'WEBP'],
                'max_size_mb': 5,
                'min_width': 600,
                'max_width': 1200,
                'min_height': 335,
                'max_height': 675,
                'max_count': 4
            },
            'videos': {
                'formats': ['MP4', 'MOV'],
                'max_size_mb': 512,
                'min_duration': 0.5,
                'max_duration': 140,  # 2 minutes 20 seconds
                'min_width': 32,
                'max_width': 1920,
                'min_height': 32,
                'max_height': 1080
            }
        }
    }
    
    @classmethod
    def validate_file(cls, file_path: str, platform: str, post_type: str = 'image') -> Dict[str, any]:
        """
        Validate a media file against platform requirements
        
        Args:
            file_path: Path to the media file
            platform: Target platform (instagram, facebook, etc.)
            post_type: Type of post (image, video, story, reel)
            
        Returns:
            Dict with validation results and metadata
        """
        result = {
            'valid': False,
            'errors': [],
            'warnings': [],
            'metadata': {},
            'platform_specific': {}
        }
        
        try:
            # Check if file exists
            if not os.path.exists(file_path):
                result['errors'].append(f"File not found: {file_path}")
                return result
            
            # Get file info
            file_size = os.path.getsize(file_path)
            file_size_mb = file_size / (1024 * 1024)
            mime_type, _ = mimetypes.guess_type(file_path)
            
            result['metadata'] = {
                'file_size': file_size,
                'file_size_mb': round(file_size_mb, 2),
                'mime_type': mime_type
            }
            
            # Determine media type
            media_type = cls._get_media_type(mime_type)
            if not media_type:
                result['errors'].append(f"Unsupported file type: {mime_type}")
                return result
            
            result['metadata']['media_type'] = media_type
            
            # Get platform requirements
            platform_reqs = cls.PLATFORM_REQUIREMENTS.get(platform, {})
            if not platform_reqs:
                result['errors'].append(f"Unsupported platform: {platform}")
                return result
            
            # Validate based on media type
            if media_type == 'image':
                cls._validate_image(file_path, platform_reqs, post_type, result)
            elif media_type == 'video':
                cls._validate_video(file_path, platform_reqs, post_type, result)
            
            # Platform-specific validations
            cls._validate_platform_specific(platform, post_type, result)
            
            # Set overall validity
            result['valid'] = len(result['errors']) == 0
            
        except Exception as e:
            result['errors'].append(f"Validation error: {str(e)}")
        
        return result
    
    @classmethod
    def _get_media_type(cls, mime_type: str) -> Optional[str]:
        """Determine media type from MIME type"""
        if not mime_type:
            return None
        
        if mime_type.startswith('image/'):
            return 'image'
        elif mime_type.startswith('video/'):
            return 'video'
        
        return None
    
    @classmethod
    def _validate_image(cls, file_path: str, platform_reqs: Dict, post_type: str, result: Dict):
        """Validate image file"""
        try:
            with Image.open(file_path) as img:
                width, height = img.size
                format_name = img.format
                
                result['metadata'].update({
                    'width': width,
                    'height': height,
                    'format': format_name,
                    'aspect_ratio': round(width / height, 2) if height > 0 else 0
                })
                
                # Get image requirements
                img_reqs = platform_reqs.get('images', {})
                
                # Validate format
                allowed_formats = img_reqs.get('formats', [])
                if format_name not in allowed_formats:
                    result['errors'].append(
                        f"Image format {format_name} not supported. Allowed: {', '.join(allowed_formats)}"
                    )
                
                # Validate size
                max_size_mb = img_reqs.get('max_size_mb', float('inf'))
                if result['metadata']['file_size_mb'] > max_size_mb:
                    result['errors'].append(f"Image size {result['metadata']['file_size_mb']}MB exceeds limit of {max_size_mb}MB")
                
                # Validate dimensions
                min_width = img_reqs.get('min_width', 0)
                max_width = img_reqs.get('max_width', float('inf'))
                min_height = img_reqs.get('min_height', 0)
                max_height = img_reqs.get('max_height', float('inf'))
                
                if width < min_width or width > max_width:
                    result['errors'].append(f"Image width {width}px not in range {min_width}-{max_width}px")
                
                if height < min_height or height > max_height:
                    result['errors'].append(f"Image height {height}px not in range {min_height}-{max_height}px")
                
                # Validate aspect ratio for specific post types
                cls._validate_aspect_ratio(width, height, platform_reqs, post_type, result)
                
        except Exception as e:
            result['errors'].append(f"Image validation error: {str(e)}")
    
    @classmethod
    def _validate_video(cls, file_path: str, platform_reqs: Dict, post_type: str, result: Dict):
        """Validate video file"""
        try:
            with VideoFileClip(file_path) as video:
                duration = video.duration
                width, height = video.size
                fps = video.fps
                
                result['metadata'].update({
                    'width': width,
                    'height': height,
                    'duration': round(duration, 2),
                    'fps': fps,
                    'aspect_ratio': round(width / height, 2) if height > 0 else 0
                })
                
                # Get video requirements
                vid_reqs = platform_reqs.get('videos', {})
                
                # Validate duration
                min_duration = vid_reqs.get('min_duration', 0)
                max_duration = vid_reqs.get('max_duration', float('inf'))
                
                if duration < min_duration:
                    result['errors'].append(f"Video duration {duration}s below minimum {min_duration}s")
                
                if duration > max_duration:
                    result['errors'].append(f"Video duration {duration}s exceeds maximum {max_duration}s")
                
                # Validate size
                max_size_mb = vid_reqs.get('max_size_mb', float('inf'))
                if result['metadata']['file_size_mb'] > max_size_mb:
                    result['errors'].append(f"Video size {result['metadata']['file_size_mb']}MB exceeds limit of {max_size_mb}MB")
                
                # Validate dimensions
                min_width = vid_reqs.get('min_width', 0)
                max_width = vid_reqs.get('max_width', float('inf'))
                min_height = vid_reqs.get('min_height', 0)
                max_height = vid_reqs.get('max_height', float('inf'))
                
                if width < min_width or width > max_width:
                    result['errors'].append(f"Video width {width}px not in range {min_width}-{max_width}px")
                
                if height < min_height or height > max_height:
                    result['errors'].append(f"Video height {height}px not in range {min_height}-{max_height}px")
                
                # Validate frame rate
                max_fps = vid_reqs.get('frame_rate_max', float('inf'))
                if fps > max_fps:
                    result['errors'].append(f"Video frame rate {fps}fps exceeds maximum {max_fps}fps")
                
                # Validate aspect ratio for specific post types
                cls._validate_aspect_ratio(width, height, platform_reqs, post_type, result)
                
        except Exception as e:
            result['errors'].append(f"Video validation error: {str(e)}")
    
    @classmethod
    def _validate_aspect_ratio(cls, width: int, height: int, platform_reqs: Dict, post_type: str, result: Dict):
        """Validate aspect ratio for specific post types"""
        aspect_ratio = width / height if height > 0 else 0
        
        # Check post-type specific requirements
        if post_type in ['story', 'reel']:
            type_reqs = platform_reqs.get(post_type, {})
            required_ratio = type_reqs.get('aspect_ratio')
            
            if required_ratio:
                expected_ratio = required_ratio[0] / required_ratio[1]
                tolerance = 0.1  # 10% tolerance
                
                if abs(aspect_ratio - expected_ratio) > tolerance:
                    result['errors'].append(
                        f"{post_type.title()} requires aspect ratio {required_ratio[0]}:{required_ratio[1]} "
                        f"(got {round(aspect_ratio, 2)})"
                    )
        
        # Check general aspect ratio constraints
        elif 'images' in platform_reqs and 'aspect_ratios' in platform_reqs['images']:
            allowed_ratios = platform_reqs['images']['aspect_ratios']
            tolerance = 0.1
            
            valid_ratio = False
            for ratio_tuple in allowed_ratios:
                expected_ratio = ratio_tuple[0] / ratio_tuple[1]
                if abs(aspect_ratio - expected_ratio) <= tolerance:
                    valid_ratio = True
                    break
            
            if not valid_ratio:
                ratio_strings = [f"{r[0]}:{r[1]}" for r in allowed_ratios]
                result['warnings'].append(
                    f"Aspect ratio {round(aspect_ratio, 2)} may not be optimal. "
                    f"Recommended: {', '.join(ratio_strings)}"
                )
    
    @classmethod
    def _validate_platform_specific(cls, platform: str, post_type: str, result: Dict):
        """Add platform-specific validation messages"""
        if platform == 'instagram':
            if post_type == 'text':
                result['errors'].append("Instagram does not support text-only posts. Image or video required.")
            
            if post_type == 'story':
                result['platform_specific']['note'] = "Stories are only available for Instagram Business accounts"
            
            if post_type == 'reel':
                result['platform_specific']['note'] = "Reels should be vertical (9:16) for best performance"
        
        elif platform == 'facebook':
            if post_type in ['story', 'reel']:
                result['warnings'].append(f"{post_type.title()}s are not natively supported on Facebook")
    
    @classmethod
    def get_platform_recommendations(cls, platform: str, post_type: str = 'image') -> Dict[str, any]:
        """
        Get recommended media specifications for a platform
        
        Args:
            platform: Target platform
            post_type: Type of post
            
        Returns:
            Dict with recommended specifications
        """
        platform_reqs = cls.PLATFORM_REQUIREMENTS.get(platform, {})
        
        recommendations = {
            'platform': platform,
            'post_type': post_type,
            'supported': True
        }
        
        if platform == 'instagram':
            if post_type == 'image':
                recommendations.update({
                    'format': 'JPEG only',
                    'size': 'Max 30MB',
                    'dimensions': '1080x1080px (square) recommended',
                    'aspect_ratios': 'Square (1:1), Portrait (4:5), or Landscape (16:9)',
                    'note': 'Instagram requires images for all posts'
                })
            elif post_type == 'video':
                recommendations.update({
                    'format': 'MP4 or MOV',
                    'size': 'Max 100MB',
                    'duration': '3-90 seconds',
                    'dimensions': 'Up to 1080x1920px',
                    'codec': 'H.264 or H.265',
                    'fps': 'Max 60fps'
                })
            elif post_type == 'story':
                recommendations.update({
                    'format': 'JPEG, MP4, or MOV',
                    'aspect_ratio': '9:16 (vertical)',
                    'duration': 'Max 15 seconds for videos',
                    'note': 'Business accounts only'
                })
            elif post_type == 'reel':
                recommendations.update({
                    'format': 'MP4 or MOV',
                    'aspect_ratio': '9:16 (vertical)',
                    'duration': '3-90 seconds',
                    'size': 'Max 100MB'
                })
            elif post_type == 'text':
                recommendations.update({
                    'supported': False,
                    'reason': 'Instagram requires images or videos for all posts'
                })
        
        return recommendations
    
    @classmethod
    def validate_multiple_files(cls, file_paths: List[str], platform: str, post_type: str = 'carousel') -> Dict[str, any]:
        """
        Validate multiple files for carousel posts
        
        Args:
            file_paths: List of file paths
            platform: Target platform
            post_type: Type of post (usually 'carousel')
            
        Returns:
            Dict with validation results for all files
        """
        result = {
            'valid': True,
            'files': [],
            'errors': [],
            'warnings': [],
            'total_count': len(file_paths)
        }
        
        platform_reqs = cls.PLATFORM_REQUIREMENTS.get(platform, {})
        max_count = platform_reqs.get('images', {}).get('max_count', 10)
        
        # Check file count
        if len(file_paths) > max_count:
            result['errors'].append(f"Too many files: {len(file_paths)} (max {max_count} for {platform})")
            result['valid'] = False
        
        # Validate each file
        for i, file_path in enumerate(file_paths):
            file_result = cls.validate_file(file_path, platform, 'image')
            file_result['index'] = i
            result['files'].append(file_result)
            
            if not file_result['valid']:
                result['valid'] = False
        
        return result