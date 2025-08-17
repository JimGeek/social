import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import socialAPI, { SocialPlatform, SocialAccount, AIContentSuggestion } from '../../services/socialApi';
import api from '../../services/api';
import { convertLocalToUTC, debugTimezone } from '../../utils/timezone';

interface MediaFile {
  id: string;
  file_url: string;
  file_name: string;
  file_type: 'image' | 'video';
  file_size_mb: number;
  width?: number;
  height?: number;
  duration?: number;
  alt_text?: string;
}

interface PlatformCapability {
  type: string;
  display_name: string;
  description: string;
  requires_media: boolean;
  media_types: string[];
  max_media: number;
  notes?: string;
}

interface CreatePostProps {}

const CreatePost: React.FC<CreatePostProps> = () => {
  const navigate = useNavigate();
  const { organizationSlug } = useParams<{ organizationSlug: string }>();
  
  // State management
  const [platforms, setPlatforms] = useState<SocialPlatform[]>([]);
  const [accounts, setAccounts] = useState<SocialAccount[]>([]);
  const [selectedAccount, setSelectedAccount] = useState<string>('');
  
  // Post content state
  const [content, setContent] = useState('');
  const [postType, setPostType] = useState<'text' | 'image' | 'video' | 'carousel' | 'story' | 'reel' | ''>('');
  const [hashtags, setHashtags] = useState<string[]>([]);
  const [firstComment, setFirstComment] = useState('');
  const [scheduledAt, setScheduledAt] = useState('');
  
  // Media state
  const [mediaFiles, setMediaFiles] = useState<MediaFile[]>([]);
  const [isUploadingMedia, setIsUploadingMedia] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  const [platformCapabilities, setPlatformCapabilities] = useState<{[key: string]: PlatformCapability[]}>({});
  
  // Validation state
  const [validationErrors, setValidationErrors] = useState<string[]>([]);
  const [validationWarnings, setValidationWarnings] = useState<string[]>([]);
  
  // AI assistance state
  const [isAILoading, setIsAILoading] = useState(false);
  const [aiSuggestions, setAISuggestions] = useState<AIContentSuggestion[]>([]);
  const [showAISuggestions, setShowAISuggestions] = useState(false);
  const [selectedPlatformForAI, setSelectedPlatformForAI] = useState('instagram');
  
  // UI state
  const [isPublishing, setIsPublishing] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [characterCount, setCharacterCount] = useState(0);
  const [hashtagInput, setHashtagInput] = useState('');
  
  // Load data on component mount
  useEffect(() => {
    loadInitialData();
  }, []);
  
  // Update character count when content changes
  useEffect(() => {
    setCharacterCount(content.length);
  }, [content]);
  
  // Validate post when content or account change
  useEffect(() => {
    validatePost();
  }, [content, mediaFiles, selectedAccount, postType]);
  
  const loadInitialData = async () => {
    try {
      const [platformsData, accountsData] = await Promise.all([
        socialAPI.getPlatforms(),
        socialAPI.getAccounts()
      ]);
      
      setPlatforms(platformsData);
      const connectedAccounts = accountsData.filter(acc => acc.status === 'connected');
      setAccounts(connectedAccounts);
      
      // Load platform capabilities for connected accounts
      await loadPlatformCapabilities(connectedAccounts);
      
    } catch (error) {
      console.error('Failed to load data:', error);
    }
  };
  
  const loadPlatformCapabilities = async (accountList: SocialAccount[]) => {
    try {
      const capabilities: {[key: string]: PlatformCapability[]} = {};
      
      // Get unique platform names
      const platformNames = Array.from(new Set(accountList.map(acc => acc.platform.name)));
      
      for (const platformName of platformNames) {
        try {
          const response = await api.get(`/api/social/platforms/capabilities/?platform=${platformName}`);
          
          if (response.status === 200) {
            const data = response.data;
            if (data.account_capabilities && data.account_capabilities.length > 0) {
              capabilities[platformName] = data.account_capabilities[0].supported_types;
            }
          }
        } catch (error) {
          console.error(`Failed to load capabilities for ${platformName}:`, error);
        }
      }
      
      setPlatformCapabilities(capabilities);
    } catch (error) {
      console.error('Failed to load platform capabilities:', error);
    }
  };
  
  const validatePost = async () => {
    const errors: string[] = [];
    const warnings: string[] = [];
    
    if (!selectedAccount) return;
    
    // Get selected platform name
    const account = accounts.find(acc => acc.id === selectedAccount);
    const platformName = account?.platform.name;
    
    // Check Instagram requirements
    if (platformName === 'instagram') {
      if (mediaFiles.length === 0) {
        errors.push('Instagram requires at least one image or video. Text-only posts are not supported.');
      }
      
      // Check post type restrictions
      if (postType === 'story') {
        // Would need to check account type via API call
        warnings.push('Stories are only available for Instagram Business accounts.');
      }
      
      if (postType === 'reel' && mediaFiles.length > 0) {
        const nonVideoFiles = mediaFiles.filter(file => file.file_type !== 'video');
        if (nonVideoFiles.length > 0) {
          errors.push('Instagram Reels require video content only.');
        }
      }
    }
    
    // Check character limits
    if (account && content.length > account.platform.max_text_length) {
      errors.push(`Content exceeds ${account.platform.display_name} character limit (${account.platform.max_text_length} characters).`);
    }
    
    // Check media count limits
    if (account && mediaFiles.length > account.platform.max_image_count) {
      errors.push(`Too many media files for ${account.platform.display_name} (max ${account.platform.max_image_count}).`);
    }
    
    setValidationErrors(errors);
    setValidationWarnings(warnings);
  };
  
  const handleAccountSelection = (accountId: string) => {
    const account = accounts.find(acc => acc.id === accountId);
    if (!account?.posting_enabled) {
      return;
    }
    
    // If clicking the same account, deselect it
    if (selectedAccount === accountId) {
      setSelectedAccount('');
      setPostType('');
      setMediaFiles([]);
      setContent('');
      setFirstComment('');
    } else {
      // Select new account and clear form
      setSelectedAccount(accountId);
      setPostType('');
      setMediaFiles([]);
      setContent('');
      setFirstComment('');
    }
  };
  
  const handlePostTypeChange = (newPostType: typeof postType) => {
    // Clear media files and related state when changing post type
    setPostType(newPostType);
    setMediaFiles([]);
    setFirstComment('');
    
    // Also clear content if switching between text and media types
    if ((postType === 'text' && newPostType !== 'text') || 
        (postType !== 'text' && newPostType === 'text')) {
      setContent('');
    }
  };
  
  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  }, []);
  
  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const files = Array.from(e.dataTransfer.files);
      uploadFiles(files);
    }
  }, []);
  
  const uploadFiles = async (files: File[]) => {
    setIsUploadingMedia(true);
    
    try {
      // Get selected platform name for upload validation
      const platformName = selectedAccount 
        ? accounts.find(acc => acc.id === selectedAccount)?.platform.name || 'instagram'
        : 'instagram';
        
      const uploadPromises = files.map(async (file) => {
        const result = await socialAPI.uploadMedia(file, true);
        return result.file;
      });
      
      const uploadedFiles = await Promise.all(uploadPromises);
      setMediaFiles(prev => [...prev, ...uploadedFiles]);
      
    } catch (error) {
      console.error('Failed to upload files:', error);
      alert(`Upload failed: ${error}`);
    } finally {
      setIsUploadingMedia(false);
    }
  };
  
  const removeMediaFile = (fileId: string) => {
    setMediaFiles(prev => prev.filter(file => file.id !== fileId));
  };
  
  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const files = Array.from(e.target.files);
      uploadFiles(files);
    }
  };
  
  const addHashtag = () => {
    if (hashtagInput.trim() && !hashtags.includes(hashtagInput.trim())) {
      const tag = hashtagInput.trim().replace('#', '');
      setHashtags(prev => [...prev, tag]);
      setHashtagInput('');
    }
  };
  
  const removeHashtag = (tagToRemove: string) => {
    setHashtags(prev => prev.filter(tag => tag !== tagToRemove));
  };
  
  const getAISuggestions = async (action: 'improve' | 'shorten' | 'expand' | 'rewrite') => {
    if (!content.trim()) return;
    
    setIsAILoading(true);
    try {
      const suggestions = await socialAPI.getAIContentSuggestions({
        content,
        platform: selectedPlatformForAI,
        action
      });
      
      setAISuggestions(suggestions);
      setShowAISuggestions(true);
    } catch (error) {
      console.error('Failed to get AI suggestions:', error);
    } finally {
      setIsAILoading(false);
    }
  };
  
  const applySuggestion = (suggestion: AIContentSuggestion) => {
    setContent(suggestion.content);
    setShowAISuggestions(false);
  };
  
  const handlePublish = async (publishNow: boolean = true) => {
    if (!selectedAccount || validationErrors.length > 0 || !postType) {
      return;
    }
    
    // Instagram requires media
    const account = accounts.find(acc => acc.id === selectedAccount);
    const isInstagram = account?.platform.name === 'instagram';
    
    if (isInstagram && mediaFiles.length === 0) {
      alert('Instagram requires at least one image or video.');
      return;
    }
    
    setIsPublishing(true);
    try {
      // Create the post
      const postData = {
        content,
        post_type: postType as 'text' | 'image' | 'video' | 'carousel' | 'story' | 'reel',
        hashtags,
        first_comment: firstComment,
        media_files: mediaFiles.map(file => file.file_url),
        target_accounts: [selectedAccount]
      };
      
      const createdPost = await socialAPI.createPost(postData);
      
      if (publishNow) {
        // Publish immediately
        await socialAPI.publishPost(createdPost.id, [selectedAccount]);
        alert('Post published successfully!');
      } else if (scheduledAt) {
        // Schedule for later - properly convert local time to UTC
        const localDateTime = new Date(scheduledAt);
        debugTimezone(localDateTime, 'Scheduling Post');
        const utcDateTime = convertLocalToUTC(localDateTime);
        await socialAPI.schedulePost(createdPost.id, utcDateTime, [selectedAccount]);
        alert('Post scheduled successfully!');
      } else {
        // Save as draft
        alert('Post saved as draft!');
      }
      
      // Reset form
      setContent('');
      setMediaFiles([]);
      setHashtags([]);
      setFirstComment('');
      setSelectedAccount('');
      setScheduledAt('');
      
    } catch (error) {
      console.error('Failed to publish post:', error);
      alert('Failed to publish post. Please try again.');
    } finally {
      setIsPublishing(false);
    }
  };
  
  const getCharacterLimit = () => {
    if (!selectedAccount) return 2000;
    
    const account = accounts.find(acc => acc.id === selectedAccount);
    return account?.platform.max_text_length || 2000;
  };
  
  const getAvailablePostTypes = () => {
    if (!selectedAccount) return [];
    
    const account = accounts.find(acc => acc.id === selectedAccount);
    if (!account) return [];
    
    const platformName = account.platform.name;
    
    // Get supported post types for the selected platform
    const platformPostTypes: { [key: string]: string[] } = {
      'facebook': ['text', 'image', 'video', 'carousel'],
      'instagram': ['image', 'video', 'carousel', 'story', 'reel'],
      'linkedin': ['text', 'image', 'video'],
      'twitter': ['text', 'image', 'video'],
    };
    
    return platformPostTypes[platformName] || ['text', 'image'];
  };
  
  const selectedAccount_obj = accounts.find(acc => acc.id === selectedAccount);
  const selectedPlatformName = selectedAccount_obj?.platform.name;
  
  const characterLimit = getCharacterLimit();
  const isOverLimit = characterCount > characterLimit;
  const availablePostTypes = getAvailablePostTypes();
  const hasValidationIssues = validationErrors.length > 0;
  
  return (
    <div className="max-w-4xl mx-auto p-6">
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-brand-900">Create Post</h1>
        <p className="text-brand-600 mt-2">Create and publish content across your social media platforms</p>
      </div>
      
      {/* Platform Selection */}
      <div className="bg-white rounded-lg shadow-sm border p-6 mb-6">
        <h2 className="text-lg font-semibold mb-4">Select Account</h2>
        
        {accounts.length === 0 ? (
          <div className="text-center py-8">
            <div className="text-gray-400 mb-4">
              <svg className="mx-auto h-12 w-12" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
              </svg>
            </div>
            <h3 className="text-brand-900 font-medium mb-2">No connected accounts</h3>
            <p className="text-brand-600 mb-4">Connect your social media accounts to start posting</p>
            <button
              onClick={() => navigate(`/${organizationSlug}/social/settings`)}
              className="bg-brand-800 text-white px-4 py-2 rounded-lg hover:bg-brand-900 transition-colors"
            >
              Connect Accounts
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {accounts.map((account) => (
              <div
                key={account.id}
                onClick={() => handleAccountSelection(account.id)}
                className={`p-4 border-2 rounded-lg transition-all ${
                  !account.posting_enabled
                    ? 'border-gray-200 bg-gray-100 cursor-not-allowed opacity-60'
                    : selectedAccount === account.id
                    ? 'border-brand-800 bg-brand-50 cursor-pointer'
                    : 'border-gray-200 hover:border-gray-300 cursor-pointer'
                }`}
              >
                <div className="flex items-center space-x-3">
                  <div 
                    className="w-10 h-10 rounded-full flex items-center justify-center text-white text-sm font-bold"
                    style={{ backgroundColor: account.platform.color_hex }}
                  >
                    {account.platform.display_name.charAt(0)}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-brand-900 truncate">{account.account_name}</p>
                    <p className="text-sm text-brand-600">{account.platform.display_name}</p>
                    {!account.posting_enabled && (
                      <p className="text-xs text-red-500 flex items-center space-x-1 mt-1">
                        <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                          <path fillRule="evenodd" d="M13.477 14.89A6 6 0 015.11 6.524l8.367 8.368zm1.414-1.414L6.524 5.11a6 6 0 018.367 8.367zM18 10a8 8 0 11-16 0 8 8 0 0116 0z" clipRule="evenodd" />
                        </svg>
                        <span>Posting disabled</span>
                      </p>
                    )}
                  </div>
                  {selectedAccount === account.id && account.posting_enabled && (
                    <svg className="w-5 h-5 text-brand-800" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                    </svg>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
      
      {/* Post Type Selection */}
      {selectedAccount && (
        <div className="bg-white rounded-lg shadow-sm border p-6 mb-6">
          <h2 className="text-lg font-semibold mb-4">Content Type</h2>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            {availablePostTypes.map((type) => {
              const typeConfig = {
                text: { label: 'Text Post', icon: '📝', description: 'Text-only post' },
                image: { label: 'Image', icon: '🖼️', description: 'Single image with caption' },
                video: { label: 'Video', icon: '🎥', description: 'Single video with caption' },
                carousel: { label: 'Carousel', icon: '🎠', description: 'Multiple images/videos' },
                story: { label: 'Story', icon: '📖', description: '24-hour content' },
                reel: { label: 'Reel', icon: '🎬', description: 'Short vertical video' }
              };
              
              const config = typeConfig[type as keyof typeof typeConfig];
              
              return (
                <button
                  key={type}
                  onClick={() => handlePostTypeChange(type as any)}
                  className={`p-4 text-center rounded-lg border-2 transition-all ${
                    postType === type
                      ? 'border-brand-800 bg-brand-50 text-brand-800'
                      : 'border-gray-200 hover:border-gray-300 text-brand-700'
                  }`}
                >
                  <div className="text-2xl mb-2">{config.icon}</div>
                  <div className="font-medium text-sm">{config.label}</div>
                  <div className="text-xs text-brand-600 mt-1">{config.description}</div>
                </button>
              );
            })}
          </div>
          
          {/* Platform-specific notes */}
          {selectedPlatformName === 'instagram' && (
            <div className="mt-4 p-3 bg-brand-50 border border-brand-200 rounded-lg">
              <div className="flex items-start space-x-2">
                <svg className="w-5 h-5 text-brand-800 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
                </svg>
                <div className="text-sm text-brand-800">
                  <p className="font-medium">Instagram Requirements:</p>
                  <ul className="mt-1 list-disc list-inside space-y-1">
                    <li>All posts require at least one image or video</li>
                    <li>Stories are only available for Business accounts</li>
                    <li>Reels should be vertical videos (9:16 ratio) for best performance</li>
                    <li>Videos should be 3-90 seconds for Reels</li>
                  </ul>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
      
      {/* Media Upload Section - Only show for media posts */}
      {selectedAccount && ['image', 'video', 'carousel', 'story', 'reel'].includes(postType) && (
        <div className="bg-white rounded-lg shadow-sm border p-6 mb-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">Media Files</h2>
          <span className="text-sm text-brand-600">
            {mediaFiles.length} file{mediaFiles.length !== 1 ? 's' : ''} uploaded
          </span>
        </div>
        
        {/* Drag and drop area */}
        <div
          className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
            dragActive 
              ? 'border-brand-800 bg-brand-50' 
              : 'border-gray-300 hover:border-gray-400'
          }`}
          onDragEnter={handleDrag}
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={handleDrop}
        >
          {isUploadingMedia ? (
            <div className="space-y-2">
              <svg className="mx-auto h-8 w-8 text-brand-800 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              <p className="text-brand-800 font-medium">Uploading files...</p>
            </div>
          ) : (
            <div className="space-y-3">
              <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
              </svg>
              <div>
                <p className="text-brand-700 font-medium">Drop files here or click to browse</p>
                <p className="text-sm text-brand-600">Supports JPEG, PNG, GIF, MP4, MOV (max 100MB)</p>
              </div>
              <input
                type="file"
                multiple
                accept="image/*,video/*"
                onChange={handleFileInput}
                className="hidden"
                id="file-input"
              />
              <label
                htmlFor="file-input"
                className="inline-block bg-brand-800 text-white px-4 py-2 rounded-lg hover:bg-brand-900 cursor-pointer transition-colors"
              >
                Choose Files
              </label>
            </div>
          )}
        </div>
        
        {/* Uploaded files preview */}
        {mediaFiles.length > 0 && (
          <div className="mt-6">
            <h3 className="text-sm font-medium text-brand-700 mb-3">Uploaded Files</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {mediaFiles.map((file) => (
                <div key={file.id} className="relative bg-gray-50 rounded-lg p-3">
                  <div className="aspect-square bg-gray-200 rounded mb-2 flex items-center justify-center overflow-hidden">
                    {file.file_type === 'image' ? (
                      <img 
                        src={file.file_url} 
                        alt={file.alt_text || file.file_name}
                        className="w-full h-full object-cover"
                      />
                    ) : (
                      <div className="text-center">
                        <svg className="mx-auto h-8 w-8 text-gray-400 mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
                        </svg>
                        <span className="text-xs text-brand-600">
                          {file.duration ? `${Math.round(file.duration)}s` : 'Video'}
                        </span>
                      </div>
                    )}
                  </div>
                  <p className="text-xs text-brand-600 truncate" title={file.file_name}>
                    {file.file_name}
                  </p>
                  <p className="text-xs text-brand-600">
                    {file.file_size_mb.toFixed(1)} MB
                    {file.width && file.height && ` • ${file.width}×${file.height}`}
                  </p>
                  <button
                    onClick={() => removeMediaFile(file.id)}
                    className="absolute -top-2 -right-2 bg-red-500 text-white rounded-full w-6 h-6 flex items-center justify-center hover:bg-red-600 transition-colors"
                  >
                    <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
      )}
      
      {/* Validation Alerts */}
      {(validationErrors.length > 0 || validationWarnings.length > 0) && (
        <div className="mb-6 space-y-3">
          {validationErrors.map((error, index) => (
            <div key={`error-${index}`} className="bg-red-50 border border-red-200 rounded-lg p-4">
              <div className="flex">
                <svg className="w-5 h-5 text-red-400 mr-3 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                </svg>
                <p className="text-red-800 text-sm">{error}</p>
              </div>
            </div>
          ))}
          
          {validationWarnings.map((warning, index) => (
            <div key={`warning-${index}`} className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
              <div className="flex">
                <svg className="w-5 h-5 text-yellow-400 mr-3 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                </svg>
                <p className="text-yellow-800 text-sm">{warning}</p>
              </div>
            </div>
          ))}
        </div>
      )}
      
      {/* Content Composer - Show for all post types */}
      {selectedAccount && postType && (
        <div className="bg-white rounded-lg shadow-sm border p-6 mb-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">{postType === 'text' ? 'Post Content' : 'Caption'}</h2>
          <div className="flex items-center space-x-2">
            <span className={`text-sm ${isOverLimit ? 'text-red-600' : 'text-brand-600'}`}>
              {characterCount}/{characterLimit}
            </span>
            {isOverLimit && (
              <svg className="w-4 h-4 text-red-600" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
              </svg>
            )}
          </div>
        </div>
        
        <div className="relative">
          <textarea
            value={content}
            onChange={(e) => setContent(e.target.value)}
            placeholder={postType === 'text' ? 
              (selectedPlatformName === 'instagram' ? 
                "What's on your mind?" : 
                "What's on your mind?"
              ) : 
              "Write a caption for your post..."
            }
            rows={6}
            className={`w-full p-4 border rounded-lg resize-none focus:ring-2 focus:ring-brand-800 focus:border-transparent ${
              isOverLimit ? 'border-red-300 bg-red-50' : 'border-gray-300'
            }`}
          />
          
          {/* AI Assistance Buttons */}
          <div className="absolute bottom-3 right-3 flex space-x-1">
            <button
              onClick={() => getAISuggestions('improve')}
              disabled={!content.trim() || isAILoading}
              className="p-2 text-brand-600 hover:text-brand-800 disabled:opacity-50"
              title="AI Improve"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            </button>
            <button
              onClick={() => getAISuggestions('shorten')}
              disabled={!content.trim() || isAILoading}
              className="p-2 text-brand-600 hover:text-brand-800 disabled:opacity-50"
              title="AI Shorten"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 14l-7 7m0 0l-7-7m7 7V3" />
              </svg>
            </button>
            <button
              onClick={() => getAISuggestions('expand')}
              disabled={!content.trim() || isAILoading}
              className="p-2 text-brand-600 hover:text-brand-800 disabled:opacity-50"
              title="AI Expand"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 10l7-7m0 0l7 7m-7-7v18" />
              </svg>
            </button>
          </div>
        </div>
        
        {/* AI Suggestions Panel */}
        {showAISuggestions && (
          <div className="mt-4 p-4 bg-brand-50 border border-brand-200 rounded-lg">
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-medium text-brand-900">AI Suggestions</h3>
              <button
                onClick={() => setShowAISuggestions(false)}
                className="text-brand-800 hover:text-brand-800"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            
            <div className="space-y-3">
              {aiSuggestions.map((suggestion, index) => (
                <div key={index} className="p-3 bg-white rounded border">
                  <p className="text-gray-800 mb-2">{suggestion.content}</p>
                  <div className="flex items-center justify-between">
                    <span className={`text-xs ${suggestion.within_limit ? 'text-green-600' : 'text-red-600'}`}>
                      {suggestion.character_count} characters
                    </span>
                    <button
                      onClick={() => applySuggestion(suggestion)}
                      className="text-brand-800 hover:text-brand-800 text-sm font-medium"
                    >
                      Use This
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
      )}
      
      {/* Advanced Options */}
      <div className="bg-white rounded-lg shadow-sm border p-6 mb-6">
        <button
          onClick={() => setShowAdvanced(!showAdvanced)}
          className="flex items-center justify-between w-full text-left"
        >
          <h2 className="text-lg font-semibold">Advanced Options</h2>
          <svg 
            className={`w-5 h-5 transition-transform ${showAdvanced ? 'rotate-180' : ''}`}
            fill="none" 
            stroke="currentColor" 
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </button>
        
        {showAdvanced && (
          <div className="mt-4 space-y-4">
            {/* Hashtags */}
            <div>
              <label className="block text-sm font-medium text-brand-700 mb-2">Hashtags</label>
              <div className="flex flex-wrap gap-2 mb-2">
                {hashtags.map((tag) => (
                  <span
                    key={tag}
                    className="inline-flex items-center px-3 py-1 rounded-full text-sm bg-brand-100 text-brand-800"
                  >
                    #{tag}
                    <button
                      onClick={() => removeHashtag(tag)}
                      className="ml-2 text-brand-800 hover:text-brand-800"
                    >
                      <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  </span>
                ))}
              </div>
              <div className="flex space-x-2">
                <input
                  type="text"
                  value={hashtagInput}
                  onChange={(e) => setHashtagInput(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && addHashtag()}
                  placeholder="Add hashtag"
                  className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-800"
                />
                <button
                  onClick={addHashtag}
                  className="px-4 py-2 bg-brand-800 text-white rounded-lg hover:bg-brand-900"
                >
                  Add
                </button>
              </div>
            </div>
            
            {/* First Comment */}
            <div>
              <label className="block text-sm font-medium text-brand-700 mb-2">
                First Comment (Instagram/Facebook)
              </label>
              <textarea
                value={firstComment}
                onChange={(e) => setFirstComment(e.target.value)}
                placeholder="Add a first comment..."
                rows={3}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-800"
              />
            </div>
            
            {/* Scheduling */}
            <div>
              <label className="block text-sm font-medium text-brand-700 mb-2">Schedule Post</label>
              <input
                type="datetime-local"
                value={scheduledAt}
                onChange={(e) => setScheduledAt(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-800"
              />
            </div>
          </div>
        )}
      </div>
      
      {/* Action Buttons */}
      <div className="flex flex-col sm:flex-row gap-3">
        <button
          onClick={() => handlePublish(false)}
          disabled={!selectedAccount || !postType || isPublishing}
          className="flex-1 px-6 py-3 border border-gray-300 text-brand-700 rounded-lg hover:bg-brand-50 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Save as Draft
        </button>
        
        {scheduledAt && (
          <button
            onClick={() => handlePublish(false)}
            disabled={!selectedAccount || !postType || isPublishing || hasValidationIssues}
            className="flex-1 px-6 py-3 bg-orange-600 text-white rounded-lg hover:bg-orange-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isPublishing ? 'Scheduling...' : 'Schedule Post'}
          </button>
        )}
        
        <button
          onClick={() => handlePublish(true)}
          disabled={!selectedAccount || !postType || isPublishing || isOverLimit || hasValidationIssues}
          className="flex-1 px-6 py-3 bg-brand-800 text-white rounded-lg hover:bg-brand-900 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isPublishing ? 'Publishing...' : 'Publish Now'}
        </button>
      </div>
    </div>
  );
};

export default CreatePost;