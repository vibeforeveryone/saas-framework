/*
 * Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
 * Author: Christopher Niven
 */
import React, { useState, useEffect } from 'react';
import { apiReady } from '../api/config';  // NEW: apiReady is a Promise that resolves to the configured axios instance

import './TransactionList.css';

const TransactionList = () => {
  const [transactions, setTransactions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [filters, setFilters] = useState({
    customer_id: '',
    status: '',
    transaction_type: '',
    start_date: '',
    end_date: '',
    min_amount: '',
    max_amount: '',
    limit: 50
  });
  const [summary, setSummary] = useState(null);

  useEffect(() => {
    fetchTransactions();
  }, []);

  const fetchTransactions = async () => {
    try {
      setLoading(true);
      setError('');

      // Build query parameters
      const queryParams = new URLSearchParams();
      Object.entries(filters).forEach(([key, value]) => {
        if (value) queryParams.append(key, value);
      });

      const api = await apiReady;
      const response = await api.getWithLog(`/transactions?${queryParams}`,
          `${import.meta.url.split('/').pop()}`);
      
      if (response.data.success) {
        setTransactions(response.data.data.transactions || []);
        setSummary(response.data.data.summary || null);
      } else {
        setError(response.data.error || 'Failed to load transactions');
      }
    } catch (err) {
      console.error('Error fetching transactions:', err);
      setError(err.response?.data?.error || 'Failed to load transactions');
    } finally {
      setLoading(false);
    }
  };

  const handleFilterChange = (e) => {
    const { name, value } = e.target;
    setFilters(prev => ({ ...prev, [name]: value }));
  };

  const handleSearch = (e) => {
    e.preventDefault();
    fetchTransactions();
  };

  const clearFilters = () => {
    setFilters({
      customer_id: '',
      status: '',
      transaction_type: '',
      start_date: '',
      end_date: '',
      min_amount: '',
      max_amount: '',
      limit: 50
    });
    setTimeout(fetchTransactions, 100);
  };

  const getStatusBadge = (status) => {
    const badges = {
      completed: { color: 'success', icon: '✅' },
      pending: { color: 'warning', icon: '⏳' },
      failed: { color: 'danger', icon: '❌' },
      voided: { color: 'secondary', icon: '🚫' }
    };
    return badges[status] || { color: 'secondary', icon: '❓' };
  };

  const formatCurrency = (amount, currency = 'USD') => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: currency
    }).format(amount);
  };

  return (
    <div className="content-wrapper">
      <div className="page-header primary">
        <h1>💳 Transactions</h1>
        <p>View and manage all payment transactions</p>
      </div>

      {success && (
        <div className="alert alert-success">
          {success}
          <button onClick={() => setSuccess('')} style={{ background: 'none', border: 'none', float: 'right', cursor: 'pointer', fontSize: '20px' }}>×</button>
        </div>
      )}

      {error && (
        <div className="alert alert-danger">
          <strong>Error:</strong> {error}
          <button onClick={() => setError('')} style={{ background: 'none', border: 'none', float: 'right', cursor: 'pointer', fontSize: '20px' }}>×</button>
        </div>
      )}

      {summary && (
        <div className="stats-grid">
          <div className="stat-card">
            <div className="stat-icon">📊</div>
            <div className="stat-content">
              <h3>{summary.total_returned || 0}</h3>
              <p>Total Transactions</p>
            </div>
          </div>
          <div className="stat-card">
            <div className="stat-icon">💰</div>
            <div className="stat-content">
              <h3>{formatCurrency(summary.total_amount || 0, summary.currency)}</h3>
              <p>Total Amount</p>
            </div>
          </div>
          {summary.status_breakdown && (
            <>
              <div className="stat-card">
                <div className="stat-icon">✅</div>
                <div className="stat-content">
                  <h3>{summary.status_breakdown.completed || 0}</h3>
                  <p>Completed</p>
                </div>
              </div>
              <div className="stat-card">
                <div className="stat-icon">❌</div>
                <div className="stat-content">
                  <h3>{summary.status_breakdown.failed || 0}</h3>
                  <p>Failed</p>
                </div>
              </div>
            </>
          )}
        </div>
      )}

      <div className="card">
        <div className="card-section">
          <h2>🔍 Search Filters</h2>
          <form onSubmit={handleSearch}>
            <div className="form-grid">
              <div className="form-group">
                <label htmlFor="customer_id">Customer ID</label>
                <input id="customer_id" type="text" name="customer_id" value={filters.customer_id} onChange={handleFilterChange} placeholder="Filter by customer" className="form-control" />
              </div>
              <div className="form-group">
                <label htmlFor="status">Status</label>
                <select id="status" name="status" value={filters.status} onChange={handleFilterChange} className="form-control">
                  <option value="">All Statuses</option>
                  <option value="completed">Completed</option>
                  <option value="pending">Pending</option>
                  <option value="failed">Failed</option>
                  <option value="voided">Voided</option>
                </select>
              </div>
              <div className="form-group">
                <label htmlFor="transaction_type">Transaction Type</label>
                <select id="transaction_type" name="transaction_type" value={filters.transaction_type} onChange={handleFilterChange} className="form-control">
                  <option value="">All Types</option>
                  <option value="payment">Payment</option>
                  <option value="refund">Refund</option>
                </select>
              </div>
              <div className="form-group">
                <label htmlFor="start_date">Start Date</label>
                <input id="start_date" type="date" name="start_date" value={filters.start_date} onChange={handleFilterChange} className="form-control" />
              </div>
              <div className="form-group">
                <label htmlFor="end_date">End Date</label>
                <input id="end_date" type="date" name="end_date" value={filters.end_date} onChange={handleFilterChange} className="form-control" />
              </div>
              <div className="form-group">
                <label htmlFor="min_amount">Min Amount</label>
                <input id="min_amount" type="number" name="min_amount" value={filters.min_amount} onChange={handleFilterChange} placeholder="0.00" step="0.01" min="0" className="form-control" />
              </div>
              <div className="form-group">
                <label htmlFor="max_amount">Max Amount</label>
                <input id="max_amount" type="number" name="max_amount" value={filters.max_amount} onChange={handleFilterChange} placeholder="1000.00" step="0.01" min="0" className="form-control" />
              </div>
              <div className="form-group">
                <label htmlFor="limit">Limit</label>
                <select id="limit" name="limit" value={filters.limit} onChange={handleFilterChange} className="form-control">
                  <option value="25">25</option>
                  <option value="50">50</option>
                  <option value="100">100</option>
                  <option value="200">200</option>
                </select>
              </div>
            </div>
            <div className="search-actions" style={{ display: 'flex', gap: '10px', marginTop: '20px' }}>
              <button type="submit" className="btn btn-primary" disabled={loading}>{loading ? '🔄 Searching...' : '🔍 Search'}</button>
              <button type="button" onClick={clearFilters} className="btn btn-secondary" disabled={loading}>🧹 Clear Filters</button>
            </div>
          </form>
        </div>
      </div>

      <div className="card">
        <div className="card-section">
          <h2>📊 Transactions ({transactions.length})</h2>
          {loading ? (
            <div style={{ textAlign: 'center', padding: '40px' }}>
              <div className="loading-spinner">🔄 Loading transactions...</div>
            </div>
          ) : transactions.length > 0 ? (
            <div className="table-container">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Transaction ID</th>
                    <th>Customer</th>
                    <th>Amount</th>
                    <th>Type</th>
                    <th>Status</th>
                    <th>Date</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {transactions.map((txn) => {
                    const badge = getStatusBadge(txn.status);
                    return (
                      <tr key={txn.transaction_id}>
                        <td><code>{txn.transaction_id}</code></td>
                        <td>
                          <div><strong>{txn.customer_name || txn.customer_id}</strong></div>
                          {txn.customer_email && <small style={{ color: '#666' }}>{txn.customer_email}</small>}
                        </td>
                        <td><strong>{formatCurrency(txn.amount, txn.currency)}</strong></td>
                        <td><span className="badge badge-info">{txn.transaction_type}</span></td>
                        <td><span className={`badge badge-${badge.color}`}>{badge.icon} {txn.status}</span></td>
                        <td><small>{new Date(txn.created_at).toLocaleString()}</small></td>
                        <td><button className="btn btn-sm btn-primary">👁️ View</button></td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <div style={{ textAlign: 'center', padding: '40px' }}>
              <p style={{ fontSize: '48px', margin: '0 0 20px 0' }}>📭</p>
              <p style={{ color: '#666' }}>No transactions found.</p>
              <button onClick={clearFilters} className="btn btn-secondary" style={{ marginTop: '10px' }}>Clear Filters</button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default TransactionList;
