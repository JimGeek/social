#!/usr/bin/env python3
"""
LinkedIn API Permissions Checker
This script checks what LinkedIn API access and permissions your app currently has
"""

import requests
import json
from social.models import SocialAccount

def check_linkedin_permissions():
    """Check current LinkedIn API access and permissions"""
    
    # Get LinkedIn account
    linkedin_account = SocialAccount.objects.filter(platform__name='linkedin').first()
    if not linkedin_account:
        print("❌ No LinkedIn account found in database")
        return
    
    print(f"🔍 Checking LinkedIn permissions for account: {linkedin_account.account_name}")
    print(f"Account ID: {linkedin_account.account_id}")
    print(f"Token expires: {linkedin_account.token_expires_at}")
    print()
    
    access_token = linkedin_account.access_token
    headers = {
        'Authorization': f'Bearer {access_token}',
        'LinkedIn-Version': '202210',
        'X-Restli-Protocol-Version': '2.0.0'
    }
    
    # Test 1: Basic profile access (should work with basic permissions)
    print("1️⃣ Testing basic profile access...")
    profile_url = f"https://api.linkedin.com/v2/people/(id:{linkedin_account.account_id})"
    params = {'projection': '(id,firstName,lastName,profilePicture)'}
    
    response = requests.get(profile_url, headers=headers, params=params)
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        print("   ✅ Basic profile access: WORKING")
    else:
        print(f"   ❌ Basic profile access: FAILED - {response.text}")
    print()
    
    # Test 2: Shares/Posts access (requires r_member_social or organization permissions)
    print("2️⃣ Testing posts/shares access...")
    shares_url = "https://api.linkedin.com/v2/shares"
    params = {
        'q': 'owners',
        'owners': f'urn:li:person:{linkedin_account.account_id}',
        'count': 5
    }
    
    response = requests.get(shares_url, headers=headers, params=params)
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        posts_count = len(data.get('elements', []))
        print(f"   ✅ Posts access: WORKING - Found {posts_count} posts")
    else:
        error_data = response.json() if response.headers.get('content-type') == 'application/json' else response.text
        print(f"   ❌ Posts access: FAILED - {error_data}")
    print()
    
    # Test 3: Share statistics (analytics) - requires Marketing Developer Platform
    print("3️⃣ Testing share statistics access...")
    if response.status_code == 200 and 'elements' in data and data['elements']:
        # Use first share for testing
        share_id = data['elements'][0].get('id')
        if share_id:
            stats_url = f"https://api.linkedin.com/v2/shareStatistics/{share_id}"
            response = requests.get(stats_url, headers=headers)
            print(f"   Status: {response.status_code}")
            if response.status_code == 200:
                print("   ✅ Share statistics: WORKING")
            else:
                error_data = response.json() if response.headers.get('content-type') == 'application/json' else response.text
                print(f"   ❌ Share statistics: FAILED - {error_data}")
        else:
            print("   ⚠️  No share ID available for testing")
    else:
        print("   ⚠️  Cannot test - no posts available")
    print()
    
    # Test 4: Organization access (if user has company pages)
    print("4️⃣ Testing organization access...")
    org_url = "https://api.linkedin.com/v2/organizationAcls"
    params = {'q': 'roleAssignee'}
    
    response = requests.get(org_url, headers=headers, params=params)
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        orgs_count = len(data.get('elements', []))
        print(f"   ✅ Organization access: WORKING - Found {orgs_count} organizations")
        if orgs_count > 0:
            print("   📝 You may want to switch to organization posting for better API access")
    else:
        error_data = response.json() if response.headers.get('content-type') == 'application/json' else response.text
        print(f"   ❌ Organization access: FAILED - {error_data}")
    print()
    
    # Test 5: Check token introspection (what scopes we actually have)
    print("5️⃣ Checking token scopes...")
    introspect_url = "https://api.linkedin.com/v2/introspectToken"
    response = requests.post(introspect_url, headers=headers)
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        scopes = data.get('scope', 'No scopes returned')
        print(f"   ✅ Current scopes: {scopes}")
    else:
        print(f"   ❌ Cannot introspect token: {response.text}")
    print()
    
    # Summary and recommendations
    print("📋 SUMMARY & RECOMMENDATIONS:")
    print("=" * 50)
    
    print("\n🔍 Based on the test results above, here's what you need:")
    print("\n📱 **Current LinkedIn App Products Needed:**")
    print("   1. Sign In with LinkedIn using OpenID Connect (Basic)")
    print("   2. Marketing Developer Platform (MDP) - FOR ANALYTICS")
    print("   3. Share on LinkedIn (for posting capabilities)")
    
    print("\n🔑 **Required API Permissions/Scopes:**")
    print("   • r_liteprofile - Basic profile (usually already granted)")
    print("   • r_emailaddress - Email access (usually already granted)")
    print("   • w_member_social - Post as individual")
    print("   • r_member_social - Read individual posts")
    print("   • rw_organization_admin - Organization page management")
    print("   • r_organization_social - Read organization posts")
    print("   • r_ads_reporting - Analytics and reporting (MDP required)")
    
    print("\n🚀 **Next Steps:**")
    print("   1. Log into LinkedIn Developer Portal: https://developer.linkedin.com/")
    print("   2. Go to your app settings")
    print("   3. Check 'Products' tab - request Marketing Developer Platform")
    print("   4. Update 'Auth' tab - add the scopes listed above")
    print("   5. Some products require LinkedIn approval (can take days/weeks)")
    
    print("\n💡 **Alternative Approach:**")
    print("   • Consider switching to LinkedIn Company Page posting")
    print("   • Company pages often have better API access")
    print("   • Organization posts have more comprehensive analytics")

if __name__ == "__main__":
    import os
    import sys
    import django
    
    # Setup Django
    sys.path.append('/Users/macbookpro/ProductionProjects/social-media/backend')
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'social_backend.settings')
    django.setup()
    
    check_linkedin_permissions()