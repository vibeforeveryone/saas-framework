/*
 * Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
 * Author: Christopher Niven
 */
import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

import { apiReady } from '../api/config';  // NEW: apiReady is a Promise that resolves to the configured axios instance
import './PublicSignup.css';

const PublicSignup = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  
  // Form state
  const [formData, setFormData] = useState({
    firstName: '',
    lastName: '',
    email: '',
    password: '',
    confirmPassword: '',
    customerName: '',
    addressLine1: '',
    addressLine2: '',
    city: '',
    state: '',
    postalCode: '',
    country: 'US',
    customerPhone: '',
    cardNumber: '',
    cardholderName: '',
    expiryMonth: '',
    expiryYear: '',
    cvv: '',
    billingAddressSame: true,
    billingAddress: {
      addressLine1: '',
      city: '',
      state: '',
      postalCode: '',
      country: 'US'
    }
  });
  
  // Completion tracking
  const [completedSteps, setCompletedSteps] = useState({
    userInfo: false,
    customerInfo: false,
    payment: false,
    emailVerification: false,
    subscriptions: false
  });
  
  // Payment verification state
  const [paymentVerified, setPaymentVerified] = useState(false);
  const [paymentToken, setPaymentToken] = useState('');
  const [paymentDetails, setPaymentDetails] = useState(null);
  
  // Email availability check
  const [emailAvailable, setEmailAvailable] = useState(null); // null=unchecked, true=available, false=taken
  const [emailChecking, setEmailChecking] = useState(false);
  
  // Email verification state (Section 4)
  const [emailVerification, setEmailVerification] = useState({
    codeSent: false,
    code: '',
    verified: false,
    codeId: '',
    expiresAt: null,
    timeRemaining: 0,
    attempts: 0,
    sending: false
  });
  
  // Subscriptions
   const [selectedLicenseKey, setSelectedLicenseKey] = useState('');
   const [availableLicenses, setAvailableLicenses]   = useState([]);
  
  // Timer for verification code
  useEffect(() => {
    if (emailVerification.codeSent && emailVerification.expiresAt) {
      const interval = setInterval(() => {
        const now = new Date();
        const expires = new Date(emailVerification.expiresAt);
        const remaining = Math.floor((expires - now) / 1000);
        
        if (remaining <= 0) {
          setEmailVerification(prev => ({ ...prev, codeSent: false, timeRemaining: 0 }));
          clearInterval(interval);
        } else {
          setEmailVerification(prev => ({ ...prev, timeRemaining: remaining }));
        }
      }, 1000);
      
      return () => clearInterval(interval);
    }
  }, [emailVerification.codeSent, emailVerification.expiresAt]);
  
  useEffect(() => {
    fetchActiveLicenses();
  }, []);

  const fetchActiveLicenses = async () => {
    try {
      const api = await apiReady;
      const response = await api.getWithLog(
        '/licenses/active',
        'PublicSignup.js - Fetch Active Licenses'
      );
      if (response.data.success) {
        setAvailableLicenses(response.data.data.licenses || []);
      }
    } catch (err) {
      console.error('Error fetching licenses:', err);
    }
  };
  
  const handleInputChange = (e) => {
    const { name, value, type, checked } = e.target;
    
    if (name.startsWith('billing.')) {
      const field = name.split('.')[1];
      setFormData(prev => ({
        ...prev,
        billingAddress: {
          ...prev.billingAddress,
          [field]: value
        }
      }));
    } else {
      setFormData(prev => ({
        ...prev,
        [name]: type === 'checkbox' ? checked : value
      }));
      
      // Reset email availability when email changes
      if (name === 'email') {
        setEmailAvailable(null);
      }
    }
  };
  
  const handleCheckEmail = async () => {
    const email = formData.email.trim().toLowerCase();
    if (!email) return;
    
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email)) return;
    
    setEmailChecking(true);
    try {
      const api = await apiReady;
      const response = await api.postWithLog('/public/check-email', {
        email
      }, 'PublicSignup.js - Check Email Availability');
      
      if (response.data.success) {
        const available = response.data.data.available;
        setEmailAvailable(available);
        if (!available) {
          setError('This email address is already registered. Please use a different email.');
        } else {
          // Clear error only if it was the duplicate email error
          setError(prev => prev === 'This email address is already registered. Please use a different email.' ? '' : prev);
        }
      }
    } catch (err) {
      console.error('Error checking email availability:', err);
      // Don't block the user on a failed check; backend will catch it at signup
      setEmailAvailable(null);
    } finally {
      setEmailChecking(false);
    }
  };
  
  const validateUserInfo = () => {
    if (!formData.firstName || !formData.lastName) {
      setError('First and last name are required');
      return false;
    }
    if (!formData.email) {
      setError('Email is required');
      return false;
    }
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(formData.email)) {
      setError('Please enter a valid email address');
      return false;
    }
    if (emailAvailable === false) {
      setError('This email address is already registered. Please use a different email.');
      return false;
    }
    if (!formData.password || formData.password.length < 8) {
      setError('Password must be at least 8 characters');
      return false;
    }
    if (formData.password !== formData.confirmPassword) {
      setError('Passwords do not match');
      return false;
    }
    
    const hasUpper = /[A-Z]/.test(formData.password);
    const hasLower = /[a-z]/.test(formData.password);
    const hasNumber = /[0-9]/.test(formData.password);
    
    if (!hasUpper || !hasLower || !hasNumber) {
      setError('Password must contain uppercase, lowercase, and numbers');
      return false;
    }
    
    return true;
  };
  
  const validatecustomerInfo = () => {
    if (!formData.customerName || !formData.addressLine1 || !formData.city || !formData.state || !formData.postalCode) {
      setError('Complete customer information is required');
      return false;
    }
    if (!formData.customerPhone) {
      setError('Customer phone is required');
      return false;
    }
    return true;
  };
  
  const validatePaymentInfo = () => {
    if (!formData.cardNumber || !formData.cardholderName || !formData.expiryMonth || !formData.expiryYear || !formData.cvv) {
      setError('All payment fields are required');
      return false;
    }
    
    const cardNumber = formData.cardNumber.replace(/\s|-/g, '');
    if (cardNumber.length < 13 || cardNumber.length > 19) {
      setError('Invalid card number');
      return false;
    }
    
    if (!formData.cvv.match(/^\d{3,4}$/)) {
      setError('Invalid CVV');
      return false;
    }
    
    return true;
  };
  
  const handleVerifyPayment = async () => {
    setError('');
    
    // Ensure email has been checked for duplicates before proceeding
    if (emailAvailable === false) {
      setError('This email address is already registered. Please use a different email before continuing.');
      return;
    }
    if (emailAvailable === null && formData.email) {
      // Email hasn't been checked yet — run the check now
      setEmailChecking(true);
      try {
        const api = await apiReady;
        const checkResp = await api.postWithLog('/public/check-email', {
          email: formData.email.trim().toLowerCase()
        }, 'PublicSignup.js - Check Email (before payment)');
        
        if (checkResp.data.success && !checkResp.data.data.available) {
          setEmailAvailable(false);
          setEmailChecking(false);
          setError('This email address is already registered. Please use a different email before continuing.');
          return;
        }
        setEmailAvailable(true);
      } catch (err) {
        console.error('Error checking email:', err);
        // Allow to proceed; backend will catch duplicates at signup time
      } finally {
        setEmailChecking(false);
      }
    }
    
    if (!validatePaymentInfo()) return;
    
    setLoading(true);
    try {
      const billingAddr = formData.billingAddressSame 
        ? {
            address_line1: formData.addressLine1,
            city: formData.city,
            state: formData.state,
            postal_code: formData.postalCode,
            country: formData.country
          }
        : {
            address_line1: formData.billingAddress.addressLine1,
            city: formData.billingAddress.city,
            state: formData.billingAddress.state,
            postal_code: formData.billingAddress.postalCode,
            country: formData.billingAddress.country
          };
      
      const api = await apiReady;
      const response = await api.postWithLog('/public/verify-payment', {
        card_number: formData.cardNumber.replace(/\s|-/g, ''),
        expiry_month: formData.expiryMonth,
        expiry_year: formData.expiryYear,
        cvv: formData.cvv,
        cardholder_name: formData.cardholderName,
        billing_address: billingAddr
      }, 'PublicSignup.js - Verify Payment');
      
      if (response.data.success) {
        setPaymentVerified(true);
        setPaymentToken(response.data.data.token);
        setPaymentDetails(response.data.data);
        setCompletedSteps(prev => ({ ...prev, payment: true }));
        setSuccess('Payment method verified! Sending verification code...');
        
        // Automatically send verification code after successful payment
        try {
          const api2 = await apiReady;
          const codeResponse = await api2.postWithLog('/public/send-verification-code', {
            email: formData.email
          }, 'PublicSignup.js - Send Verification Code (after payment)');
          
          if (codeResponse.data.success) {
            setEmailVerification(prev => ({
              ...prev,
              codeSent: true,
              codeId: codeResponse.data.data.code_id,
              expiresAt: codeResponse.data.data.expires_at,
              sending: false
            }));
            setSuccess('Payment verified & verification code sent! Check your email.');
          }
        } catch (codeErr) {
          // Payment succeeded but code failed - user can resend manually
          setSuccess('Payment verified! Click below to send the verification code.');
          console.error('Failed to auto-send verification code:', codeErr);
        }
      }
    } catch (err) {
      setError(err.response?.data?.error || 'Payment verification failed');
    } finally {
      setLoading(false);
    }
  };
  
  // Section 4: Send verification code
  const handleSendVerificationCode = async () => {
    setError('');
    
    if (!formData.email) {
      setError('Email is required');
      return;
    }
    
    setEmailVerification(prev => ({ ...prev, sending: true }));
    try {
      const api = await apiReady;
      const response = await api.postWithLog('/public/send-verification-code', {
        email: formData.email
      }, 'PublicSignup.js - Send Verification Code');
      
      if (response.data.success) {
        setEmailVerification(prev => ({
          ...prev,
          codeSent: true,
          codeId: response.data.data.code_id,
          expiresAt: response.data.data.expires_at,
          sending: false
        }));
        setSuccess('Verification code sent! Check your email.');
      }
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to send verification code');
      setEmailVerification(prev => ({ ...prev, sending: false }));
    }
  };
  
  const handleVerifyEmailCode = async () => {
    setError('');
    
    if (!emailVerification.code || emailVerification.code.length !== 6) {
      setError('Please enter the 6-digit code');
      return;
    }
    
    setLoading(true);
    try {
      const api = await apiReady;
      const response = await api.postWithLog('/public/verify-email-code', {
        email: formData.email,
        code: emailVerification.code,
        code_id: emailVerification.codeId
      }, 'PublicSignup.js - Verify Email Code');
      
      if (response.data.success && response.data.data.verified) {
        setEmailVerification(prev => ({ ...prev, verified: true }));
        setCompletedSteps(prev => ({ ...prev, emailVerification: true }));
        setSuccess('Email verified successfully!');
      }
    } catch (err) {
      setError(err.response?.data?.error || 'Invalid verification code');
      setEmailVerification(prev => ({ ...prev, attempts: prev.attempts + 1 }));
    } finally {
      setLoading(false);
    }
  };
  
  
  
  
  const handleCompleteSignup = async () => {
    setError('');
    setSuccess('');
    
    if (!validateUserInfo() || !validatecustomerInfo()) return;
    
    if (!paymentVerified) {
      setError('Please verify your payment method');
      return;
    }
    
    if (!emailVerification.verified) {
      setError('Please verify your email address');
      return;
    }
    
    if (!selectedLicenseKey) {
        setError('Please select a plan before completing registration');
        return;
    }
    
    setLoading(true);
    try {
      const api = await apiReady;
      const response = await api.postWithLog('/public/complete-signup', {
        admin_user: {
          first_name: formData.firstName,
          last_name: formData.lastName,
          email: formData.email,
          password: formData.password
        },
        customer: {
          customer_name: formData.customerName,
          address_line1: formData.addressLine1,
          address_line2: formData.addressLine2,
          city: formData.city,
          state: formData.state,
          postal_code: formData.postalCode,
          country: formData.country,
          phone: formData.customerPhone
        },
        payment_token: paymentToken,
        payment_details: paymentDetails,

        license_key: selectedLicenseKey,
      }, 'PublicSignup.js - Complete Signup');
      
      if (response.data.success) {
        setSuccess('Registration complete! Redirecting to login...');
        setTimeout(() => {
          navigate('/login');
        }, 3000);
      }
    } catch (err) {
      setError(err.response?.data?.error || 'Signup failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };
  
  const formatCardNumber = (value) => {
    const v = value.replace(/\s+/g, '').replace(/[^0-9]/gi, '');
    const matches = v.match(/\d{4,16}/g);
    const match = (matches && matches[0]) || '';
    const parts = [];
    
    for (let i = 0, len = match.length; i < len; i += 4) {
      parts.push(match.substring(i, i + 4));
    }
    
    return parts.length ? parts.join(' ') : value;
  };
  
  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };
  
  return (
    <div className="public-signup">
      <div className="signup-container">
        <div className="signup-header">
          <h1>🚀 Start Your Subscription</h1>
          <p>Join thousands of satisfied customers</p>
        </div>
        
        {error && <div className="alert alert-danger">❌ {error}</div>}
        {success && <div className="alert alert-success">✅ {success}</div>}
        
        {/* Section 1: Customer Information */}
        <div className="signup-section">
          <div className="section-header">
            <h2>{completedSteps.customerInfo ? '✅' : '1️⃣'} Customer Information</h2>
          </div>
          
          <div className="form-grid">
            <div className="form-group full-width">
              <label>Customer Name <span className="required">*</span></label>
              <input type="text" name="customerName" value={formData.customerName} onChange={handleInputChange} placeholder="Your Company Inc." required />
            </div>
            
            <div className="form-group">
              <label>First Name <span className="required">*</span></label>
              <input type="text" name="firstName" value={formData.firstName} onChange={handleInputChange} placeholder="John" required />
            </div>
            <div className="form-group">
              <label>Last Name <span className="required">*</span></label>
              <input type="text" name="lastName" value={formData.lastName} onChange={handleInputChange} placeholder="Doe" required />
            </div>
            
            <div className="form-group full-width">
              <label>Address Line 1 <span className="required">*</span></label>
              <input type="text" name="addressLine1" value={formData.addressLine1} onChange={handleInputChange} placeholder="123 Main Street" required />
            </div>
            
            <div className="form-group full-width">
              <label>Address Line 2</label>
              <input type="text" name="addressLine2" value={formData.addressLine2} onChange={handleInputChange} placeholder="Suite 100 (optional)" />
            </div>
            
            <div className="form-group third-width">
              <label>City <span className="required">*</span></label>
              <input type="text" name="city" value={formData.city} onChange={handleInputChange} placeholder="Anytown" required />
            </div>
            
            <div className="form-group third-width">
              <label>State/Province <span className="required">*</span></label>
              <input type="text" name="state" value={formData.state} onChange={handleInputChange} placeholder="CA" required />
            </div>
            
            <div className="form-group third-width">
              <label>Postal Code <span className="required">*</span></label>
              <input type="text" name="postalCode" value={formData.postalCode} onChange={handleInputChange} placeholder="12345" required />
            </div>
            
            <div className="form-group">
              <label>Country <span className="required">*</span></label>
              <select name="country" value={formData.country} onChange={handleInputChange} required>
                <option value="US">United States</option>
                <option value="CA">Canada</option>
                <option value="GB">United Kingdom</option>
                <option value="AU">Australia</option>
                <option value="other">Other</option>
              </select>
            </div>
            
            <div className="form-group">
              <label>Customer Phone <span className="required">*</span></label>
              <input type="tel" name="customerPhone" value={formData.customerPhone} onChange={handleInputChange} placeholder="+1-555-0199" required />
            </div>
          </div>
        </div>
        
        {/* Section 2: Admin User Information */}
        <div className="signup-section">
          <div className="section-header">
            <h2>{completedSteps.userInfo ? '✅' : '2️⃣'} Administrator Information</h2>
            <p>This will be your login credential</p>
          </div>
          
          <div className="form-grid">
            <div className="form-group">
              <label>Email (Username) <span className="required">*</span></label>
              <input type="email" name="email" value={formData.email} onChange={handleInputChange} onBlur={handleCheckEmail} placeholder="john@company.com" required style={emailAvailable === false ? { borderColor: '#e74c3c', backgroundColor: '#fdf2f2' } : emailAvailable === true ? { borderColor: '#27ae60' } : {}} />
              {emailChecking && <small style={{ color: '#667eea' }}>Checking availability...</small>}
              {!emailChecking && emailAvailable === true && <small style={{ color: '#27ae60' }}>✅ Email is available</small>}
              {!emailChecking && emailAvailable === false && <small style={{ color: '#e74c3c' }}>❌ This email is already registered. Please use a different email.</small>}
              {!emailChecking && emailAvailable === null && <small>This will be your username</small>}
            </div>
            <div className="form-group">
              <label>Password <span className="required">*</span></label>
              <input type="password" name="password" value={formData.password} onChange={handleInputChange} placeholder="Min 8 characters" required />
              <small>Must include uppercase, lowercase, and number</small>
            </div>
            <div className="form-group">
              <label>Confirm Password <span className="required">*</span></label>
              <input type="password" name="confirmPassword" value={formData.confirmPassword} onChange={handleInputChange} placeholder="Re-enter password" required />
            </div>
          </div>
        </div>


        {/* Section 3: Select Your Plan */}
        <div className="signup-section">
          <div className="section-header">
            <h2>3️⃣ Select Your Plan</h2>
            <p>Choose the plan that fits your needs. You can change it anytime after signup.</p>
          </div>

          {availableLicenses.length === 0 ? (
            <p>Loading available plans...</p>
          ) : (
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))',
              gap: '16px',
              marginBottom: '8px'
            }}>
              {availableLicenses.map(license => {
                const isSelected = selectedLicenseKey === license.license_key;
                return (
                  <div
                    key={license.license_key}
                    onClick={() => setSelectedLicenseKey(license.license_key)}
                    style={{
                      border: `2px solid ${isSelected ? '#007bff' : '#dee2e6'}`,
                      borderRadius: '8px',
                      padding: '16px',
                      cursor: 'pointer',
                      backgroundColor: isSelected ? '#f0f7ff' : '#fff',
                      transition: 'all 0.15s',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                      <strong>{license.license_type_desc}</strong>
                      <div style={{ textAlign: 'right', marginLeft: '8px' }}>
                        {license.license_type === 'transactionsPerMonth' ? (
                          <>
                            <div style={{ fontWeight: 'bold' }}>
                              ${parseFloat(license.base_cost_per_month).toFixed(2)}/mo
                            </div>
                            <div style={{ fontSize: '0.75rem', color: '#666' }}>
                              + ${parseFloat(license.cost_per_transaction).toFixed(3)}/txn
                            </div>
                          </>
                        ) : (
                          <div style={{ fontWeight: 'bold' }}>
                            ${parseFloat(license.cost_per_month).toFixed(2)}/mo
                          </div>
                        )}
                      </div>
                    </div>
                    <div style={{ marginTop: '8px', fontSize: '0.85rem', color: '#555' }}>
                      {license.license_type === 'transactionsPerMonth'
                        ? `Up to ${Number(license.max_transactions).toLocaleString()} transactions/month`
                        : `Up to ${Number(license.max_seats).toLocaleString()} users`
                      }
                    </div>
                    {isSelected && (
                      <div style={{ marginTop: '8px' }}>
                        <span className="badge badge-info">✓ Selected</span>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}

          {!selectedLicenseKey && availableLicenses.length > 0 && (
            <p className="text-secondary" style={{ fontSize: '0.875rem', marginTop: '8px' }}>
              👆 Please select a plan to continue
            </p>
          )}
        </div>
        
        {/* Section 3: Payment Information */}
        {selectedLicenseKey && (
          <div className="signup-section">
            <div className="section-header">
              <h2>{completedSteps.payment ? '✅' : '4️⃣'} Payment Information</h2>
              <p>Your card will be verified but not charged now</p>
            </div>
            
            <div className="form-grid">
              <div className="form-group">
                <label>Card Number <span className="required">*</span></label>
                <input
                  type="text"
                  name="cardNumber"
                  value={formData.cardNumber}
                  onChange={(e) => {
                    const formatted = formatCardNumber(e.target.value);
                    handleInputChange({ target: { name: 'cardNumber', value: formatted } });
                  }}
                  placeholder="4111 1111 1111 1111"
                  maxLength="19"
                  required
                  disabled={paymentVerified}
                />
              </div>
              
              <div className="form-group">
                <label>Cardholder Name <span className="required">*</span></label>
                <input type="text" name="cardholderName" value={formData.cardholderName} onChange={handleInputChange} placeholder="JOHN DOE" required disabled={paymentVerified} />
              </div>
              
              <div className="form-group third-width">
                <label>Expiry Month <span className="required">*</span></label>
                <select name="expiryMonth" value={formData.expiryMonth} onChange={handleInputChange} required disabled={paymentVerified}>
                  <option value="">MM</option>
                  {Array.from({ length: 12 }, (_, i) => i + 1).map(m => (
                    <option key={m} value={m.toString().padStart(2, '0')}>
                      {m.toString().padStart(2, '0')}
                    </option>
                  ))}
                </select>
              </div>
              
              <div className="form-group third-width">
                <label>Expiry Year <span className="required">*</span></label>
                <select name="expiryYear" value={formData.expiryYear} onChange={handleInputChange} required disabled={paymentVerified}>
                  <option value="">YY</option>
                  {Array.from({ length: 15 }, (_, i) => (new Date().getFullYear() % 100) + i).map(y => (
                    <option key={y} value={y.toString().padStart(2, '0')}>
                      {y}
                    </option>
                  ))}
                </select>
              </div>
              
              <div className="form-group third-width">
                <label>CVV <span className="required">*</span></label>
                <input type="text" name="cvv" value={formData.cvv} onChange={handleInputChange} placeholder="123" maxLength="4" required disabled={paymentVerified} />
              </div>
              
              <div className="form-group full-width">
                <label>
                  <input type="checkbox" name="billingAddressSame" checked={formData.billingAddressSame} onChange={handleInputChange} disabled={paymentVerified} />
                  {' '}Billing address same as customer address
                </label>
              </div>
              
              {!formData.billingAddressSame && (
                <>
                  <div className="form-group full-width">
                    <label>Billing Address</label>
                    <input type="text" name="billing.addressLine1" value={formData.billingAddress.addressLine1} onChange={handleInputChange} placeholder="Billing street address" disabled={paymentVerified} />
                  </div>
                  
                  <div className="form-group third-width">
                    <label>City</label>
                    <input type="text" name="billing.city" value={formData.billingAddress.city} onChange={handleInputChange} disabled={paymentVerified} />
                  </div>
                  
                  <div className="form-group third-width">
                    <label>State</label>
                    <input type="text" name="billing.state" value={formData.billingAddress.state} onChange={handleInputChange} disabled={paymentVerified} />
                  </div>
                  
                  <div className="form-group third-width">
                    <label>Postal Code</label>
                    <input type="text" name="billing.postalCode" value={formData.billingAddress.postalCode} onChange={handleInputChange} disabled={paymentVerified} />
                  </div>
                </>
              )}
              
              <div className="form-group full-width">
                {paymentVerified ? (
                  <div className="verification-status success">
                    ✅ Payment method verified - Card ending in {paymentDetails?.last4}
                  </div>
                ) : (
                  <button type="button" className="btn btn-primary" onClick={handleVerifyPayment} disabled={loading}>
                    {loading ? 'Verifying...' : '🔒 Verify Payment Method'}
                  </button>
                )}
              </div>
            </div>
          </div>
        )}
        
        {/* Section 4: Email Verification */}
        {paymentVerified && (
          <div className="signup-section">
            <div className="section-header">
              <h2>{completedSteps.emailVerification ? '✅' : '5️⃣'} Email Verification</h2>
              <p>Verify your email with a one-time code</p>
            </div>
            
            <div className="verification-box">
              {!emailVerification.verified ? (
                <>
                  {!emailVerification.codeSent ? (
                    <button className="btn btn-primary btn-lg" onClick={handleSendVerificationCode} disabled={emailVerification.sending || !formData.email}>
                      {emailVerification.sending ? 'Sending...' : '📧 Send Verification Code'}
                    </button>
                  ) : (
                    <div className="code-input-section">
                      <p>Enter the 6-digit code sent to <strong>{formData.email}</strong></p>
                      
                      <div className="code-input-container">
                        <input
                          type="text"
                          value={emailVerification.code}
                          onChange={(e) => {
                            const value = e.target.value.replace(/\D/g, '').slice(0, 6);
                            setEmailVerification(prev => ({ ...prev, code: value }));
                          }}
                          placeholder="000000"
                          maxLength="6"
                          className="code-input"
                        />
                      </div>
                      
                      <button className="btn btn-success" onClick={handleVerifyEmailCode} disabled={loading || emailVerification.code.length !== 6}>
                        {loading ? 'Verifying...' : 'Verify Code'}
                      </button>
                      
                      {emailVerification.timeRemaining > 0 && (
                        <p className="timer">
                          Code expires in: <strong>{formatTime(emailVerification.timeRemaining)}</strong>
                        </p>
                      )}
                      
                      {emailVerification.timeRemaining <= 0 || emailVerification.attempts >= 3 ? (
                        <button className="btn btn-link" onClick={handleSendVerificationCode} disabled={emailVerification.sending}>
                          Resend Code
                        </button>
                      ) : null}
                    </div>
                  )}
                </>
              ) : (
                <div className="verification-status success">
                  ✅ Email verified successfully!
                </div>
              )}
            </div>
          </div>
        )}
        
  
        
        {/* Section 6: Review & Complete */}
        {emailVerification.verified && (
          <div className="signup-section">
            <div className="section-header">
              <h2>6️⃣ Review & Complete</h2>
            </div>
            
            <div className="review-box">
              <h3>Registration Summary</h3>
              
              <div className="review-item">
                <strong>Administrator:</strong> {formData.firstName} {formData.lastName} ({formData.email})
              </div>
              
              <div className="review-item">
                <strong>Customer:</strong> {formData.customerName}
              </div>
              
              <div className="review-item">
                <strong>Payment:</strong> {paymentVerified ? `✅ Verified - Card ending in ${paymentDetails?.last4}` : '❌ Not verified'}
              </div>
              
              <div className="review-item">
                <strong>Email:</strong> {emailVerification.verified ? '✅ Verified' : '❌ Not verified'}
              </div>
              
              {selectedLicenseKey && (() => {
                const plan = availableLicenses.find(l => l.license_key === selectedLicenseKey);
                return plan ? (
                  <div className="review-item">
                    <strong>Selected Plan:</strong>{' '}
                    {plan.license_type_desc}{' '}
                    {plan.license_type === 'transactionsPerMonth'
                      ? `— $${parseFloat(plan.base_cost_per_month).toFixed(2)}/mo base + $${parseFloat(plan.cost_per_transaction).toFixed(3)}/txn`
                      : `— $${parseFloat(plan.cost_per_month).toFixed(2)}/mo`
                    }
                  </div>
                ) : null;
              })()}
            </div>
            
            <div className="terms-box">
              <p>
                By clicking "Complete Registration", you agree to our Terms of Service and Privacy Policy.
              </p>
            </div>
            
            <button className="btn btn-success btn-lg btn-complete" onClick={handleCompleteSignup} disabled={loading || !paymentVerified || !emailVerification.verified}>
              {loading ? 'Completing Registration...' : '🎉 Complete Registration'}
            </button>
          </div>
        )}
        
      </div>
    </div>
  );
};

export default PublicSignup;
