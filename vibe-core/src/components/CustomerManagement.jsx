/*
 * Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
 * Author: Christopher Niven
 */
import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiReady } from '../api/config';  // NEW: apiReady is a Promise that resolves to the configured axios instance
import './CustomerManagement.css';

const CustomerManagement = () => {
  const [customers, setCustomers] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [showModal, setShowModal] = useState(false);
  const [editingCustomer, setEditingCustomer] = useState(null);
  const navigate = useNavigate();

  const [formData, setFormData] = useState({
    company_name: '',
    customer_id: '',
    email: '',
    name: '',
    phone: '',
    address: '',
    city: '',
    state: '',
    zip: '',
    country: '',
    admin_name: '',
    admin_email: '',
    admin_password: ''
  });

  useEffect(() => {
    fetchCustomers();
  }, []);

  const fetchCustomers = async () => {
    try {
      setLoading(true);

      const dummy = 1
      const d2 = dummy

      // OLD: const response = await api.getWithLog('/customers',
      //        `${import.meta.url.split('/').pop()}`);

      // NEW: await apiReady first to get the configured axios instance, then call it
      const api = await apiReady;
      const response = await api.getWithLog(
        '/customers',
        `${import.meta.url.split('/').pop()}`
      );

      if (response.data.success) {
        setCustomers(response.data.data.customers);
      }
    } catch (err) {
      console.error('Error fetching customers:', err);
      // NEW: distinguish config load failure vs API failure
      if (err.message?.includes('apiConfig.json')) {
        setError('API is not configured. Please check that public/apiConfig.json exists.');
      } else {
        setError('Failed to fetch customers');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = () => {
    setEditingCustomer(null);
    setFormData({
      company_name: '',
      customer_id: '',
      email: '',
      name: '',
      phone: '',
      address: '',
      city: '',
      state: '',
      zip: '',
      country: '',
      admin_name: '',
      admin_email: '',
      admin_password: ''
    });
    setError('');
    setSuccess('');
    setShowModal(true);
  };

  const handleEdit = (customer) => {
    setEditingCustomer(customer);
    setFormData({
      company_name: customer.company_name || '',
      customer_id: customer.customer_id || '',
      email: customer.email || '',
      name: customer.name || '',
      phone: customer.phone || '',
      address: customer.address || '',
      city: customer.city || '',
      state: customer.state || '',
      zip: customer.zip || '',
      country: customer.country || '',
      admin_name: '',
      admin_email: '',
      admin_password: ''
    });
    setError('');
    setSuccess('');
    setShowModal(true);
  };

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
  };

  const validateForm = () => {
    if (!editingCustomer) {
      // Creating new customer
      if (!formData.company_name) { setError('Company Name is required'); return false; }
      if (!formData.customer_id)  { setError('Customer ID is required');   return false; }
      if (!formData.name)         { setError('Name is required');           return false; }
      if (!formData.email)        { setError('Email is required');          return false; }
      if (!formData.admin_email)  { setError('Admin Email is required for new customers'); return false; }
      if (!formData.admin_password) { setError('Admin Password is required for new customers'); return false; }
      if (formData.admin_password.length < 8) { setError('Admin Password must be at least 8 characters'); return false; }

      const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
      if (!emailRegex.test(formData.email))       { setError('Please enter a valid email address');       return false; }
      if (!emailRegex.test(formData.admin_email)) { setError('Please enter a valid admin email address'); return false; }
    } else {
      // Editing existing customer
      if (!formData.company_name) { setError('Company Name is required'); return false; }
      if (!formData.name)         { setError('Name is required');         return false; }
      if (!formData.email)        { setError('Email is required');        return false; }
    }
    return true;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');

    if (!validateForm()) return;

    try {
      setLoading(true);

      // NEW: await apiReady once and reuse for all branches below
      const api = await apiReady;

      if (editingCustomer) {
        // OLD: await api.putWithLog(`/customers/${editingCustomer.customer_id}`, formData,
        //        `${import.meta.url.split('/').pop()}`);
        const api = await apiReady;
        const response = await api.putWithLog(
          `/customers/${editingCustomer.customer_id}`,
          formData,
          `${import.meta.url.split('/').pop()}`
        );
        setSuccess('Customer updated successfully!');
      } else {
        // OLD: await api.postWithLog('/customers', formData);
        const api = await apiReady;
        const response = await api.postWithLog(
          '/customers',
          formData,
          `${import.meta.url.split('/').pop()}`  // NEW: added missing log label for consistency
        );
        setSuccess('Customer created successfully!');
      }

      setShowModal(false);
      fetchCustomers();
    } catch (err) {
      console.error('Error saving customer:', err);
      // NEW: distinguish config load failure vs API failure
      if (err.message?.includes('apiConfig.json')) {
        setError('API is not configured. Please check that public/apiConfig.json exists.');
      } else {
        setError(err.response?.data?.error || 'Failed to save customer');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (customerId) => {
    if (window.confirm('Delete this customer? This action cannot be undone.')) {
      try {
        setLoading(true);

        // OLD: await api.deleteWithLog(`/customers/${customerId}`,
        //        `${import.meta.url.split('/').pop()}`);

        // NEW: await apiReady first to get the configured axios instance, then call it
        const api = await apiReady;
        await api.deleteWithLog(
          `/customers/${customerId}`,
          `${import.meta.url.split('/').pop()}`
        );

        setSuccess('Customer deleted successfully!');
        fetchCustomers();
      } catch (err) {
        console.error('Error deleting customer:', err);
        // NEW: distinguish config load failure vs API failure
        if (err.message?.includes('apiConfig.json')) {
          setError('API is not configured. Please check that public/apiConfig.json exists.');
        } else {
          setError('Failed to delete customer');
        }
      } finally {
        setLoading(false);
      }
    }
  };

  const handleManageUsers = (customer) => {
    // Navigate to users page with customer context passed via state
    navigate('/users', {
      state: {
        selectedCustomer: customer.customer_id,
        customerName: customer.name
      }
    });
  };

  return (
    <div className="content-wrapper">
      <div className="page-header primary">
        <h1>👥 Customer Management</h1>
        <p>Manage customers and their information</p>
      </div>

      {/* Error/Success Messages */}
      {error && (
        <div className="card" style={{ marginBottom: '20px' }}>
          <div className="card-section">
            <div className="error-message">⚠️ {error}</div>
          </div>
        </div>
      )}

      {success && (
        <div className="card" style={{ marginBottom: '20px' }}>
          <div className="card-section">
            <div className="success-message">✅ {success}</div>
          </div>
        </div>
      )}

      <div className="card">
        <div className="card-section">
          <div className="section-header">
            <h2>📋 Customers ({customers.length})</h2>
            <button className="btn btn-primary" onClick={handleCreate}>
              ➕ Add Customer
            </button>
          </div>

          {loading && !showModal ? (
            <div className="loading-container">
              <div className="loading-spinner">🔄 Loading...</div>
            </div>
          ) : customers.length > 0 ? (
            <div className="customer-grid">
              {customers.map((customer) => (
                <div key={customer.customer_id} className="customer-card">
                  <div className="customer-header">
                    <h3>{customer.name}</h3>
                    <div className="customer-actions">
                      <button className="btn-icon" onClick={() => handleEdit(customer)}>✏️</button>
                      <button className="btn-icon danger" onClick={() => handleDelete(customer.customer_id)}>🗑️</button>
                    </div>
                  </div>
                  <div className="customer-details">
                    <p><strong>ID:</strong> {customer.customer_id}</p>
                    <p><strong>Email:</strong> {customer.email}</p>
                    <p><strong>Phone:</strong> {customer.phone || 'N/A'}</p>
                    <p><strong>Company:</strong> {customer.company_name}</p>
                    {customer.city && customer.state && (
                      <p><strong>Location:</strong> {customer.city}, {customer.state}</p>
                    )}
                  </div>
                  <div className="customer-footer">
                    <button
                      className="btn btn-sm btn-secondary"
                      onClick={() => handleManageUsers(customer)}
                      style={{ width: '100%', marginTop: '10px' }}
                    >
                      👤 Manage Users
                    </button>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="no-data">
              <p>No customers found</p>
              <button className="btn btn-primary" onClick={handleCreate}>
                ➕ Add First Customer
              </button>
            </div>
          )}
        </div>
      </div>

      {showModal && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '800px', maxHeight: '90vh', overflowY: 'auto' }}>
            <div className="modal-header">
              <h2>{editingCustomer ? '✏️ Edit Customer' : '➕ Add Customer'}</h2>
              <button className="btn-close" onClick={() => setShowModal(false)}>✕</button>
            </div>
            <form onSubmit={handleSubmit}>
              <div className="modal-body">
                {/* Company Information */}
                <div style={{ marginBottom: '30px' }}>
                  <h3 style={{ marginTop: 0, marginBottom: '20px', color: '#3498db', borderBottom: '2px solid #3498db', paddingBottom: '10px' }}>
                    Company Information
                  </h3>

                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '15px' }}>
                    <div className="form-group">
                      <label>Company Name <span className="required">*</span></label>
                      <input type="text" name="company_name" value={formData.company_name} onChange={handleInputChange} required placeholder="Enter company name" />
                    </div>

                    <div className="form-group">
                      <label>Customer ID <span className="required">*</span></label>
                      <input type="text" name="customer_id" value={formData.customer_id} onChange={handleInputChange} required disabled={!!editingCustomer} placeholder="Unique customer identifier" />
                    </div>

                    <div className="form-group">
                      <label>Name <span className="required">*</span></label>
                      <input type="text" name="name" value={formData.name} onChange={handleInputChange} required placeholder="Primary contact name" />
                    </div>

                    <div className="form-group">
                      <label>Email <span className="required">*</span></label>
                      <input type="email" name="email" value={formData.email} onChange={handleInputChange} required placeholder="contact@company.com" />
                    </div>

                    <div className="form-group">
                      <label>Phone</label>
                      <input type="tel" name="phone" value={formData.phone} onChange={handleInputChange} placeholder="+1-555-0123" />
                    </div>
                  </div>

                  {/* Address Fields */}
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: '15px', marginTop: '15px' }}>
                    <div className="form-group">
                      <label>Address</label>
                      <input type="text" name="address" value={formData.address} onChange={handleInputChange} placeholder="Street address" />
                    </div>
                  </div>

                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr', gap: '15px' }}>
                    <div className="form-group">
                      <label>City</label>
                      <input type="text" name="city" value={formData.city} onChange={handleInputChange} placeholder="City" />
                    </div>

                    <div className="form-group">
                      <label>State/Province</label>
                      <input type="text" name="state" value={formData.state} onChange={handleInputChange} placeholder="State" />
                    </div>

                    <div className="form-group">
                      <label>ZIP/Postal Code</label>
                      <input type="text" name="zip" value={formData.zip} onChange={handleInputChange} placeholder="ZIP code" />
                    </div>

                    <div className="form-group">
                      <label>Country</label>
                      <input type="text" name="country" value={formData.country} onChange={handleInputChange} placeholder="Country" />
                    </div>
                  </div>
                </div>

                {/* Admin User Section (only for new customers) */}
                {!editingCustomer && (
                  <div style={{ marginTop: '30px' }}>
                    <h3 style={{ marginTop: 0, marginBottom: '20px', color: '#3498db', borderBottom: '2px solid #3498db', paddingBottom: '10px' }}>
                      Admin User (Required for New Customers)
                    </h3>

                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '15px' }}>
                      <div className="form-group">
                        <label>Admin Name</label>
                        <input type="text" name="admin_name" value={formData.admin_name} onChange={handleInputChange} placeholder="Admin user name (optional)" />
                        <small className="text-secondary">Defaults to "Admin" if not provided</small>
                      </div>

                      <div className="form-group">
                        <label>Admin Email <span className="required">*</span></label>
                        <input type="email" name="admin_email" value={formData.admin_email} onChange={handleInputChange} required={!editingCustomer} placeholder="admin@company.com" />
                        <small className="text-secondary">This will be the login email</small>
                      </div>

                      <div className="form-group" style={{ gridColumn: 'span 2' }}>
                        <label>Admin Password <span className="required">*</span></label>
                        <input type="password" name="admin_password" value={formData.admin_password} onChange={handleInputChange} required={!editingCustomer} minLength="8" placeholder="Minimum 8 characters" />
                        <small className="text-secondary">Min 8 characters. Use a strong password.</small>
                      </div>
                    </div>
                  </div>
                )}
              </div>

              <div className="modal-footer">
                <button type="button" className="btn btn-secondary" onClick={() => setShowModal(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary" disabled={loading}>
                  {loading ? 'Saving...' : (editingCustomer ? '💾 Update Customer' : '➕ Create Customer')}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default CustomerManagement;
