import React, { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import socialAPI, { SocialPlatform, SocialAccount } from '../../services/socialApi';

interface SocialSettingsProps {}

const SocialSettings: React.FC<SocialSettingsProps> = () => {
  const [platforms, setPlatforms] = useState<SocialPlatform[]>([]);
  const [accounts, setAccounts] = useState<SocialAccount[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isConnecting, setIsConnecting] = useState<string | null>(null);
  const [searchParams, setSearchParams] = useSearchParams();
  const [notification, setNotification] = useState<{type: 'success' | 'error', message: string} | null>(null);

  useEffect(() => {
    loadData();
    handleOAuthCallback();
  }, []);

  const handleOAuthCallback = () => {
    const success = searchParams.get('success');
    const error = searchParams.get('error');
    const message = searchParams.get('message');
    const accounts = searchParams.get('accounts');
    const token = searchParams.get('token');

    // If token is provided, store it in localStorage to restore authentication
    if (token) {
      localStorage.setItem('token', token);
    }

    if (success === 'facebook_connected') {
      setNotification({
        type: 'success',
        message: `Facebook connected successfully! ${accounts} account(s) added.`
      });
      // Clear URL parameters
      setSearchParams({});
      // Reload data to show new accounts
      setTimeout(() => loadData(), 1000);
    } else if (success === 'instagram_connected') {
      setNotification({
        type: 'success',
        message: `Instagram connected successfully!`
      });
      // Clear URL parameters
      setSearchParams({});
      // Reload data to show new accounts
      setTimeout(() => loadData(), 1000);
    } else if (success === 'instagram_direct_connected') {
      const accountName = searchParams.get('account');
      setNotification({
        type: 'success',
        message: `Instagram account ${accountName ? `(${accountName})` : ''} connected successfully via Instagram Direct API!`
      });
      // Clear URL parameters
      setSearchParams({});
      // Reload data to show new accounts
      setTimeout(() => loadData(), 1000);
    } else if (success === 'linkedin_connected' || success === 'linkedin_updated') {
      const accountName = searchParams.get('account');
      setNotification({
        type: 'success',
        message: `LinkedIn account ${accountName ? `(${accountName})` : ''} ${success === 'linkedin_connected' ? 'connected' : 'updated'} successfully!`
      });
      // Clear URL parameters
      setSearchParams({});
      // Reload data to show new accounts
      setTimeout(() => loadData(), 1000);
    } else if (error) {
      let errorMessage = 'Connection failed';
      if (error === 'facebook_oauth_error' || error === 'instagram_oauth_error' || error === 'instagram_direct_oauth_error' || error === 'linkedin_oauth_error') {
        errorMessage = `OAuth error: ${message || 'Unknown error'}`;
      } else if (error === 'invalid_state') {
        errorMessage = 'Security validation failed. Please try again.';
      } else if (error === 'token_exchange_failed') {
        errorMessage = `Token exchange failed: ${message || 'Unknown error'}`;
      } else if (error === 'authentication_required') {
        errorMessage = 'Authentication expired. Please refresh the page and try again.';
      } else if (error === 'no_authorization_code') {
        errorMessage = 'Authorization was cancelled or incomplete. Please try connecting again.';
      }
      
      setNotification({
        type: 'error',
        message: errorMessage
      });
      // Clear URL parameters
      setSearchParams({});
    }

    // Auto-hide notification after 5 seconds
    if (success || error) {
      setTimeout(() => setNotification(null), 5000);
    }
  };

  const loadData = async () => {
    try {
      const [platformsData, accountsData] = await Promise.all([
        socialAPI.getPlatforms(),
        socialAPI.getAccounts()
      ]);
      
      setPlatforms(platformsData);
      setAccounts(accountsData);
    } catch (error) {
      console.error('Failed to load data:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleFacebookConnect = async () => {
    setIsConnecting('facebook');
    try {
      const response = await socialAPI.connectFacebook();
      window.location.href = response.auth_url;
    } catch (error) {
      console.error('Failed to connect Facebook:', error);
      alert('Failed to connect Facebook. Please try again.');
      setIsConnecting(null);
    }
  };

  const handleInstagramConnect = async () => {
    setIsConnecting('instagram');
    try {
      const response = await socialAPI.connectInstagram();
      window.location.href = response.auth_url;
    } catch (error) {
      console.error('Failed to connect Instagram:', error);
      alert('Failed to connect Instagram. Please try again.');
      setIsConnecting(null);
    }
  };

  const handleInstagramDirectConnect = async () => {
    setIsConnecting('instagram-direct');
    try {
      const response = await socialAPI.connectInstagramDirect();
      window.location.href = response.auth_url;
    } catch (error) {
      console.error('Failed to connect Instagram Direct:', error);
      alert('Failed to connect Instagram Direct. Please try again.');
      setIsConnecting(null);
    }
  };

  const handleLinkedInConnect = async () => {
    setIsConnecting('linkedin');
    try {
      const response = await socialAPI.connectLinkedIn();
      window.location.href = response.auth_url;
    } catch (error) {
      console.error('Failed to connect LinkedIn:', error);
      alert('Failed to connect LinkedIn. Please try again.');
      setIsConnecting(null);
    }
  };

  const handleDisconnect = async (accountId: string) => {
    if (!window.confirm('Are you sure you want to disconnect this account?')) {
      return;
    }

    try {
      await socialAPI.disconnectAccount(accountId);
      await loadData(); // Refresh data
      alert('Account disconnected successfully');
    } catch (error) {
      console.error('Failed to disconnect account:', error);
      alert('Failed to disconnect account. Please try again.');
    }
  };

  const handleRefreshToken = async (accountId: string) => {
    try {
      await socialAPI.refreshToken(accountId);
      await loadData(); // Refresh data
      alert('Token refreshed successfully');
    } catch (error) {
      console.error('Failed to refresh token:', error);
      alert('Failed to refresh token. Please try again.');
    }
  };

  const getConnectionStatus = (platform: SocialPlatform) => {
    return accounts.filter(acc => acc.platform.name === platform.name);
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'connected': return 'text-green-600 bg-green-100';
      case 'expired': return 'text-yellow-600 bg-yellow-100';
      case 'error': return 'text-red-600 bg-red-100';
      default: return 'text-gray-600 bg-gray-100';
    }
  };

  if (isLoading) {
    return (
      <div className="max-w-4xl mx-auto p-6">
        <div className="animate-pulse">
          <div className="h-8 bg-gray-200 rounded w-1/4 mb-4"></div>
          <div className="space-y-4">
            {[1, 2, 3].map(i => (
              <div key={i} className="h-20 bg-gray-200 rounded"></div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto p-6">
      {/* Notification Toast */}
      {notification && (
        <div className={`fixed top-4 right-4 z-50 p-4 rounded-lg shadow-lg ${
          notification.type === 'success' 
            ? 'bg-green-500 text-white' 
            : 'bg-red-500 text-white'
        }`}>
          <div className="flex items-center space-x-2">
            {notification.type === 'success' ? (
              <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
              </svg>
            ) : (
              <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
              </svg>
            )}
            <span>{notification.message}</span>
            <button 
              onClick={() => setNotification(null)}
              className="ml-2 hover:opacity-75"
            >
              <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
              </svg>
            </button>
          </div>
        </div>
      )}

      <div className="mb-6">
        <h1 className="text-3xl font-bold text-gray-900">Social Media Settings</h1>
        <p className="text-gray-600 mt-2">Connect and manage your social media accounts</p>
      </div>

      {/* Connected Accounts Summary */}
      <div className="bg-white rounded-lg shadow-sm border p-6 mb-6">
        <h2 className="text-lg font-semibold mb-4">Account Overview</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="text-center p-4 bg-green-50 rounded-lg">
            <div className="text-2xl font-bold text-green-600">
              {accounts.filter(acc => acc.status === 'connected').length}
            </div>
            <div className="text-sm text-green-800">Connected</div>
          </div>
          <div className="text-center p-4 bg-yellow-50 rounded-lg">
            <div className="text-2xl font-bold text-yellow-600">
              {accounts.filter(acc => acc.status === 'expired').length}
            </div>
            <div className="text-sm text-yellow-800">Token Expired</div>
          </div>
          <div className="text-center p-4 bg-red-50 rounded-lg">
            <div className="text-2xl font-bold text-red-600">
              {accounts.filter(acc => acc.status === 'error').length}
            </div>
            <div className="text-sm text-red-800">Connection Issues</div>
          </div>
        </div>
      </div>

      {/* Platform Connections */}
      <div className="space-y-4">
        {platforms.map((platform) => {
          const connectedAccounts = getConnectionStatus(platform);
          const isSupported = ['facebook', 'instagram', 'linkedin'].includes(platform.name); // Facebook, Instagram, and LinkedIn implemented

          return (
            <div key={platform.id} className="bg-white rounded-lg shadow-sm border p-6">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center space-x-4">
                  <div 
                    className="w-12 h-12 rounded-full flex items-center justify-center text-white text-lg font-bold"
                    style={{ backgroundColor: platform.color_hex }}
                  >
                    {platform.display_name.charAt(0)}
                  </div>
                  <div>
                    <h3 className="text-lg font-semibold">{platform.display_name}</h3>
                    <p className="text-sm text-gray-500">
                      {connectedAccounts.length} account{connectedAccounts.length !== 1 ? 's' : ''} connected
                    </p>
                  </div>
                </div>

                {isSupported ? (
                  <div className="flex space-x-2">
                    {platform.name === 'facebook' && (
                      <button
                        onClick={handleFacebookConnect}
                        disabled={isConnecting === 'facebook'}
                        className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 flex items-center space-x-2"
                      >
                        {isConnecting === 'facebook' ? (
                          <>
                            <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                            <span>Connecting...</span>
                          </>
                        ) : (
                          <>
                            <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                              <path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"/>
                            </svg>
                            <span>Connect Facebook</span>
                          </>
                        )}
                      </button>
                    )}
                    {platform.name === 'instagram' && (
                      <div className="flex flex-col space-y-2">
                        {/* Instagram via Facebook - WORKING METHOD */}
                        <button
                          onClick={handleInstagramConnect}
                          disabled={isConnecting === 'instagram'}
                          className="px-4 py-2 bg-gradient-to-r from-purple-500 to-pink-500 text-white rounded-lg hover:from-purple-600 hover:to-pink-600 disabled:opacity-50 flex items-center space-x-2"
                        >
                          {isConnecting === 'instagram' ? (
                            <>
                              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                              <span>Connecting...</span>
                            </>
                          ) : (
                            <>
                              <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                                <path d="M12.017 0C8.396 0 7.989.016 6.756.072 5.526.128 4.699.167 3.953.31c-.789.152-1.37.355-1.861.531-.507.18-.93.396-1.354.822-.424.426-.64.847-.822 1.354-.176.491-.379 1.072-.531 1.861-.143.746-.182 1.573-.238 2.803C.016 7.989 0 8.396 0 12.017c0 3.624.016 4.031.072 5.264.056 1.23.095 2.057.238 2.803.152.789.355 1.37.531 1.861.18.507.396.93.822 1.354.426.424.847.64 1.354.822.491.176 1.072.379 1.861.531.746.143 1.573.182 2.803.238 1.233.056 1.64.072 5.264.072 3.624 0 4.031-.016 5.264-.072 1.23-.056 2.057-.095 2.803-.238.789-.152 1.37-.355 1.861-.531.507-.18.93-.396 1.354-.822.424-.426.64-.847.822-1.354.176-.491.379-1.072.531-1.861.143-.746.182-1.573.238-2.803.056-1.233.072-1.64.072-5.264 0-3.621-.016-4.028-.072-5.261-.056-1.23-.095-2.057-.238-2.803-.152-.789-.355-1.37-.531-1.861-.18-.507-.396-.93-.822-1.354-.426-.424-.847-.64-1.354-.822-.491-.176-1.072-.379-1.861-.531C19.087.167 18.26.128 17.03.072 15.797.016 15.39 0 12.017 0zm0 2.144c3.529 0 3.913.016 5.289.072 1.236.056 2.124.174 2.623.29.623.215 1.146.501 1.595.95.449.449.735.972.95 1.595.116.499.234 1.387.29 2.623.056 1.376.072 1.76.072 5.289 0 3.529-.016 3.913-.072 5.289-.056 1.236-.174 2.124-.29 2.623-.215.623-.501 1.146-.95 1.595-.449.449-.972.735-1.595.95-.499.116-1.387.234-2.623.29-1.376.056-1.76.072-5.289.072-3.529 0-3.913-.016-5.289-.072-1.236-.056-2.124-.174-2.623-.29-.623-.215-1.146-.501-1.595-.95-.449-.449-.735-.972-.95-1.595-.116-.499-.234-1.387-.29-2.623-.056-1.376-.072-1.76-.072-5.289 0-3.529.016-3.913.072-5.289.056-1.236.174-2.124.29-2.623.215-.623.501-1.146.95-1.595.449-.449.972-.735 1.595-.95.499-.116 1.387-.234 2.623-.29 1.376-.056 1.76-.072 5.289-.072z"/>
                                <path d="M12.017 5.838c-3.403 0-6.162 2.759-6.162 6.162s2.759 6.163 6.162 6.163 6.162-2.759 6.162-6.163c0-3.403-2.759-6.162-6.162-6.162zm0 10.162c-2.209 0-4-1.79-4-4 0-2.209 1.791-4 4-4s4 1.791 4 4c0 2.21-1.791 4-4 4zm6.406-11.845c-.796 0-1.441.645-1.441 1.44s.645 1.44 1.441 1.44c.795 0 1.439-.645 1.439-1.44s-.644-1.44-1.439-1.40z"/>
                              </svg>
                              <span>via Facebook</span>
                            </>
                          )}
                        </button>
                        
                        {/* Instagram Direct */}
                        <button
                          onClick={handleInstagramDirectConnect}
                          disabled={isConnecting === 'instagram-direct'}
                          className="px-4 py-2 bg-gradient-to-r from-pink-500 to-rose-500 text-white rounded-lg hover:from-pink-600 hover:to-rose-600 disabled:opacity-50 flex items-center space-x-2"
                        >
                          {isConnecting === 'instagram-direct' ? (
                            <>
                              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                              <span>Connecting...</span>
                            </>
                          ) : (
                            <>
                              <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                                <path d="M12.017 0C8.396 0 7.989.016 6.756.072 5.526.128 4.699.167 3.953.31c-.789.152-1.37.355-1.861.531-.507.18-.93.396-1.354.822-.424.426-.64.847-.822 1.354-.176.491-.379 1.072-.531 1.861-.143.746-.182 1.573-.238 2.803C.016 7.989 0 8.396 0 12.017c0 3.624.016 4.031.072 5.264.056 1.23.095 2.057.238 2.803.152.789.355 1.37.531 1.861.18.507.396.93.822 1.354.426.424.847.64 1.354.822.491.176 1.072.379 1.861.531.746.143 1.573.182 2.803.238 1.233.056 1.64.072 5.264.072 3.624 0 4.031-.016 5.264-.072 1.23-.056 2.057-.095 2.803-.238.789-.152 1.37-.355 1.861-.531.507-.18.93-.396 1.354-.822.424-.426.64-.847.822-1.354.176-.491.379-1.072.531-1.861.143-.746.182-1.573.238-2.803.056-1.233.072-1.64.072-5.264 0-3.621-.016-4.028-.072-5.261-.056-1.23-.095-2.057-.238-2.803-.152-.789-.355-1.37-.531-1.861-.18-.507-.396-.93-.822-1.354-.426-.424-.847-.64-1.354-.822-.491-.176-1.072-.379-1.861-.531C19.087.167 18.26.128 17.03.072 15.797.016 15.39 0 12.017 0zm0 2.144c3.529 0 3.913.016 5.289.072 1.236.056 2.124.174 2.623.29.623.215 1.146.501 1.595.95.449.449.735.972.95 1.595.116.499.234 1.387.29 2.623.056 1.376.072 1.76.072 5.289 0 3.529-.016 3.913-.072 5.289-.056 1.236-.174 2.124-.29 2.623-.215.623-.501 1.146-.95 1.595-.449.449-.972.735-1.595.95-.499.116-1.387.234-2.623.29-1.376.056-1.76.072-5.289.072-3.529 0-3.913-.016-5.289-.072-1.236-.056-2.124-.174-2.623-.29-.623-.215-1.146-.501-1.595-.95-.449-.449-.735-.972-.95-1.595-.116-.499-.234-1.387-.29-2.623-.056-1.376-.072-1.76-.072-5.289 0-3.529.016-3.913.072-5.289.056-1.236.174-2.124.29-2.623.215-.623.501-1.146.95-1.595.449-.449.972-.735 1.595-.95.499-.116 1.387-.234 2.623-.29 1.376-.056 1.76-.072 5.289-.072z"/>
                                <path d="M12.017 5.838c-3.403 0-6.162 2.759-6.162 6.162s2.759 6.163 6.162 6.163 6.162-2.759 6.162-6.163c0-3.403-2.759-6.162-6.162-6.162zm0 10.162c-2.209 0-4-1.79-4-4 0-2.209 1.791-4 4-4s4 1.791 4 4c0 2.21-1.791 4-4 4zm6.406-11.845c-.796 0-1.441.645-1.441 1.44s.645 1.44 1.441 1.44c.795 0 1.439-.645 1.439-1.40s-.644-1.40-1.439-1.40z"/>
                              </svg>
                              <span>Direct</span>
                            </>
                          )}
                        </button>
                      </div>
                    )}
                    {platform.name === 'linkedin' && (
                      <button
                        onClick={handleLinkedInConnect}
                        disabled={isConnecting === 'linkedin'}
                        className="px-4 py-2 bg-blue-700 text-white rounded-lg hover:bg-blue-800 disabled:opacity-50 flex items-center space-x-2"
                      >
                        {isConnecting === 'linkedin' ? (
                          <>
                            <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                            <span>Connecting...</span>
                          </>
                        ) : (
                          <>
                            <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                              <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/>
                            </svg>
                            <span>Connect LinkedIn</span>
                          </>
                        )}
                      </button>
                    )}
                  </div>
                ) : (
                  <div className="px-4 py-2 bg-gray-100 text-gray-500 rounded-lg">
                    Coming Soon
                  </div>
                )}
              </div>

              {/* Connected Accounts List */}
              {connectedAccounts.length > 0 && (
                <div className="space-y-3">
                  <h4 className="font-medium text-gray-900">Connected Accounts</h4>
                  {connectedAccounts.map((account) => (
                    <div key={account.id} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                      <div className="flex items-center space-x-3">
                        {account.profile_picture_url ? (
                          <img 
                            src={account.profile_picture_url} 
                            alt={account.account_name}
                            className="w-10 h-10 rounded-full object-cover"
                          />
                        ) : (
                          <div 
                            className="w-10 h-10 rounded-full flex items-center justify-center text-white text-sm font-bold"
                            style={{ backgroundColor: platform.color_hex }}
                          >
                            {account.account_name.charAt(0)}
                          </div>
                        )}
                        <div>
                          <p className="font-medium text-gray-900">{account.account_name}</p>
                          <p className="text-sm text-gray-500">@{account.account_username || account.account_id}</p>
                          
                          {/* Posting capability indicator */}
                          {!account.posting_enabled && (
                            <p className="text-xs text-red-500 flex items-center space-x-1">
                              <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                                <path fillRule="evenodd" d="M13.477 14.89A6 6 0 015.11 6.524l8.367 8.368zm1.414-1.414L6.524 5.11a6 6 0 018.367 8.367zM18 10a8 8 0 11-16 0 8 8 0 0116 0z" clipRule="evenodd" />
                              </svg>
                              <span>Posting disabled (Personal Profile)</span>
                            </p>
                          )}
                          
                          {account.platform.name === 'instagram' && (
                            <p className="text-xs text-gray-400 flex items-center space-x-1">
                              {account.connection_type === 'instagram_direct' ? (
                                <>
                                  <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 24 24">
                                    <path d="M12.017 0C8.396 0 7.989.016 6.756.072 5.526.128 4.699.167 3.953.31c-.789.152-1.37.355-1.861.531-.507.18-.93.396-1.354.822-.424.426-.64.847-.822 1.354-.176.491-.379 1.072-.531 1.861-.143.746-.182 1.573-.238 2.803C.016 7.989 0 8.396 0 12.017c0 3.624.016 4.031.072 5.264.056 1.23.095 2.057.238 2.803.152.789.355 1.37.531 1.861.18.507.396.93.822 1.354.426.424.847.64 1.354.822.491.176 1.072.379 1.861.531.746.143 1.573.182 2.803.238 1.233.056 1.64.072 5.264.072 3.624 0 4.031-.016 5.264-.072 1.23-.056 2.057-.095 2.803-.238.789-.152 1.37-.355 1.861-.531.507-.18.93-.396 1.354-.822.424-.426.64-.847.822-1.354.176-.491.379-1.072.531-1.861.143-.746.182-1.573.238-2.803.056-1.233.072-1.64.072-5.264 0-3.621-.016-4.028-.072-5.261-.056-1.23-.095-2.057-.238-2.803-.152-.789-.355-1.37-.531-1.861-.18-.507-.396-.93-.822-1.354-.426-.424-.847-.64-1.354-.822-.491-.176-1.072-.379-1.861-.531C19.087.167 18.26.128 17.03.072 15.797.016 15.39 0 12.017 0zm0 2.144c3.529 0 3.913.016 5.289.072 1.236.056 2.124.174 2.623.29.623.215 1.146.501 1.595.95.449.449.735.972.95 1.595.116.499.234 1.387.29 2.623.056 1.376.072 1.76.072 5.289 0 3.529-.016 3.913-.072 5.289-.056 1.236-.174 2.124-.29 2.623-.215.623-.501 1.146-.95 1.595-.449.449-.972.735-1.595.95-.499.116-1.387.234-2.623.29-1.376.056-1.76.072-5.289.072-3.529 0-3.913-.016-5.289-.072-1.236-.056-2.124-.174-2.623-.29-.623-.215-1.146-.501-1.595-.95-.449-.449-.735-.972-.95-1.595-.116-.499-.234-1.387-.29-2.623-.056-1.376-.072-1.76-.072-5.289 0-3.529.016-3.913.072-5.289.056-1.236.174-2.124.29-2.623.215-.623.501-1.146.95-1.595.449-.449.972-.735 1.595-.95.499-.116 1.387-.234 2.623-.29 1.376-.056 1.76-.072 5.289-.072z"/>
                                    <path d="M12.017 5.838c-3.403 0-6.162 2.759-6.162 6.162s2.759 6.163 6.162 6.163 6.162-2.759 6.162-6.163c0-3.403-2.759-6.162-6.162-6.162zm0 10.162c-2.209 0-4-1.79-4-4 0-2.209 1.791-4 4-4s4 1.791 4 4c0 2.21-1.791 4-4 4zm6.406-11.845c-.796 0-1.441.645-1.441 1.44s.645 1.44 1.441 1.44c.795 0 1.439-.645 1.439-1.40s-.644-1.40-1.439-1.40z"/>
                                  </svg>
                                  <span>Connected via Instagram Direct</span>
                                </>
                              ) : (
                                <>
                                  <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 24 24">
                                    <path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"/>
                                  </svg>
                                  <span>Connected via Facebook</span>
                                </>
                              )}
                            </p>
                          )}
                          {account.platform.name === 'facebook' && account.connection_type === 'facebook_business' && (
                            <p className="text-xs text-gray-400">
                              via Facebook Business
                            </p>
                          )}
                        </div>
                        <div className="flex items-center space-x-2">
                          {account.platform.name === 'instagram' && (
                            <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                              account.connection_type === 'instagram_direct' 
                                ? 'bg-pink-100 text-pink-800' 
                                : 'bg-blue-100 text-blue-800'
                            }`}>
                              {account.connection_type === 'instagram_direct' ? 'Direct' : 'via Facebook'}
                            </span>
                          )}
                          <span className={`px-2 py-1 rounded-full text-xs font-medium ${getStatusColor(account.status)}`}>
                            {account.status}
                          </span>
                        </div>
                      </div>

                      <div className="flex items-center space-x-2">
                        {account.is_token_expired && (
                          <>
                            {account.platform.name === 'linkedin' ? (
                              <button
                                onClick={() => handleLinkedInConnect()}
                                className="px-3 py-1 text-sm bg-blue-600 text-white rounded hover:bg-blue-700"
                                disabled={isConnecting === 'linkedin'}
                              >
                                {isConnecting === 'linkedin' ? 'Reconnecting...' : 'Reconnect LinkedIn'}
                              </button>
                            ) : (
                              <button
                                onClick={() => handleRefreshToken(account.id)}
                                className="px-3 py-1 text-sm bg-yellow-600 text-white rounded hover:bg-yellow-700"
                              >
                                Refresh Token
                              </button>
                            )}
                          </>
                        )}
                        <button
                          onClick={() => handleDisconnect(account.id)}
                          className="px-3 py-1 text-sm bg-red-600 text-white rounded hover:bg-red-700"
                        >
                          Disconnect
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* Platform Features */}
              <div className="mt-4 pt-4 border-t border-gray-100">
                <h4 className="font-medium text-gray-900 mb-2">Platform Features</h4>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
                  <div className="flex items-center space-x-2">
                    <svg className={`w-4 h-4 ${platform.supports_scheduling ? 'text-green-500' : 'text-gray-400'}`} fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-12a1 1 0 10-2 0v4a1 1 0 00.293.707l2.828 2.829a1 1 0 101.415-1.415L11 9.586V6z" clipRule="evenodd" />
                    </svg>
                    <span className={platform.supports_scheduling ? 'text-gray-700' : 'text-gray-400'}>
                      Scheduling
                    </span>
                  </div>
                  <div className="flex items-center space-x-2">
                    <svg className={`w-4 h-4 ${platform.supports_hashtags ? 'text-green-500' : 'text-gray-400'}`} fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M9.243 3.03a1 1 0 01.727 1.213L9.53 6h2.94l.56-2.243a1 1 0 111.94.486L14.53 6H17a1 1 0 110 2h-2.97l-1 4H15a1 1 0 110 2h-2.47l-.56 2.242a1 1 1-1.94-.485L10.47 14H7.53l-.56 2.242a1 1 0 11-1.94-.485L5.47 14H3a1 1 0 110-2h2.97l1-4H5a1 1 0 110-2h2.47l.56-2.243a1 1 0 011.213-.727zM9.03 8l-1 4h2.94l1-4H9.03z" clipRule="evenodd" />
                    </svg>
                    <span className={platform.supports_hashtags ? 'text-gray-700' : 'text-gray-400'}>
                      Hashtags
                    </span>
                  </div>
                  <div className="flex items-center space-x-2">
                    <svg className={`w-4 h-4 ${platform.supports_first_comment ? 'text-green-500' : 'text-gray-400'}`} fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M18 10c0 3.866-3.582 7-8 7a8.841 8.841 0 01-4.083-.98L2 17l1.338-3.123C2.493 12.767 2 11.434 2 10c0-3.866 3.582-7 8-7s8 3.134 8 7zM7 9H5v2h2V9zm8 0h-2v2h2V9zM9 9h2v2H9V9z" clipRule="evenodd" />
                    </svg>
                    <span className={platform.supports_first_comment ? 'text-gray-700' : 'text-gray-400'}>
                      First Comment
                    </span>
                  </div>
                  <div className="flex items-center space-x-2">
                    <span className="text-gray-700">{platform.max_text_length} chars</span>
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Help Section */}
      <div className="mt-8 p-6 bg-blue-50 border border-blue-200 rounded-lg">
        <h3 className="font-semibold text-blue-900 mb-2">Need Help?</h3>
        <p className="text-blue-800 mb-4">
          <strong>Facebook:</strong> Requires Facebook App setup with API keys.<br/>
          <strong>Instagram via Facebook:</strong> For Business accounts connected to Facebook Pages (posting enabled). ✅ Working<br/>
          <strong>Instagram Direct:</strong> For personal accounts using Instagram Login API (read-only access). ✅ Ready
        </p>
        <div className="flex space-x-4">
          <button
            onClick={() => window.open('/FACEBOOK_SETUP.md', '_blank')}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            Facebook Setup Guide
          </button>
          <button
            onClick={() => window.open('https://developers.facebook.com/', '_blank')}
            className="px-4 py-2 border border-blue-600 text-blue-600 rounded-lg hover:bg-blue-600 hover:text-white"
          >
            Facebook Developers
          </button>
        </div>
      </div>
    </div>
  );
};

export default SocialSettings;