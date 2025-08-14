import React, { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import socialAPI, { SocialPost, SocialAccount, SocialPlatform } from '../../services/socialApi';

interface CalendarSchedulerProps {}

interface CalendarDay {
  date: Date;
  posts: SocialPost[];
  isCurrentMonth: boolean;
  isToday: boolean;
  isPast: boolean;
}

interface OptimalTime {
  platform: string;
  hour: number;
  engagement_score: number;
}

const CalendarScheduler: React.FC<CalendarSchedulerProps> = () => {
  const navigate = useNavigate();
  
  // State management
  const [currentDate, setCurrentDate] = useState(new Date());
  const [posts, setPosts] = useState<SocialPost[]>([]);
  const [accounts, setAccounts] = useState<SocialAccount[]>([]);
  const [platforms, setPlatforms] = useState<SocialPlatform[]>([]);
  const [selectedPlatform, setSelectedPlatform] = useState<string>('all');
  const [viewMode, setViewMode] = useState<'month' | 'week'>('month');
  const [optimalTimes, setOptimalTimes] = useState<OptimalTime[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [showOptimalTimes, setShowOptimalTimes] = useState(false);
  const [selectedPost, setSelectedPost] = useState<SocialPost | null>(null);
  const [showPostModal, setShowPostModal] = useState(false);
  
  // Load initial data
  useEffect(() => {
    loadCalendarData();
  }, [currentDate, selectedPlatform]);

  const loadCalendarData = async () => {
    setIsLoading(true);
    try {
      const startDate = getMonthStart(currentDate);
      const endDate = getMonthEnd(currentDate);
      
      const [postsData, accountsData, platformsData, optimalTimesData] = await Promise.all([
        socialAPI.getCalendarPosts(
          startDate.toISOString().split('T')[0],
          endDate.toISOString().split('T')[0]
        ),
        socialAPI.getAccounts(),
        socialAPI.getPlatforms(),
        socialAPI.getOptimalTimes(selectedPlatform !== 'all' ? selectedPlatform : undefined).catch(err => {
          console.warn('Optimal times failed:', err);
          return { optimal_times: [] };
        })
      ]);
      
      setPosts(postsData || []);
      setAccounts(accountsData || []);
      setPlatforms(platformsData || []);
      setOptimalTimes(optimalTimesData.optimal_times || []);
    } catch (error) {
      console.error('Failed to load calendar data:', error);
      setPosts([]);
      setAccounts([]);
      setPlatforms([]);
      setOptimalTimes([]);
    } finally {
      setIsLoading(false);
    }
  };

  // Calendar calculations
  const getMonthStart = (date: Date) => {
    const start = new Date(date.getFullYear(), date.getMonth(), 1);
    const dayOfWeek = start.getDay();
    start.setDate(start.getDate() - dayOfWeek);
    return start;
  };

  const getMonthEnd = (date: Date) => {
    const end = new Date(date.getFullYear(), date.getMonth() + 1, 0);
    const dayOfWeek = end.getDay();
    end.setDate(end.getDate() + (6 - dayOfWeek));
    return end;
  };

  const generateCalendarDays = useMemo(() => {
    const days: CalendarDay[] = [];
    const startDate = getMonthStart(currentDate);
    const endDate = getMonthEnd(currentDate);
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    
    for (let date = new Date(startDate); date <= endDate; date.setDate(date.getDate() + 1)) {
      const dayPosts = posts.filter(post => {
        if (!post.scheduled_at) return false;
        const postDate = new Date(post.scheduled_at);
        
        // Use local dates for comparison instead of UTC to match user's timezone
        const postLocalDate = new Date(postDate.getFullYear(), postDate.getMonth(), postDate.getDate());
        const calendarLocalDate = new Date(date.getFullYear(), date.getMonth(), date.getDate());
        
        const matches = postLocalDate.getTime() === calendarLocalDate.getTime();
        
        
        return matches;
      });

      days.push({
        date: new Date(date),
        posts: dayPosts,
        isCurrentMonth: date.getMonth() === currentDate.getMonth(),
        isToday: date.toDateString() === today.toDateString(),
        isPast: date < today
      });
    }
    
    return days;
  }, [currentDate, posts]);

  // Post scheduling handlers
  const handlePostClick = (post: SocialPost) => {
    setSelectedPost(post);
    setShowPostModal(true);
  };

  const handleReschedulePost = async (postId: string, newDate: Date, newTime: string) => {
    try {
      const [hours, minutes] = newTime.split(':').map(Number);
      const scheduledDateTime = new Date(newDate);
      scheduledDateTime.setHours(hours, minutes);
      
      await socialAPI.updatePost(postId, { 
        scheduled_at: scheduledDateTime.toISOString() 
      });
      await loadCalendarData();
      setShowPostModal(false);
    } catch (error) {
      console.error('Failed to reschedule post:', error);
      alert('Failed to reschedule post. Please try again.');
    }
  };

  const handleUnschedulePost = async (postId: string) => {
    try {
      await socialAPI.updatePost(postId, { scheduled_at: null });
      await loadCalendarData();
      setShowPostModal(false);
    } catch (error: any) {
      console.error('Failed to unschedule post:', error);
      if (error?.response?.data?.error?.includes('Published posts cannot be edited')) {
        alert('This post has already been published and cannot be unscheduled.');
      } else {
        alert('Failed to unschedule post. Please try again.');
      }
    }
  };

  // Navigation handlers
  const navigateMonth = (direction: 'prev' | 'next') => {
    setCurrentDate(prev => {
      const newDate = new Date(prev);
      newDate.setMonth(prev.getMonth() + (direction === 'next' ? 1 : -1));
      return newDate;
    });
  };

  const goToToday = () => {
    setCurrentDate(new Date());
  };

  // Utility functions
  const formatPostTime = (scheduledAt: string) => {
    const date = new Date(scheduledAt);
    return date.toLocaleTimeString('en-US', { 
      hour: 'numeric', 
      minute: '2-digit',
      hour12: true 
    });
  };

  const getPostStatusColor = (status: string) => {
    switch (status) {
      case 'published': return 'bg-green-100 text-green-800 border-green-200';
      case 'partially_published': return 'bg-yellow-100 text-yellow-800 border-yellow-200';
      case 'scheduled': return 'bg-blue-100 text-blue-800 border-blue-200';
      case 'draft': return 'bg-gray-100 text-gray-800 border-gray-200';
      case 'failed': return 'bg-red-100 text-red-800 border-red-200';
      default: return 'bg-gray-100 text-gray-800 border-gray-200';
    }
  };

  const getPlatformColor = (platformName: string) => {
    const platform = platforms.find(p => p.name === platformName);
    return platform?.color_hex || '#6B7280';
  };

  const unscheduledPosts = posts.filter(post => 
    !post.scheduled_at && post.status === 'draft'
  );

  if (isLoading) {
    return (
      <div className="max-w-7xl mx-auto p-6">
        <div className="animate-pulse">
          <div className="h-8 bg-gray-200 rounded w-1/4 mb-6"></div>
          <div className="grid grid-cols-7 gap-4 mb-4">
            {Array(7).fill(0).map((_, i) => (
              <div key={i} className="h-4 bg-gray-200 rounded"></div>
            ))}
          </div>
          <div className="grid grid-cols-7 gap-4">
            {Array(35).fill(0).map((_, i) => (
              <div key={i} className="h-32 bg-gray-200 rounded"></div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto p-6 min-h-screen flex flex-col">
      {/* Header */}
      <div className="mb-6 flex-shrink-0">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Calendar Scheduler</h1>
            <p className="text-gray-600 mt-1">Schedule and manage your social media posts</p>
          </div>
          
          <div className="flex items-center space-x-3">
            {/* View Mode Toggle */}
            <div className="flex bg-gray-100 rounded-lg p-1">
              <button
                onClick={() => setViewMode('month')}
                className={`px-3 py-1 rounded text-sm font-medium transition-colors ${
                  viewMode === 'month' 
                    ? 'bg-white text-gray-900 shadow-sm' 
                    : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                Month
              </button>
              <button
                onClick={() => setViewMode('week')}
                className={`px-3 py-1 rounded text-sm font-medium transition-colors ${
                  viewMode === 'week' 
                    ? 'bg-white text-gray-900 shadow-sm' 
                    : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                Week
              </button>
            </div>

            {/* Platform Filter */}
            <select
              value={selectedPlatform}
              onChange={(e) => setSelectedPlatform(e.target.value)}
              className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
            >
              <option value="all">All Platforms</option>
              {platforms.map(platform => (
                <option key={platform.id} value={platform.name}>
                  {platform.display_name}
                </option>
              ))}
            </select>

            {/* Optimal Times Toggle */}
            <button
              onClick={() => setShowOptimalTimes(!showOptimalTimes)}
              className={`px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                showOptimalTimes
                  ? 'bg-green-100 text-green-800 border border-green-200'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              {showOptimalTimes ? '✨ Optimal Times ON' : 'Show Optimal Times'}
            </button>

            {/* Create Post Button */}
            <button
              onClick={() => navigate('../create-post')}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
            >
              + Create Post
            </button>
          </div>
        </div>

        {/* Calendar Navigation */}
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <button
              onClick={() => navigateMonth('prev')}
              className="p-2 text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
            </button>
            
            <h2 className="text-xl font-semibold text-gray-900">
              {currentDate.toLocaleDateString('en-US', { month: 'long', year: 'numeric' })}
            </h2>
            
            <button
              onClick={() => navigateMonth('next')}
              className="p-2 text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
            </button>
          </div>

          <button
            onClick={goToToday}
            className="px-3 py-1 text-sm bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors"
          >
            Today
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-4 gap-6 flex-1">
        {/* Main Calendar */}
        <div className="xl:col-span-3">
          <div className="bg-white rounded-lg shadow-sm border overflow-hidden">
            {/* Calendar Header */}
            <div className="grid grid-cols-7 bg-gray-50">
              {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map(day => (
                <div key={day} className="p-3 text-center text-sm font-medium text-gray-700 border-r border-gray-200 last:border-r-0">
                  {day}
                </div>
              ))}
            </div>

            {/* Calendar Grid */}
            <div className="grid grid-cols-7 max-h-[calc(100vh-16rem)] overflow-y-auto">
              {generateCalendarDays.map((day, index) => (
                <div
                  key={day.date.toISOString()}
                  className={`min-h-32 p-2 border-r border-b border-gray-200 last:border-r-0 transition-colors ${
                    day.isCurrentMonth ? 'bg-white' : 'bg-gray-50'
                  } ${
                    day.isToday ? 'bg-blue-50' : ''
                  } ${
                    day.isPast ? 'opacity-60' : ''
                  }`}
                >
                  {/* Day number */}
                  <div className={`text-sm font-medium mb-2 ${
                    day.isToday 
                      ? 'text-blue-600 bg-blue-600 text-white w-6 h-6 rounded-full flex items-center justify-center' 
                      : day.isCurrentMonth ? 'text-gray-900' : 'text-gray-400'
                  }`}>
                    {day.date.getDate()}
                  </div>

                  {/* Optimal times indicator */}
                  {showOptimalTimes && !day.isPast && (
                    <div className="mb-1">
                      {optimalTimes.slice(0, 2).map((time, idx) => (
                        <div key={idx} className="text-xs text-green-600 bg-green-50 px-1 rounded mb-1">
                          ✨ {time.hour}:00
                        </div>
                      ))}
                    </div>
                  )}

                  
                  {/* Posts */}
                  <div className="space-y-1">
                    {day.posts.length > 0 && (
                      <div className="text-xs font-semibold text-blue-600 mb-1">
                        📅 {day.posts.length} post{day.posts.length > 1 ? 's' : ''}
                      </div>
                    )}
                    {day.posts.map((post) => (
                      <div
                        key={post.id}
                        onClick={() => handlePostClick(post)}
                        className={`p-2 rounded text-xs cursor-pointer transition-all hover:shadow-sm border-l-2 border-l-blue-500 ${
                          getPostStatusColor(post.status)
                        } ${
                          day.isPast ? 'cursor-not-allowed' : 'cursor-pointer'
                        }`}
                      >
                        {/* Post time */}
                        {post.scheduled_at && (
                          <div className="font-medium mb-1">
                            {formatPostTime(post.scheduled_at)}
                          </div>
                        )}
                        
                        {/* Post content preview */}
                        <div className="truncate text-gray-600 mb-1">
                          {post.content.substring(0, 30)}...
                        </div>
                        
                        {/* Status indicator and platform indicators */}
                        <div className="flex items-center justify-between">
                          <div className="flex space-x-1">
                            {post.targets.map((target, idx) => (
                              <div
                                key={idx}
                                className="w-3 h-3 rounded-full"
                                style={{ backgroundColor: getPlatformColor(target.account.platform.name) }}
                                title={target.account.platform.display_name}
                              />
                            ))}
                          </div>
                          {(post.status === 'published' || post.status === 'partially_published') && (
                            <span className="text-xs font-bold text-green-700 bg-green-200 px-1 rounded">
                              ✓ PUBLISHED
                            </span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Sidebar */}
        <div className="space-y-6 max-h-[calc(100vh-16rem)] overflow-y-auto">
          {/* Unscheduled Posts */}
          <div className="bg-white rounded-lg shadow-sm border p-4">
            <h3 className="font-semibold text-gray-900 mb-3">Draft Posts</h3>
            
            <div className="space-y-2 min-h-16 p-2 rounded-lg border-2 border-dashed border-gray-200">
              {unscheduledPosts.length === 0 ? (
                <div className="text-center py-8 text-gray-500">
                  <svg className="mx-auto h-8 w-8 mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 13h6m-3-3v6m5 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                  <p className="text-sm">No draft posts</p>
                </div>
              ) : (
                unscheduledPosts.map((post) => (
                  <div
                    key={post.id}
                    onClick={() => handlePostClick(post)}
                    className="p-3 bg-gray-50 rounded-lg cursor-pointer hover:bg-gray-100 transition-colors"
                  >
                    <div className="text-sm text-gray-900 font-medium mb-2">
                      {post.content.substring(0, 40)}...
                    </div>
                    <div className="flex items-center justify-between">
                      <div className="flex space-x-1">
                        {post.targets.map((target, idx) => (
                          <div
                            key={idx}
                            className="w-3 h-3 rounded-full"
                            style={{ backgroundColor: getPlatformColor(target.account.platform.name) }}
                          />
                        ))}
                      </div>
                      <span className="text-xs text-gray-500">Draft</span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Quick Actions */}
          <div className="bg-white rounded-lg shadow-sm border p-4">
            <h3 className="font-semibold text-gray-900 mb-3">Quick Actions</h3>
            <div className="space-y-2">
              <button
                onClick={() => navigate('../create-post')}
                className="w-full text-left px-3 py-2 text-sm text-gray-700 hover:bg-gray-50 rounded-lg transition-colors"
              >
                📝 Create New Post
              </button>
              <button
                onClick={() => navigate('../ideas')}
                className="w-full text-left px-3 py-2 text-sm text-gray-700 hover:bg-gray-50 rounded-lg transition-colors"
              >
                💡 Browse Ideas
              </button>
              <button
                onClick={() => navigate('../analytics')}
                className="w-full text-left px-3 py-2 text-sm text-gray-700 hover:bg-gray-50 rounded-lg transition-colors"
              >
                📊 View Analytics
              </button>
            </div>
          </div>

          {/* Stats */}
          <div className="bg-white rounded-lg shadow-sm border p-4">
            <h3 className="font-semibold text-gray-900 mb-3">This Month</h3>
            <div className="space-y-3">
              <div className="flex justify-between">
                <span className="text-sm text-gray-600">Scheduled</span>
                <span className="text-sm font-medium text-blue-600">
                  {posts.filter(p => p.status === 'scheduled').length}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm text-gray-600">Published</span>
                <span className="text-sm font-medium text-green-600">
                  {posts.filter(p => p.status === 'published').length}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm text-gray-600">Drafts</span>
                <span className="text-sm font-medium text-gray-600">
                  {posts.filter(p => p.status === 'draft').length}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Post Modal */}
      {showPostModal && selectedPost && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold">Post Details</h3>
              <button
                onClick={() => setShowPostModal(false)}
                className="text-gray-400 hover:text-gray-600"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Content</label>
                <div className="p-3 border border-gray-200 rounded-lg bg-gray-50 text-sm">
                  {selectedPost.content}
                </div>
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Platforms</label>
                <div className="flex space-x-2">
                  {selectedPost.targets.map((target, idx) => (
                    <div key={idx} className="flex items-center space-x-1">
                      <div
                        className="w-4 h-4 rounded-full"
                        style={{ backgroundColor: getPlatformColor(target.account.platform.name) }}
                      />
                      <span className="text-sm">{target.account.platform.display_name}</span>
                    </div>
                  ))}
                </div>
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Status</label>
                <div className="flex items-center space-x-2">
                  <span className={`inline-block px-2 py-1 text-xs font-semibold rounded ${getPostStatusColor(selectedPost.status)}`}>
                    {selectedPost.status.toUpperCase()}
                  </span>
                  {(selectedPost.status === 'published' || selectedPost.status === 'partially_published') && selectedPost.published_at && (
                    <span className="text-xs text-gray-500">
                      Published: {new Date(selectedPost.published_at).toLocaleString()}
                    </span>
                  )}
                </div>
              </div>
              
              {selectedPost.scheduled_at && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Scheduled Time</label>
                  <div className="text-sm text-gray-600">
                    {new Date(selectedPost.scheduled_at).toLocaleString()}
                  </div>
                </div>
              )}
              
              <div className="flex space-x-3 pt-4">
                {selectedPost.status === 'published' || selectedPost.status === 'partially_published' ? (
                  // Published post - only show view and delete options
                  <>
                    <button
                      onClick={() => navigate(`../posts/${selectedPost.id}`)}
                      className="flex-1 px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700 transition-colors"
                    >
                      View Details
                    </button>
                    <button
                      onClick={() => {
                        if (window.confirm('Are you sure you want to delete this published post? This action cannot be undone.')) {
                          // Handle delete - you may want to implement this
                          alert('Delete functionality not yet implemented.');
                        }
                      }}
                      className="flex-1 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors"
                    >
                      Delete
                    </button>
                  </>
                ) : (
                  // Draft or scheduled post - show edit options
                  <>
                    <button
                      onClick={() => navigate(`../posts/${selectedPost.id}`)}
                      className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
                    >
                      Edit Post
                    </button>
                    {selectedPost.scheduled_at ? (
                      <button
                        onClick={() => handleUnschedulePost(selectedPost.id)}
                        className="flex-1 px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors"
                      >
                        Unschedule
                      </button>
                    ) : (
                      <button
                        onClick={() => navigate(`../create-post?duplicate=${selectedPost.id}`)}
                        className="flex-1 px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors"
                      >
                        Schedule
                      </button>
                    )}
                  </>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default CalendarScheduler;