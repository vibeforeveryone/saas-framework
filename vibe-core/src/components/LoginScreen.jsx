/*
 * Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
 * Author: Christopher Niven
 */
import React, { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { apiReady } from '../api/config';
import { useAuth } from '../context/AuthContext';
import './LoginScreen.css';

const LoginScreen = () => {
  const [formData, setFormData] = useState({ username: '', password: '' });
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState('');

  const navigate  = useNavigate();
  const location  = useLocation();
  const { accessToken, setAuth } = useAuth();

  // Redirect if already authenticated (e.g. browser back after login)
  useEffect(() => {
    if (accessToken) {
      const destination = location.state?.from?.pathname || '/dashboard';
      navigate(destination, { replace: true });
    }
  }, [accessToken, navigate, location]);

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
    if (error) setError('');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      const api      = await apiReady;
      const response = await api.postWithLog(
        '/auth',
        formData,
        `${import.meta.url.split('/').pop()}`
      );

      if (response.data.success) {
        const { access_token, user } = response.data.data;

        // Store in AuthContext memory — no localStorage
        setAuth(access_token, user);

        const destination = location.state?.from?.pathname || '/dashboard';
        navigate(destination, { replace: true });
      } else {
        setError(response.data.error || 'Login failed');
      }
    } catch (err) {
      console.error('Login error:', err);

      if (err.message?.includes('apiConfig.json')) {
        setError('API is not configured. Please check that public/apiConfig.json exists.');
      } else if (err.response?.data?.error) {
        setError(err.response.data.error);
      } else if (err.response?.status === 401) {
        setError('Invalid username or password');
      } else {
        setError('Login failed. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-container">
      <div className="login-box">
        <div className="login-header">
          <h1>📊 Usage Tracker</h1>
          <p>Provider Login</p>
        </div>

        <form onSubmit={handleSubmit} className="login-form">
          {error && (
            <div className="error-message">⚠️ {error}</div>
          )}

          <div className="form-group">
            <label htmlFor="username">
              Username <span className="required">*</span>
            </label>
            <input
              type="text"
              id="username"
              name="username"
              value={formData.username}
              onChange={handleInputChange}
              required
              disabled={loading}
              placeholder="Enter your username"
            />
          </div>

          <div className="form-group">
            <label htmlFor="password">
              Password <span className="required">*</span>
            </label>
            <input
              type="password"
              id="password"
              name="password"
              value={formData.password}
              onChange={handleInputChange}
              required
              disabled={loading}
              placeholder="Enter your password"
            />
          </div>

          <button
            type="submit"
            className={`btn btn-primary btn-lg ${loading ? 'loading' : ''}`}
            disabled={loading}
          >
            {loading ? '🔄 Logging in...' : '🔐 Login'}
          </button>
        </form>

        <div className="login-footer">
          <div className="app-info">
            <p><strong>Usage Tracker</strong> — Part of SaaS System</p>
            <p>Track and monitor application usage across your SaaS platform</p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default LoginScreen;
