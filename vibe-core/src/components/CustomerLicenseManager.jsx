/*
 * Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
 * Author: Christopher Niven
 */
// Customer-facing license management page.
// Route: /my-license
// Shows current plan, allows switching, and displays full history.

import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiReady } from '../api/config';
import '../design-system.css';

function CustomerLicenseManager() {
  const navigate = useNavigate();
  const user = JSON.parse(localStorage.getItem('user') || '{}');
  const customerId = user.customer_id;

  const [currentLicense, setCurrentLicense]   = useState(null);
  const [availableLicenses, setAvailableLicenses] = useState([]);
  const [history, setHistory]                 = useState([]);
  const [showHistory, setShowHistory]         = useState(false);
  const [selectedKey, setSelectedKey]         = useState('');
  const [loading, setLoading]                 = useState(false);
  const [changingLicense, setChangingLicense] = useState(false);
  const [error, setError]                     = useState('');
  const [success, setSuccess]                 = useState('');
  const [confirmChange, setConfirmChange]     = useState(false);

  useEffect(() => {
    if (!customerId) {
      navigate('/dashboard');
      return;
    }
    fetchCurrentLicense();
    fetchAvailableLicenses();
  }, [customerId]);

  // ── Data fetching ─────────────────────────────────────────────────────────

  const fetchCurrentLicense = async () => {
    setLoading(true);
    setError('');
    try {
      const api = await apiReady;
      const response = await api.getWithLog(
        `/customers/${customerId}/license`,
        `${import.meta.url.split('/').pop()}`
      );
      if (response.data.success) {
        setCurrentLicense(response.data.data.customer_license);
      }
    } catch (err) {
      if (err.response?.status === 404) {
        setCurrentLicense(null);   // No license yet — valid state
      } else {
        setError(err.response?.data?.error || 'Failed to load current license');
      }
    } finally {
      setLoading(false);
    }
  };

  const fetchAvailableLicenses = async () => {
    try {
      const api = await apiReady;
      const response = await api.getWithLog(
        '/licenses/active',
        `${import.meta.url.split('/').pop()}`
      );
      if (response.data.success) {
        setAvailableLicenses(response.data.data.licenses || []);
      }
    } catch (err) {
      console.error('Failed to load available licenses:', err);
    }
  };

  const fetchHistory = async () => {
    if (history.length > 0) {
      setShowHistory(h => !h);
      return;
    }
    setLoading(true);
    try {
      const api = await apiReady;
      const response = await api.getWithLog(
        `/customers/${customerId}/license/history`,
        `${import.meta.url.split('/').pop()}`
      );
      if (response.data.success) {
        setHistory(response.data.data.history || []);
        setShowHistory(true);
      }
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to load license history');
    } finally {
      setLoading(false);
    }
  };

  // ── License change ────────────────────────────────────────────────────────

  const handleSelectPlan = (licenseKey) => {
    setSelectedKey(licenseKey);
    setConfirmChange(false);
    setError('');
    setSuccess('');
  };

  const handleConfirmChange = async () => {
    if (!selectedKey) return;
    setChangingLicense(true);
    setError('');
    setSuccess('');
    try {
      const api = await apiReady;
      const response = await api.postWithLog(
        `/customers/${customerId}/license`,
        {
          license_key: selectedKey,
          changed_by_user_key: user.user_key,
          changed_by_type: 'customer_self_service',
        },
        `${import.meta.url.split('/').pop()}`
      );
      if (response.data.success) {
        setSuccess('Your plan has been updated! Changes are effective immediately.');
        setSelectedKey('');
        setConfirmChange(false);
        setHistory([]);          // Clear history cache so it reloads next time
        setShowHistory(false);
        await fetchCurrentLicense();
      }
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to change license');
    } finally {
      setChangingLicense(false);
    }
  };

  // ── Helpers ───────────────────────────────────────────────────────────────

  const formatCost = (val) =>
    val !== undefined && val !== null ? `$${parseFloat(val).toFixed(2)}` : '—';

  const formatDate = (iso) => {
    if (!iso || iso === 'active') return '—';
    return new Date(iso).toLocaleDateString(undefined, {
      year: 'numeric', month: 'short', day: 'numeric'
    });
  };

  const renderLicenseDetail = (lic) => {
    if (!lic) return null;
    if (lic.license_type === 'transactionsPerMonth') {
      return (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '12px', marginTop: '12px' }}>
          <div className="stat-card" style={{ padding: '12px' }}>
            <div style={{ fontSize: '1.4rem', fontWeight: 'bold' }}>
              {Number(lic.max_transactions).toLocaleString()}
            </div>
            <div className="text-secondary" style={{ fontSize: '0.8rem' }}>Max Transactions/Month</div>
          </div>
          <div className="stat-card" style={{ padding: '12px' }}>
            <div style={{ fontSize: '1.4rem', fontWeight: 'bold' }}>{formatCost(lic.base_cost_per_month)}</div>
            <div className="text-secondary" style={{ fontSize: '0.8rem' }}>Base Cost/Month</div>
          </div>
          <div className="stat-card" style={{ padding: '12px' }}>
            <div style={{ fontSize: '1.4rem', fontWeight: 'bold' }}>{formatCost(lic.cost_per_transaction)}</div>
            <div className="text-secondary" style={{ fontSize: '0.8rem' }}>Per Transaction</div>
          </div>
        </div>
      );
    }
    return (
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '12px', marginTop: '12px' }}>
        <div className="stat-card" style={{ padding: '12px' }}>
          <div style={{ fontSize: '1.4rem', fontWeight: 'bold' }}>
            {Number(lic.max_seats).toLocaleString()}
          </div>
          <div className="text-secondary" style={{ fontSize: '0.8rem' }}>Max Seats</div>
        </div>
        <div className="stat-card" style={{ padding: '12px' }}>
          <div style={{ fontSize: '1.4rem', fontWeight: 'bold' }}>{formatCost(lic.cost_per_month)}</div>
          <div className="text-secondary" style={{ fontSize: '0.8rem' }}>Per Month</div>
        </div>
      </div>
    );
  };

  const renderPlanCard = (license) => {
    const isCurrent = currentLicense?.license_key === license.license_key;
    const isSelected = selectedKey === license.license_key;

    let borderColor = '#dee2e6';
    if (isCurrent) borderColor = '#28a745';
    else if (isSelected) borderColor = '#007bff';

    return (
      <div
        key={license.license_key}
        onClick={() => !isCurrent && handleSelectPlan(license.license_key)}
        style={{
          border: `2px solid ${borderColor}`,
          borderRadius: '8px',
          padding: '16px',
          cursor: isCurrent ? 'default' : 'pointer',
          backgroundColor: isCurrent ? '#f0fff4' : isSelected ? '#f0f7ff' : '#fff',
          transition: 'all 0.15s',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <strong style={{ fontSize: '1rem' }}>{license.license_type_desc}</strong>
            <div className="text-secondary" style={{ fontSize: '0.8rem', marginTop: '2px' }}>
              {license.license_type === 'transactionsPerMonth' ? 'API Usage Plan' : 'Seat-Based Plan'}
            </div>
          </div>
          <div style={{ textAlign: 'right' }}>
            {license.license_type === 'transactionsPerMonth' ? (
              <>
                <div style={{ fontWeight: 'bold' }}>{formatCost(license.base_cost_per_month)}/mo</div>
                <div className="text-secondary" style={{ fontSize: '0.75rem' }}>
                  + {formatCost(license.cost_per_transaction)}/txn
                </div>
              </>
            ) : (
              <div style={{ fontWeight: 'bold' }}>{formatCost(license.cost_per_month)}/mo</div>
            )}
          </div>
        </div>
        <div style={{ marginTop: '8px', fontSize: '0.85rem', color: '#555' }}>
          {license.license_type === 'transactionsPerMonth'
            ? `Up to ${Number(license.max_transactions).toLocaleString()} transactions/month`
            : `Up to ${Number(license.max_seats).toLocaleString()} users`
          }
        </div>
        {isCurrent && (
          <div style={{ marginTop: '8px' }}>
            <span className="badge badge-success">✓ Current Plan</span>
          </div>
        )}
        {isSelected && !isCurrent && (
          <div style={{ marginTop: '8px' }}>
            <span className="badge badge-info">Selected</span>
          </div>
        )}
      </div>
    );
  };

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="content-wrapper">
      <div className="page-header primary">
        <h1>📋 My Plan</h1>
        <p>View your current plan and make changes</p>
      </div>

      {error   && <div className="alert alert-danger">❌ {error}</div>}
      {success && <div className="alert alert-success">✅ {success}</div>}

      {loading && !currentLicense && (
        <div style={{ textAlign: 'center', padding: '40px' }}>
          <p>Loading your plan...</p>
        </div>
      )}

      {/* ── Current Plan ──────────────────────────────────────────────── */}
      {currentLicense && (
        <div className="card" style={{ marginBottom: '24px' }}>
          <div className="card-header">
            <h2>Current Plan</h2>
          </div>
          <div className="card-section">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
              <div>
                <h3 style={{ margin: 0 }}>{currentLicense.license?.license_type_desc}</h3>
                <div className="text-secondary" style={{ marginTop: '4px', fontSize: '0.875rem' }}>
                  Active since {formatDate(currentLicense.effective_date)}
                  {' · '}
                  {currentLicense.license?.license_type === 'transactionsPerMonth'
                    ? 'API Usage Plan'
                    : 'Seat-Based Plan'
                  }
                </div>
              </div>
              <span className="badge badge-success" style={{ fontSize: '0.9rem', padding: '6px 12px' }}>
                Active
              </span>
            </div>
            {renderLicenseDetail(currentLicense.license)}
          </div>
        </div>
      )}

      {!loading && !currentLicense && (
        <div className="card" style={{ marginBottom: '24px' }}>
          <div className="card-section" style={{ textAlign: 'center', padding: '32px' }}>
            <p className="text-secondary">You don't have an active plan yet. Select one below to get started.</p>
          </div>
        </div>
      )}

      {/* ── Change Plan ───────────────────────────────────────────────── */}
      <div className="card" style={{ marginBottom: '24px' }}>
        <div className="card-header">
          <h2>{currentLicense ? 'Change Plan' : 'Select a Plan'}</h2>
          <p className="text-secondary">Changes take effect immediately.</p>
        </div>
        <div className="card-section">
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: '16px' }}>
            {availableLicenses.map(renderPlanCard)}
          </div>

          {selectedKey && selectedKey !== currentLicense?.license_key && (
            <div style={{
              marginTop: '20px',
              padding: '16px',
              backgroundColor: '#f0f7ff',
              borderRadius: '8px',
              border: '1px solid #007bff'
            }}>
              {(() => {
                const selected = availableLicenses.find(l => l.license_key === selectedKey);
                return (
                  <>
                    <p style={{ margin: '0 0 12px' }}>
                      <strong>Confirm plan change to: </strong>{selected?.license_type_desc}
                    </p>
                    <p className="text-secondary" style={{ margin: '0 0 16px', fontSize: '0.875rem' }}>
                      Your new plan takes effect immediately. Any active session will reflect the new limits right away.
                    </p>
                    <div style={{ display: 'flex', gap: '12px' }}>
                      <button
                        className="btn btn-primary"
                        onClick={handleConfirmChange}
                        disabled={changingLicense}
                      >
                        {changingLicense ? 'Updating...' : 'Confirm Change'}
                      </button>
                      <button
                        className="btn btn-secondary"
                        onClick={() => setSelectedKey('')}
                        disabled={changingLicense}
                      >
                        Cancel
                      </button>
                    </div>
                  </>
                );
              })()}
            </div>
          )}
        </div>
      </div>

      {/* ── Plan History ──────────────────────────────────────────────── */}
      <div className="card">
        <div
          className="card-header"
          onClick={fetchHistory}
          style={{ cursor: 'pointer', userSelect: 'none' }}
        >
          <h2>
            {showHistory ? '▼' : '▶'} Plan History
          </h2>
          <p className="text-secondary" style={{ margin: 0, fontSize: '0.875rem' }}>
            Click to {showHistory ? 'collapse' : 'expand'} your license history
          </p>
        </div>

        {showHistory && (
          <div className="card-section">
            {history.length === 0 ? (
              <p className="text-secondary">No history found.</p>
            ) : (
              <div className="table-container">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Plan</th>
                      <th>Type</th>
                      <th>Effective Date</th>
                      <th>End Date</th>
                      <th>Changed By</th>
                    </tr>
                  </thead>
                  <tbody>
                    {history.map(row => (
                      <tr key={row.history_key}>
                        <td><strong>{row.license?.license_type_desc ?? row.license_key}</strong></td>
                        <td>
                          <span className="badge badge-secondary" style={{ fontSize: '0.75rem' }}>
                            {row.license?.license_type === 'transactionsPerMonth' ? 'API Usage' : 'Seats'}
                          </span>
                        </td>
                        <td>{formatDate(row.effective_date)}</td>
                        <td>
                          {row.end_date === 'active'
                            ? <span className="badge badge-success">Current</span>
                            : formatDate(row.end_date)
                          }
                        </td>
                        <td>
                          {{
                            'customer_self_service': 'You',
                            'super_user':            'Support',
                            'public_signup':         'Signup',
                          }[row.changed_by_type] ?? row.changed_by_type}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default CustomerLicenseManager;
