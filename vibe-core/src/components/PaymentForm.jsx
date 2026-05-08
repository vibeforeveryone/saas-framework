/*
 * Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
 * Author: Christopher Niven
 */
import React, { useState } from 'react';
import { apiReady } from '../api/config';  // NEW: apiReady is a Promise that resolves to the configured axios instance

import './PaymentForm.css';

const PaymentForm = () => {
  const [formData, setFormData] = useState({
    company_name: '',
    customer_id: '',
    customer_email: '',
    customer_name: '',
    amount: '',
    currency: 'USD',
    processor_type: 'merchantone',
    card_number: '',
    card_exp_month: '',
    card_exp_year: '',
    card_cvv: '',
    billing_address: '',
    billing_city: '',
    billing_state: '',
    billing_zip: '',
    billing_country: 'US'
  });

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(null);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
    if (error) setError('');
    if (success) setSuccess(null);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    setSuccess(null);

    try {
      const payload = {
        company_name: formData.company_name,
        customer_id: formData.customer_id,
        amount: parseFloat(formData.amount),
        currency: formData.currency,
        processor_type: formData.processor_type,
        customer_data: {
          email: formData.customer_email,
          name: formData.customer_name
        },
        payment_method: {
          type: 'card',
          card_number: formData.card_number,
          exp_month: formData.card_exp_month,
          exp_year: formData.card_exp_year,
          cvv: formData.card_cvv
        },
        billing_address: {
          address: formData.billing_address,
          city: formData.billing_city,
          state: formData.billing_state,
          zip: formData.billing_zip,
          country: formData.billing_country
        }
      };

      const api = await apiReady;
      const response = await api.postWithLog('/transactions/payment', payload,
          `${import.meta.url.split('/').pop()}`);

      if (response.data.success) {
        setSuccess(response.data.data);
        // Clear sensitive data
        setFormData(prev => ({
          ...prev,
          card_number: '',
          card_cvv: '',
          card_exp_month: '',
          card_exp_year: ''
        }));
      } else {
        setError(response.data.error || 'Payment failed');
      }
    } catch (err) {
      setError(err.response?.data?.error || 'Payment processing failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="content-wrapper">
      <div className="page-header primary">
        <h1>💳 Process Payment</h1>
        <p>Submit a new payment transaction</p>
      </div>

      {success && (
        <div className="card success-card">
          <div className="card-section">
            <h3>✅ Payment Successful!</h3>
            <div className="success-details">
              <p><strong>Transaction ID:</strong> {success.transaction_id}</p>
              <p><strong>Amount:</strong> {success.currency} {success.amount}</p>
              <p><strong>Status:</strong> {success.status}</p>
              <p><strong>Processor:</strong> {success.processor_type}</p>
            </div>
          </div>
        </div>
      )}

      {error && (
        <div className="card error-card">
          <div className="card-section">
            <div className="error-message">⚠️ {error}</div>
          </div>
        </div>
      )}

      <form onSubmit={handleSubmit}>
        <div className="card">
          <div className="card-section">
            <h2>🏢 Company & Customer</h2>
            <div className="form-grid">
              <div className="form-group">
                <label>Company Name <span className="required">*</span></label>
                <input
                  type="text"
                  name="company_name"
                  value={formData.company_name}
                  onChange={handleChange}
                  required
                  disabled={loading}
                />
              </div>

              <div className="form-group">
                <label>Customer ID <span className="required">*</span></label>
                <input
                  type="text"
                  name="customer_id"
                  value={formData.customer_id}
                  onChange={handleChange}
                  required
                  disabled={loading}
                />
              </div>

              <div className="form-group">
                <label>Customer Name <span className="required">*</span></label>
                <input
                  type="text"
                  name="customer_name"
                  value={formData.customer_name}
                  onChange={handleChange}
                  required
                  disabled={loading}
                />
              </div>

              <div className="form-group">
                <label>Customer Email <span className="required">*</span></label>
                <input
                  type="email"
                  name="customer_email"
                  value={formData.customer_email}
                  onChange={handleChange}
                  required
                  disabled={loading}
                />
              </div>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="card-section">
            <h2>💰 Payment Details</h2>
            <div className="form-grid">
              <div className="form-group">
                <label>Amount <span className="required">*</span></label>
                <input
                  type="number"
                  name="amount"
                  value={formData.amount}
                  onChange={handleChange}
                  required
                  disabled={loading}
                  step="0.01"
                  min="0.01"
                  placeholder="99.99"
                />
              </div>

              <div className="form-group">
                <label>Currency</label>
                <select name="currency" value={formData.currency} onChange={handleChange} disabled={loading}>
                  <option value="USD">USD</option>
                  <option value="EUR">EUR</option>
                  <option value="GBP">GBP</option>
                  <option value="CAD">CAD</option>
                </select>
              </div>

              <div className="form-group full-width">
                <label>Payment Processor <span className="required">*</span></label>
                <select name="processor_type" value={formData.processor_type} onChange={handleChange} disabled={loading}>
                  <option value="merchantone">MerchantOne</option>
                  <option value="paysafe">PaySafe</option>
                  <option value="paymentnerds">PaymentNerds</option>
                </select>
              </div>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="card-section">
            <h2>💳 Card Information</h2>
            <div className="form-grid">
              <div className="form-group full-width">
                <label>Card Number <span className="required">*</span></label>
                <input
                  type="text"
                  name="card_number"
                  value={formData.card_number}
                  onChange={handleChange}
                  required
                  disabled={loading}
                  placeholder="4111111111111111"
                  maxLength="16"
                />
              </div>

              <div className="form-group">
                <label>Exp Month <span className="required">*</span></label>
                <input
                  type="text"
                  name="card_exp_month"
                  value={formData.card_exp_month}
                  onChange={handleChange}
                  required
                  disabled={loading}
                  placeholder="12"
                  maxLength="2"
                />
              </div>

              <div className="form-group">
                <label>Exp Year <span className="required">*</span></label>
                <input
                  type="text"
                  name="card_exp_year"
                  value={formData.card_exp_year}
                  onChange={handleChange}
                  required
                  disabled={loading}
                  placeholder="2025"
                  maxLength="4"
                />
              </div>

              <div className="form-group">
                <label>CVV <span className="required">*</span></label>
                <input
                  type="text"
                  name="card_cvv"
                  value={formData.card_cvv}
                  onChange={handleChange}
                  required
                  disabled={loading}
                  placeholder="123"
                  maxLength="4"
                />
              </div>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="card-section">
            <h2>📍 Billing Address</h2>
            <div className="form-grid">
              <div className="form-group full-width">
                <label>Street Address</label>
                <input
                  type="text"
                  name="billing_address"
                  value={formData.billing_address}
                  onChange={handleChange}
                  disabled={loading}
                />
              </div>

              <div className="form-group">
                <label>City</label>
                <input
                  type="text"
                  name="billing_city"
                  value={formData.billing_city}
                  onChange={handleChange}
                  disabled={loading}
                />
              </div>

              <div className="form-group">
                <label>State</label>
                <input
                  type="text"
                  name="billing_state"
                  value={formData.billing_state}
                  onChange={handleChange}
                  disabled={loading}
                />
              </div>

              <div className="form-group">
                <label>ZIP</label>
                <input
                  type="text"
                  name="billing_zip"
                  value={formData.billing_zip}
                  onChange={handleChange}
                  disabled={loading}
                />
              </div>

              <div className="form-group">
                <label>Country</label>
                <select name="billing_country" value={formData.billing_country} onChange={handleChange} disabled={loading}>
                  <option value="US">United States</option>
                  <option value="CA">Canada</option>
                  <option value="GB">United Kingdom</option>
                  <option value="AU">Australia</option>
                </select>
              </div>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="card-section">
            <button type="submit" className="btn btn-primary btn-lg" disabled={loading}>
              {loading ? '🔄 Processing...' : '💳 Process Payment'}
            </button>
          </div>
        </div>
      </form>
    </div>
  );
};

export default PaymentForm;
