import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { socialAPI, SocialPlatform, SocialPost } from '../services/socialApi';
import Logo from '../components/Logo';

const Dashboard: React.FC = () => {
  const { user, logout } = useAuth();
  const [platforms, setPlatforms] = useState<SocialPlatform[]>([]);
  const [recentPosts, setRecentPosts] = useState<SocialPost[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [platformsData, postsData] = await Promise.all([
          socialAPI.getPlatforms(),
          socialAPI.getPosts()
        ]);
        setPlatforms(platformsData);
        setRecentPosts(postsData.slice(0, 5)); // Get first 5 posts
      } catch (error) {
        console.error('Error fetching dashboard data:', error);
      } finally {
        setIsLoading(false);
      }
    };

    fetchData();
  }, []);

  const stats = [
    { name: 'Total Posts', value: recentPosts.length, href: '/social/create-post' },
    { name: 'Platforms', value: platforms.length, href: '/social/settings' },
    { name: 'Draft Posts', value: recentPosts.filter(p => p.status === 'draft').length, href: '/social/create-post' },
    { name: 'Published', value: recentPosts.filter(p => p.status === 'published').length, href: '/social/analytics' },
  ];

  const navigation = [
    { name: 'Create Post', href: '/social/create-post', icon: '✏️' },
    { name: 'Calendar', href: '/social/calendar', icon: '📅' },
    { name: 'Ideas Board', href: '/social/ideas', icon: '💡' },
    { name: 'Analytics', href: '/social/analytics', icon: '📊' },
    { name: 'Engagement', href: '/social/engagement', icon: '💬' },
    { name: 'Settings', href: '/social/settings', icon: '⚙️' },
  ];

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-brand-800"></div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-brand-50 dark:bg-gray-950">
      {/* Header */}
      <header className="bg-white dark:bg-gray-900 shadow-theme-sm border-b border-brand-200 dark:border-gray-800">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center py-6">
            <div className="flex items-center space-x-4">
              <Logo size={48} />
              <div>
                <h1 className="text-title-md font-bold text-brand-900 dark:text-white">Social Media Manager</h1>
                <p className="text-brand-600 dark:text-gray-400 text-theme-sm mt-1">Welcome back, {user?.first_name}!</p>
              </div>
            </div>
            <button
              onClick={logout}
              className="bg-error-500 text-white px-4 py-2.5 rounded-lg hover:bg-error-600 transition-colors font-medium text-theme-sm"
            >
              Sign out
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        {/* Stats */}
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4 mb-8">
          {stats.map((stat) => (
            <Link
              key={stat.name}
              to={stat.href}
              className="bg-white dark:bg-gray-900 overflow-hidden shadow-theme-sm rounded-xl hover:shadow-theme-md transition-all duration-200 border border-brand-200 dark:border-gray-800"
            >
              <div className="p-6">
                <div className="flex items-center">
                  <div className="flex-shrink-0">
                    <div className="text-title-sm font-bold text-brand-800">{stat.value}</div>
                  </div>
                  <div className="ml-5 w-0 flex-1">
                    <dt className="text-theme-sm font-medium text-gray-500 dark:text-gray-400 truncate">{stat.name}</dt>
                  </div>
                </div>
              </div>
            </Link>
          ))}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Quick Actions */}
          <div className="lg:col-span-2">
            <div className="bg-white dark:bg-gray-900 shadow-theme-sm rounded-xl border border-brand-200 dark:border-gray-800">
              <div className="px-6 py-6">
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-6">Quick Actions</h3>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
                  {navigation.map((item) => (
                    <Link
                      key={item.name}
                      to={item.href}
                      className="bg-brand-50 dark:bg-gray-800 p-4 rounded-lg text-center hover:bg-brand-100 dark:hover:bg-gray-700 transition-all duration-200 border border-brand-200 dark:border-gray-700 group"
                    >
                      <div className="text-2xl mb-2 group-hover:scale-110 transition-transform duration-200">{item.icon}</div>
                      <div className="text-theme-sm font-medium text-gray-900 dark:text-gray-100">{item.name}</div>
                    </Link>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* Recent Posts */}
          <div>
            <div className="bg-white dark:bg-gray-900 shadow-theme-sm rounded-xl border border-brand-200 dark:border-gray-800">
              <div className="px-6 py-6">
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-6">Recent Posts</h3>
                {recentPosts.length > 0 ? (
                  <div className="space-y-4">
                    {recentPosts.map((post) => (
                      <div key={post.id} className="border-l-4 border-brand-800 pl-4 py-2 bg-brand-50 dark:bg-gray-800 rounded-r-lg">
                        <p className="text-theme-sm text-gray-900 dark:text-gray-100 truncate font-medium">{post.content}</p>
                        <p className="text-theme-xs text-gray-500 dark:text-gray-400 mt-1">
                          <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${
                            post.status === 'published' 
                              ? 'bg-success-100 text-success-800 dark:bg-success-900/20 dark:text-success-400' 
                              : 'bg-warning-100 text-warning-800 dark:bg-warning-900/20 dark:text-warning-400'
                          }`}>
                            {post.status}
                          </span>
                          <span className="ml-2">{new Date(post.created_at).toLocaleDateString()}</span>
                        </p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-8">
                    <p className="text-gray-500 dark:text-gray-400 text-theme-sm">No posts yet. Create your first post!</p>
                    <Link 
                      to="/social/create-post" 
                      className="mt-3 inline-flex items-center px-4 py-2 bg-brand-800 text-white rounded-lg hover:bg-brand-900 transition-colors text-theme-sm font-medium"
                    >
                      Create Post
                    </Link>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Connected Platforms */}
        <div className="mt-8">
          <div className="bg-white dark:bg-gray-900 shadow-theme-sm rounded-xl border border-brand-200 dark:border-gray-800">
            <div className="px-6 py-6">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-6">Available Platforms</h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                {platforms.map((platform) => (
                  <div
                    key={platform.id}
                    className="flex items-center p-4 border-2 rounded-xl bg-brand-50 dark:bg-gray-800 hover:shadow-theme-sm transition-all duration-200"
                    style={{ borderColor: platform.color_hex }}
                  >
                    <div className="text-2xl mr-4" style={{ color: platform.color_hex }}>
                      📱
                    </div>
                    <div className="flex-1">
                      <p className="font-semibold text-gray-900 dark:text-gray-100 text-theme-sm">{platform.display_name}</p>
                      <p className="text-theme-xs text-gray-500 dark:text-gray-400 mt-1">
                        {platform.max_text_length} chars max
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
};

export default Dashboard;