// import axios from 'axios';
import api from './api';

// Types for social media
export interface SocialPlatform {
  id: number;
  name: string;
  display_name: string;
  icon_class: string;
  color_hex: string;
  is_active: boolean;
  max_text_length: number;
  max_image_count: number;
  max_video_size_mb: number;
  supports_scheduling: boolean;
  supports_hashtags: boolean;
  supports_first_comment: boolean;
}

export interface SocialAccount {
  id: string;
  platform: SocialPlatform;
  account_id: string;
  account_name: string;
  account_username: string;
  profile_picture_url: string;
  status: 'connected' | 'expired' | 'disconnected' | 'error';
  connection_type: 'standard' | 'facebook_business' | 'instagram_direct';
  is_active: boolean;
  auto_publish: boolean;
  is_token_expired: boolean;
  posting_enabled: boolean;
  created_at: string;
}

export interface SocialPost {
  id: string;
  content: string;
  post_type: 'text' | 'image' | 'video' | 'carousel' | 'story' | 'reel';
  hashtags: string[];
  mentions: string[];
  first_comment: string;
  media_files: string[];
  thumbnail_url: string;
  status: 'draft' | 'scheduled' | 'publishing' | 'published' | 'partially_published' | 'failed' | 'cancelled';
  scheduled_at: string | null;
  published_at: string | null;
  ai_generated: boolean;
  targets: SocialPostTarget[];
  character_count: number;
  created_by_name: string;
  created_at: string;
  updated_at: string;
}

export interface SocialPostTarget {
  id: string;
  account: SocialAccount;
  content_override: string;
  hashtags_override: string[];
  platform_post_id: string;
  platform_url: string;
  status: string;
  error_message: string;
  published_at: string | null;
}

export interface SocialIdea {
  id: string;
  title: string;
  description: string;
  content_draft: string;
  tags: string[];
  category: string;
  target_platforms: string[];
  status: 'idea' | 'in_progress' | 'scheduled' | 'published' | 'archived';
  priority: number;
  ai_generated: boolean;
  created_by_name: string;
  created_at: string;
}

export interface SocialComment {
  id: string;
  account: SocialAccount;
  content: string;
  author_name: string;
  author_username: string;
  author_avatar_url: string;
  sentiment: 'positive' | 'neutral' | 'negative' | 'question' | 'complaint';
  is_replied: boolean;
  is_flagged: boolean;
  priority_score: number;
  platform_created_at: string;
  time_since_created: string;
}

export interface AIContentSuggestion {
  content: string;
  character_count: number;
  within_limit: boolean;
}

export interface AIContentRequest {
  content: string;
  platform: string;
  action: 'improve' | 'shorten' | 'expand' | 'rewrite';
}

export interface AIIdeaRequest {
  topics?: string[];
  business_type?: string;
  platform: string;
  count: number;
}

