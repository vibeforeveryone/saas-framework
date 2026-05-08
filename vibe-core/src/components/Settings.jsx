/*
 * Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
 * Author: Christopher Niven
 */
import React, { useState, useEffect } from 'react';
import { apiReady } from '../api/config';  // NEW: apiReady is a Promise that resolves to the configured axios instance

import './Settings.css';

const Settings = () => {
  const [processors, setProcessors] = useState([]);
  const [loading, setLoading] = useState(false);
  const [editingProcessor, setEditingProcessor] = useState(null);

  useEffect(() => {
    fetchProcessors();
  }, []);

  const fetchProcessors = async () => {
    try {
      setLoading(true);
      const api = await apiReady;
      const response = await api.getWithLog('/processor-configs',
          `${import.meta.url.split('/').pop()}`);

      if (response.data.success) {
        setProcessors(response.data.data.configurations);
      }
    } catch (err) {
      console.error('Error fetching processors:', err);
    } finally {
      setLoading(false);
    }
  };

  const toggleProcessor = async (configId, isActive) => {
    try {
      const api = await apiReady;
      await api.putWithLog(`/processor-configs/${configId}/activate`, {
        is_active: !isActive
      },
      `${import.meta.url.split('/').pop()}`);

      fetchProcessors();
    } catch (err) {
      console.error('Error toggling processor:', err);
    }
  };

  return (
    <div className="content-wrapper">
      <div className="page-header primary">
        <h1>⚙️ Settings</h1>
        <p>Configure payment processors and system settings</p>
      </div>

      <div className="card">
        <div className="card-section">
          <h2>💳 Payment Processors</h2>
          
          {loading ? (
            <div className="loading-container">
              <div className="loading-spinner">🔄 Loading...</div>
            </div>
          ) : (
            <div className="processors-list">
              {processors.map((proc) => (
                <div key={proc.config_id} className="processor-item">
                  <div className="processor-info">
                    <h3>{proc.processor_type.toUpperCase()}</h3>
                    <p>{proc.company_name}</p>
                    <span className={`status-badge status-${proc.is_active ? 'success' : 'secondary'}`}>
                      {proc.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </div>
                  <div className="processor-actions">
                    <button 
                      className={`btn ${proc.is_active ? 'btn-danger' : 'btn-success'}`}
                      onClick={() => toggleProcessor(proc.config_id, proc.is_active)}
                    >
                      {proc.is_active ? 'Deactivate' : 'Activate'}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="card">
        <div className="card-section">
          <h2>🔔 Notification Settings</h2>
          <div className="form-group">
            <label>
              <input type="checkbox" />
              Email notifications for new transactions
            </label>
          </div>
          <div className="form-group">
            <label>
              <input type="checkbox" />
              Email notifications for disputes
            </label>
          </div>
          <div className="form-group">
            <label>
              <input type="checkbox" />
              SMS alerts for failed payments
            </label>
          </div>
          <button className="btn btn-primary">Save Settings</button>
        </div>
      </div>
    </div>
  );
};

export default Settings;
