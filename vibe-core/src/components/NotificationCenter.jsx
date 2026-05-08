/*
 * Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
 * Author: Christopher Niven
 */
import React, { useState, useEffect } from 'react';
import { apiReady } from '../api/config';  // NEW: apiReady is a Promise that resolves to the configured axios instance

import './NotificationCenter.css';

const NotificationCenter = () => {
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [stats, setStats] = useState(null);
  const [preferences, setPreferences] = useState(null);
  const [showPreferences, setShowPreferences] = useState(false);

  useEffect(() => {
    fetchNotifications();
    fetchStats();
    fetchPreferences();
  }, []);

  const fetchNotifications = async () => {
    setLoading(true);
    setError(null);
    try {
      const api = await apiReady;
      const response = await api.getWithLog('/notifications/history',
          `${import.meta.url.split('/').pop()}`);

      if (response.data.success) {
        const notifs = response.data.data.notifications || [];
        setNotifications(notifs);
        setUnreadCount(notifs.filter(n => n.status === 'unread').length);
      } else {
        setError(response.data.error || 'Failed to fetch notifications');
      }
    } catch (err) {
      console.error('Error fetching notifications:', err);
      setError(err.response?.data?.error || 'Failed to fetch notifications');
    } finally {
      setLoading(false);
    }
  };

  const fetchStats = async () => {
    try {
      const api = await apiReady;
      const response = await api.getWithLog('/notifications/history/stats',
          `${import.meta.url.split('/').pop()}`);

      if (response.data.success) {
        setStats(response.data.data);
      }
    } catch (err) {
      console.error('Error fetching statsBB:', err);
    }
  };

  const fetchPreferences = async () => {
    try {
      const api = await apiReady;
      const response = await api.getWithLog('/notifications/preferences',
          `${import.meta.url.split('/').pop()}`);

      if (response.data.success) {
        setPreferences(response.data.data);
      }
    } catch (err) {
      console.error('Error fetching preferences:', err);
    }
  };

  const markAsRead = async (notifId) => {
    try {
      const api = await apiReady;
      const response = await api.patch(`/notifications/history/${notifId}`, {
        status: 'read'
      });
      if (response.data.success) {
        fetchNotifications();
      }
    } catch (err) {
      console.error('Error marking as read:', err);
      setError(err.response?.data?.error || 'Failed to mark as read');
    }
  };

  const markAllAsRead = async () => {
    try {
      const unreadNotifications = notifications.filter(n => n.status === 'unread');
      
      // // Mark all unread notifications as read
      // await Promise.all(

      //   //const api = await apiReady;
      //   // TODO add await for next linw?
      //   unreadNotifications.map(notif => 
      //     api.patch(`/notifications/history/${notif.notificationId}`, {
      //       status: 'read'
      //     })
      //   )
      // );
      
      // fetchNotifications();
    } catch (err) {
      console.error('Error marking all as read:', err);
      setError(err.response?.data?.error || 'Failed to mark all as read');
    }
  };

  const archiveNotification = async (notifId) => {
    try {
      const api = await apiReady;
      const response = await api.patch(`/notifications/history/${notifId}`, {
        archived: true
      });
      if (response.data.success) {
        fetchNotifications();
      }
    } catch (err) {
      console.error('Error archiving notification:', err);
      setError(err.response?.data?.error || 'Failed to archive notification');
    }
  };

  const deleteNotification = async (notifId) => {
    if (!window.confirm('Are you sure you want to delete this notification?')) {
      return;
    }
    
    try {
      const api = await apiReady;
      const response = await api.deleteWithLog(`/notifications/history/${notifId}`,
          `${import.meta.url.split('/').pop()}`);

      if (response.data.success) {
        fetchNotifications();
      }
    } catch (err) {
      console.error('Error deleting notification:', err);
      setError(err.response?.data?.error || 'Failed to delete notification');
    }
  };

  const updatePreferences = async (newPreferences) => {
    try {
      const api = await apiReady;
      const response = await api.putWithLog('/notifications/preferences', newPreferences,
          `${import.meta.url.split('/').pop()}`);

      if (response.data.success) {
        setPreferences(response.data.data.preferences);
        setShowPreferences(false);
        alert('Preferences updated successfully');
      }
    } catch (err) {
      console.error('Error updating preferences:', err);
      setError(err.response?.data?.error || 'Failed to update preferences');
    }
  };

  const getNotificationIcon = (type) => {
    const icons = {
      appointments: '📅',
      tasks: '✅',
      payments: '💳',
      disputes: '⚖️',
      systemUpdates: 'ℹ️',
      other: '📬'
    };
    return icons[type] || '📬';
  };

  const getPriorityBadge = (priority) => {
    const badges = {
      urgent: '🔴',
      high: '🟠',
      normal: '🟢',
      low: '⚪'
    };
    return badges[priority] || '';
  };

  return (
    <div className="content-wrapper">
      <div className="page-header primary">
        <h1>🔔 Notifications</h1>
        <p>System alerts and updates ({unreadCount} unread)</p>
      </div>

      {error && (
        <div className="alert alert-danger">
          {error}
          <button onClick={() => setError(null)}>×</button>
        </div>
      )}

      {/* Stats Section */}
      {stats && (
        <div className="card">
          <div className="card-section">
            <h2>📊 Notification Statistics</h2>
            <div className="stats-grid">
              <div className="stat-item">
                <span className="stat-label">Total</span>
                <span className="stat-value">{stats.total}</span>
              </div>
              <div className="stat-item">
                <span className="stat-label">Unread</span>
                <span className="stat-value">{stats.unread}</span>
              </div>
              <div className="stat-item">
                <span className="stat-label">Last 30 Days</span>
                <span className="stat-value">{stats.last30Days}</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Preferences Section */}
      <div className="card">
        <div className="card-section">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h2>⚙️ Notification Preferences</h2>
            <button 
              className="btn btn-secondary"
              onClick={() => setShowPreferences(!showPreferences)}
            >
              {showPreferences ? 'Hide' : 'Show'} Preferences
            </button>
          </div>

          {showPreferences && preferences && (
            <PreferencesEditor 
              preferences={preferences}
              onSave={updatePreferences}
              onCancel={() => setShowPreferences(false)}
            />
          )}
        </div>
      </div>

      {/* Actions Bar */}
      <div className="card">
        <div className="card-section">
          <div style={{ display: 'flex', gap: '10px' }}>
            <button 
              className="btn btn-primary"
              onClick={fetchNotifications}
              disabled={loading}
            >
              🔄 Refresh
            </button>
            <button 
              className="btn btn-secondary"
              onClick={markAllAsRead}
              disabled={unreadCount === 0}
            >
              ✅ Mark All as Read
            </button>
          </div>
        </div>
      </div>

      {/* Notifications List */}
      <div className="card">
        <div className="card-section">
          <h2>📬 Recent Notifications</h2>
          
          {loading ? (
            <div className="loading">Loading notifications...</div>
          ) : notifications.length > 0 ? (
            <div className="notifications-list">
              {notifications.map((notif) => (
                <div 
                  key={notif.notificationId} 
                  className={`notification-item ${notif.status === 'unread' ? 'unread' : 'read'}`}
                >
                  <div className="notif-icon">
                    {getNotificationIcon(notif.notificationType)}
                  </div>
                  <div className="notif-content">
                    <div className="notif-header">
                      <h4>{notif.subject}</h4>
                      <span className="notif-priority">
                        {getPriorityBadge(notif.priority)} {notif.priority}
                      </span>
                    </div>
                    <p>{notif.body}</p>
                    <div className="notif-meta">
                      <small>{new Date(notif.sentAt).toLocaleString()}</small>
                      {notif.deliveryStatus && (
                        <small className="delivery-status">
                          {notif.deliveryStatus.email === 'sent' && '📧 '}
                          {notif.deliveryStatus.sms === 'sent' && '📱 '}
                          {notif.deliveryStatus.push === 'sent' && '🔔 '}
                        </small>
                      )}
                    </div>
                  </div>
                  <div className="notif-actions">
                    {notif.status === 'unread' && (
                      <button 
                        className="btn-icon"
                        onClick={() => markAsRead(notif.notificationId)}
                        title="Mark as read"
                      >
                        ✅
                      </button>
                    )}
                    <button 
                      className="btn-icon"
                      onClick={() => archiveNotification(notif.notificationId)}
                      title="Archive"
                    >
                      📦
                    </button>
                    <button 
                      className="btn-icon"
                      onClick={() => deleteNotification(notif.notificationId)}
                      title="Delete"
                    >
                      🗑️
                    </button>
                  </div>
                  {notif.status === 'unread' && <div className="unread-dot"></div>}
                </div>
              ))}
            </div>
          ) : (
            <div className="no-data">
              <p>No notifications</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

// Preferences Editor Component
const PreferencesEditor = ({ preferences, onSave, onCancel }) => {
  const [localPrefs, setLocalPrefs] = useState(preferences);

  const handleToggle = (category, type) => {
    setLocalPrefs(prev => ({
      ...prev,
      [category]: {
        ...prev[category],
        [type]: !prev[category][type]
      }
    }));
  };

  const handleFrequencyChange = (e) => {
    setLocalPrefs(prev => ({
      ...prev,
      frequency: e.target.value
    }));
  };

  const handleQuietHoursToggle = () => {
    setLocalPrefs(prev => ({
      ...prev,
      quietHours: {
        ...prev.quietHours,
        enabled: !prev.quietHours.enabled
      }
    }));
  };

  const handleQuietHoursChange = (field, value) => {
    setLocalPrefs(prev => ({
      ...prev,
      quietHours: {
        ...prev.quietHours,
        [field]: value
      }
    }));
  };

  const notificationTypes = ['appointments', 'tasks', 'payments', 'disputes', 'systemUpdates'];

  return (
    <div className="preferences-editor">
      <h3>Email Notifications</h3>
      <div className="preference-toggles">
        {notificationTypes.map(type => (
          <label key={type}>
            <input
              type="checkbox"
              checked={localPrefs.emailNotifications?.[type] || false}
              onChange={() => handleToggle('emailNotifications', type)}
            />
            {type.charAt(0).toUpperCase() + type.slice(1)}
          </label>
        ))}
      </div>

      <h3>SMS Notifications</h3>
      <div className="preference-toggles">
        {notificationTypes.map(type => (
          <label key={type}>
            <input
              type="checkbox"
              checked={localPrefs.smsNotifications?.[type] || false}
              onChange={() => handleToggle('smsNotifications', type)}
            />
            {type.charAt(0).toUpperCase() + type.slice(1)}
          </label>
        ))}
      </div>

      <h3>Push Notifications</h3>
      <div className="preference-toggles">
        {notificationTypes.map(type => (
          <label key={type}>
            <input
              type="checkbox"
              checked={localPrefs.pushNotifications?.[type] || false}
              onChange={() => handleToggle('pushNotifications', type)}
            />
            {type.charAt(0).toUpperCase() + type.slice(1)}
          </label>
        ))}
      </div>

      <h3>Delivery Frequency</h3>
      <select value={localPrefs.frequency} onChange={handleFrequencyChange}>
        <option value="immediate">Immediate</option>
        <option value="daily_digest">Daily Digest</option>
        <option value="weekly_digest">Weekly Digest</option>
      </select>

      <h3>Quiet Hours</h3>
      <label>
        <input
          type="checkbox"
          checked={localPrefs.quietHours?.enabled || false}
          onChange={handleQuietHoursToggle}
        />
        Enable Quiet Hours
      </label>
      {localPrefs.quietHours?.enabled && (
        <div className="quiet-hours-config">
          <label>
            Start:
            <input
              type="time"
              value={localPrefs.quietHours.start || '22:00'}
              onChange={(e) => handleQuietHoursChange('start', e.target.value)}
            />
          </label>
          <label>
            End:
            <input
              type="time"
              value={localPrefs.quietHours.end || '08:00'}
              onChange={(e) => handleQuietHoursChange('end', e.target.value)}
            />
          </label>
        </div>
      )}

      <div className="preference-actions">
        <button className="btn btn-primary" onClick={() => onSave(localPrefs)}>
          Save Preferences
        </button>
        <button className="btn btn-secondary" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </div>
  );
};

export default NotificationCenter;