// Social Media API
export const socialAPI = {
  // Platforms
  getPlatforms: async (): Promise<SocialPlatform[]> => {
    const response = await api.get('/api/social/platforms/');
    return response.data.results || response.data;
  },

  // Accounts
  getAccounts: async (): Promise<SocialAccount[]> => {
    const response = await api.get('/api/social/accounts/');
    return response.data.results || response.data;
  },

  connectFacebook: async (): Promise<{ auth_url: string }> => {
    const response = await api.get('/api/social/auth/facebook/connect/');
    return response.data;
  },

  connectInstagram: async (): Promise<{ auth_url: string }> => {
    const response = await api.get('/api/social/auth/instagram/connect/');
    return response.data;
  },
  connectInstagramDirect: async (): Promise<{ auth_url: string }> => {
    const response = await api.get('/api/social/auth/instagram-direct/connect/');
    return response.data;
  },

  connectLinkedIn: async (): Promise<{ auth_url: string }> => {
    const response = await api.get('/api/social/auth/linkedin/connect/');
    return response.data;
  },

  disconnectAccount: async (accountId: string): Promise<void> => {
    await api.post(`/api/social/auth/disconnect/${accountId}/`);
  },

  refreshToken: async (accountId: string): Promise<void> => {
    await api.post(`/api/social/accounts/${accountId}/refresh_token/`);
  },

  // Posts
  getPosts: async (): Promise<SocialPost[]> => {
    const response = await api.get('/api/social/posts/');
    return response.data.results || response.data;
  },

  createPost: async (postData: Partial<SocialPost>): Promise<SocialPost> => {
    const response = await api.post('/api/social/posts/', postData);
    return response.data;
  },

  updatePost: async (postId: string, postData: Partial<SocialPost>): Promise<SocialPost> => {
    const response = await api.patch(`/api/social/posts/${postId}/`, postData);
    return response.data;
  },

  deletePost: async (postId: string): Promise<void> => {
    await api.delete(`/api/social/posts/${postId}/`);
  },

  duplicatePost: async (postId: string): Promise<SocialPost> => {
    const response = await api.post(`/api/social/posts/${postId}/duplicate/`);
    return response.data;
  },

  publishPost: async (postId: string, targetAccounts: string[]): Promise<any> => {
    const response = await api.post(`/api/social/posts/${postId}/publish/`, {
      target_accounts: targetAccounts
    });
    return response.data;
  },

  schedulePost: async (postId: string, scheduledAt: string, targetAccounts: string[]): Promise<any> => {
    const response = await api.post(`/api/social/posts/${postId}/schedule/`, {
      scheduled_at: scheduledAt,
      target_accounts: targetAccounts
    });
    return response.data;
  },

  cancelPost: async (postId: string): Promise<void> => {
    await api.post(`/api/social/posts/${postId}/cancel/`);
  },

  // Ideas
  getIdeas: async (): Promise<SocialIdea[]> => {
    const response = await api.get('/api/social/ideas/');
    return response.data.results || response.data;
  },

  createIdea: async (ideaData: Partial<SocialIdea>): Promise<SocialIdea> => {
    const response = await api.post('/api/social/ideas/', ideaData);
    return response.data;
  },

  updateIdea: async (ideaId: string, ideaData: Partial<SocialIdea>): Promise<SocialIdea> => {
    const response = await api.patch(`/api/social/ideas/${ideaId}/`, ideaData);
    return response.data;
  },

  deleteIdea: async (ideaId: string): Promise<void> => {
    await api.delete(`/api/social/ideas/${ideaId}/`);
  },

  convertIdeaToPost: async (ideaId: string): Promise<SocialPost> => {
    const response = await api.post(`/api/social/ideas/${ideaId}/convert_to_post/`);
    return response.data;
  },

  // Comments (Engagement Inbox)
  getEngagementInbox: async (filter?: string): Promise<SocialComment[]> => {
    const params = filter ? { filter } : {};
    const response = await api.get('/api/social/engagement/inbox/', { params });
    return response.data.results || response.data;
  },

  flagComment: async (commentId: string): Promise<{ is_flagged: boolean }> => {
    const response = await api.post(`/api/social/engagement/flag/${commentId}/`);
    return response.data;
  },

  // AI Assistance
  getAIContentSuggestions: async (request: AIContentRequest): Promise<AIContentSuggestion[]> => {
    const response = await api.post('/api/social/ai/content-suggestions/', request);
    return response.data.suggestions;
  },

  getAIHashtagSuggestions: async (content: string, platform: string): Promise<string[]> => {
    const response = await api.get('/api/social/hashtags/suggestions/', {
      params: { content, platform }
    });
    return response.data.ai_suggestions;
  },

  generateAIIdeas: async (request: AIIdeaRequest): Promise<any[]> => {
    const response = await api.post('/api/social/ai/generate-ideas/', request);
    return response.data.ideas;
  },

  // Analytics
  getAnalyticsSummary: async (dateRange?: { startDate: string; endDate: string }): Promise<any> => {
    const params: any = {};
    
    if (dateRange) {
      params.start_date = dateRange.startDate;
      params.end_date = dateRange.endDate;
    }
    
    const response = await api.get('/api/social/analytics/summary/', { params });
    return response.data;
  },

  getPlatformAnalytics: async (platform: string, dateRange?: { startDate: string; endDate: string }): Promise<any> => {
    const params: any = {};
    
    if (dateRange) {
      params.start_date = dateRange.startDate;
      params.end_date = dateRange.endDate;
    }
    
    const response = await api.get(`/api/social/analytics/platform/${platform}/`, { params });
    return response.data;
  },

  // Sync analytics data
  syncAnalytics: async (accountId?: string, daysBack: number = 30): Promise<any> => {
    const data: any = { days_back: daysBack };
    
    if (accountId) {
      data.account_id = accountId;
    }
    
    const response = await api.post('/api/social/analytics/sync/', data);
    return response.data;
  },

  // Export analytics data
  exportAnalytics: async (format: 'csv' | 'excel' = 'csv', dateRange?: { startDate: string; endDate: string }, platform?: string): Promise<Blob> => {
    const params = new URLSearchParams();
    
    params.append('format', format);
    if (dateRange) {
      params.append('start_date', dateRange.startDate);
      params.append('end_date', dateRange.endDate);
    }
    if (platform) {
      params.append('platform', platform);
    }
    
    const response = await api.get('/api/social/analytics/export/', {
      params,
      responseType: 'blob'
    });
    
    return response.data;
  },

  // Calendar
  getCalendarPosts: async (startDate: string, endDate: string): Promise<SocialPost[]> => {
    const response = await api.get('/api/social/calendar/posts/', {
      params: { start_date: startDate, end_date: endDate }
    });
    return response.data.results || response.data;
  },

  getOptimalTimes: async (platform?: string): Promise<any> => {
    const params = platform ? { platform } : {};
    const response = await api.get('/api/social/calendar/optimal-times/', { params });
    return response.data;
  },

  // Media
  uploadMedia: async (file: File, analyzeContent = true): Promise<any> => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('analyze_content', String(analyzeContent));
    formData.append('generate_alt_text', 'true');

    const response = await api.post('/api/social/media/upload/', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  // Advanced Analytics endpoints
  getPostPerformance: async (dateRange?: { startDate: string; endDate: string }, platform?: string): Promise<any> => {
    const params: any = {};
    
    if (dateRange) {
      params.start_date = dateRange.startDate;
      params.end_date = dateRange.endDate;
    }
    if (platform) {
      params.platform = platform;
    }
    
    const response = await api.get('/api/social/analytics/post-performance/', { params });
    return response.data;
  },

  getEngagementAnalysis: async (dateRange?: { startDate: string; endDate: string }, platform?: string): Promise<any> => {
    const params: any = {};
    
    if (dateRange) {
      params.start_date = dateRange.startDate;
      params.end_date = dateRange.endDate;
    }
    if (platform) {
      params.platform = platform;
    }
    
    const response = await api.get('/api/social/analytics/engagement-analysis/', { params });
    return response.data;
  },

  autoSyncAnalytics: async (includeOldPosts?: boolean): Promise<any> => {
    const data: any = {};
    
    if (includeOldPosts !== undefined) {
      data.include_old_posts = includeOldPosts;
    }
    
    const response = await api.post('/api/social/analytics/auto-sync/', data);
    return response.data;
  },
};

export default socialAPI;