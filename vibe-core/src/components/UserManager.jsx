/*
 * Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
 * Author: Christopher Niven
 *
 * UserManager — comprehensive user management.
 * Admins can create/edit/delete users and manage their role assignments.
 * Roles are now system-wide; the old per-app assignment panel is replaced
 * by a single "Manage Roles" modal that checks/unchecks system roles.
 */
import React, { useState, useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { apiReady } from '../api/config';
import '../design-system.css';

function UserManager() {
  const location = useLocation();

  // ── Core state ────────────────────────────────────────────────────────────
  const [users, setUsers]                       = useState([]);
  const [customers, setCustomers]               = useState([]);
  const [loading, setLoading]                   = useState(false);
  const [error, setError]                       = useState('');
  const [success, setSuccess]                   = useState('');
  const [showForm, setShowForm]                 = useState(false);
  const [editingUser, setEditingUser]           = useState(null);
  const [selectedCustomerFilter, setSelectedCustomerFilter] = useState('');

  const [formData, setFormData] = useState({
    customer_id: '',
    user_name: '',
    password: '',
    user_email: '',
    status: 'active'
  });

  // ── Role-assignment modal state ───────────────────────────────────────────
  const [roleModalUser, setRoleModalUser]       = useState(null);   // user object
  const [allRoles, setAllRoles]                 = useState([]);     // all system roles
  const [assignedRoleKeys, setAssignedRoleKeys] = useState([]);     // role_keys currently assigned
  const [pendingRoleKeys, setPendingRoleKeys]   = useState([]);     // role_keys after edits
  const [roleModalLoading, setRoleModalLoading] = useState(false);
  const [roleModalError, setRoleModalError]     = useState('');

  // ── Navigation state: pre-select customer ─────────────────────────────────
  useEffect(() => {
    if (location.state?.selectedCustomer) {
      setSelectedCustomerFilter(location.state.selectedCustomer);
    }
  }, [location.state]);

  useEffect(() => {
    fetchCustomers();
  }, []);

  useEffect(() => {
    if (selectedCustomerFilter) {
      fetchUsers(selectedCustomerFilter);
    }
  }, [selectedCustomerFilter]);

  // ── Data fetchers ─────────────────────────────────────────────────────────
  const fetchCustomers = async () => {
    try {
      const api = await apiReady;
      const response = await api.getWithLog('/customers', `${import.meta.url.split('/').pop()}`);
      if (response.data.success) {
        setCustomers(response.data.data.customers || []);
      }
    } catch (err) {
      console.error('Failed to fetch customers:', err);
    }
  };

  const fetchUsers = async (customerId) => {
    if (!customerId) return;
    setLoading(true);
    setError('');
    try {
      const api = await apiReady;
      const response = await api.getWithLog(
        `/customers/${customerId}/users`,
        `${import.meta.url.split('/').pop()}`
      );
      if (response.data.success) {
        setUsers(response.data.data.users || []);
      }
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to fetch users');
    } finally {
      setLoading(false);
    }
  };

  // ── User CRUD ─────────────────────────────────────────────────────────────
  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');

    if (!formData.customer_id || !formData.user_email) {
      setError('Customer and email are required');
      return;
    }

    setLoading(true);
    try {
      const api = await apiReady;
      if (editingUser) {
        const response = await api.putWithLog(
          `/customers/${formData.customer_id}/users/${editingUser.user_key}`,
          formData,
          `${import.meta.url.split('/').pop()}`
        );
        if (response.data.success) {
          setSuccess('User updated successfully!');
          setShowForm(false);
          setEditingUser(null);
          resetForm();
          fetchUsers(selectedCustomerFilter);
        }
      } else {
        const response = await api.postWithLog(
          `/customers/${formData.customer_id}/users`,
          formData,
          `${import.meta.url.split('/').pop()}`
        );
        if (response.data.success) {
          setSuccess('User created successfully!');
          setShowForm(false);
          resetForm();
          fetchUsers(selectedCustomerFilter);
        }
      }
    } catch (err) {
      setError(err.response?.data?.error || 'Operation failed');
    } finally {
      setLoading(false);
    }
  };

  const handleEdit = (user) => {
    setEditingUser(user);
    setFormData({
      customer_id: user.customer_id,
      user_name: user.user_name || '',
      password: '',
      user_email: user.user_email || '',
      status: user.status || 'active'
    });
    setShowForm(true);
    setError('');
    setSuccess('');
  };

  const handleDelete = async (customerId, userKey) => {
    if (!window.confirm('Delete this user? This cannot be undone.')) return;
    setLoading(true);
    setError('');
    setSuccess('');
    try {
      const api = await apiReady;
      const response = await api.deleteWithLog(
        `/customers/${customerId}/users/${userKey}`,
        `${import.meta.url.split('/').pop()}`
      );
      if (response.data.success) {
        setSuccess('User deleted successfully!');
        fetchUsers(selectedCustomerFilter);
      }
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to delete user');
    } finally {
      setLoading(false);
    }
  };

  const handleUpdateStatus = async (customerId, userKey, newStatus) => {
    setLoading(true);
    setError('');
    try {
      const api = await apiReady;
      const response = await api.putWithLog(
        `/customers/${customerId}/users/${userKey}/status`,
        { status: newStatus },
        `${import.meta.url.split('/').pop()}`
      );
      if (response.data.success) {
        setSuccess(`User status updated to ${newStatus}`);
        fetchUsers(selectedCustomerFilter);
      }
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to update status');
    } finally {
      setLoading(false);
    }
  };

  const resetForm = () => {
    setFormData({
      customer_id: selectedCustomerFilter || '',
      user_name: '',
      password: '',
      user_email: '',
      status: 'active'
    });
  };

  const handleCancel = () => {
    setShowForm(false);
    setEditingUser(null);
    resetForm();
    setError('');
    setSuccess('');
  };

  // ── Role assignment modal ─────────────────────────────────────────────────

  /**
   * Open the modal for a given user.
   * Loads all system roles and the user's current assignments in parallel.
   */
  const openRoleModal = async (user) => {
    setRoleModalUser(user);
    setRoleModalError('');
    setRoleModalLoading(true);

    try {
      const api = await apiReady;

      const [allRolesRes, userRolesRes] = await Promise.all([
        api.getWithLog('/roles', `${import.meta.url.split('/').pop()}`),
        api.getWithLog(
          `/customers/${user.customer_id}/users/${user.user_key}/roles`,
          `${import.meta.url.split('/').pop()}`
        )
      ]);

      const systemRoles   = allRolesRes.data.data.roles  || [];
      const currentAssigned = userRolesRes.data.data.roles || [];
      const currentKeys   = currentAssigned.map(r => r.role_key);

      setAllRoles(systemRoles);
      setAssignedRoleKeys(currentKeys);
      setPendingRoleKeys(currentKeys);       // start from current state

    } catch (err) {
      setRoleModalError(err.response?.data?.error || 'Failed to load roles');
    } finally {
      setRoleModalLoading(false);
    }
  };

  const closeRoleModal = () => {
    setRoleModalUser(null);
    setAllRoles([]);
    setAssignedRoleKeys([]);
    setPendingRoleKeys([]);
    setRoleModalError('');
  };

  const togglePendingRole = (roleKey) => {
    setPendingRoleKeys(prev =>
      prev.includes(roleKey)
        ? prev.filter(k => k !== roleKey)
        : [...prev, roleKey]
    );
  };

  /**
   * Diff pending vs assigned and fire the minimum set of assign/remove calls.
   */
  const saveRoleAssignments = async () => {
    if (!roleModalUser) return;

    const toAdd    = pendingRoleKeys.filter(k => !assignedRoleKeys.includes(k));
    const toRemove = assignedRoleKeys.filter(k => !pendingRoleKeys.includes(k));

    if (toAdd.length === 0 && toRemove.length === 0) {
      closeRoleModal();
      return;
    }

    setRoleModalLoading(true);
    setRoleModalError('');

    try {
      const api = await apiReady;
      const { customer_id, user_key } = roleModalUser;

      // Fire all assign calls
      await Promise.all(
        toAdd.map(role_key =>
          api.postWithLog(
            `/customers/${customer_id}/users/${user_key}/roles`,
            { role_key },
            `${import.meta.url.split('/').pop()}`
          )
        )
      );

      // Fire all remove calls
      await Promise.all(
        toRemove.map(role_key =>
          api.deleteWithLog(
            `/customers/${customer_id}/users/${user_key}/roles/${role_key}`,
            `${import.meta.url.split('/').pop()}`
          )
        )
      );

      setSuccess(`Role assignments updated for ${roleModalUser.user_email}`);
      closeRoleModal();
      // Refresh user list (token won't update until next login, but data is correct)
      fetchUsers(selectedCustomerFilter);

    } catch (err) {
      setRoleModalError(err.response?.data?.error || 'Failed to save role assignments');
    } finally {
      setRoleModalLoading(false);
    }
  };

  // ── Helpers ───────────────────────────────────────────────────────────────
  const getCustomerName = (customerId) => {
    const c = customers.find(c => c.customer_id === customerId);
    return c ? c.customer_name : customerId;
  };

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div className="page-container">
      <div className="page-content">

        {/* Header */}
        <div style={{ marginBottom: '24px' }}>
          <h1>User Manager</h1>
          <p className="text-secondary">
            Manage users and their role assignments.
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

        {/* Customer filter */}
        <div className="card" style={{ marginBottom: '20px' }}>
          <div className="card-section">
            <div className="form-group" style={{ marginBottom: 0 }}>
              <label htmlFor="customerFilter"><strong>Filter by Customer</strong></label>
              <select
                id="customerFilter"
                value={selectedCustomerFilter}
                onChange={(e) => setSelectedCustomerFilter(e.target.value)}
                className="form-control"
              >
                <option value="">Select a Customer</option>
                {customers.map(c => (
                  <option key={c.customer_id} value={c.customer_id}>{c.customer_name}</option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {/* Add user button */}
        {selectedCustomerFilter && !showForm && (
          <div style={{ marginBottom: '20px' }}>
            <button
              className="btn btn-success"
              onClick={() => {
                resetForm();
                setFormData(prev => ({ ...prev, customer_id: selectedCustomerFilter }));
                setShowForm(true);
                setError('');
                setSuccess('');
              }}
              disabled={loading}
            >
              ➕ Add New User
            </button>
          </div>
        )}

        {/* Create / Edit user form */}
        {showForm && (
          <div className="card" style={{ marginBottom: '30px' }}>
            <div className="card-section">
              <h2 style={{ marginTop: 0 }}>
                {editingUser ? 'Edit User' : 'Create New User'}
              </h2>
              <form onSubmit={handleSubmit}>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                  <div className="form-group">
                    <label htmlFor="user_email">Email <span className="required">*</span></label>
                    <input
                      id="user_email"
                      type="email"
                      className="form-control"
                      value={formData.user_email}
                      onChange={(e) => setFormData(prev => ({ ...prev, user_email: e.target.value }))}
                      required
                    />
                  </div>
                  <div className="form-group">
                    <label htmlFor="user_name">Display Name</label>
                    <input
                      id="user_name"
                      type="text"
                      className="form-control"
                      value={formData.user_name}
                      onChange={(e) => setFormData(prev => ({ ...prev, user_name: e.target.value }))}
                    />
                  </div>
                  <div className="form-group">
                    <label htmlFor="password">
                      Password {!editingUser && <span className="required">*</span>}
                      {editingUser && <small className="text-secondary"> (leave blank to keep current)</small>}
                    </label>
                    <input
                      id="password"
                      type="password"
                      className="form-control"
                      value={formData.password}
                      onChange={(e) => setFormData(prev => ({ ...prev, password: e.target.value }))}
                      required={!editingUser}
                    />
                  </div>
                  <div className="form-group">
                    <label htmlFor="status">Status</label>
                    <select
                      id="status"
                      className="form-control"
                      value={formData.status}
                      onChange={(e) => setFormData(prev => ({ ...prev, status: e.target.value }))}
                    >
                      <option value="active">Active</option>
                      <option value="inactive">Inactive</option>
                    </select>
                  </div>
                </div>

                <div className="button-group" style={{ marginTop: '16px' }}>
                  <button type="submit" className="btn btn-primary" disabled={loading}>
                    {loading ? 'Saving...' : editingUser ? 'Update User' : 'Create User'}
                  </button>
                  <button type="button" className="btn btn-secondary" onClick={handleCancel} disabled={loading}>
                    Cancel
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* Users table */}
        {selectedCustomerFilter && (
          <div className="card">
            <div className="card-section">
              <h2 style={{ marginTop: 0 }}>
                Users — {getCustomerName(selectedCustomerFilter)}
                {!loading && <span className="badge badge-secondary" style={{ marginLeft: '10px' }}>{users.length}</span>}
              </h2>

              {loading && <p className="text-secondary">Loading users...</p>}

              {!loading && users.length === 0 && (
                <p className="text-secondary" style={{ textAlign: 'center', padding: '40px' }}>
                  No users found. Click "Add New User" to create one.
                </p>
              )}

              {!loading && users.length > 0 && (
                <div className="table-container">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Email</th>
                        <th>Name</th>
                        <th>Status</th>
                        <th>Created</th>
                        <th>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {users.map(user => (
                        <tr key={user.user_key}>
                          <td>{user.user_email}</td>
                          <td>{user.user_name || '—'}</td>
                          <td>
                            <span className={`badge ${user.status === 'active' ? 'badge-success' : 'badge-secondary'}`}>
                              {user.status}
                            </span>
                          </td>
                          <td>{new Date(user.created_at).toLocaleDateString()}</td>
                          <td>
                            <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                              <button
                                className="btn btn-sm btn-primary"
                                onClick={() => handleEdit(user)}
                                disabled={loading}
                                title="Edit user"
                              >
                                ✏️ Edit
                              </button>

                              {/* ── Manage Roles button ── */}
                              <button
                                className="btn btn-sm btn-info"
                                onClick={() => openRoleModal(user)}
                                disabled={loading}
                                title="Manage role assignments"
                              >
                                🎭 Roles
                              </button>

                              <button
                                className="btn btn-sm btn-warning"
                                onClick={() => handleUpdateStatus(
                                  user.customer_id,
                                  user.user_key,
                                  user.status === 'active' ? 'inactive' : 'active'
                                )}
                                disabled={loading}
                                title={user.status === 'active' ? 'Deactivate user' : 'Activate user'}
                              >
                                {user.status === 'active' ? '⏸️ Deactivate' : '▶️ Activate'}
                              </button>

                              <button
                                className="btn btn-sm btn-danger"
                                onClick={() => handleDelete(user.customer_id, user.user_key)}
                                disabled={loading}
                                title="Delete user"
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
        )}

        {!selectedCustomerFilter && !showForm && (
          <div className="card">
            <div className="card-section">
              <div style={{ textAlign: 'center', padding: '60px 20px' }}>
                <p style={{ fontSize: '48px', marginBottom: '20px' }}>👥</p>
                <h3>Welcome to User Manager</h3>
                <p className="text-secondary">Select a customer above to view and manage their users.</p>
              </div>
            </div>
          </div>
        )}

      </div>

      {/* ── Role Assignment Modal ─────────────────────────────────────────── */}
      {roleModalUser && (
        <div
          style={{
            position: 'fixed', inset: 0,
            background: 'rgba(0,0,0,0.5)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            zIndex: 1000
          }}
          onClick={(e) => { if (e.target === e.currentTarget) closeRoleModal(); }}
        >
          <div
            style={{
              background: 'var(--color-surface, #fff)',
              borderRadius: '8px',
              padding: '32px',
              width: '480px',
              maxWidth: '90vw',
              maxHeight: '80vh',
              overflowY: 'auto',
              boxShadow: '0 20px 60px rgba(0,0,0,0.3)'
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '20px' }}>
              <div>
                <h2 style={{ margin: 0 }}>Manage Roles</h2>
                <p className="text-secondary" style={{ margin: '4px 0 0' }}>
                  {roleModalUser.user_email}
                </p>
              </div>
              <button
                onClick={closeRoleModal}
                style={{ background: 'none', border: 'none', fontSize: '24px', cursor: 'pointer', lineHeight: 1 }}
                title="Close"
              >
                ×
              </button>
            </div>

            {roleModalError && (
              <div className="alert alert-error" style={{ marginBottom: '16px' }}>
                {roleModalError}
              </div>
            )}

            {roleModalLoading && (
              <p className="text-secondary">Loading roles...</p>
            )}

            {!roleModalLoading && allRoles.length === 0 && (
              <p className="text-secondary">
                No system roles defined yet. Ask a superuser to create roles in Role Manager.
              </p>
            )}

            {!roleModalLoading && allRoles.length > 0 && (
              <>
                <p className="text-secondary" style={{ marginBottom: '16px', fontSize: '14px' }}>
                  Check the roles to assign. Changes take effect at the user's next login.
                </p>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', marginBottom: '24px' }}>
                  {allRoles.map(role => {
                    const isChecked = pendingRoleKeys.includes(role.role_key);
                    return (
                      <label
                        key={role.role_key}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '12px',
                          padding: '10px 14px',
                          border: `2px solid ${isChecked ? 'var(--color-primary, #667eea)' : 'var(--color-border, #e2e8f0)'}`,
                          borderRadius: '6px',
                          cursor: 'pointer',
                          background: isChecked ? 'var(--color-primary-subtle, #ebf4ff)' : 'transparent',
                          transition: 'all 0.15s'
                        }}
                      >
                        <input
                          type="checkbox"
                          checked={isChecked}
                          onChange={() => togglePendingRole(role.role_key)}
                          style={{ width: '18px', height: '18px', cursor: 'pointer' }}
                        />
                        <div style={{ flex: 1 }}>
                          <strong>{role.role_desc}</strong>
                          {role.is_default && (
                            <span className="badge badge-info" style={{ marginLeft: '8px', fontSize: '11px' }}>Default</span>
                          )}
                        </div>
                      </label>
                    );
                  })}
                </div>

                {/* Summary of pending changes */}
                {(() => {
                  const toAdd    = pendingRoleKeys.filter(k => !assignedRoleKeys.includes(k));
                  const toRemove = assignedRoleKeys.filter(k => !pendingRoleKeys.includes(k));
                  if (toAdd.length === 0 && toRemove.length === 0) return null;
                  return (
                    <div style={{
                      background: 'var(--color-warning-subtle, #fffbeb)',
                      border: '1px solid var(--color-warning, #f59e0b)',
                      borderRadius: '6px',
                      padding: '10px 14px',
                      marginBottom: '16px',
                      fontSize: '13px'
                    }}>
                      {toAdd.length > 0 && (
                        <div>➕ Adding: {toAdd.map(k => allRoles.find(r => r.role_key === k)?.role_desc).join(', ')}</div>
                      )}
                      {toRemove.length > 0 && (
                        <div>➖ Removing: {toRemove.map(k => allRoles.find(r => r.role_key === k)?.role_desc).join(', ')}</div>
                      )}
                    </div>
                  );
                })()}

                <div className="button-group">
                  <button
                    className="btn btn-primary"
                    onClick={saveRoleAssignments}
                    disabled={roleModalLoading}
                  >
                    {roleModalLoading ? 'Saving...' : 'Save Changes'}
                  </button>
                  <button
                    className="btn btn-secondary"
                    onClick={closeRoleModal}
                    disabled={roleModalLoading}
                  >
                    Cancel
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}

    </div>
  );
}

export default UserManager;
