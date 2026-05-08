/*
 * Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
 * Author: Christopher Niven
 */
import React, { useState, useEffect } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { apiReady } from '../api/config';
import { useAuth } from '../context/AuthContext';

const Navigation = () => {
  const location  = useNavigate();
  const navigate  = useNavigate();
  const loc       = useLocation();
  const { user, clearAuth } = useAuth();

  const isSuperUser = user?.is_super_user === true;

  const [applications, setApplications] = useState([]);
  const [loading, setLoading]           = useState(false);

  const [openSections, setOpenSections] = useState({
    configuration: true,
    management:    true,
    applications:  false,
    payments:      true,
    reports:       true,
    system:        true,
    customers:     false,
  });

  useEffect(() => {
    fetchApplications();
  }, []);

  const fetchApplications = async () => {
    setLoading(true);
    try {
      const api      = await apiReady;
      const response = await api.getWithLog(
        '/applications',
        `${import.meta.url.split('/').pop()}`
      );
      if (response.data.success) {
        const apps = response.data.data.applications || [];
        setApplications(apps.slice(0, 3));
      }
    } catch (err) {
      console.error('Error fetching applications:', err);
      setApplications([]);
    } finally {
      setLoading(false);
    }
  };

  const isActive = (path) => loc.pathname === path;

  const toggleSection = (section) => {
    setOpenSections(prev => ({ ...prev, [section]: !prev[section] }));
  };

  const handleLogout = async () => {
    try {
      // Call /auth/logout to revoke the refresh token server-side and clear cookie
      const api = await apiReady;
      await api.postWithLog('/auth/logout', {}, 'Navigation.js - Logout');
    } catch (err) {
      // Non-fatal — proceed with client-side logout regardless
      console.warn('Logout endpoint error (proceeding anyway):', err);
    } finally {
      // Clear access token from AuthContext memory
      clearAuth();
      navigate('/login');
    }
  };

  const handleApplicationClick = (app) => {
    navigate('/applications', {
      state: { selectedApp: { app_key: app.app_key, app_name: app.app_name } },
    });
    setTimeout(() => window.history.replaceState({}, document.title), 100);
  };

  return (
    <nav className="sidebar">
      <div className="sidebar-header">
        <h2>💳 Provider Manager</h2>
        <div className="subtitle">Payment Platform</div>
      </div>

      <ul className="nav-menu">

        {/* Dashboard */}
        <li>
          <Link to="/dashboard" className={isActive('/dashboard') ? 'active' : ''}>
            <span className="nav-icon">🏠</span> Dashboard
          </Link>
        </li>

        {/* ── Configuration Section (admin only) ────────────────────── */}
        {isSuperUser && (
          <li className="nav-section">
            <button
              className="nav-section-header"
              onClick={() => toggleSection('configuration')}
            >
              <span className="nav-icon">🔧</span> Configuration
              <span className={`accordion-arrow ${openSections.configuration ? 'open' : ''}`}>▼</span>
            </button>
            {openSections.configuration && (
              <ul className="nav-submenu">
                <li>
                  <Link to="/api-settings" className={isActive('/api-settings') ? 'active' : ''}>
                    <span className="nav-icon">⚙️</span> API Settings
                  </Link>
                </li>
                <li>
                  <Link to="/applications" className={isActive('/applications') ? 'active' : ''}>
                    <span className="nav-icon">📱</span> Applications
                  </Link>
                </li>
                <li>
                  <Link to="/roles" className={isActive('/roles') ? 'active' : ''}>
                    <span className="nav-icon">🎭</span> Roles
                  </Link>
                </li>
                <li>
                  <Link to="/features" className={isActive('/features') ? 'active' : ''}>
                    <span className="nav-icon">🏷️</span> Features
                  </Link>
                </li>
                <li>
                  <Link to="/licenses" className={isActive('/licenses') ? 'active' : ''}>
                    <span className="nav-icon">📄</span> Licenses
                  </Link>
                </li>
              </ul>
            )}
          </li>
        )}

        {/* ── Management Section ─────────────────────────────────────── */}
        <li className="nav-section">
          <button
            className="nav-section-header"
            onClick={() => toggleSection('management')}
          >
            <span className="nav-icon">👥</span> Management
            <span className={`accordion-arrow ${openSections.management ? 'open' : ''}`}>▼</span>
          </button>
          {openSections.management && (
            <ul className="nav-submenu">
              <li>
                <Link to="/customers" className={isActive('/customers') ? 'active' : ''}>
                  <span className="nav-icon">🏢</span> Customers
                </Link>
              </li>
              <li>
                <Link to="/users" className={isActive('/users') ? 'active' : ''}>
                  <span className="nav-icon">👤</span> Users
                </Link>
              </li>
            </ul>
          )}
        </li>

        {/* ── Payments Section ───────────────────────────────────────── */}
        <li className="nav-section">
          <button
            className="nav-section-header"
            onClick={() => toggleSection('payments')}
          >
            <span className="nav-icon">💳</span> Payments
            <span className={`accordion-arrow ${openSections.payments ? 'open' : ''}`}>▼</span>
          </button>
          {openSections.payments && (
            <ul className="nav-submenu">
              <li>
                <Link to="/transactions" className={isActive('/transactions') ? 'active' : ''}>
                  <span className="nav-icon">💰</span> Transactions
                </Link>
              </li>
              <li>
                <Link to="/payment" className={isActive('/payment') ? 'active' : ''}>
                  <span className="nav-icon">➕</span> New Payment
                </Link>
              </li>
              <li>
                <Link to="/disputes" className={isActive('/disputes') ? 'active' : ''}>
                  <span className="nav-icon">⚖️</span> Disputes
                </Link>
              </li>
            </ul>
          )}
        </li>

        {/* ── Reports Section ────────────────────────────────────────── */}
        <li className="nav-section">
          <button
            className="nav-section-header"
            onClick={() => toggleSection('reports')}
          >
            <span className="nav-icon">📊</span> Reports
            <span className={`accordion-arrow ${openSections.reports ? 'open' : ''}`}>▼</span>
          </button>
          {openSections.reports && (
            <ul className="nav-submenu">
              <li>
                <Link to="/analytics" className={isActive('/analytics') ? 'active' : ''}>
                  <span className="nav-icon">📈</span> Analytics
                </Link>
              </li>
              <li>
                <Link to="/reports" className={isActive('/reports') ? 'active' : ''}>
                  <span className="nav-icon">📋</span> Reports
                </Link>
              </li>
              <li>
                <Link to="/search" className={isActive('/search') ? 'active' : ''}>
                  <span className="nav-icon">🔍</span> Search
                </Link>
              </li>
            </ul>
          )}
        </li>

        {/* ── System Section (admin only) ────────────────────────────── */}
        {isSuperUser && (
          <li className="nav-section">
            <button
              className="nav-section-header"
              onClick={() => toggleSection('system')}
            >
              <span className="nav-icon">🖥️</span> System
              <span className={`accordion-arrow ${openSections.system ? 'open' : ''}`}>▼</span>
            </button>
            {openSections.system && (
              <ul className="nav-submenu">
                <li>
                  <Link to="/processor-config" className={isActive('/processor-config') ? 'active' : ''}>
                    <span className="nav-icon">🔌</span> Processor Config
                  </Link>
                </li>
                <li>
                  <Link to="/webhooks" className={isActive('/webhooks') ? 'active' : ''}>
                    <span className="nav-icon">🔔</span> Webhooks
                  </Link>
                </li>
                <li>
                  <Link to="/notifications" className={isActive('/notifications') ? 'active' : ''}>
                    <span className="nav-icon">📣</span> Notifications
                  </Link>
                </li>
                <li>
                  <Link to="/settings" className={isActive('/settings') ? 'active' : ''}>
                    <span className="nav-icon">⚙️</span> Settings
                  </Link>
                </li>
              </ul>
            )}
          </li>
        )}

      </ul>

      {/* ── User info + logout ─────────────────────────────────────────── */}
      <div className="sidebar-footer">
        {user && (
          <div className="user-info">
            <span className="nav-icon">👤</span>
            <span>{user.user_name || user.username || user.user_email || 'User'}</span>
            {isSuperUser && <span className="badge badge-info" style={{ marginLeft: 6 }}>Admin</span>}
          </div>
        )}
        <button className="btn btn-secondary btn-sm logout-btn" onClick={handleLogout}>
          🚪 Logout
        </button>
      </div>
    </nav>
  );
};

export default Navigation;
