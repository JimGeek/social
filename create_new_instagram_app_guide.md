# Create New Instagram App - Step by Step Guide

## 1. Create New Facebook App
1. Go to https://developers.facebook.com/
2. Click "Create App"
3. Choose "Business" app type
4. Fill in app details:
   - App Name: "Your Social Media Manager"
   - App Contact Email: your email
   - Business Portfolio: select or create one

## 2. Add Instagram Product
1. In your new app dashboard, go to "Products"
2. Find "Instagram" and click "Set Up"
3. Choose "Instagram API with Instagram Login"

## 3. Configure Business Login Settings
1. Go to Products > Instagram > Instagram API with Instagram Login
2. Configure "Business Login Settings"
3. Add redirect URI: `https://localhost:8000/api/social/auth/instagram-direct/callback/`
4. Enable scopes:
   - instagram_business_basic
   - instagram_business_content_publish
   - instagram_business_manage_comments

## 4. Get App Credentials
1. Go to Settings > Basic
2. Copy your:
   - Instagram App ID
   - Instagram App Secret

## 5. Update Environment Variables
Update your `.env` file:
```
INSTAGRAM_BASIC_APP_ID=YOUR_NEW_APP_ID
INSTAGRAM_BASIC_APP_SECRET=YOUR_NEW_APP_SECRET
```

## 6. Test the New Configuration
Run the Instagram Direct OAuth test to verify everything works.