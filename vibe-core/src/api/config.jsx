/*
 * Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
 * Author: Christopher Niven
 */
/**
 * config.js — Axios instance factory
 *
 * Token strategy:
 *   - Access token read from AuthContext module-level getter (never localStorage)
 *   - On 401: attempts /auth/refresh once using httpOnly cookie
 *   - Concurrent 401s are queued and replayed after the single refresh resolves
 *   - On refresh failure: clears auth state and redirects to /login
 */
import axios from 'axios';
import {
  getAccessToken,
  setAuthFromOutside,
  clearAuthFromOutside,
} from '../context/AuthContext';

// ── API config loader ─────────────────────────────────────────────────────────
const loadApiConfig = async () => {
  const response = await fetch('/apiconfig.json');
  if (!response.ok) {
    throw new Error(`Failed to load apiConfig.json: ${response.status} ${response.statusText}`);
  }
  return response.json();
};

const buildBaseUrl = ({ apiPath, awsRegion, stageName }) =>
  `https://${apiPath}.execute-api.${awsRegion}.amazonaws.com/${stageName}`;


// ── Refresh state (module-level — shared across all interceptor calls) ────────
let isRefreshing    = false;
let refreshQueue    = [];   // array of { resolve, reject } for queued requests

const processQueue = (error, token = null) => {
  refreshQueue.forEach(({ resolve, reject }) =>
    error ? reject(error) : resolve(token)
  );
  refreshQueue = [];
};

const doSilentRefresh = async () => {
  const response = await fetch('/auth/refresh', {
    method:      'POST',
    credentials: 'include',
    headers:     { 'Content-Type': 'application/json' },
  });

  if (!response.ok) throw new Error('Refresh failed');

  const data = await response.json();
  if (!data.success || !data.data?.access_token) throw new Error('Refresh returned no token');

  // Push new token back into AuthContext React state and module-level store
  setAuthFromOutside(data.data.access_token, data.data.user);
  return data.data.access_token;
};


// ── Axios instance factory ────────────────────────────────────────────────────
const createApiInstance = (baseURL) => {
  const instance = axios.create({
    baseURL,
    timeout:     10000,
    //withCredentials: true,   // required so browser sends the refresh-token cookie
    headers:     { 'Content-Type': 'application/json' },
  });

  // ── Request interceptor — attach Bearer token ───────────────────────────
  instance.interceptors.request.use(
    (config) => {
      const label     = config.metadata?.label || 'API Request';
      const startTime = performance.now();
      config.metadata = { ...config.metadata, startTime };

      console.group(`🔵 ${label}: ${config.method.toUpperCase()} ${config.url}`);
      console.log('📤 Full URL:', config.baseURL + config.url);
      console.log('📋 Headers:', config.headers);
      if (config.data)   console.log('📦 Request Data:', config.data);
      if (config.params) console.log('🔗 Query Params:', config.params);
      console.log('⏰ Started:', new Date().toISOString());
      console.groupEnd();

      // Read token from AuthContext module store — never localStorage
      const token = getAccessToken();
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }

      return config;
    },
    (error) => {
      console.error('❌ Request Error:', error);
      return Promise.reject(error);
    }
  );

  // ── Response interceptor — log, handle 401 with silent refresh ──────────
  instance.interceptors.response.use(
    (response) => {
      const label    = response.config.metadata?.label || 'API Response';
      const duration = response.config.metadata?.startTime
        ? performance.now() - response.config.metadata.startTime
        : 0;

      console.group(`🟢 ${label}: ${response.config.method.toUpperCase()} ${response.config.url}`);
      console.log('✅ Status:', response.status);
      console.log('📥 Response Data:', response.data);
      console.log('⏱️ Duration:', `${duration.toFixed(2)}ms`);
      console.log('⏰ Completed:', new Date().toISOString());
      console.groupEnd();

      return response;
    },
    async (error) => {
      const label    = error.config?.metadata?.label || 'API Error';
      const duration = error.config?.metadata?.startTime
        ? performance.now() - error.config.metadata.startTime
        : 0;

      console.group(`🔴 ${label}: ${error.config?.method?.toUpperCase()} ${error.config?.url}`);
      console.error('❌ Status:', error.response?.status);
      console.error('📥 Error Data:', error.response?.data);
      console.error('💬 Error Message:', error.message);
      console.error('⏱️ Duration:', `${duration.toFixed(2)}ms`);
      console.error('⏰ Failed at:', new Date().toISOString());
      console.groupEnd();

      const originalRequest = error.config;

      // ── 401 handling — attempt silent refresh ──────────────────────────
      if (error.response?.status === 401 && !originalRequest._retry) {
        originalRequest._retry = true;

        if (isRefreshing) {
          // Another request is already refreshing — queue this one
          return new Promise((resolve, reject) => {
            refreshQueue.push({ resolve, reject });
          }).then((newToken) => {
            originalRequest.headers.Authorization = `Bearer ${newToken}`;
            return instance(originalRequest);
          }).catch((err) => Promise.reject(err));
        }

        isRefreshing = true;

        try {
          const newToken = await doSilentRefresh();
          processQueue(null, newToken);
          originalRequest.headers.Authorization = `Bearer ${newToken}`;
          return instance(originalRequest);
        } catch (refreshError) {
          processQueue(refreshError, null);
          // Refresh failed — clear auth and send to login
          clearAuthFromOutside();
          window.location.href = '/login';
          return Promise.reject(refreshError);
        } finally {
          isRefreshing = false;
        }
      }

      return Promise.reject(error);
    }
  );

  // ── Convenience methods with logging labels ──────────────────────────────
  instance.getWithLog = function (url, label, config = {}) {
    return this.get(url, { ...config, metadata: { ...config.metadata, label } });
  };
  instance.postWithLog = function (url, data, label, config = {}) {
    return this.post(url, data, { ...config, metadata: { ...config.metadata, label } });
  };
  instance.putWithLog = function (url, data, label, config = {}) {
    return this.put(url, data, { ...config, metadata: { ...config.metadata, label } });
  };
  instance.deleteWithLog = function (url, label, config = {}) {
    return this.delete(url, { ...config, metadata: { ...config.metadata, label } });
  };

  return instance;
};


// ── Initialisation ─────────────────────────────────────────────────────────────
export const apiReady = loadApiConfig()
  .then((config) => {
    const baseURL = buildBaseUrl(config);
    console.log('✅ API configured:', baseURL);
    return createApiInstance(baseURL);
  })
  .catch((err) => {
    console.error('🚨 Could not load apiConfig.json. Is the file in your public/ directory?', err);
    throw err;
  });


// ── Helpers (unchanged) ───────────────────────────────────────────────────────
export const isApiConfigured = async () => {
  try {
    const response = await fetch('/apiconfig.json');
    return response.ok;
  } catch {
    return false;
  }
};

export const getApiConfig = async () => {
  try {
    return await loadApiConfig();
  } catch (err) {
    console.error('Error loading API config:', err);
    return null;
  }
};
