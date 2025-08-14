"""
Instagram Business Account Helper

This service provides enhanced Instagram Business account detection,
setup guidance, and troubleshooting for analytics access.
"""

import logging
import requests
from typing import Dict, List, Any, Optional
from django.conf import settings
from django.utils import timezone

from ..models import SocialAccount

logger = logging.getLogger(__name__)


class InstagramBusinessHelper:
    """Helper service for Instagram Business account management and diagnostics"""
    
    def __init__(self):
        self.base_url = "https://graph.facebook.com/v18.0"
    
    def diagnose_account(self, account: SocialAccount) -> Dict[str, Any]:
        """Comprehensive diagnosis of Instagram account for Business readiness"""
        logger.info(f"Diagnosing Instagram account: {account.account_name}")
        
        diagnosis = {
            'account_name': account.account_name,
            'account_username': account.account_username,
            'account_id': account.account_id,
            'diagnosis_timestamp': timezone.now().isoformat(),
            'tests': {},
            'issues': [],
            'recommendations': [],
            'overall_status': 'unknown'
        }
        
        try:
            # Test 1: Basic Account Access
            basic_access = self._test_basic_access(account)
            diagnosis['tests']['basic_access'] = basic_access
            
            # Test 2: Account Type Detection
            account_type = self._detect_account_type(account)
            diagnosis['tests']['account_type'] = account_type
            
            # Test 3: Business Features Access
            business_features = self._test_business_features(account)
            diagnosis['tests']['business_features'] = business_features
            
            # Test 4: Facebook Page Connection
            page_connection = self._test_facebook_page_connection(account)
            diagnosis['tests']['page_connection'] = page_connection
            
            # Test 5: Insights Access
            insights_access = self._test_insights_access(account)
            diagnosis['tests']['insights_access'] = insights_access
            
            # Test 6: Permissions Check
            permissions_check = self._check_app_permissions(account)
            diagnosis['tests']['permissions'] = permissions_check
            
            # Analyze results and provide recommendations
            self._analyze_diagnosis(diagnosis)
            
            return diagnosis
            
        except Exception as e:
            logger.error(f"Error diagnosing Instagram account {account.account_name}: {str(e)}")
            diagnosis['error'] = str(e)
            diagnosis['overall_status'] = 'error'
            return diagnosis
    
    def _test_basic_access(self, account: SocialAccount) -> Dict[str, Any]:
        """Test basic Instagram account access"""
        try:
            url = f"{self.base_url}/{account.account_id}"
            params = {
                'fields': 'id,username',
                'access_token': account.access_token
            }
            
            response = requests.get(url, params=params)
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'status': 'success',
                    'can_access_account': True,
                    'account_data': data
                }
            else:
                return {
                    'status': 'failed',
                    'can_access_account': False,
                    'error': response.text,
                    'status_code': response.status_code
                }
                
        except Exception as e:
            return {
                'status': 'error',
                'can_access_account': False,
                'error': str(e)
            }
    
    def _detect_account_type(self, account: SocialAccount) -> Dict[str, Any]:
        """Detect if account is Personal, Business, or Creator"""
        try:
            # Try to get account type field
            url = f"{self.base_url}/{account.account_id}"
            params = {
                'fields': 'account_type',
                'access_token': account.access_token
            }
            
            response = requests.get(url, params=params)
            
            if response.status_code == 200:
                data = response.json()
                account_type = data.get('account_type', 'PERSONAL')
                return {
                    'status': 'success',
                    'account_type': account_type,
                    'is_business': account_type in ['BUSINESS', 'CREATOR'],
                    'node_type': 'IGBusiness' if account_type in ['BUSINESS', 'CREATOR'] else 'IGUser'
                }
            else:
                # If account_type field fails, account is likely Personal
                error_data = response.json()
                error_message = error_data.get('error', {}).get('message', '')
                
                if 'nonexisting field (account_type)' in error_message:
                    return {
                        'status': 'detected_personal',
                        'account_type': 'PERSONAL',
                        'is_business': False,
                        'node_type': 'IGUser',
                        'reason': 'account_type field not available (indicates Personal account)'
                    }
                else:
                    return {
                        'status': 'failed',
                        'error': response.text,
                        'status_code': response.status_code
                    }
                    
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e)
            }
    
    def _test_business_features(self, account: SocialAccount) -> Dict[str, Any]:
        """Test access to Business-specific features"""
        business_features = {
            'status': 'testing',
            'features_available': [],
            'features_blocked': [],
            'tests_run': 0
        }
        
        # Test 1: Media Insights
        try:
            url = f"{self.base_url}/{account.account_id}/media"
            params = {
                'fields': 'id',
                'limit': 1,
                'access_token': account.access_token
            }
            
            response = requests.get(url, params=params)
            business_features['tests_run'] += 1
            
            if response.status_code == 200:
                business_features['features_available'].append('media_access')
            else:
                business_features['features_blocked'].append('media_access')
                
        except Exception as e:
            business_features['features_blocked'].append('media_access')
        
        # Test 2: Business Discovery
        try:
            url = f"{self.base_url}/me"
            params = {
                'fields': f'business_discovery.username({account.account_username}){{username,name}}',
                'access_token': account.access_token
            }
            
            response = requests.get(url, params=params)
            business_features['tests_run'] += 1
            
            if response.status_code == 200:
                business_features['features_available'].append('business_discovery')
            else:
                business_features['features_blocked'].append('business_discovery')
                
        except Exception as e:
            business_features['features_blocked'].append('business_discovery')
        
        business_features['status'] = 'completed'
        return business_features
    
    def _test_facebook_page_connection(self, account: SocialAccount) -> Dict[str, Any]:
        """Test if Instagram account is connected to a Facebook Page"""
        try:
            url = f"{self.base_url}/{account.account_id}"
            params = {
                'fields': 'connected_facebook_page',
                'access_token': account.access_token
            }
            
            response = requests.get(url, params=params)
            
            if response.status_code == 200:
                data = response.json()
                connected_page = data.get('connected_facebook_page')
                
                if connected_page:
                    return {
                        'status': 'connected',
                        'has_facebook_page': True,
                        'page_data': connected_page
                    }
                else:
                    return {
                        'status': 'not_connected',
                        'has_facebook_page': False,
                        'reason': 'No connected Facebook Page found'
                    }
            else:
                error_data = response.json()
                error_message = error_data.get('error', {}).get('message', '')
                
                return {
                    'status': 'failed',
                    'has_facebook_page': False,
                    'error': error_message,
                    'reason': 'Cannot check Facebook Page connection (likely Personal account)'
                }
                
        except Exception as e:
            return {
                'status': 'error',
                'has_facebook_page': False,
                'error': str(e)
            }
    
    def _test_insights_access(self, account: SocialAccount) -> Dict[str, Any]:
        """Test Instagram Insights API access"""
        try:
            url = f"{self.base_url}/{account.account_id}/insights"
            params = {
                'metric': 'impressions,reach,profile_views',
                'period': 'day',
                'since': '2025-08-01',
                'until': '2025-08-05',
                'access_token': account.access_token
            }
            
            response = requests.get(url, params=params)
            
            if response.status_code == 200:
                data = response.json()
                insights_count = len(data.get('data', []))
                return {
                    'status': 'available',
                    'has_insights_access': True,
                    'insights_count': insights_count
                }
            else:
                error_data = response.json()
                error_code = error_data.get('error', {}).get('code', 0)
                error_message = error_data.get('error', {}).get('message', '')
                
                return {
                    'status': 'blocked',
                    'has_insights_access': False,
                    'error_code': error_code,
                    'error_message': error_message,
                    'reason': self._interpret_insights_error(error_code, error_message)
                }
                
        except Exception as e:
            return {
                'status': 'error',
                'has_insights_access': False,
                'error': str(e)
            }
    
    def _check_app_permissions(self, account: SocialAccount) -> Dict[str, Any]:
        """Check Facebook App permissions for Instagram"""
        try:
            # Get app access token to check permissions
            app_token_url = f"{self.base_url}/oauth/access_token"
            app_params = {
                'client_id': settings.FACEBOOK_APP_ID,
                'client_secret': settings.FACEBOOK_APP_SECRET,
                'grant_type': 'client_credentials'
            }
            
            app_response = requests.get(app_token_url, params=app_params)
            
            if app_response.status_code != 200:
                return {
                    'status': 'failed',
                    'error': 'Cannot get app access token'
                }
            
            app_token = app_response.json().get('access_token')
            
            # Check app permissions
            permissions_url = f"{self.base_url}/{settings.FACEBOOK_APP_ID}/permissions"
            perm_params = {
                'access_token': app_token
            }
            
            perm_response = requests.get(permissions_url, params=perm_params)
            
            if perm_response.status_code == 200:
                permissions_data = perm_response.json()
                instagram_permissions = [
                    'instagram_basic',
                    'instagram_manage_insights',
                    'pages_show_list',
                    'pages_read_engagement'
                ]
                
                available_permissions = [p['permission'] for p in permissions_data.get('data', [])]
                
                return {
                    'status': 'checked',
                    'required_permissions': instagram_permissions,
                    'available_permissions': available_permissions,
                    'missing_permissions': [p for p in instagram_permissions if p not in available_permissions]
                }
            else:
                return {
                    'status': 'failed',
                    'error': 'Cannot check app permissions'
                }
                
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e)
            }
    
    def _interpret_insights_error(self, error_code: int, error_message: str) -> str:
        """Interpret Instagram Insights API errors"""
        if error_code == 10:
            return "App does not have Instagram Insights permission"
        elif error_code == 100:
            if "permission" in error_message.lower():
                return "Insufficient permissions for Instagram Insights"
            else:
                return "Account may not be a Business account or not properly configured"
        elif error_code == 190:
            return "Access token expired or invalid"
        else:
            return f"Unknown error (Code: {error_code})"
    
    def _analyze_diagnosis(self, diagnosis: Dict[str, Any]) -> None:
        """Analyze diagnosis results and provide recommendations"""
        tests = diagnosis.get('tests', {})
        issues = []
        recommendations = []
        
        # Check basic access
        basic_access = tests.get('basic_access', {})
        if not basic_access.get('can_access_account'):
            issues.append("Cannot access Instagram account")
            recommendations.append("Check if access token is valid and not expired")
        
        # Check account type
        account_type = tests.get('account_type', {})
        if not account_type.get('is_business'):
            issues.append("Account is not configured as Business account")
            recommendations.append("Convert Instagram account to Business account in Instagram mobile app")
        
        # Check Facebook Page connection
        page_connection = tests.get('page_connection', {})
        if not page_connection.get('has_facebook_page'):
            issues.append("Instagram account is not connected to a Facebook Page")
            recommendations.append("Connect Instagram Business account to a Facebook Page")
        
        # Check insights access
        insights_access = tests.get('insights_access', {})
        if not insights_access.get('has_insights_access'):
            issues.append("Cannot access Instagram Insights")
            error_reason = insights_access.get('reason', 'Unknown reason')
            recommendations.append(f"Fix insights access: {error_reason}")
        
        # Check app permissions
        permissions = tests.get('permissions', {})
        missing_perms = permissions.get('missing_permissions', [])
        if missing_perms:
            issues.append(f"Missing app permissions: {', '.join(missing_perms)}")
            recommendations.append("Submit Facebook App for review to get advanced Instagram permissions")
        
        # Determine overall status
        if not issues:
            overall_status = 'ready_for_analytics'
        elif len(issues) <= 2:
            overall_status = 'needs_minor_fixes'
        else:
            overall_status = 'needs_major_setup'
        
        diagnosis['issues'] = issues
        diagnosis['recommendations'] = recommendations
        diagnosis['overall_status'] = overall_status
    
    def generate_setup_guide(self, diagnosis: Dict[str, Any]) -> str:
        """Generate a personalized setup guide based on diagnosis"""
        account_name = diagnosis.get('account_name', 'Instagram Account')
        issues = diagnosis.get('issues', [])
        recommendations = diagnosis.get('recommendations', [])
        overall_status = diagnosis.get('overall_status', 'unknown')
        
        guide = f"# Instagram Business Setup Guide for {account_name}\n\n"
        
        if overall_status == 'ready_for_analytics':
            guide += "✅ **Good News!** Your Instagram account is properly configured for analytics.\n\n"
        else:
            guide += "⚠️ **Setup Required** - Your Instagram account needs configuration for analytics access.\n\n"
            
            guide += "## Issues Found:\n"
            for i, issue in enumerate(issues, 1):
                guide += f"{i}. {issue}\n"
            
            guide += "\n## Recommended Actions:\n"
            for i, rec in enumerate(recommendations, 1):
                guide += f"{i}. {rec}\n"
            
            guide += "\n## Step-by-Step Instructions:\n"
            guide += "1. Open Instagram mobile app\n"
            guide += "2. Go to Profile → Settings → Account\n"
            guide += "3. Switch to Professional Account → Business\n"
            guide += "4. Connect to your Facebook Page\n"
            guide += "5. Return to your dashboard and reconnect the Instagram account\n"
        
        return guide