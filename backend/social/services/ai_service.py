import openai
import logging
from typing import List, Dict, Any
from django.conf import settings

logger = logging.getLogger(__name__)

class AIService:
    """
    Service for AI-powered content generation and analysis
    """
    
    def __init__(self):
        openai.api_key = settings.OPENAI_API_KEY
        self.model = "gpt-4"
    
    def generate_content_suggestions(self, original_content: str, platform: str, 
                                   action: str = 'improve') -> List[Dict[str, Any]]:
        """
        Generate AI content suggestions based on the original content
        """
        try:
            # Define platform-specific characteristics
            platform_info = self.get_platform_info(platform)
            
            # Create prompt based on action type
            prompts = {
                'improve': f"""
                Improve the following social media post for {platform_info['name']}:
                
                Original: "{original_content}"
                
                Make it more engaging, clear, and suitable for {platform_info['name']}. 
                Keep it under {platform_info['char_limit']} characters.
                Consider the platform's audience and best practices.
                
                Provide 3 different improved versions.
                """,
                
                'shorten': f"""
                Shorten the following social media post for {platform_info['name']}:
                
                Original: "{original_content}"
                
                Make it more concise while keeping the key message intact.
                Keep it under {platform_info['char_limit']} characters.
                
                Provide 3 different shortened versions.
                """,
                
                'expand': f"""
                Expand the following social media post for {platform_info['name']}:
                
                Original: "{original_content}"
                
                Add more detail, context, or engagement elements while keeping it appropriate for the platform.
                Keep it under {platform_info['char_limit']} characters.
                
                Provide 3 different expanded versions.
                """,
                
                'rewrite': f"""
                Completely rewrite the following social media post for {platform_info['name']}:
                
                Original: "{original_content}"
                
                Maintain the core message but present it in a completely different way.
                Make it more engaging and suitable for {platform_info['name']}.
                Keep it under {platform_info['char_limit']} characters.
                
                Provide 3 different rewritten versions.
                """
            }
            
            prompt = prompts.get(action, prompts['improve'])
            
            response = openai.ChatCompletion.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a social media content expert specializing in construction and home improvement industry. Create engaging, professional content that resonates with homeowners and business clients."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=500,
                temperature=0.7
            )
            
            # Parse the response to extract individual suggestions
            content = response.choices[0].message.content.strip()
            suggestions = self.parse_suggestions(content, platform_info['char_limit'])
            
            return suggestions
            
        except Exception as e:
            logger.error(f"Error generating AI content suggestions: {str(e)}")
            return self.get_fallback_suggestions(original_content, action)
    
    def generate_hashtag_suggestions(self, content: str, platform: str, count: int = 10) -> List[str]:
        """
        Generate relevant hashtags for the content
        """
        try:
            prompt = f"""
            Generate {count} relevant hashtags for this {platform} post about construction/home improvement:
            
            Content: "{content}"
            
            Focus on:
            - Construction and home improvement terms
            - Industry-specific keywords
            - Popular engagement hashtags
            - Location-based tags (general)
            
            Return only the hashtags, one per line, without the # symbol.
            """
            
            response = openai.ChatCompletion.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a social media hashtag expert for the construction and home improvement industry."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=200,
                temperature=0.5
            )
            
            hashtags_text = response.choices[0].message.content.strip()
            hashtags = [tag.strip().replace('#', '') for tag in hashtags_text.split('\n') if tag.strip()]
            
            return hashtags[:count]
            
        except Exception as e:
            logger.error(f"Error generating hashtag suggestions: {str(e)}")
            return self.get_fallback_hashtags()
    
    def generate_content_ideas(self, business_type: str, platform: str, count: int = 5) -> List[Dict[str, Any]]:
        """
        Generate content ideas for the business
        """
        try:
            prompt = f"""
            Generate {count} creative social media content ideas for a {business_type} business on {platform}.
            
            Each idea should include:
            - A catchy title
            - A brief description
            - Suggested content/caption
            - Relevant hashtags
            - Content type (text, image, video, carousel)
            
            Focus on engaging, valuable content that showcases expertise and builds trust with potential clients.
            
            Format as JSON array with objects containing: title, description, content, hashtags, type
            """
            
            response = openai.ChatCompletion.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": f"You are a content marketing expert for the {business_type} industry. Create valuable, engaging content ideas."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=800,
                temperature=0.7
            )
            
            content = response.choices[0].message.content.strip()
            
            # Try to parse as JSON, fallback to manual parsing if needed
            try:
                import json
                ideas = json.loads(content)
                return ideas[:count]
            except:
                return self.parse_content_ideas(content, count)
                
        except Exception as e:
            logger.error(f"Error generating content ideas: {str(e)}")
            return self.get_fallback_content_ideas(business_type)
    
    def analyze_content_performance(self, content: str, metrics: Dict[str, int]) -> Dict[str, Any]:
        """
        Analyze why content performed well or poorly
        """
        try:
            prompt = f"""
            Analyze the performance of this social media post:
            
            Content: "{content}"
            
            Metrics:
            - Reach: {metrics.get('reach', 0)}
            - Engagement: {metrics.get('engagement', 0)}
            - Likes: {metrics.get('likes', 0)}
            - Comments: {metrics.get('comments', 0)}
            - Shares: {metrics.get('shares', 0)}
            
            Provide insights on:
            1. What worked well
            2. What could be improved
            3. Recommendations for future posts
            
            Keep the analysis concise and actionable.
            """
            
            response = openai.ChatCompletion.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a social media analytics expert. Provide actionable insights based on post performance."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=300,
                temperature=0.5
            )
            
            analysis = response.choices[0].message.content.strip()
            
            return {
                'analysis': analysis,
                'performance_score': self.calculate_performance_score(metrics),
                'recommendations': self.extract_recommendations(analysis)
            }
            
        except Exception as e:
            logger.error(f"Error analyzing content performance: {str(e)}")
            return {
                'analysis': 'Analysis unavailable',
                'performance_score': 50,
                'recommendations': []
            }
    
    def get_platform_info(self, platform: str) -> Dict[str, Any]:
        """
        Get platform-specific information
        """
        platforms = {
            'facebook': {
                'name': 'Facebook',
                'char_limit': 2000,
                'best_practices': ['Use engaging questions', 'Include visuals', 'Post at optimal times']
            },
            'instagram': {
                'name': 'Instagram',
                'char_limit': 2200,
                'best_practices': ['Use relevant hashtags', 'High-quality visuals', 'Stories for engagement']
            },
            'twitter': {
                'name': 'Twitter',
                'char_limit': 280,
                'best_practices': ['Be concise', 'Use trending hashtags', 'Engage in conversations']
            },
            'linkedin': {
                'name': 'LinkedIn',
                'char_limit': 1300,
                'best_practices': ['Professional tone', 'Industry insights', 'Network engagement']
            }
        }
        
        return platforms.get(platform, platforms['facebook'])
    
    def parse_suggestions(self, content: str, char_limit: int) -> List[Dict[str, Any]]:
        """
        Parse AI response into structured suggestions
        """
        lines = content.split('\n')
        suggestions = []
        current_suggestion = ""
        
        for line in lines:
            line = line.strip()
            if not line:
                if current_suggestion:
                    suggestions.append({
                        'content': current_suggestion.strip(),
                        'character_count': len(current_suggestion.strip()),
                        'within_limit': len(current_suggestion.strip()) <= char_limit
                    })
                    current_suggestion = ""
            else:
                # Remove numbering and formatting
                clean_line = line.lstrip('123456789. -•')
                if clean_line:
                    current_suggestion = clean_line
        
        # Add the last suggestion if exists
        if current_suggestion:
            suggestions.append({
                'content': current_suggestion.strip(),
                'character_count': len(current_suggestion.strip()),
                'within_limit': len(current_suggestion.strip()) <= char_limit
            })
        
        return suggestions[:3]  # Return max 3 suggestions
    
    def parse_content_ideas(self, content: str, count: int) -> List[Dict[str, Any]]:
        """
        Parse content ideas from AI response
        """
        # Fallback parsing for content ideas
        ideas = []
        lines = content.split('\n')
        
        current_idea = {'title': '', 'description': '', 'content': '', 'hashtags': [], 'type': 'text'}
        
        for line in lines:
            line = line.strip()
            if line.startswith(('Title:', 'title:')):
                if current_idea['title']:
                    ideas.append(current_idea.copy())
                current_idea = {'title': line.split(':', 1)[1].strip(), 'description': '', 'content': '', 'hashtags': [], 'type': 'text'}
            elif line.startswith(('Description:', 'description:')):
                current_idea['description'] = line.split(':', 1)[1].strip()
            elif line.startswith(('Content:', 'content:')):
                current_idea['content'] = line.split(':', 1)[1].strip()
            elif line.startswith(('Hashtags:', 'hashtags:')):
                hashtag_text = line.split(':', 1)[1].strip()
                current_idea['hashtags'] = [tag.strip().replace('#', '') for tag in hashtag_text.split() if tag.startswith('#')]
        
        if current_idea['title']:
            ideas.append(current_idea)
        
        return ideas[:count]
    
    def get_fallback_suggestions(self, original_content: str, action: str) -> List[Dict[str, Any]]:
        """
        Provide fallback suggestions when AI is unavailable
        """
        suggestions = []
        
        if action == 'shorten':
            suggestions.append({
                'content': original_content[:100] + '...' if len(original_content) > 100 else original_content,
                'character_count': min(len(original_content), 103),
                'within_limit': True
            })
        elif action == 'expand':
            expanded = f"{original_content} Contact us for more information! #construction #homeimprovement"
            suggestions.append({
                'content': expanded,
                'character_count': len(expanded),
                'within_limit': len(expanded) <= 2000
            })
        else:
            suggestions.append({
                'content': original_content,
                'character_count': len(original_content),
                'within_limit': len(original_content) <= 2000
            })
        
        return suggestions
    
    def get_fallback_hashtags(self) -> List[str]:
        """
        Provide fallback hashtags
        """
        return [
            'construction', 'homeimprovement', 'renovation', 'building',
            'contractor', 'home', 'design', 'remodeling', 'quality', 'professional'
        ]
    
    def get_fallback_content_ideas(self, business_type: str) -> List[Dict[str, Any]]:
        """
        Provide fallback content ideas
        """
        return [
            {
                'title': 'Before & After Showcase',
                'description': 'Show transformation of recent projects',
                'content': 'Check out this amazing transformation! From outdated to outstanding.',
                'hashtags': ['beforeandafter', 'transformation', 'renovation'],
                'type': 'image'
            },
            {
                'title': 'Client Testimonial',
                'description': 'Share positive feedback from satisfied customers',
                'content': 'Here\'s what our clients are saying about our work...',
                'hashtags': ['testimonial', 'happyclient', 'quality'],
                'type': 'text'
            }
        ]
    
    def calculate_performance_score(self, metrics: Dict[str, int]) -> int:
        """
        Calculate a performance score based on metrics
        """
        reach = metrics.get('reach', 0)
        engagement = metrics.get('engagement', 0)
        
        if reach == 0:
            return 0
        
        engagement_rate = (engagement / reach) * 100
        
        if engagement_rate >= 10:
            return 90
        elif engagement_rate >= 5:
            return 75
        elif engagement_rate >= 2:
            return 60
        elif engagement_rate >= 1:
            return 45
        else:
            return 30
    
    def extract_recommendations(self, analysis: str) -> List[str]:
        """
        Extract actionable recommendations from analysis
        """
        recommendations = []
        lines = analysis.split('\n')
        
        for line in lines:
            if 'recommend' in line.lower() or 'suggest' in line.lower() or 'try' in line.lower():
                recommendations.append(line.strip())
        
        return recommendations[:3]