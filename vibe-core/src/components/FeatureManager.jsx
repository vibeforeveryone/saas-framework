/*
 * Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
 * Author: Christopher Niven
 *
 * FeatureManager — system-wide feature management for superusers.
 * Features are no longer tied to an application. A superuser creates named
 * features (e.g. "Reporting", "BulkExport") for the entire system.
 * Customer admins assign those features to their users via UserManager.
 */
import React, { useState, useEffect } from 'react';
import { apiReady } from '../api/config';
import '../design-system.css';

function FeatureManager() {
  const [features, setFeatures]         = useState([]);
  const [loading, setLoading]           = useState(false);
  const [error, setError]               = useState('');
  const [success, setSuccess]           = useState('');
  const [showForm, setShowForm]         = useState(false);
  const [editingFeature, setEditingFeature] = useState(null);

  const [formData, setFormData] = useState({ featureDesc: '' });

  // ── Load features on mount ────────────────────────────────────────────────
  useEffect(() => {
    fetchFeatures();
  }, []);

  const fetchFeatures = async () => {
    setLoading(true);
    setError('');
    try {
      const api = await apiReady;
      const response = await api.getWithLog('/features', `${import.meta.url.split('/').pop()}`);
      if (response.data.success) {
        setFeatures(response.data.data.features || []);
      }
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to fetch features');
      setFeatures([]);
    } finally {
      setLoading(false);
    }
  };

  // ── Form helpers ──────────────────────────────────────────────────────────
  const resetForm = () => setFormData({ featureDesc: '' });

  const handleCancel = () => {
    setShowForm(false);
    setEditingFeature(null);
    resetForm();
    setError('');
    setSuccess('');
  };

  const validateForm = () => {
    if (!formData.featureDesc.trim()) {
      setError('Feature name is required');
      return false;
    }
    if (formData.featureDesc.length > 30) {
      setError('Feature name must be 30 characters or less');
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
      const payload = { feature_desc: formData.featureDesc.trim() };

      if (editingFeature) {
        const response = await api.putWithLog(
          `/features/${editingFeature.feature_key}`,
          payload,
          `${import.meta.url.split('/').pop()}`
        );
        if (response.data.success) {
          setSuccess('Feature updated successfully!');
          setShowForm(false);
          setEditingFeature(null);
          resetForm();
          fetchFeatures();
        }
      } else {
        const response = await api.postWithLog(
          '/features',
          payload,
          `${import.meta.url.split('/').pop()}`
        );
        if (response.data.success) {
          setSuccess('Feature created successfully!');
          setShowForm(false);
          resetForm();
          fetchFeatures();
        }
      }
    } catch (err) {
      setError(err.response?.data?.error || 'Operation failed');
    } finally {
      setLoading(false);
    }
  };

  const handleEdit = (feature) => {
    setEditingFeature(feature);
    setFormData({ featureDesc: feature.feature_desc });
    setShowForm(true);
    setError('');
    setSuccess('');
  };

  const handleDelete = async (feature) => {
    if (!window.confirm(`Delete feature "${feature.feature_desc}"? This cannot be undone.`)) return;

    setLoading(true);
    setError('');
    setSuccess('');
    try {
      const api = await apiReady;
      const response = await api.deleteWithLog(
        `/features/${feature.feature_key}`,
        `${import.meta.url.split('/').pop()}`
      );
      if (response.data.success) {
        setSuccess('Feature deleted successfully!');
        fetchFeatures();
      }
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to delete feature');
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
          <h1>Feature Manager</h1>
          <p className="text-secondary">
            Create and manage system-wide features. Features are available to all customers
            and are assigned to individual users by customer admins.
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

        {/* Add button */}
        {!showForm && (
          <div style={{ marginBottom: '20px' }}>
            <button
              className="btn btn-success"
              onClick={() => { setShowForm(true); setError(''); setSuccess(''); }}
              disabled={loading}
            >
              ➕ Add New Feature
            </button>
          </div>
        )}

        {/* Create / Edit form */}
        {showForm && (
          <div className="card" style={{ marginBottom: '30px' }}>
            <div className="card-section">
              <h2 style={{ marginTop: 0 }}>
                {editingFeature ? `Edit Feature: ${editingFeature.feature_desc}` : 'Create New Feature'}
              </h2>
              <form onSubmit={handleSubmit}>
                <div className="form-group">
                  <label htmlFor="featureDesc">
                    Feature Name <span className="required">*</span>
                  </label>
                  <input
                    id="featureDesc"
                    name="featureDesc"
                    type="text"
                    className="form-control"
                    placeholder="e.g. Reporting, BulkExport, AdvancedSearch"
                    value={formData.featureDesc}
                    onChange={(e) => setFormData({ featureDesc: e.target.value })}
                    maxLength={30}
                    autoFocus
                  />
                  <small className="text-secondary">
                    {formData.featureDesc.length}/30 characters. This name is used in code
                    via <code>isFeatureAssigned('FeatureName')</code>.
                  </small>
                </div>

                <div className="button-group" style={{ marginTop: '16px' }}>
                  <button type="submit" className="btn btn-primary" disabled={loading}>
                    {loading ? 'Saving...' : editingFeature ? 'Update Feature' : 'Create Feature'}
                  </button>
                  <button type="button" className="btn btn-secondary" onClick={handleCancel} disabled={loading}>
                    Cancel
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* Features table */}
        <div className="card">
          <div className="card-section">
            <h2 style={{ marginTop: 0 }}>
              System Features
              {!loading && <span className="badge badge-secondary" style={{ marginLeft: '10px' }}>{features.length}</span>}
            </h2>

            {loading && <p className="text-secondary">Loading features...</p>}

            {!loading && features.length === 0 && (
              <div style={{ textAlign: 'center', padding: '40px 20px' }}>
                <p style={{ fontSize: '48px', marginBottom: '16px' }}>🧩</p>
                <p className="text-secondary">No features yet. Click "Add New Feature" to create the first one.</p>
              </div>
            )}

            {!loading && features.length > 0 && (
              <div className="table-container">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Feature Name</th>
                      <th>Created</th>
                      <th>Modified</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {features.map(feature => (
                      <tr key={feature.feature_key}>
                        <td><strong>{feature.feature_desc}</strong></td>
                        <td>{new Date(feature.created_at).toLocaleDateString()}</td>
                        <td>{new Date(feature.modified_at).toLocaleDateString()}</td>
                        <td>
                          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                            <button
                              className="btn btn-sm btn-primary"
                              onClick={() => handleEdit(feature)}
                              disabled={loading}
                            >
                              ✏️ Edit
                            </button>
                            <button
                              className="btn btn-sm btn-danger"
                              onClick={() => handleDelete(feature)}
                              disabled={loading}
                            >
                              🗑️ Delete
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
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

export default FeatureManager;
