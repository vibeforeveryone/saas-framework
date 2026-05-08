/*
 * Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
 * Author: Christopher Niven
 */
import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import './ApiConfigSetup.css';

const AWS_REGIONS = [
  { value: 'us-east-1', label: 'US East (N. Virginia)' },
  { value: 'us-east-2', label: 'US East (Ohio)' },
  { value: 'us-west-1', label: 'US West (N. California)' },
  { value: 'us-west-2', label: 'US West (Oregon)' },
  { value: 'ca-central-1', label: 'Canada (Central)' },
  { value: 'eu-west-1', label: 'EU (Ireland)' },
  { value: 'eu-west-2', label: 'EU (London)' },
  { value: 'eu-west-3', label: 'EU (Paris)' },
  { value: 'eu-central-1', label: 'EU (Frankfurt)' },
  { value: 'eu-north-1', label: 'EU (Stockholm)' },
  { value: 'ap-south-1', label: 'Asia Pacific (Mumbai)' },
  { value: 'ap-northeast-1', label: 'Asia Pacific (Tokyo)' },
  { value: 'ap-northeast-2', label: 'Asia Pacific (Seoul)' },
  { value: 'ap-southeast-1', label: 'Asia Pacific (Singapore)' },
  { value: 'ap-southeast-2', label: 'Asia Pacific (Sydney)' },
  { value: 'sa-east-1', label: 'South America (São Paulo)' }
];

