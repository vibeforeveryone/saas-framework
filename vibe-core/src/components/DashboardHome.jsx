/*
 * Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
 * Author: Christopher Niven
 */
// CHANGES FROM PREVIOUS VERSION:
//   - On load, fetches the current customer's license via GET /customers/{id}/license
//   - If license is transactionsPerMonth, also fetches current month usage
//     via GET /analytics/usage?customer_id={id}
//   - Renders a dismissible warning banner if usage >= warning_threshold_pct
//   - Dismissal is session-only (sessionStorage) — reappears on next login
//   - All other dashboard content is unchanged

import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { apiReady } from './api/config';
import './DashboardHome.css';

const DashboardHome = () => {
  const [stats, setStats] = useState({
    total_transactions: 0,
    total_revenue: 0,
    active_disputes: 0,
    total_customers: 0,
    active_subscriptions: 0,
    monthly_recurring_revenue: 0
  });
  const [loading, setLoading]       = useState(false);
  const [error, setError]           = useState('');

  // ── License warning state ─────────────────────────────────────────────────
  const [licenseWarning, setLicenseWarning] = useState(null);   // null | { pct, max, used, threshold }
  const [warningDismissed, setWarningDismissed] = useState(false);

  const user       = JSON.parse(localStorage.getItem('user') || '{}');
  const customerId = user.customer_id;
  const DISMISS_KEY = `txn_warning_dismissed_${customerId}`;

  useEffect(() => {
    fetchStats();
    if (customerId) {
      checkLicenseWarning();
      // Restore dismiss state for this session
      if (sessionStorage.getItem(DISMISS_KEY) === 'true') {
        setWarningDismissed(true);
      }
    }
  }, []);

  // ── Stats ─────────────────────────────────────────────────────────────────

  const fetchStats = async () => {
    try {
      setLoading(true);
      setError('');
      const api = await apiReady;
      const response = await api.getWithLog(
        '/dashboard/metrics',
        `${import.meta.url.split('/').pop()}`
      );
      if (response.data.success) {
        setStats(response.data.data || stats);
      }
    } catch (err) {
      console.error('Error fetching stats:', err);
      if (err.message?.includes('apiConfig.json')) {
        setError('API is not configured. Please check that public/apiConfig.json exists.');
      } else {
        setError('Failed to load dashboard statistics');
      }
    } finally {
      setLoading(false);
    }
  };

  // ── License warning ───────────────────────────────────────────────────────

  const checkLicenseWarning = async () => {
    try {
      const api = await apiReady;

      // 1. Get customer's current license
      const licResponse = await api.getWithLog(
        `/customers/${customerId}/license`,
        `${import.meta.url.split('/').pop()}`
      );
      if (!licResponse.data.success) return;

      const cl = licResponse.data.data.customer_license;
      const lic = cl?.license;
      if (!lic || lic.license_type !== 'transactionsPerMonth') return;

      const maxTxns     = Number(lic.max_transactions);
      const thresholdPct = Number(lic.warning_threshold_pct ?? 80);

      // 2. Get current month usage
      const usageResponse = await api.getWithLog(
        `/analytics/usage?customer_id=${customerId}`,
        `${import.meta.url.split('/').pop()}`
      );
      if (!usageResponse.data.success) return;

      // Usage API returns total_usage for the current period
      const usedTxns = Number(
        usageResponse.data.data?.analytics?.total_usage ??
        usageResponse.data.data?.total_transactions ?? 0
      );

      const usedPct = maxTxns > 0 ? Math.round((usedTxns / maxTxns) * 100) : 0;

      if (usedPct >= thresholdPct) {
        setLicenseWarning({
          pct:       usedPct,
          max:       maxTxns,
          used:      usedTxns,
          threshold: thresholdPct,
        });
      }
    } catch (err) {
      // Non-fatal — dashboard still renders without the warning
      console.warn('Could not check license warning:', err.message);
    }
  };

  const handleDismissWarning = () => {
    setWarningDismissed(true);
    sessionStorage.setItem(DISMISS_KEY, 'true');
  };

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="content-wrapper">
      <div className="page-header primary">
        <h1>🏠 Dashboard</h1>
        <p>Welcome to Provider Manager</p>
      </div>

      {/* ── Transaction warning banner ──────────────────────────────── */}
      {licenseWarning && !warningDismissed && (
        <div style={{
          backgroundColor: licenseWarning.pct >= 100 ? '#fff3cd' : '#fff3cd',
          border: `1px solid ${licenseWarning.pct >= 100 ? '#dc3545' : '#ffc107'}`,
          borderLeft: `4px solid ${licenseWarning.pct >= 100 ? '#dc3545' : '#ffc107'}`,
          borderRadius: '6px',
          padding: '14px 16px',
          marginBottom: '20px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '12px',
        }}>
          <div>
            <strong>
              {licenseWarning.pct >= 100 ? '🚨' : '⚠️'}{' '}
              {licenseWarning.pct >= 100
                ? 'Transaction limit reached'
                : 'Approaching transaction limit'
              }
            </strong>
            <div style={{ marginTop: '4px', fontSize: '0.875rem' }}>
              You have used{' '}
              <strong>{licenseWarning.used.toLocaleString()}</strong> of{' '}
              <strong>{licenseWarning.max.toLocaleString()}</strong> transactions this month
              {' '}({licenseWarning.pct}%).{' '}
              <Link to="/my-license" style={{ color: '#0066cc', fontWeight: '600' }}>
                Upgrade your plan →
              </Link>
            </div>
          </div>
          <button
            onClick={handleDismissWarning}
            style={{
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              fontSize: '1.1rem',
              color: '#666',
              padding: '0 4px',
              lineHeight: 1,
            }}
            title="Dismiss until next login"
          >
            ✕
          </button>
        </div>
      )}

      {error && (
        <div className="alert alert-danger">{error}</div>
      )}

      {/* ── Stats grid (unchanged) ──────────────────────────────────── */}
      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-icon">💰</div>
          <div className="stat-content">
            <h3>${stats.total_revenue.toLocaleString()}</h3>
            <p>Total Revenue</p>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon">📈</div>
          <div className="stat-content">
            <h3>{stats.total_transactions.toLocaleString()}</h3>
            <p>Transactions</p>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon">👥</div>
          <div className="stat-content">
            <h3>{stats.total_customers.toLocaleString()}</h3>
            <p>Customers</p>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon">📄</div>
          <div className="stat-content">
            <h3>{stats.active_subscriptions.toLocaleString()}</h3>
            <p>Active Subscriptions</p>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon">💵</div>
          <div className="stat-content">
            <h3>${stats.monthly_recurring_revenue.toLocaleString()}</h3>
            <p>Monthly Recurring Revenue</p>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon">⚖️</div>
          <div className="stat-content">
            <h3>{stats.active_disputes.toLocaleString()}</h3>
            <p>Active Disputes</p>
          </div>
        </div>
      </div>

      {/* ── Quick actions (unchanged + new My Plan card) ────────────── */}
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

        <Link to="/my-license" className="action-card">
          <span className="action-icon">📋</span>
          <h3>My Plan</h3>
          <p>View or change your license</p>
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

      {loading && (
        <div style={{ textAlign: 'center', padding: '20px' }}>
          <p>Loading dashboard data...</p>
        </div>
      )}
    </div>
  );
};

export default DashboardHome;
