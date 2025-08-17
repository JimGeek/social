#!/usr/bin/env python3
"""
Comprehensive Social Media Test Suite
Run all platform posting tests with a single command

This test suite validates all social media posting functionality across:
- Facebook Pages (text, image, multi-image, video, stories, reels)
- Instagram via Facebook Business (image, multi-image, video, stories)
- Instagram Direct (image, multi-image, video, stories, reels)
- LinkedIn (text, image, multi-image, video)

Usage:
    python3 comprehensive_social_media_test_suite.py [--delete-after]
    
Options:
    --delete-after    Delete created posts after testing (optional)
"""

import os
import sys
import time
import argparse
from datetime import datetime

# Add the backend directory to the Python path
sys.path.append('/opt/social-media/backend')
os.chdir('/opt/social-media/backend')

# Configure Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'social_backend.settings.production')

import django
django.setup()

from social.models import SocialPost, SocialAccount, SocialPostTarget
from social.tasks import publish_to_facebook, publish_to_instagram, publish_to_facebook_instagram, publish_to_linkedin

class ComprehensiveSocialMediaTestSuite:
    def __init__(self, delete_after=False):
        self.delete_after = delete_after
        self.test_results = []
        self.created_posts = []
        self.test_media = {
            'image': 'https://social-api.marvelhomes.pro/media/social_media/2025/8/933bf051-8e8c-4333-a611-778a765f6b91_Independence Day Ad - Marvel Homes.jpg',
            'multi_images': [
                'https://social-api.marvelhomes.pro/media/social_media/2025/8/933bf051-8e8c-4333-a611-778a765f6b91_Independence Day Ad - Marvel Homes.jpg',
                'https://social-api.marvelhomes.pro/media/social_media/2025/8/5c3c8a5e-7f43-4f0b-8a67-f2e8c9d4b1a3_sample_image.jpg'
            ],
            'video': 'https://social-api.marvelhomes.pro/media/temp/test_reel_video.mp4',
            'vertical_video': 'https://social-api.marvelhomes.pro/media/temp/facebook_reel_vertical.mp4'
        }
        
        # Get accounts
        self.accounts = self._get_test_accounts()
        
    def _get_test_accounts(self):
        """Get all test accounts"""
        accounts = {}
        
        try:
            accounts['facebook_page'] = SocialAccount.objects.get(
                platform__name='facebook',
                account_name='Marvel Homes'
            )
        except SocialAccount.DoesNotExist:
            print("❌ Facebook page account not found")
            
        try:
            accounts['instagram_facebook'] = SocialAccount.objects.get(
                platform__name='instagram',
                connection_type='facebook_business',
                account_name='Marvel Homes'
            )
        except SocialAccount.DoesNotExist:
            print("❌ Instagram Facebook Business account not found")
            
        try:
            accounts['instagram_direct'] = SocialAccount.objects.get(
                platform__name='instagram',
                connection_type='instagram_direct',
                account_username='thesincereseekerofficial'
            )
        except SocialAccount.DoesNotExist:
            print("❌ Instagram Direct account not found")
            
        try:
            accounts['linkedin'] = SocialAccount.objects.get(
                platform__name='linkedin',
                account_name='Jim Geek'
            )
        except SocialAccount.DoesNotExist:
            print("❌ LinkedIn account not found")
            
        return accounts
    
    def _create_test_post(self, content, post_type, media_files=None):
        """Create a test post"""
        post = SocialPost.objects.create(
            content=content,
            post_type=post_type,
            media_files=media_files or [],
            status='draft',
            created_by_id=1
        )
        self.created_posts.append(post)
        return post
    
    def _create_target_and_publish(self, post, account, publish_function):
        """Create target and publish post"""
        target = SocialPostTarget.objects.create(
            post=post,
            account=account,
            status='pending'
        )
        
        success, platform_post_id, platform_url, error_message = publish_function(post, account, target)
        
        return {
            'success': success,
            'platform_post_id': platform_post_id,
            'platform_url': platform_url,
            'error': error_message,
            'target': target
        }
    
    def _log_test_result(self, test_name, account_name, result):
        """Log test result"""
        status = "✅ PASS" if result['success'] else "❌ FAIL"
        self.test_results.append({
            'test': test_name,
            'account': account_name,
            'status': result['success'],
            'platform_post_id': result.get('platform_post_id'),
            'platform_url': result.get('platform_url'),
            'error': result.get('error')
        })
        
        print(f"{status} | {test_name} | {account_name}")
        if result['success']:
            print(f"      Platform Post ID: {result['platform_post_id']}")
            if result['platform_url']:
                print(f"      URL: {result['platform_url']}")
        else:
            print(f"      Error: {result['error']}")
        print()
    
    def test_facebook_page(self):
        """Test Facebook Page posting"""
        if 'facebook_page' not in self.accounts:
            print("⏭️  Skipping Facebook Page tests - account not found")
            return
            
        account = self.accounts['facebook_page']
        print(f"🧪 Testing Facebook Page: {account.account_name}")
        print("=" * 50)
        
        # Test 1: Text post
        post = self._create_test_post("Test Facebook Page - Text Post", "text")
        result = self._create_target_and_publish(post, account, publish_to_facebook)
        self._log_test_result("Facebook Page - Text Post", account.account_name, result)
        
        # Test 2: Image post
        post = self._create_test_post("Test Facebook Page - Image Post", "image", [self.test_media['image']])
        result = self._create_target_and_publish(post, account, publish_to_facebook)
        self._log_test_result("Facebook Page - Image Post", account.account_name, result)
        
        # Test 3: Multi-image post
        post = self._create_test_post("Test Facebook Page - Multi Image Post", "carousel", self.test_media['multi_images'])
        result = self._create_target_and_publish(post, account, publish_to_facebook)
        self._log_test_result("Facebook Page - Multi Image Post", account.account_name, result)
        
        # Test 4: Video post
        post = self._create_test_post("Test Facebook Page - Video Post", "video", [self.test_media['video']])
        result = self._create_target_and_publish(post, account, publish_to_facebook)
        self._log_test_result("Facebook Page - Video Post", account.account_name, result)
        
        # Test 5: Story Image
        post = self._create_test_post("Test Facebook Page - Story Image", "story", [self.test_media['image']])
        result = self._create_target_and_publish(post, account, publish_to_facebook)
        self._log_test_result("Facebook Page - Story Image", account.account_name, result)
        
        # Test 6: Story Video
        post = self._create_test_post("Test Facebook Page - Story Video", "story", [self.test_media['video']])
        result = self._create_target_and_publish(post, account, publish_to_facebook)
        self._log_test_result("Facebook Page - Story Video", account.account_name, result)
        
        # Test 7: Reel (with proper vertical video)
        post = self._create_test_post("🎬 Test Facebook Page - Reel (9:16 Vertical Video)", "reel", [self.test_media['vertical_video']])
        result = self._create_target_and_publish(post, account, publish_to_facebook)
        self._log_test_result("Facebook Page - Reel Video", account.account_name, result)
    
    def test_instagram_facebook_business(self):
        """Test Instagram via Facebook Business"""
        if 'instagram_facebook' not in self.accounts:
            print("⏭️  Skipping Instagram Facebook Business tests - account not found")
            return
            
        account = self.accounts['instagram_facebook']
        print(f"🧪 Testing Instagram via Facebook Business: {account.account_name}")
        print("=" * 50)
        
        # Test 1: Image post
        post = self._create_test_post("Test Instagram FB - Image Post", "image", [self.test_media['image']])
        result = self._create_target_and_publish(post, account, publish_to_facebook_instagram)
        self._log_test_result("Instagram FB - Image Post", account.account_name, result)
        
        # Test 2: Multi-image post
        post = self._create_test_post("Test Instagram FB - Multi Image Post", "carousel", self.test_media['multi_images'])
        result = self._create_target_and_publish(post, account, publish_to_facebook_instagram)
        self._log_test_result("Instagram FB - Multi Image Post", account.account_name, result)
        
        # Test 3: Video post (will be posted as Reel)
        post = self._create_test_post("Test Instagram FB - Video Post", "video", [self.test_media['video']])
        result = self._create_target_and_publish(post, account, publish_to_facebook_instagram)
        self._log_test_result("Instagram FB - Video Post", account.account_name, result)
        
        # Test 4: Story Image
        post = self._create_test_post("Test Instagram FB - Story Image", "story", [self.test_media['image']])
        result = self._create_target_and_publish(post, account, publish_to_facebook_instagram)
        self._log_test_result("Instagram FB - Story Image", account.account_name, result)
        
        # Test 5: Story Video
        post = self._create_test_post("Test Instagram FB - Story Video", "story", [self.test_media['video']])
        result = self._create_target_and_publish(post, account, publish_to_facebook_instagram)
        self._log_test_result("Instagram FB - Story Video", account.account_name, result)
    
    def test_instagram_direct(self):
        """Test Instagram Direct"""
        if 'instagram_direct' not in self.accounts:
            print("⏭️  Skipping Instagram Direct tests - account not found")
            return
            
        account = self.accounts['instagram_direct']
        print(f"🧪 Testing Instagram Direct: {account.account_username}")
        print("=" * 50)
        
        # Test 1: Image post
        post = self._create_test_post("Test Instagram Direct - Image Post", "image", [self.test_media['image']])
        result = self._create_target_and_publish(post, account, publish_to_instagram)
        self._log_test_result("Instagram Direct - Image Post", account.account_username, result)
        
        # Test 2: Multi-image post
        post = self._create_test_post("Test Instagram Direct - Multi Image Post", "carousel", self.test_media['multi_images'])
        result = self._create_target_and_publish(post, account, publish_to_instagram)
        self._log_test_result("Instagram Direct - Multi Image Post", account.account_username, result)
        
        # Test 3: Video post (will be posted as Reel)
        post = self._create_test_post("Test Instagram Direct - Video Post", "video", [self.test_media['video']])
        result = self._create_target_and_publish(post, account, publish_to_instagram)
        self._log_test_result("Instagram Direct - Video Post", account.account_username, result)
        
        # Test 4: Story Image
        post = self._create_test_post("Test Instagram Direct - Story Image", "story", [self.test_media['image']])
        result = self._create_target_and_publish(post, account, publish_to_instagram)
        self._log_test_result("Instagram Direct - Story Image", account.account_username, result)
        
        # Test 5: Story Video
        post = self._create_test_post("Test Instagram Direct - Story Video", "story", [self.test_media['video']])
        result = self._create_target_and_publish(post, account, publish_to_instagram)
        self._log_test_result("Instagram Direct - Story Video", account.account_username, result)
        
        # Test 6: Reel
        post = self._create_test_post("Test Instagram Direct - Reel", "reel", [self.test_media['video']])
        result = self._create_target_and_publish(post, account, publish_to_instagram)
        self._log_test_result("Instagram Direct - Reel", account.account_username, result)
    
    def test_linkedin(self):
        """Test LinkedIn posting"""
        if 'linkedin' not in self.accounts:
            print("⏭️  Skipping LinkedIn tests - account not found")
            return
            
        account = self.accounts['linkedin']
        print(f"🧪 Testing LinkedIn: {account.account_name}")
        print("=" * 50)
        
        # Test 1: Text post
        post = self._create_test_post("Test LinkedIn - Text Post", "text")
        result = self._create_target_and_publish(post, account, publish_to_linkedin)
        self._log_test_result("LinkedIn - Text Post", account.account_name, result)
        
        # Test 2: Image post
        post = self._create_test_post("Test LinkedIn - Image Post", "image", [self.test_media['image']])
        result = self._create_target_and_publish(post, account, publish_to_linkedin)
        self._log_test_result("LinkedIn - Image Post", account.account_name, result)
        
        # Test 3: Multi-image post
        post = self._create_test_post("Test LinkedIn - Multi Image Post", "carousel", self.test_media['multi_images'])
        result = self._create_target_and_publish(post, account, publish_to_linkedin)
        self._log_test_result("LinkedIn - Multi Image Post", account.account_name, result)
        
        # Test 4: Video post
        post = self._create_test_post("Test LinkedIn - Video Post", "video", [self.test_media['video']])
        result = self._create_target_and_publish(post, account, publish_to_linkedin)
        self._log_test_result("LinkedIn - Video Post", account.account_name, result)
    
    def cleanup_posts(self):
        """Delete created test posts"""
        if not self.delete_after:
            return
            
        print("🧹 Cleaning up test posts...")
        deleted_count = 0
        
        for post in self.created_posts:
            try:
                # Delete associated targets first
                post.targets.all().delete()
                # Delete the post
                post.delete()
                deleted_count += 1
            except Exception as e:
                print(f"❌ Failed to delete post {post.id}: {str(e)}")
        
        print(f"✅ Cleaned up {deleted_count} test posts")
    
    def print_summary(self):
        """Print test summary"""
        print("\n" + "=" * 70)
        print("📊 COMPREHENSIVE TEST RESULTS SUMMARY")
        print("=" * 70)
        
        total_tests = len(self.test_results)
        passed_tests = len([r for r in self.test_results if r['status']])
        failed_tests = total_tests - passed_tests
        
        print(f"Total Tests: {total_tests}")
        print(f"✅ Passed: {passed_tests}")
        print(f"❌ Failed: {failed_tests}")
        print(f"Success Rate: {(passed_tests/total_tests*100):.1f}%")
        
        if failed_tests > 0:
            print("\n❌ FAILED TESTS:")
            print("-" * 50)
            for result in self.test_results:
                if not result['status']:
                    print(f"• {result['test']} | {result['account']}")
                    print(f"  Error: {result['error']}")
        
        print("\n✅ SUCCESSFUL POSTS:")
        print("-" * 50)
        for result in self.test_results:
            if result['status']:
                print(f"• {result['test']} | {result['account']}")
                if result['platform_url']:
                    print(f"  URL: {result['platform_url']}")
        
        print(f"\n🕒 Test completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    def run_all_tests(self):
        """Run all tests"""
        print("🚀 Starting Comprehensive Social Media Test Suite")
        print(f"🕒 Test started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)
        
        # Run all platform tests
        self.test_facebook_page()
        self.test_instagram_facebook_business()
        self.test_instagram_direct()
        self.test_linkedin()
        
        # Print summary
        self.print_summary()
        
        # Cleanup if requested
        self.cleanup_posts()

def main():
    parser = argparse.ArgumentParser(description='Comprehensive Social Media Test Suite')
    parser.add_argument('--delete-after', action='store_true', 
                       help='Delete created posts after testing')
    
    args = parser.parse_args()
    
    # Run the test suite
    test_suite = ComprehensiveSocialMediaTestSuite(delete_after=args.delete_after)
    test_suite.run_all_tests()

if __name__ == "__main__":
    main()