/*
 * Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
 * Author: Christopher Niven
 */
import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { apiReady } from './api/config';
import './DashboardHome.css';

// Safe number formatter — never crashes on undefined/null
const fmt    = (n)   => (n ?? 0).toLocaleString();
const fmtUSD = (n)   => `$${(n ?? 0).toLocaleString(undefined, {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2
})}`;

const DEFAULTS = {
  total_transactions:         0,
  total_revenue:              0,
  active_disputes:            0,
  total_customers:            0,
  active_subscriptions:       0,
  monthly_recurring_revenue:  0,
  recent_activity:            [],
};

const DashboardHome = () => {
  const [stats, setStats]     = useState(DEFAULTS);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState('');

  useEffect(() => { fetchStats(); }, []);

  const fetchStats = async () => {
    try {
      setLoading(true);
      setError('');

      const api      = await apiReady;
      const response = await api.getWithLog(
        '/dashboard/metrics',
        `${import.meta.url.split('/').pop()}`
      );

      if (response.data.success) {
        // Merge into defaults — fields missing from the API response
        // keep their 0 value instead of becoming undefined.
        setStats(prev => ({ ...prev, ...(response.data.data || {}) }));
      }
    } catch (err) {
      console.error('Error fetching stats:', err);
      if (err.message?.includes('apiConfig.json')) {
        setError('API is not configured. Please check that public/apiConfig.json exists.');
      } else {
        setError('Failed to load dashboard statistics.');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="content-wrapper">

      {/* Header */}
      <div className="page-header primary">
        <h1>🏠 Dashboard</h1>
        <p>Welcome to Provider Manager</p>
      </div>

      {error && (
        <div className="alert alert-danger" style={{ marginBottom: '20px' }}>
          {error}
        </div>
      )}

      {/* ── Stats grid ────────────────────────────────────────────────── */}
      <div className="stats-grid">

        <div className="stat-card">
          <div className="stat-icon">💰</div>
          <div className="stat-content">
            <h3>{fmtUSD(stats.total_revenue)}</h3>
            <p>Total Revenue</p>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon">📈</div>
          <div className="stat-content">
            <h3>{fmt(stats.total_transactions)}</h3>
            <p>Transactions</p>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon">👥</div>
          <div className="stat-content">
            <h3>{fmt(stats.total_customers)}</h3>
            <p>Customers</p>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon">📄</div>
          <div className="stat-content">
            <h3>{fmt(stats.active_subscriptions)}</h3>
            <p>Active Subscriptions</p>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon">💵</div>
          <div className="stat-content">
            <h3>{fmtUSD(stats.monthly_recurring_revenue)}</h3>
            <p>Monthly Recurring Revenue</p>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon">⚖️</div>
          <div className="stat-content">
            <h3>{fmt(stats.active_disputes)}</h3>
            <p>Active Disputes</p>
          </div>
        </div>

      </div>

      {/* ── Quick actions ─────────────────────────────────────────────── */}
      <div className="quick-actions">

        <Link to="/payment" className="action-card">
          <span className="action-icon">💳</span>
          <h3>Process Payment</h3>
          <p>Submit a new transaction</p>
        </Link>

        <Link to="/customers" className="action-card">
          <span className="action-icon">👥</span>
          <h3>Manage Customers</h3>
          <p>View and edit customers</p>
        </Link>

        <Link to="/transactions" className="action-card">
          <span className="action-icon">📄</span>
          <h3>Transactions</h3>
          <p>View transaction history</p>
        </Link>

        <Link to="/licenses" className="action-card">
          <span className="action-icon">🎫</span>
          <h3>License Tiers</h3>
          <p>Configure pricing plans</p>
        </Link>

        <Link to="/disputes" className="action-card">
          <span className="action-icon">⚖️</span>
          <h3>Handle Disputes</h3>
          <p>Manage chargebacks</p>
        </Link>

        <Link to="/analytics" className="action-card">
          <span className="action-icon">📊</span>
          <h3>View Analytics</h3>
          <p>Reports and insights</p>
        </Link>

      </div>

      {/* ── Recent activity ───────────────────────────────────────────── */}
      {stats.recent_activity && stats.recent_activity.length > 0 && (
        <div className="card" style={{ marginTop: '24px' }}>
          <div className="card-section">
            <h2 style={{ marginTop: 0 }}>🕒 Recent Activity</h2>
            <div className="table-container">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Time</th>
                    <th>Event</th>
                    <th>Resource</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {stats.recent_activity.map((event, idx) => (
                    <tr key={event.eventId || idx}>
                      <td style={{ whiteSpace: 'nowrap' }}>
                        {event.timestamp
                          ? new Date(event.timestamp).toLocaleString()
                          : '—'}
                      </td>
                      <td>{event.eventType || '—'}</td>
                      <td>{event.resourceType || '—'}</td>
                      <td>
                        <span className={`badge ${
                          event.action === 'created' ? 'badge-success' :
                          event.action === 'deleted' ? 'badge-danger'  :
                          'badge-secondary'
                        }`}>
                          {event.action || '—'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {loading && (
        <div style={{ textAlign: 'center', padding: '20px', color: 'var(--text-secondary)' }}>
          <p>Loading dashboard data...</p>
        </div>
      )}

    </div>
  );
};

export default DashboardHome;
