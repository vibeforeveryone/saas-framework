/*
 * Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
 * Author: Christopher Niven
 */
import React, { useState, useEffect } from 'react';

import { apiReady } from '../api/config';  // NEW: apiReady is a Promise that resolves to the configured axios instance
import './DisputeManagement.css';

const DisputeManagement = () => {
  const [disputes, setDisputes] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selectedDispute, setSelectedDispute] = useState(null);
  const [error, setError] = useState('');
  const [filters, setFilters] = useState({
    company_name: '',
    status: '',
    dispute_type: ''
  });

  const [customerId, setCustomerId] = useState(''); // Customer ID from context/props

  useEffect(() => {
    fetchDisputes();
  }, []);

  const fetchDisputes = async () => {
  try {
      setLoading(true);
      if (!customerId) {
        setError('Customer ID is required');
        return;
      }
      const params = new URLSearchParams(filters);
      const api = await apiReady;
      const response = await api.getWithLog(`/customers/${customerId}/disputes?${params}`,
          `${import.meta.url.split('/').pop()}`);

      if (response.data.success) {
        setDisputes(response.data.data.disputes);
      }
      } catch (err) {
      console.error('Error fetching disputes:', err);
      } finally {
      setLoading(false);
      }
  };

  

  const handleRespond = async (disputeId, action) => {
    try {
      const api = await apiReady;
      await api.postWithLog(`/customers/${customerId}/disputes/${disputeId}/respond`, {
        action: action  // Only send action, not dispute_id
      },
      `${import.meta.url.split('/').pop()}`);

      fetchDisputes();
      setSelectedDispute(null);
    } catch (err) {
      console.error('Error responding to dispute:', err);
    }
  };

  const getStatusColor = (status) => {
    const colors = {
      open: 'warning',
      under_review: 'info',
      won: 'success',
      lost: 'danger',
      closed: 'secondary'
    };
    return colors[status] || 'secondary';
  };

  return (
    <div className="content-wrapper">
      <div className="page-header danger">
        <h1>⚖️ Dispute Management</h1>
        <p>Handle chargebacks and disputes</p>
      </div>

      <div className="card">
        <div className="card-section">
          <h2>🔍 Filter Disputes</h2>
          <div className="form-grid">
            <div className="form-group">
              <label>Company Name</label>
              <input
                type="text"
                value={filters.company_name}
                onChange={(e) => setFilters({...filters, company_name: e.target.value})}
                placeholder="Filter by company"
              />
            </div>

            <div className="form-group">
              <label>Status</label>
              <select value={filters.status} onChange={(e) => setFilters({...filters, status: e.target.value})}>
                <option value="">All Statuses</option>
                <option value="open">Open</option>
                <option value="under_review">Under Review</option>
                <option value="won">Won</option>
                <option value="lost">Lost</option>
                <option value="closed">Closed</option>
              </select>
            </div>

            <div className="form-group">
              <label>Type</label>
              <select value={filters.dispute_type} onChange={(e) => setFilters({...filters, dispute_type: e.target.value})}>
                <option value="">All Types</option>
                <option value="chargeback">Chargeback</option>
                <option value="inquiry">Inquiry</option>
                <option value="fraud">Fraud</option>
              </select>
            </div>

            <div className="form-group">
              <label>Customer ID <span className="required">*</span></label>
              <input
                type="text"
                value={customerId}
                onChange={(e) => setCustomerId(e.target.value)}
                placeholder="Enter customer ID"
                required
              />
            </div>

            <div className="form-group">
              <button className="btn btn-primary" onClick={fetchDisputes}>
                🔍 Search
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="card">
        <div className="card-section">
          <h2>📋 Disputes ({disputes.length})</h2>
          
          {loading ? (
            <div className="loading-container">
              <div className="loading-spinner">🔄 Loading...</div>
            </div>
          ) : (
            <div className="disputes-list">
              {disputes.map((dispute) => (
                <div key={dispute.dispute_id} className="dispute-card">
                  <div className="dispute-header">
                    <div>
                      <h3>{dispute.dispute_type.toUpperCase()}</h3>
                      <span className={`status-badge status-${getStatusColor(dispute.status)}`}>
                        {dispute.status}
                      </span>
                    </div>
                    <div className="dispute-amount">
                      {dispute.currency} {dispute.disputed_amount}
                    </div>
                  </div>

                  <div className="dispute-details">
                    <p><strong>Dispute ID:</strong> {dispute.dispute_id}</p>
                    <p><strong>Transaction:</strong> {dispute.transaction_id}</p>
                    <p><strong>Customer:</strong> {dispute.customer_name} ({dispute.customer_email})</p>
                    <p><strong>Reason:</strong> {dispute.reason_code}</p>
                    <p><strong>Created:</strong> {new Date(dispute.created_at).toLocaleDateString()}</p>
                  </div>

                  {dispute.status === 'open' && (
                    <div className="dispute-actions">
                      <button className="btn btn-success" onClick={() => handleRespond(dispute.dispute_id, 'challenge')}>
                        ⚔️ Challenge
                      </button>
                      <button className="btn btn-danger" onClick={() => handleRespond(dispute.dispute_id, 'accept')}>
                        ✓ Accept
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default DisputeManagement;
