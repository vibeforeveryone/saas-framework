/*
 * Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
 * Author: Christopher Niven
 */
import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

/**
 * ProtectedRoute
 * Redirects unauthenticated users to /login.
 * Shows a loading spinner while AuthProvider performs the initial
 * silent refresh (so users with a valid cookie aren't flashed to /login).
 */
export const ProtectedRoute = ({ children }) => {
  const location = useLocation();
  const { accessToken, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        height: '100vh', fontSize: '18px', color: '#666'
      }}>
        🔄 Loading...
      </div>
    );
  }

  if (!accessToken) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return children;
};

/**
 * AdminRoute
 * Wraps routes that require is_super_user === true.
 * Non-admins are redirected to /dashboard silently.
 * Unauthenticated users hit ProtectedRoute first.
 */
export const AdminRoute = ({ children }) => {
  const location = useLocation();
  const { accessToken, user, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        height: '100vh', fontSize: '18px', color: '#666'
      }}>
        🔄 Loading...
      </div>
    );
  }

  if (!accessToken) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (!user?.is_super_user) {
    return <Navigate to="/dashboard" replace />;
  }

  return children;
};

export default ProtectedRoute;