const ApiConfigSetup = () => {
  const navigate = useNavigate();
  const [formData, setFormData] = useState({
    apiPath: '',
    awsRegion: 'us-east-2',
    stageName: 'v1'
  });
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState(null);
  const [error, setError] = useState('');
  const [isEditMode, setIsEditMode] = useState(false);

  useEffect(() => {
    // Check if config already exists (edit mode)
    const existingConfig = localStorage.getItem('apiConfig');
    if (existingConfig) {
      try {
        const config = JSON.parse(existingConfig);
        setFormData({
          apiPath: config.apiPath || '',
          awsRegion: config.awsRegion || 'us-east-2',
          stageName: config.stageName || 'v1'
        });
        setIsEditMode(true);
      } catch (err) {
        console.error('Error loading existing config:', err);
      }
    }
  }, []);

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
    setError('');
    setTestResult(null);
  };

  const buildApiUrl = () => {
    const { apiPath, awsRegion, stageName } = formData;
    if (!apiPath || !awsRegion || !stageName) return '';
    return `https://${apiPath}.execute-api.${awsRegion}.amazonaws.com/${stageName}`;
  };

  const validateForm = () => {
    if (!formData.apiPath.trim()) {
      setError('API Path is required');
      return false;
    }
    if (formData.apiPath.length < 8) {
      setError('API Path should be at least 8 characters');
      return false;
    }
    if (!formData.awsRegion) {
      setError('AWS Region is required');
      return false;
    }
    if (!formData.stageName.trim()) {
      setError('Stage Name is required');
      return false;
    }
    return true;
  };

  const testConnection = async () => {
    if (!validateForm()) return;

    setTesting(true);
    setTestResult(null);
    setError('');

    const testUrl = buildApiUrl();

    try {
      // Try to call a public endpoint (adjust based on your API)
      const response = await axios.get(`${testUrl}/public/applications`, {
        timeout: 5000,
        validateStatus: (status) => status < 500 // Accept any status < 500 as "connection works"
      });

      setTestResult({
        success: true,
        message: 'Connection successful! API is reachable.',
        status: response.status
      });
    } catch (err) {
      if (err.code === 'ECONNABORTED') {
        setTestResult({
          success: false,
          message: 'Connection timeout. Please check your settings.',
          error: 'Timeout'
        });
      } else if (err.response) {
        // API responded with error, but connection works
        setTestResult({
          success: true,
          message: `Connection successful! API responded with status ${err.response.status}.`,
          status: err.response.status,
          note: 'API is reachable (endpoint may require authentication)'
        });
      } else {
        setTestResult({
          success: false,
          message: 'Connection failed. Please verify your settings.',
          error: err.message
        });
      }
    } finally {
      setTesting(false);
    }
  };

  const handleSave = () => {
    if (!validateForm()) return;

    const config = {
      apiPath: formData.apiPath.trim(),
      awsRegion: formData.awsRegion,
      stageName: formData.stageName.trim(),
      configuredAt: isEditMode 
        ? JSON.parse(localStorage.getItem('apiConfig')).configuredAt 
        : new Date().toISOString(),
      lastModified: new Date().toISOString()
    };

    try {
      localStorage.setItem('apiConfig', JSON.stringify(config));
      
      // Trigger a page reload to reinitialize the API config
      window.location.href = '/dashboard';
    } catch (err) {
      setError('Failed to save configuration. Please try again.');
      console.error('Save error:', err);
    }
  };

  const handleCancel = () => {
    if (isEditMode) {
      navigate('/dashboard');
    } else {
      setError('Configuration is required to use the application');
    }
  };

  const previewUrl = buildApiUrl();

  return (
    <div className="api-config-container">
      <div className="api-config-card">
        <div className="config-header">
          <h1>🔧 API Configuration Setup</h1>
          <p className="config-subtitle">
            {isEditMode 
              ? 'Update your AWS API Gateway settings'
              : 'Configure your AWS API Gateway settings to get started'
            }
          </p>
        </div>

        {error && (
          <div className="alert alert-error">
            ⚠️ {error}
          </div>
        )}

        {testResult && (
          <div className={`alert ${testResult.success ? 'alert-success' : 'alert-error'}`}>
            {testResult.success ? '✅' : '❌'} {testResult.message}
            {testResult.note && (
              <div style={{ fontSize: '0.9em', marginTop: '5px', opacity: 0.8 }}>
                {testResult.note}
              </div>
            )}
          </div>
        )}

        <div className="config-form">
          <div className="form-group">
            <label htmlFor="apiPath">
              API Path <span className="required">*</span>
            </label>
            <input
              type="text"
              id="apiPath"
              name="apiPath"
              className="form-control"
              value={formData.apiPath}
              onChange={handleInputChange}
              placeholder="e.g., zf9i6u7t7a"
              maxLength="50"
            />
            <small className="form-text">
              The 8-10 character code from your API Gateway (found in AWS Console)
            </small>
          </div>

          <div className="form-group">
            <label htmlFor="awsRegion">
              AWS Region <span className="required">*</span>
            </label>
            <select
              id="awsRegion"
              name="awsRegion"
              className="form-control"
              value={formData.awsRegion}
              onChange={handleInputChange}
            >
              {AWS_REGIONS.map(region => (
                <option key={region.value} value={region.value}>
                  {region.label}
                </option>
              ))}
            </select>
            <small className="form-text">
              Select the AWS region where your API Gateway is deployed
            </small>
          </div>

          <div className="form-group">
            <label htmlFor="stageName">
              Stage Name <span className="required">*</span>
            </label>
            <input
              type="text"
              id="stageName"
              name="stageName"
              className="form-control"
              value={formData.stageName}
              onChange={handleInputChange}
              placeholder="e.g., v1, prod, dev"
              maxLength="50"
            />
            <small className="form-text">
              The deployment stage name (e.g., v1, prod, dev) from API Gateway
            </small>
          </div>

          {previewUrl && (
            <div className="preview-section">
              <label>Preview URL:</label>
              <div className="preview-url">
                {previewUrl}
              </div>
            </div>
          )}

          <div className="button-group">
            <button 
              type="button"
              className="btn btn-secondary"
              onClick={handleCancel}
              disabled={testing}
            >
              Cancel
            </button>
            <button 
              type="button"
              className="btn btn-info"
              onClick={testConnection}
              disabled={testing || !previewUrl}
            >
              {testing ? '🔄 Testing...' : '🔌 Test Connection'}
            </button>
            <button 
              type="button"
              className="btn btn-success"
              onClick={handleSave}
              disabled={testing || !previewUrl}
            >
              {isEditMode ? '💾 Update Configuration' : '✅ Save Configuration'}
            </button>
          </div>
        </div>

        {!isEditMode && (
          <div className="help-section">
            <h3>📚 Where to find these values:</h3>
            <ul>
              <li>
                <strong>API Path:</strong> AWS Console → API Gateway → Your API → 
                Look for the invoke URL (the random characters before "execute-api")
              </li>
              <li>
                <strong>AWS Region:</strong> Check the region dropdown in AWS Console 
                (e.g., us-east-2 for Ohio)
              </li>
              <li>
                <strong>Stage Name:</strong> AWS Console → API Gateway → Your API → 
                Stages tab (e.g., v1, prod, dev)
              </li>
            </ul>
          </div>
        )}
      </div>
    </div>
  );
};

export default ApiConfigSetup;
