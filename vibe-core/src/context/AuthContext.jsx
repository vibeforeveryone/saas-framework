/*
 * Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
 * Author: Christopher Niven
 */
/**
 * AuthContext.js
 *
 * Single source of truth for authentication state.
 * The access token NEVER touches localStorage or sessionStorage — it lives
 * only in React state and in the module-level accessor below (for config.js).
 *
 * On app startup, AuthProvider silently calls /auth/refresh.
 * If the browser holds a valid httpOnly refresh-token cookie the call succeeds
 * and the user is restored without a login screen.
 * If not, isLoading becomes false and ProtectedRoute redirects to /login.
 *
 * Module-level exports (non-React, used by config.js):
 *   getAccessToken()          → current token string or null
 *   setAuthTokens(token,user) → called by config.js after a silent refresh
 *   clearAuthTokens()         → called by config.js on unrecoverable 401
 */

import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  useRef,
} from 'react';

// ── Module-level token store (accessible outside React tree) ─────────────────
// config.js imports these directly so the axios interceptor can read/write
// the token without needing a React hook.
let _accessToken = null;
let _onClearAuth = null;   // callback set by AuthProvider so config.js can trigger logout

export const getAccessToken = ()        => _accessToken;
export const setModuleToken  = (token)  => { _accessToken = token; };
export const clearModuleToken = ()      => { _accessToken = null; };

/** Called by config.js when a silent refresh succeeds mid-flight. */
export const setAuthFromOutside = (token, user) => {
  _accessToken = token;
  // Notify the React tree so components re-render with updated user
  if (_onClearAuth?._setUser) _onClearAuth._setUser(user);
  if (_onClearAuth?._setToken) _onClearAuth._setToken(token);
};

/** Called by config.js when refresh fails — forces logout. */
export const clearAuthFromOutside = () => {
  _accessToken = null;
  if (_onClearAuth?._clear) _onClearAuth._clear();
};


// ── React context ─────────────────────────────────────────────────────────────
const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [accessToken, _setAccessToken] = useState(null);
  const [user, _setUser]               = useState(null);
  const [isLoading, setIsLoading]      = useState(true);  // true while checking cookie
  const isMounted = useRef(true);

  // Wire up the module-level callbacks so config.js can call back into React
  useEffect(() => {
    _onClearAuth = {
      _setUser:  (u) => { if (isMounted.current) _setUser(u); },
      _setToken: (t) => { if (isMounted.current) _setAccessToken(t); },
      _clear:    ()  => {
        if (isMounted.current) {
          _setAccessToken(null);
          _setUser(null);
        }
      },
    };
    return () => { isMounted.current = false; };
  }, []);

  // ── setAuth: called after login or successful refresh ─────────────────────
  const setAuth = useCallback((token, userData) => {
    _accessToken = token;
    _setAccessToken(token);
    _setUser(userData);
  }, []);

  // ── clearAuth: called on logout or unrecoverable 401 ─────────────────────
  const clearAuth = useCallback(() => {
    _accessToken = null;
    _setAccessToken(null);
    _setUser(null);
  }, []);

  // ── Silent refresh on app mount ───────────────────────────────────────────
  // Attempts /auth/refresh using the httpOnly cookie. On success the user is
  // seamlessly restored. On failure (no cookie / expired) isLoading → false
  // and ProtectedRoute redirects to /login.
  useEffect(() => {
    let cancelled = false;

    const attemptSilentRefresh = async () => {
      try {
        // Use fetch directly here — config.js (axios) hasn't been initialised yet
        // and would create a circular dependency.
        const response = await fetch('/auth/refresh', {
          method:      'POST',
          credentials: 'include',   // send the httpOnly cookie
          headers:     { 'Content-Type': 'application/json' },
        });

        if (!cancelled && response.ok) {
          const data = await response.json();
          if (data.success && data.data?.access_token) {
            setAuth(data.data.access_token, data.data.user);
          }
        }
      } catch {
        // Network error or no cookie — normal on first visit
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    };

    attemptSilentRefresh();
    return () => { cancelled = true; };
  }, [setAuth]);

  // ── Proactive token refresh (1 min before 15-min expiry) ─────────────────
  useEffect(() => {
    if (!accessToken) return;

    // Decode exp from JWT payload (no verification needed here — just timing)
    try {
      const payload = JSON.parse(atob(accessToken.split('.')[1]));
      const expiresAt = payload.exp * 1000;   // ms
      const refreshAt = expiresAt - 60_000;   // 1 min early
      const delay     = refreshAt - Date.now();

      if (delay <= 0) return;   // already near expiry; interceptor will handle it

      const timer = setTimeout(async () => {
        try {
          const response = await fetch('/auth/refresh', {
            method:      'POST',
            credentials: 'include',
            headers:     { 'Content-Type': 'application/json' },
          });
          if (response.ok) {
            const data = await response.json();
            if (data.success && data.data?.access_token) {
              setAuth(data.data.access_token, data.data.user);
            }
          }
        } catch {
          // Will fall back to interceptor-driven refresh
        }
      }, delay);

      return () => clearTimeout(timer);
    } catch {
      // Malformed token — ignore; interceptor will handle the 401
    }
  }, [accessToken, setAuth]);

  return (
    <AuthContext.Provider value={{ accessToken, user, isLoading, setAuth, clearAuth }}>
      {children}
    </AuthContext.Provider>
  );
};

/**
 * useAuth()
 * Hook for React components.
 * Returns { accessToken, user, isLoading, setAuth, clearAuth }
 */
export const useAuth = () => {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>');
  return ctx;
};

export default AuthContext;
