/*
 * Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
 * Author: Christopher Niven
 */
import React, { useState, useEffect } from 'react';
import { apiReady } from '../api/config';  // NEW: apiReady is a Promise that resolves to the configured axios instance
import './AnalyticsDashboard.css';

const AnalyticsDashboard = () => {
  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [dateRange, setDateRange] = useState({
    start_date: new Date(Date.now() - 30*24*60*60*1000).toISOString().split('T')[0],
    end_date: new Date().toISOString().split('T')[0]
  });

  useEffect(() => {
    fetchAnalytics();
  }, []);

  const fetchAnalytics = async () => {
    try {
      setLoading(true);
      setError('');
      
      const params = new URLSearchParams(dateRange);
      const api = await apiReady;
      const response = await api.getWithLog(`/transactions/analytics?${params}`);
      
      if (response.data.success) {
        setAnalytics(response.data.data);
      } else {
        setError(response.data.error || 'Failed to load analytics');
      }
    } catch (err) {
      console.error('Error fetching analytics:', err);
      setError(err.response?.data?.error || 'Failed to load analytics data');
    } finally {
      setLoading(false);
    }
  };

  const handleDateChange = (e) => {
    const { name, value } = e.target;
    setDateRange(prev => ({ ...prev, [name]: value }));
  };

  const formatCurrency = (amount) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD'
    }).format(amount);
  };

  return (
    <div className="content-wrapper">
      <div className="page-header primary">
        <h1>📊 Analytics Dashboard</h1>
        <p>Transaction analytics and insights</p>
      </div>

      {error && (
        <div className="alert alert-danger">
          <strong>Error:</strong> {error}
          <button onClick={() => setError('')} style={{ background: 'none', border: 'none', float: 'right', cursor: 'pointer', fontSize: '20px' }}>×</button>
        </div>
      )}

      {/* Date Range Selector */}
      <div className="card">
        <div className="card-section">
          <h2>📅 Date Range</h2>
          <div className="form-grid">
            <div className="form-group">
              <label htmlFor="start_date">Start Date</label>
              <input
                id="start_date"
                type="date"
                name="start_date"
                value={dateRange.start_date}
                onChange={handleDateChange}
                className="form-control"
              />
            </div>
            <div className="form-group">
              <label htmlFor="end_date">End Date</label>
              <input
                id="end_date"
                type="date"
                name="end_date"
                value={dateRange.end_date}
                onChange={handleDateChange}
                className="form-control"
              />
            </div>
            <div className="form-group">
              <label>&nbsp;</label>
              <button 
                className="btn btn-primary" 
                onClick={fetchAnalytics}
                disabled={loading}
              >
                {loading ? '🔄 Loading...' : '🔄 Update'}
              </button>
            </div>
          </div>
        </div>
      </div>

      {loading && !analytics && (
        <div style={{ textAlign: 'center', padding: '40px' }}>
          <div className="loading-spinner">🔄 Loading analytics...</div>
        </div>
      )}

      {analytics && (
        <>
          {/* Overview Stats */}
          {analytics.overview && (
            <div className="stats-grid">
              <div className="stat-card">
                <div className="stat-icon">💰</div>
                <div className="stat-content">
                  <h3>{formatCurrency(analytics.overview.total_volume || 0)}</h3>
                  <p>Total Volume</p>
                </div>
              </div>
              <div className="stat-card">
                <div className="stat-icon">📊</div>
                <div className="stat-content">
                  <h3>{(analytics.overview.total_transactions || 0).toLocaleString()}</h3>
                  <p>Total Transactions</p>
                </div>
              </div>
              <div className="stat-card">
                <div className="stat-icon">✅</div>
                <div className="stat-content">
                  <h3>{analytics.overview.success_rate || 0}%</h3>
                  <p>Success Rate</p>
                </div>
              </div>
              <div className="stat-card">
                <div className="stat-icon">💵</div>
                <div className="stat-content">
                  <h3>{formatCurrency(analytics.overview.average_transaction_value || 0)}</h3>
                  <p>Avg Transaction</p>
                </div>
              </div>
            </div>
          )}

          {/* By Status */}
          {analytics.by_status && Object.keys(analytics.by_status).length > 0 && (
            <div className="card">
              <div className="card-section">
                <h2>📊 By Status</h2>
                <div className="analytics-grid">
                  {Object.entries(analytics.by_status).map(([status, data]) => (
                    <div key={status} className="analytics-item">
                      <h4>{status.toUpperCase()}</h4>
                      <p className="big-number">{data.count}</p>
                      <p className="subtitle">Transactions</p>
                      <p className="amount">{formatCurrency(data.volume)}</p>
                      <p className="subtitle">Volume</p>
                      <p className="percentage">{data.percentage.toFixed(1)}%</p>
                      <p className="subtitle">of Total</p>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* By Processor */}
          {analytics.by_processor && Object.keys(analytics.by_processor).length > 0 && (
            <div className="card">
              <div className="card-section">
                <h2>🏦 By Processor</h2>
                <div className="table-container">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Processor</th>
                        <th>Count</th>
                        <th>Volume</th>
                        <th>Successful</th>
                        <th>Failed</th>
                        <th>Success Rate</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(analytics.by_processor).map(([proc, data]) => (
                        <tr key={proc}>
                          <td><strong>{proc}</strong></td>
                          <td>{data.count}</td>
                          <td>{formatCurrency(data.volume)}</td>
                          <td className="text-success">{data.successful}</td>
                          <td className="text-danger">{data.failed}</td>
                          <td>{data.success_rate.toFixed(2)}%</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {/* Top Customers */}
          {analytics.top_customers && analytics.top_customers.length > 0 && (
            <div className="card">
              <div className="card-section">
                <h2>🏆 Top Customers</h2>
                <div className="table-container">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Customer</th>
                        <th>Email</th>
                        <th>Transactions</th>
                        <th>Total Volume</th>
                      </tr>
                    </thead>
                    <tbody>
                      {analytics.top_customers.map((customer, idx) => (
                        <tr key={customer.customer_id || idx}>
                          <td><strong>{customer.customer_name || customer.customer_id}</strong></td>
                          <td>{customer.customer_email || 'N/A'}</td>
                          <td>{customer.transaction_count}</td>
                          <td><strong>{formatCurrency(customer.total_volume)}</strong></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {/* Timeline */}
          {analytics.timeline && analytics.timeline.length > 0 && (
            <div className="card">
              <div className="card-section">
                <h2>📈 Timeline</h2>
                <div className="table-container">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Date</th>
                        <th>Count</th>
                        <th>Volume</th>
                        <th>Successful</th>
                      </tr>
                    </thead>
                    <tbody>
                      {analytics.timeline.map((day, idx) => (
                        <tr key={idx}>
                          <td><strong>{day.date}</strong></td>
                          <td>{day.count}</td>
                          <td>{formatCurrency(day.volume)}</td>
                          <td className="text-success">{day.successful}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {/* Payment Methods */}
          {analytics.payment_methods && Object.keys(analytics.payment_methods).length > 0 && (
            <div className="card">
              <div className="card-section">
                <h2>💳 Payment Methods</h2>
                <div className="analytics-grid">
                  {Object.entries(analytics.payment_methods).map(([method, count]) => (
                    <div key={method} className="analytics-item">
                      <h4>{method.toUpperCase()}</h4>
                      <p className="big-number">{count}</p>
                      <p className="subtitle">Transactions</p>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </>
      )}

      {!loading && !analytics && (
        <div className="card">
          <div className="card-section" style={{ textAlign: 'center', padding: '40px' }}>
            <p style={{ fontSize: '48px', margin: '0 0 20px 0' }}>📊</p>
            <p style={{ color: '#666' }}>No analytics data available for the selected date range.</p>
          </div>
        </div>
      )}
    </div>
  );
};

export default AnalyticsDashboard;
