/*
 * Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
 * Author: Christopher Niven
 *
 * LicenseManager — system-wide license tier management for superusers.
 * Licenses are no longer tied to an application.
 * Defaults to showing only active tiers; a toggle reveals inactive ones.
 */
import React, { useState, useEffect } from 'react';
import { apiReady } from '../api/config';
import '../design-system.css';

function LicenseManager() {
  const [licenseTypes, setLicenseTypes]     = useState([]);
  const [loading, setLoading]               = useState(false);
  const [error, setError]                   = useState('');
  const [success, setSuccess]               = useState('');
  const [showForm, setShowForm]             = useState(false);
  const [editingLicense, setEditingLicense] = useState(null);
  const [showInactive, setShowInactive]     = useState(false); // default: active only

  const [formData, setFormData] = useState({
    tierDesc:           '',
    minUsers:           '',
    maxUsers:           '',
    monthlyCost:        '',
    discountPercentage: '0',
    isActive:           true,
  });

  // ── Load licenses on mount and when showInactive changes ─────────────────
  useEffect(() => {
    fetchLicenses();
  }, [showInactive]);

  const fetchLicenses = async () => {
    setLoading(true);
    setError('');
    try {
      const api   = await apiReady;
      const url   = showInactive ? '/licenses' : '/licenses?active=true';
      const response = await api.getWithLog(url, `${import.meta.url.split('/').pop()}`);
      if (response.data.success) {
        setLicenseTypes(response.data.data.licenses || []);
      }
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to fetch licenses');
      setLicenseTypes([]);
    } finally {
      setLoading(false);
    }
  };

  // ── Form helpers ──────────────────────────────────────────────────────────
  const resetForm = () => setFormData({
    tierDesc:           '',
    minUsers:           '',
    maxUsers:           '',
    monthlyCost:        '',
    discountPercentage: '0',
    isActive:           true,
  });

  const handleCancel = () => {
    setShowForm(false);
    setEditingLicense(null);
    resetForm();
    setError('');
    setSuccess('');
  };

  const handleInputChange = (e) => {
    const { name, value, type, checked } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value,
    }));
  };

  const validateForm = () => {
    if (!formData.tierDesc || !formData.minUsers ||
        !formData.maxUsers  || !formData.monthlyCost) {
      setError('Tier Description, Min Users, Max Users, and Monthly Cost are required');
      return false;
    }
    if (formData.tierDesc.length > 100) {
      setError('Tier Description must be 100 characters or less');
      return false;
    }
    if (isNaN(formData.monthlyCost) || parseFloat(formData.monthlyCost) < 0) {
      setError('Monthly Cost must be a valid positive number');
      return false;
    }
    if (isNaN(formData.minUsers) || parseInt(formData.minUsers) < 0) {
      setError('Min Users must be a valid positive integer');
      return false;
    }
    if (isNaN(formData.maxUsers) ||
        parseInt(formData.maxUsers) < parseInt(formData.minUsers)) {
      setError('Max Users must be >= Min Users');
      return false;
    }
    if (formData.discountPercentage && (
        isNaN(formData.discountPercentage) ||
        parseFloat(formData.discountPercentage) < 0 ||
        parseFloat(formData.discountPercentage) > 100)) {
      setError('Discount Percentage must be between 0 and 100');
      return false;
    }
    return true;
  };

  // ── CRUD handlers ─────────────────────────────────────────────────────────
  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');
    if (!validateForm()) return;

    setLoading(true);
    try {
      const api = await apiReady;
      const payload = {
        tier_desc:           formData.tierDesc,
        min_users:           parseInt(formData.minUsers),
        max_users:           parseInt(formData.maxUsers),
        monthly_cost:        parseFloat(formData.monthlyCost),
        discount_percentage: parseFloat(formData.discountPercentage || 0),
        is_active:           formData.isActive,
      };

      if (editingLicense) {
        const response = await api.putWithLog(
          `/licenses/${editingLicense.license_key}`,
          payload,
          `${import.meta.url.split('/').pop()}`
        );
        if (response.data.success) {
          setSuccess('License tier updated successfully!');
          setShowForm(false);
          setEditingLicense(null);
          resetForm();
          fetchLicenses();
        }
      } else {
        const response = await api.postWithLog(
          '/licenses',
          payload,
          `${import.meta.url.split('/').pop()}`
        );
        if (response.data.success) {
          setSuccess('License tier created successfully!');
          setShowForm(false);
          resetForm();
          fetchLicenses();
        }
      }
    } catch (err) {
      setError(err.response?.data?.error || 'Operation failed');
    } finally {
      setLoading(false);
    }
  };

  const handleEdit = (license) => {
    setEditingLicense(license);
    setFormData({
      tierDesc:           license.tier_desc,
      minUsers:           license.min_users?.toString() || '',
      maxUsers:           license.max_users?.toString()  || '',
      monthlyCost:        license.monthly_cost?.toString() || '',
      discountPercentage: license.discount_percentage?.toString() || '0',
      isActive:           license.is_active !== false, // treat missing as true
    });
    setShowForm(true);
    setError('');
    setSuccess('');
  };

  const handleDelete = async (license) => {
    if (!window.confirm(
      `Delete "${license.tier_desc}"? This cannot be undone.\n\n` +
      `Consider deactivating instead to preserve history.`
    )) return;

    setLoading(true);
    setError('');
    setSuccess('');
    try {
      const api = await apiReady;
      const response = await api.deleteWithLog(
        `/licenses/${license.license_key}`,
        `${import.meta.url.split('/').pop()}`
      );
      if (response.data.success) {
        setSuccess('License tier deleted successfully!');
        fetchLicenses();
      }
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to delete license');
    } finally {
      setLoading(false);
    }
  };

  /**
   * Quick-toggle is_active without opening the full edit form.
   */
  const handleToggleActive = async (license) => {
    const newState = !license.is_active;
    const verb     = newState ? 'activate' : 'deactivate';
    if (!window.confirm(`${verb.charAt(0).toUpperCase() + verb.slice(1)} "${license.tier_desc}"?`)) return;

    setLoading(true);
    setError('');
    try {
      const api = await apiReady;
      const response = await api.putWithLog(
        `/licenses/${license.license_key}`,
        { is_active: newState },
        `${import.meta.url.split('/').pop()}`
      );
      if (response.data.success) {
        setSuccess(`"${license.tier_desc}" ${verb}d successfully!`);
        fetchLicenses();
      }
    } catch (err) {
      setError(err.response?.data?.error || `Failed to ${verb} license`);
    } finally {
      setLoading(false);
    }
  };

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div className="page-container">
      <div className="page-content">

        {/* Header */}
        <div style={{ marginBottom: '24px' }}>
          <h1>License Manager</h1>
          <p className="text-secondary">
            Create and manage system-wide license tiers. Tiers are available to
            all customers and are no longer tied to a specific application.
          </p>
        </div>

        {/* Notifications */}
        {error && (
          <div className="alert alert-error" style={{ marginBottom: '16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span>{error}</span>
            <button onClick={() => setError('')} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '20px', color: 'inherit' }}>×</button>
          </div>
        )}
        {success && (
          <div className="alert alert-success" style={{ marginBottom: '16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span>{success}</span>
            <button onClick={() => setSuccess('')} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '20px', color: 'inherit' }}>×</button>
          </div>
        )}

        {/* Toolbar: Add button + Show inactive toggle */}
        {!showForm && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginBottom: '20px', flexWrap: 'wrap' }}>
            <button
              className="btn btn-success"
              onClick={() => { setShowForm(true); setError(''); setSuccess(''); }}
              disabled={loading}
            >
              ➕ Add New License Tier
            </button>

            <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', userSelect: 'none' }}>
              <input
                type="checkbox"
                checked={showInactive}
                onChange={(e) => setShowInactive(e.target.checked)}
                style={{ width: '16px', height: '16px', cursor: 'pointer' }}
              />
              <span className="text-secondary" style={{ fontSize: '14px' }}>
                Show inactive tiers
              </span>
            </label>
          </div>
        )}

        {/* Create / Edit form */}
        {showForm && (
          <div className="card" style={{ marginBottom: '30px' }}>
            <div className="card-section">
              <h2 style={{ marginTop: 0 }}>
                {editingLicense
                  ? `Edit: ${editingLicense.tier_desc}`
                  : 'Create New License Tier'}
              </h2>

              <form onSubmit={handleSubmit}>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>

                  <div className="form-group" style={{ gridColumn: '1 / -1' }}>
                    <label htmlFor="tierDesc">
                      Tier Description <span className="required">*</span>
                    </label>
                    <input
                      id="tierDesc"
                      name="tierDesc"
                      type="text"
                      className="form-control"
                      placeholder="e.g. Starter, Professional, Enterprise"
                      value={formData.tierDesc}
                      onChange={handleInputChange}
                      maxLength={100}
                      autoFocus
                    />
                    <small className="text-secondary">{formData.tierDesc.length}/100</small>
                  </div>

                  <div className="form-group">
                    <label htmlFor="minUsers">
                      Min Users <span className="required">*</span>
                    </label>
                    <input
                      id="minUsers"
                      name="minUsers"
                      type="number"
                      className="form-control"
                      placeholder="0"
                      min="0"
                      value={formData.minUsers}
                      onChange={handleInputChange}
                    />
                  </div>

                  <div className="form-group">
                    <label htmlFor="maxUsers">
                      Max Users <span className="required">*</span>
                    </label>
                    <input
                      id="maxUsers"
                      name="maxUsers"
                      type="number"
                      className="form-control"
                      placeholder="100"
                      min="0"
                      value={formData.maxUsers}
                      onChange={handleInputChange}
                    />
                  </div>

                  <div className="form-group">
                    <label htmlFor="monthlyCost">
                      Monthly Cost ($) <span className="required">*</span>
                    </label>
                    <input
                      id="monthlyCost"
                      name="monthlyCost"
                      type="number"
                      className="form-control"
                      placeholder="0.00"
                      min="0"
                      step="0.01"
                      value={formData.monthlyCost}
                      onChange={handleInputChange}
                    />
                  </div>

                  <div className="form-group">
                    <label htmlFor="discountPercentage">Discount (%)</label>
                    <input
                      id="discountPercentage"
                      name="discountPercentage"
                      type="number"
                      className="form-control"
                      placeholder="0"
                      min="0"
                      max="100"
                      step="0.1"
                      value={formData.discountPercentage}
                      onChange={handleInputChange}
                    />
                  </div>

                  <div className="form-group" style={{ gridColumn: '1 / -1' }}>
                    <label style={{ display: 'flex', alignItems: 'center', gap: '10px', cursor: 'pointer' }}>
                      <input
                        type="checkbox"
                        name="isActive"
                        checked={formData.isActive}
                        onChange={handleInputChange}
                        style={{ width: '18px', height: '18px', cursor: 'pointer' }}
                      />
                      <span><strong>Active</strong> — uncheck to create as inactive / retire this tier</span>
                    </label>
                  </div>

                </div>

                <div className="button-group" style={{ marginTop: '16px' }}>
                  <button type="submit" className="btn btn-primary" disabled={loading}>
                    {loading ? 'Saving...' : editingLicense ? 'Update Tier' : 'Create Tier'}
                  </button>
                  <button type="button" className="btn btn-secondary" onClick={handleCancel} disabled={loading}>
                    Cancel
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* License tiers table */}
        <div className="card">
          <div className="card-section">
            <h2 style={{ marginTop: 0 }}>
              {showInactive ? 'All License Tiers' : 'Active License Tiers'}
              {!loading && (
                <span className="badge badge-secondary" style={{ marginLeft: '10px' }}>
                  {licenseTypes.length}
                </span>
              )}
            </h2>

            {loading && <p className="text-secondary">Loading license tiers...</p>}

            {!loading && licenseTypes.length === 0 && (
              <div style={{ textAlign: 'center', padding: '40px 20px' }}>
                <p style={{ fontSize: '48px', marginBottom: '16px' }}>🔑</p>
                <p className="text-secondary">
                  {showInactive
                    ? 'No license tiers found.'
                    : 'No active license tiers. Click "Add New License Tier" or enable "Show inactive tiers".'}
                </p>
              </div>
            )}

            {!loading && licenseTypes.length > 0 && (
              <div className="table-container">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Tier</th>
                      <th>Users</th>
                      <th>Monthly Cost</th>
                      <th>Discount</th>
                      <th>Status</th>
                      <th>Modified</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {licenseTypes.map(license => {
                      const isActive = license.is_active !== false; // missing = true
                      return (
                        <tr
                          key={license.license_key}
                          style={{ opacity: isActive ? 1 : 0.6 }}
                        >
                          <td><strong>{license.tier_desc}</strong></td>
                          <td>
                            {license.min_users} – {license.max_users}
                          </td>
                          <td>${parseFloat(license.monthly_cost).toFixed(2)}</td>
                          <td>
                            {parseFloat(license.discount_percentage || 0) > 0 ? (
                              <span className="badge badge-success">
                                {parseFloat(license.discount_percentage).toFixed(1)}%
                              </span>
                            ) : (
                              <span className="badge badge-secondary">None</span>
                            )}
                          </td>
                          <td>
                            {isActive
                              ? <span className="badge badge-success">✅ Active</span>
                              : <span className="badge badge-secondary">⏸️ Inactive</span>
                            }
                          </td>
                          <td>{new Date(license.modified_at).toLocaleDateString()}</td>
                          <td>
                            <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                              <button
                                className="btn btn-sm btn-primary"
                                onClick={() => handleEdit(license)}
                                disabled={loading}
                              >
                                ✏️ Edit
                              </button>
                              <button
                                className={`btn btn-sm ${isActive ? 'btn-warning' : 'btn-success'}`}
                                onClick={() => handleToggleActive(license)}
                                disabled={loading}
                                title={isActive ? 'Deactivate this tier' : 'Activate this tier'}
                              >
                                {isActive ? '⏸️ Deactivate' : '▶️ Activate'}
                              </button>
                              <button
                                className="btn btn-sm btn-danger"
                                onClick={() => handleDelete(license)}
                                disabled={loading}
                                title="Permanently delete"
                              >
                                🗑️ Delete
                              </button>
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>

      </div>
    </div>
  );
}

export default LicenseManager;
