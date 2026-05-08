/*
 * Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
 * Author: Christopher Niven
 *
 * RoleManager — system-wide role management for superusers.
 * Roles are no longer tied to an application. A superuser creates named
 * roles (e.g. "Admin", "Invoicing", "RoleA") for the entire system.
 * Customer admins then assign those roles to their users via UserManager.
 */
import React, { useState, useEffect } from 'react';
import { apiReady } from '../api/config';
import '../design-system.css';

function RoleManager() {
  const [roles, setRoles]           = useState([]);
  const [loading, setLoading]       = useState(false);
  const [error, setError]           = useState('');
  const [success, setSuccess]       = useState('');
  const [showForm, setShowForm]     = useState(false);
  const [editingRole, setEditingRole] = useState(null);

  const [formData, setFormData] = useState({ roleDesc: '' });

  // ── Load roles on mount ───────────────────────────────────────────────────
  useEffect(() => {
    fetchRoles();
  }, []);

  const fetchRoles = async () => {
    setLoading(true);
    setError('');
    try {
      const api = await apiReady;
      const response = await api.getWithLog('/roles', `${import.meta.url.split('/').pop()}`);
      if (response.data.success) {
        setRoles(response.data.data.roles || []);
      }
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to fetch roles');
      setRoles([]);
    } finally {
      setLoading(false);
    }
  };

  // ── Form helpers ──────────────────────────────────────────────────────────
  const resetForm = () => setFormData({ roleDesc: '' });

  const handleCancel = () => {
    setShowForm(false);
    setEditingRole(null);
    resetForm();
    setError('');
    setSuccess('');
  };

  const validateForm = () => {
    if (!formData.roleDesc.trim()) {
      setError('Role name is required');
      return false;
    }
    if (formData.roleDesc.length > 30) {
      setError('Role name must be 30 characters or less');
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
      const payload = { role_desc: formData.roleDesc.trim() };

      if (editingRole) {
        const response = await api.putWithLog(
          `/roles/${editingRole.role_key}`,
          payload,
          `${import.meta.url.split('/').pop()}`
        );
        if (response.data.success) {
          setSuccess('Role updated successfully!');
          setShowForm(false);
          setEditingRole(null);
          resetForm();
          fetchRoles();
        }
      } else {
        const response = await api.postWithLog(
          '/roles',
          payload,
          `${import.meta.url.split('/').pop()}`
        );
        if (response.data.success) {
          setSuccess('Role created successfully!');
          setShowForm(false);
          resetForm();
          fetchRoles();
        }
      }
    } catch (err) {
      setError(err.response?.data?.error || 'Operation failed');
    } finally {
      setLoading(false);
    }
  };

  const handleEdit = (role) => {
    setEditingRole(role);
    setFormData({ roleDesc: role.role_desc });
    setShowForm(true);
    setError('');
    setSuccess('');
  };

  const handleDelete = async (role) => {
    if (role.is_default) return; // button is disabled, guard anyway
    if (!window.confirm(`Delete role "${role.role_desc}"? This cannot be undone.`)) return;

    setLoading(true);
    setError('');
    setSuccess('');
    try {
      const api = await apiReady;
      const response = await api.deleteWithLog(
        `/roles/${role.role_key}`,
        `${import.meta.url.split('/').pop()}`
      );
      if (response.data.success) {
        setSuccess('Role deleted successfully!');
        fetchRoles();
      }
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to delete role');
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
          <h1>Role Manager</h1>
          <p className="text-secondary">
            Create and manage system-wide roles. Roles are available to all customers
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
              ➕ Add New Role
            </button>
          </div>
        )}

        {/* Create / Edit form */}
        {showForm && (
          <div className="card" style={{ marginBottom: '30px' }}>
            <div className="card-section">
              <h2 style={{ marginTop: 0 }}>
                {editingRole ? `Edit Role: ${editingRole.role_desc}` : 'Create New Role'}
              </h2>
              <form onSubmit={handleSubmit}>
                <div className="form-group">
                  <label htmlFor="roleDesc">
                    Role Name <span className="required">*</span>
                  </label>
                  <input
                    id="roleDesc"
                    name="roleDesc"
                    type="text"
                    className="form-control"
                    placeholder="e.g. Invoicing, RoleA, Manager"
                    value={formData.roleDesc}
                    onChange={(e) => setFormData({ roleDesc: e.target.value })}
                    maxLength={30}
                    autoFocus
                  />
                  <small className="text-secondary">
                    {formData.roleDesc.length}/30 characters. This name is used in code
                    via <code>isRoleAssigned('RoleName')</code>.
                  </small>
                </div>

                <div className="button-group" style={{ marginTop: '16px' }}>
                  <button type="submit" className="btn btn-primary" disabled={loading}>
                    {loading ? 'Saving...' : editingRole ? 'Update Role' : 'Create Role'}
                  </button>
                  <button type="button" className="btn btn-secondary" onClick={handleCancel} disabled={loading}>
                    Cancel
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* Roles table */}
        <div className="card">
          <div className="card-section">
            <h2 style={{ marginTop: 0 }}>
              System Roles
              {!loading && <span className="badge badge-secondary" style={{ marginLeft: '10px' }}>{roles.length}</span>}
            </h2>

            {loading && <p className="text-secondary">Loading roles...</p>}

            {!loading && roles.length === 0 && (
              <div style={{ textAlign: 'center', padding: '40px 20px' }}>
                <p style={{ fontSize: '48px', marginBottom: '16px' }}>🎭</p>
                <p className="text-secondary">No roles yet. Click "Add New Role" to create the first one.</p>
              </div>
            )}

            {!loading && roles.length > 0 && (
              <div className="table-container">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Role Name</th>
                      <th>Type</th>
                      <th>Created</th>
                      <th>Modified</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {roles.map(role => (
                      <tr key={role.role_key}>
                        <td><strong>{role.role_desc}</strong></td>
                        <td>
                          {role.is_default
                            ? <span className="badge badge-info">🔒 Default</span>
                            : <span className="badge badge-secondary">✏️ Custom</span>
                          }
                        </td>
                        <td>{new Date(role.created_at).toLocaleDateString()}</td>
                        <td>{new Date(role.modified_at).toLocaleDateString()}</td>
                        <td>
                          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                            <button
                              className="btn btn-sm btn-primary"
                              onClick={() => handleEdit(role)}
                              disabled={loading || role.is_default}
                              title={role.is_default ? 'Cannot edit default roles' : 'Edit role'}
                            >
                              ✏️ Edit
                            </button>
                            <button
                              className="btn btn-sm btn-danger"
                              onClick={() => handleDelete(role)}
                              disabled={loading || role.is_default}
                              title={role.is_default ? 'Cannot delete default roles' : 'Delete role'}
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

export default RoleManager;
