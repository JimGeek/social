import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import DashboardLayout from './components/DashboardLayout';
import Login from './pages/Login';
import Register from './pages/Register';
import Dashboard from './pages/Dashboard';
import CreatePost from './pages/social/CreatePost';
import CalendarScheduler from './pages/social/CalendarScheduler';
import SocialSettings from './pages/social/SocialSettings';
import IdeasBoard from './pages/social/IdeasBoard';
import Analytics from './pages/social/Analytics';
import EngagementInbox from './pages/social/EngagementInbox';
import ProtectedRoute from './components/ProtectedRoute';

function App() {
  return (
    <AuthProvider>
      <Router>
        <div className="min-h-screen bg-gray-50">
          <Routes>
            {/* Public routes */}
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Register />} />
            
            {/* Protected routes with layout */}
            <Route path="/" element={<ProtectedRoute><DashboardLayout><Dashboard /></DashboardLayout></ProtectedRoute>} />
            <Route path="/dashboard" element={<ProtectedRoute><DashboardLayout><Dashboard /></DashboardLayout></ProtectedRoute>} />
            <Route path="/social/create-post" element={<ProtectedRoute><DashboardLayout><CreatePost /></DashboardLayout></ProtectedRoute>} />
            <Route path="/social/calendar" element={<ProtectedRoute><DashboardLayout noPadding><CalendarScheduler /></DashboardLayout></ProtectedRoute>} />
            <Route path="/social/ideas" element={<ProtectedRoute><DashboardLayout><IdeasBoard /></DashboardLayout></ProtectedRoute>} />
            <Route path="/social/analytics" element={<ProtectedRoute><DashboardLayout><Analytics /></DashboardLayout></ProtectedRoute>} />
            <Route path="/social/engagement" element={<ProtectedRoute><DashboardLayout><EngagementInbox /></DashboardLayout></ProtectedRoute>} />
            <Route path="/social/settings" element={<ProtectedRoute><DashboardLayout><SocialSettings /></DashboardLayout></ProtectedRoute>} />
            
            {/* Redirect unknown routes to dashboard */}
            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Routes>
        </div>
      </Router>
    </AuthProvider>
  );
}

export default App;
