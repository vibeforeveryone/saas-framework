/*
 * Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
 * Author: Christopher Niven
 */
import React, { useState } from 'react';
import { apiReady } from '../api/config';  // NEW: apiReady is a Promise that resolves to the configured axios instance

import './ProcessorConfig.css';

const ProcessorConfig = () => {
  const [config, setConfig] = useState({
    company_name: '',
    processor_type: 'merchantone',
    api_key: '',
    api_secret: '',
    merchant_id: ''
  });

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      const api = await apiReady;
      await api.postWithLog('/processor-configs', config,
          `${import.meta.url.split('/').pop()}`);

      alert('Processor configured successfully!');
    } catch (err) {
      alert('Configuration failed');
    }
  };

  return (
    <div className="content-wrapper">
      <div className="page-header primary">
        <h1>💳 Processor Configuration</h1>
        <p>Configure payment processor credentials</p>
      </div>

      <form onSubmit={handleSubmit}>
        <div className="card">
          <div className="card-section">
            <div className="form-grid">
              <div className="form-group">
                <label>Company Name</label>
                <input
                  type="text"
                  value={config.company_name}
                  onChange={(e) => setConfig({...config, company_name: e.target.value})}
                  required
                />
              </div>

              <div className="form-group">
                <label>Processor Type</label>
                <select value={config.processor_type} onChange={(e) => setConfig({...config, processor_type: e.target.value})}>
                  <option value="merchantone">MerchantOne</option>
                  <option value="paysafe">PaySafe</option>
                  <option value="paymentnerds">PaymentNerds</option>
                </select>
              </div>

              <div className="form-group">
                <label>API Key</label>
                <input
                  type="text"
                  value={config.api_key}
                  onChange={(e) => setConfig({...config, api_key: e.target.value})}
                  required
                />
              </div>

              <div className="form-group">
                <label>API Secret</label>
                <input
                  type="password"
                  value={config.api_secret}
                  onChange={(e) => setConfig({...config, api_secret: e.target.value})}
                  required
                />
              </div>

              <div className="form-group">
                <label>Merchant ID</label>
                <input
                  type="text"
                  value={config.merchant_id}
                  onChange={(e) => setConfig({...config, merchant_id: e.target.value})}
                />
              </div>
            </div>

            <button type="submit" className="btn btn-primary">Save Configuration</button>
          </div>
        </div>
      </form>
    </div>
  );
};

export default ProcessorConfig;
