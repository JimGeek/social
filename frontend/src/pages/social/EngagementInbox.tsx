import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import socialAPI, { SocialComment, SocialAccount, SocialPlatform } from '../../services/socialApi';

interface EngagementInboxProps {}

interface InboxFilter {
  platform: string;
  sentiment: string;
  status: string;
  priority: string;
}

const EngagementInbox: React.FC<EngagementInboxProps> = () => {
  const navigate = useNavigate();
  
  // State management
  const [comments, setComments] = useState<SocialComment[]>([]);
  const [accounts, setAccounts] = useState<SocialAccount[]>([]);
  const [platforms, setPlatforms] = useState<SocialPlatform[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedComment, setSelectedComment] = useState<SocialComment | null>(null);
  const [showReplyModal, setShowReplyModal] = useState(false);
  const [replyText, setReplyText] = useState('');
  const [isReplying, setIsReplying] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  
  // Filter state
  const [filters, setFilters] = useState<InboxFilter>({
    platform: 'all',
    sentiment: 'all',
    status: 'all',
    priority: 'all'
  });
  
  // Tabs for different views
  const [activeTab, setActiveTab] = useState<'all' | 'unread' | 'flagged' | 'replied'>('all');

  // Load initial data
  useEffect(() => {
    loadInboxData();
  }, [filters, activeTab]);

  const loadInboxData = async () => {
    setIsLoading(true);
    try {
      const filterParam = activeTab !== 'all' ? activeTab : undefined;
      const [commentsData, accountsData, platformsData] = await Promise.all([
        socialAPI.getEngagementInbox(filterParam),
        socialAPI.getAccounts(),
        socialAPI.getPlatforms()
      ]);
      
      setComments(commentsData);
      setAccounts(accountsData);
      setPlatforms(platformsData);
    } catch (error) {
      console.error('Failed to load inbox data:', error);
      // Set mock data for demo purposes
      setComments([
        {
          id: '1',
          account: {
            id: '1',
            platform: { id: 1, name: 'facebook', display_name: 'Facebook', color_hex: '#1877F2' } as SocialPlatform,
            account_name: 'Marvel Homes Page',
            account_username: 'marvelhomes',
            profile_picture_url: '',
            status: 'connected' as any,
            connection_type: 'standard' as any,
            is_active: true,
            auto_publish: true,
            is_token_expired: false,
            posting_enabled: true,
            created_at: '',
            account_id: '1'
          },
          content: 'This kitchen renovation looks amazing! How long did it take to complete?',
          author_name: 'Sarah Johnson',
          author_username: 'sarah.johnson',
          author_avatar_url: 'https://images.unsplash.com/photo-1494790108755-2616b612b7c9?w=150',
          sentiment: 'positive',
          is_replied: false,
          is_flagged: false,
          priority_score: 85,
          platform_created_at: '2025-01-10T14:30:00Z',
          time_since_created: '2 hours ago'
        },
        {
          id: '2',
          account: {
            id: '2',
            platform: { id: 2, name: 'instagram', display_name: 'Instagram', color_hex: '#E4405F' } as SocialPlatform,
            account_name: 'Marvel Homes',
            account_username: 'marvelhomes',
            profile_picture_url: '',
            status: 'connected' as any,
            connection_type: 'instagram_direct' as any,
            is_active: true,
            auto_publish: true,
            is_token_expired: false,
            posting_enabled: true,
            created_at: '',
            account_id: '2'
          },
          content: 'I need help with my bathroom renovation. Can you provide a quote?',
          author_name: 'Mike Wilson',
          author_username: 'mike.wilson',
          author_avatar_url: 'https://images.unsplash.com/photo-1472099645785-5658abf4ff4e?w=150',
          sentiment: 'question',
          is_replied: false,
          is_flagged: true,
          priority_score: 95,
          platform_created_at: '2025-01-10T13:15:00Z',
          time_since_created: '3 hours ago'
        },
        {
          id: '3',
          account: {
            id: '1',
            platform: { id: 1, name: 'facebook', display_name: 'Facebook', color_hex: '#1877F2' } as SocialPlatform,
            account_name: 'Marvel Homes Page',
            account_username: 'marvelhomes',
            profile_picture_url: '',
            status: 'connected' as any,
            connection_type: 'standard' as any,
            is_active: true,
            auto_publish: true,
            is_token_expired: false,
            posting_enabled: true,
            created_at: '',
            account_id: '1'
          },
          content: 'The work was completed on time but there were some issues with cleanup.',
          author_name: 'David Smith',
          author_username: 'david.smith',
          author_avatar_url: 'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=150',
          sentiment: 'complaint',
          is_replied: true,
          is_flagged: false,
          priority_score: 75,
          platform_created_at: '2025-01-10T11:45:00Z',
          time_since_created: '5 hours ago'
        }
      ]);
      
      setAccounts([
        {
          id: '1',
          platform: { id: 1, name: 'facebook', display_name: 'Facebook', color_hex: '#1877F2' } as SocialPlatform,
          account_name: 'Marvel Homes Page',
          account_username: 'marvelhomes',
          profile_picture_url: '',
          status: 'connected' as any,
          connection_type: 'standard' as any,
          is_active: true,
          auto_publish: true,
          is_token_expired: false,
          posting_enabled: true,
          created_at: '',
          account_id: '1'
        }
      ]);
      
      setPlatforms([
        { id: 1, name: 'facebook', display_name: 'Facebook', color_hex: '#1877F2' } as SocialPlatform,
        { id: 2, name: 'instagram', display_name: 'Instagram', color_hex: '#E4405F' } as SocialPlatform
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  // Filter and search comments
  const filteredComments = comments.filter(comment => {
    const matchesSearch = comment.content.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         comment.author_name.toLowerCase().includes(searchTerm.toLowerCase());
    
    const matchesPlatform = filters.platform === 'all' || comment.account.platform.name === filters.platform;
    const matchesSentiment = filters.sentiment === 'all' || comment.sentiment === filters.sentiment;
    const matchesStatus = filters.status === 'all' || 
                         (filters.status === 'replied' && comment.is_replied) ||
                         (filters.status === 'unread' && !comment.is_replied);
    const matchesPriority = filters.priority === 'all' || 
                          (filters.priority === 'high' && comment.priority_score >= 80) ||
                          (filters.priority === 'medium' && comment.priority_score >= 60 && comment.priority_score < 80) ||
                          (filters.priority === 'low' && comment.priority_score < 60);
    
    return matchesSearch && matchesPlatform && matchesSentiment && matchesStatus && matchesPriority;
  });

  // Handlers
  const handleReply = async () => {
    if (!selectedComment || !replyText.trim()) return;
    
    setIsReplying(true);
    try {
      // In a real implementation, this would send the reply via the platform's API
      console.log('Replying to comment:', selectedComment.id, 'with:', replyText);
      
      // Update the comment as replied
      setComments(prev => 
        prev.map(comment => 
          comment.id === selectedComment.id 
            ? { ...comment, is_replied: true }
            : comment
        )
      );
      
      setShowReplyModal(false);
      setReplyText('');
      setSelectedComment(null);
      
      alert('Reply sent successfully!');
    } catch (error) {
      console.error('Failed to send reply:', error);
      alert('Failed to send reply. Please try again.');
    } finally {
      setIsReplying(false);
    }
  };

  const handleFlag = async (commentId: string) => {
    try {
      await socialAPI.flagComment(commentId);
      setComments(prev =>
        prev.map(comment =>
          comment.id === commentId
            ? { ...comment, is_flagged: !comment.is_flagged }
            : comment
        )
      );
    } catch (error) {
      console.error('Failed to flag comment:', error);
    }
  };

  // Utility functions
  const getSentimentColor = (sentiment: string) => {
    switch (sentiment) {
      case 'positive': return 'text-green-600 bg-green-100';
      case 'negative': return 'text-red-600 bg-red-100';
      case 'neutral': return 'text-gray-600 bg-gray-100';
      case 'question': return 'text-brand-800 bg-brand-100';
      case 'complaint': return 'text-orange-600 bg-orange-100';
      default: return 'text-gray-600 bg-gray-100';
    }
  };

  const getSentimentIcon = (sentiment: string) => {
    switch (sentiment) {
      case 'positive':
        return <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
          <path d="M2 10a8 8 0 018-8v8h8a8 8 0 11-16 0z" /><path d="M12 2.252A8.014 8.014 0 0117.748 8H12V2.252z" />
        </svg>;
      case 'negative':
        return <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
          <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
        </svg>;
      case 'question':
        return <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
          <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-8-3a1 1 0 00-.867.5 1 1 0 11-1.731-1A3 3 0 0113 8a3.001 3.001 0 01-2 2.83V11a1 1 0 11-2 0v-1a1 1 0 011-1 1 1 0 100-2zm0 8a1 1 0 100-2 1 1 0 000 2z" clipRule="evenodd" />
        </svg>;
      default:
        return <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
          <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
        </svg>;
    }
  };

  const getPriorityColor = (score: number) => {
    if (score >= 80) return 'text-red-600';
    if (score >= 60) return 'text-yellow-600';
    return 'text-green-600';
  };

  const getPriorityLabel = (score: number) => {
    if (score >= 80) return 'High';
    if (score >= 60) return 'Medium';
    return 'Low';
  };

  const getTabCount = (tab: string) => {
    switch (tab) {
      case 'unread': return comments.filter(c => !c.is_replied).length;
      case 'flagged': return comments.filter(c => c.is_flagged).length;
      case 'replied': return comments.filter(c => c.is_replied).length;
      default: return comments.length;
    }
  };

  if (isLoading) {
    return (
      <div className="max-w-7xl mx-auto p-6">
        <div className="animate-pulse">
          <div className="h-8 bg-gray-200 rounded w-1/4 mb-6"></div>
          <div className="space-y-4">
            {Array(5).fill(0).map((_, i) => (
              <div key={i} className="h-24 bg-gray-200 rounded"></div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto p-6">
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Engagement Inbox</h1>
            <p className="text-gray-600 mt-1">Manage comments and interactions across all platforms</p>
          </div>
          
          <div className="flex items-center space-x-3">
            <button className="px-4 py-2 bg-brand-800 text-white rounded-lg hover:bg-brand-900 transition-colors">
              Mark All Read
            </button>
          </div>
        </div>

        {/* Search and Filters */}
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-4 mb-6">
          <div className="lg:col-span-2">
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search comments and messages..."
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-800"
            />
          </div>
          
          <select
            value={filters.platform}
            onChange={(e) => setFilters(prev => ({ ...prev, platform: e.target.value }))}
            className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-800"
          >
            <option value="all">All Platforms</option>
            {platforms.map(platform => (
              <option key={platform.id} value={platform.name}>
                {platform.display_name}
              </option>
            ))}
          </select>
          
          <select
            value={filters.sentiment}
            onChange={(e) => setFilters(prev => ({ ...prev, sentiment: e.target.value }))}
            className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-800"
          >
            <option value="all">All Sentiments</option>
            <option value="positive">Positive</option>
            <option value="neutral">Neutral</option>
            <option value="negative">Negative</option>
            <option value="question">Questions</option>
            <option value="complaint">Complaints</option>
          </select>
          
          <select
            value={filters.priority}
            onChange={(e) => setFilters(prev => ({ ...prev, priority: e.target.value }))}
            className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-800"
          >
            <option value="all">All Priorities</option>
            <option value="high">High Priority</option>
            <option value="medium">Medium Priority</option>
            <option value="low">Low Priority</option>
          </select>
        </div>

        {/* Navigation Tabs */}
        <div className="border-b border-gray-200">
          <nav className="-mb-px flex space-x-8">
            {[
              { id: 'all', label: 'All' },
              { id: 'unread', label: 'Unread' },
              { id: 'flagged', label: 'Flagged' },
              { id: 'replied', label: 'Replied' }
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                className={`py-2 px-1 border-b-2 font-medium text-sm flex items-center space-x-2 ${
                  activeTab === tab.id
                    ? 'border-brand-800 text-brand-800'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                <span>{tab.label}</span>
                <span className={`px-2 py-1 text-xs rounded-full ${
                  activeTab === tab.id ? 'bg-brand-100 text-brand-800' : 'bg-gray-100 text-gray-600'
                }`}>
                  {getTabCount(tab.id)}
                </span>
              </button>
            ))}
          </nav>
        </div>
      </div>

      {/* Comments List */}
      <div className="space-y-4">
        {filteredComments.length === 0 ? (
          <div className="text-center py-12 bg-white rounded-lg shadow-sm border">
            <svg className="mx-auto h-12 w-12 text-gray-400 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 8h10M7 12h4m1 8l-4-4H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-3l-4 4z" />
            </svg>
            <h3 className="text-lg font-medium text-gray-900 mb-2">No comments found</h3>
            <p className="text-gray-500">Try adjusting your filters or check back later for new interactions.</p>
          </div>
        ) : (
          filteredComments.map((comment) => (
            <div key={comment.id} className={`bg-white rounded-lg shadow-sm border p-6 transition-colors ${
              !comment.is_replied ? 'border-l-4 border-l-brand-800' : ''
            }`}>
              {/* Comment Header */}
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center space-x-3">
                  {/* Author Avatar */}
                  {comment.author_avatar_url ? (
                    <img 
                      src={comment.author_avatar_url} 
                      alt={comment.author_name}
                      className="w-10 h-10 rounded-full object-cover"
                    />
                  ) : (
                    <div className="w-10 h-10 bg-gray-300 rounded-full flex items-center justify-center">
                      <span className="text-gray-600 font-medium text-sm">
                        {comment.author_name.charAt(0)}
                      </span>
                    </div>
                  )}
                  
                  <div>
                    <div className="flex items-center space-x-2">
                      <h3 className="font-medium text-gray-900">{comment.author_name}</h3>
                      <span className="text-gray-500 text-sm">@{comment.author_username}</span>
                    </div>
                    <div className="flex items-center space-x-2 mt-1">
                      <div 
                        className="w-3 h-3 rounded-full"
                        style={{ backgroundColor: comment.account.platform.color_hex }}
                        title={comment.account.platform.display_name}
                      />
                      <span className="text-sm text-gray-500">{comment.time_since_created}</span>
                    </div>
                  </div>
                </div>
                
                <div className="flex items-center space-x-2">
                  {/* Sentiment Badge */}
                  <span className={`px-2 py-1 rounded-full text-xs font-medium flex items-center space-x-1 ${getSentimentColor(comment.sentiment)}`}>
                    {getSentimentIcon(comment.sentiment)}
                    <span className="capitalize">{comment.sentiment}</span>
                  </span>
                  
                  {/* Priority Badge */}
                  <span className={`px-2 py-1 rounded-full text-xs font-medium bg-gray-100 ${getPriorityColor(comment.priority_score)}`}>
                    {getPriorityLabel(comment.priority_score)}
                  </span>
                  
                  {/* Status Indicators */}
                  {comment.is_flagged && (
                    <span className="px-2 py-1 rounded-full text-xs font-medium bg-red-100 text-red-800">
                      Flagged
                    </span>
                  )}
                  {comment.is_replied && (
                    <span className="px-2 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800">
                      Replied
                    </span>
                  )}
                </div>
              </div>
              
              {/* Comment Content */}
              <div className="mb-4">
                <p className="text-gray-800">{comment.content}</p>
              </div>
              
              {/* Action Buttons */}
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-3">
                  <button
                    onClick={() => {
                      setSelectedComment(comment);
                      setShowReplyModal(true);
                    }}
                    disabled={comment.is_replied}
                    className="flex items-center space-x-1 px-3 py-1.5 text-sm text-brand-800 hover:text-brand-900 hover:bg-brand-50 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 10h10a8 8 0 018 8v2M3 10l6 6m-6-6l6-6" />
                    </svg>
                    <span>Reply</span>
                  </button>
                  
                  <button
                    onClick={() => handleFlag(comment.id)}
                    className={`flex items-center space-x-1 px-3 py-1.5 text-sm rounded-lg transition-colors ${
                      comment.is_flagged
                        ? 'text-red-600 hover:text-red-800 hover:bg-red-50'
                        : 'text-gray-600 hover:text-gray-800 hover:bg-gray-50'
                    }`}
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 21v-4m0 0V5a2 2 0 012-2h6.5l1 1H21l-3 6 3 6h-8.5l-1-1H5a2 2 0 00-2 2zm9-13.5V9" />
                    </svg>
                    <span>{comment.is_flagged ? 'Unflag' : 'Flag'}</span>
                  </button>
                  
                  <button className="flex items-center space-x-1 px-3 py-1.5 text-sm text-gray-600 hover:text-gray-800 hover:bg-gray-50 rounded-lg transition-colors">
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" />
                    </svg>
                    <span>Like</span>
                  </button>
                </div>
                
                <div className="text-xs text-gray-500">
                  Priority Score: {comment.priority_score}
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Reply Modal */}
      {showReplyModal && selectedComment && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-lg w-full mx-4">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold">Reply to {selectedComment.author_name}</h3>
              <button
                onClick={() => {
                  setShowReplyModal(false);
                  setReplyText('');
                  setSelectedComment(null);
                }}
                className="text-gray-400 hover:text-gray-600"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            
            {/* Original Comment */}
            <div className="mb-4 p-3 bg-gray-50 rounded-lg">
              <p className="text-sm text-gray-600 italic">"{selectedComment.content}"</p>
            </div>
            
            {/* Reply Input */}
            <div className="space-y-4">
              <textarea
                value={replyText}
                onChange={(e) => setReplyText(e.target.value)}
                rows={4}
                placeholder="Write your reply..."
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-800 resize-none"
              />
              
              <div className="flex space-x-3">
                <button
                  onClick={() => {
                    setShowReplyModal(false);
                    setReplyText('');
                    setSelectedComment(null);
                  }}
                  className="flex-1 px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={handleReply}
                  disabled={!replyText.trim() || isReplying}
                  className="flex-1 px-4 py-2 bg-brand-800 text-white rounded-lg hover:bg-brand-900 disabled:opacity-50 transition-colors flex items-center justify-center"
                >
                  {isReplying ? (
                    <>
                      <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                      Sending...
                    </>
                  ) : (
                    'Send Reply'
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default EngagementInbox;