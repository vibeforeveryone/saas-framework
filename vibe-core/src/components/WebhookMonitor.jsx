/*
 * Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
 * Author: Christopher Niven
 */
import React, { useState, useEffect } from 'react';
import { apiReady } from '../api/config';  // NEW: apiReady is a Promise that resolves to the configured axios instance

import './WebhookMonitor.css';

const WebhookMonitor = () => {
  const [webhooks, setWebhooks] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchWebhooks();
    const interval = setInterval(fetchWebhooks, 5000);
    return () => clearInterval(interval);
  }, []);

  const fetchWebhooks = async () => {
    try {
      setLoading(true);
      const api = await apiReady;
      const response = await api.getWithLog('/webhooks?limit=20',
          `${import.meta.url.split('/').pop()}`);

      if (response.data.success) {
        setWebhooks(response.data.data.webhooks);
      }
    } catch (err) {
      console.error('Error fetching webhooks:', err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="content-wrapper">
      <div className="page-header primary">
        <h1>🔔 Webhook Monitor</h1>
        <p>Real-time webhook activity</p>
      </div>

      <div className="card">
        <div className="card-section">
          <h2>📡 Recent Webhooks</h2>
          {webhooks.map((wh) => (
            <div key={wh.webhook_id} className="webhook-item">
              <span className={`status-badge status-${wh.status}`}>{wh.status}</span>
              <span>{wh.processor_type}</span>
              <span className="data-timestamp">{new Date(wh.received_at).toLocaleString()}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default WebhookMonitor;
