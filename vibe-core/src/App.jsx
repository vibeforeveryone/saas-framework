/*
 * Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
 * Author: Christopher Niven
 */
import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import './App.css';

import { AuthProvider }              from './context/AuthContext';
import { ConfigProvider }            from './components/ConfigContext';
import { ProtectedRoute, AdminRoute } from './components/ProtectedRoute';

import DashboardHome        from './DashboardHome';
import TransactionList      from './components/TransactionList';
import PaymentForm          from './components/PaymentForm';
import CustomerManagement   from './components/CustomerManagement';
import DisputeManagement    from './components/DisputeManagement';
import AnalyticsDashboard   from './components/AnalyticsDashboard';
import Settings             from './components/Settings';
import NotificationCenter   from './components/NotificationCenter';
import SearchInterface      from './components/SearchInterface';
import ReportGenerator      from './components/ReportGenerator';
import ProcessorConfig      from './components/ProcessorConfig';
import WebhookMonitor       from './components/WebhookMonitor';
import Navigation           from './components/Navigation';
import RoleManager          from './components/RoleManager';
import FeatureManager       from './components/FeatureManager';
import LicenseManager       from './components/LicenseManager';
import UserManager          from './components/UserManager';
import LoginScreen          from './components/LoginScreen';
import ApiConfigSetup       from './components/ApiConfigSetup';
import PublicSignup         from './components/PublicSignup';

function App() {
  return (
    // AuthProvider must wrap everything so ProtectedRoute and all
    // components can access the auth context via useAuth().
    <AuthProvider>
      <ConfigProvider>
        <Router>
          <div className="App app-shell">
            <Routes>

              {/* ── Public routes ──────────────────────────────────── */}
              <Route path="/login"  element={<LoginScreen />} />
              <Route path="/signin" element={<PublicSignup />} />

              {/* ── Authenticated shell ─────────────────────────────── */}
              <Route
                path="/*"
                element={
                  <ProtectedRoute>
                    <Navigation />
                    <main className="main-content">
                      <Routes>

                        {/* General authenticated routes */}
                        <Route path="/"             element={<Navigate to="/dashboard" replace />} />
                        <Route path="/dashboard"    element={<DashboardHome />} />
                        <Route path="/transactions" element={<TransactionList />} />
                        <Route path="/payment"      element={<PaymentForm />} />
                        <Route path="/customers"    element={<CustomerManagement />} />
                        <Route path="/disputes"     element={<DisputeManagement />} />
                        <Route path="/analytics"    element={<AnalyticsDashboard />} />
                        <Route path="/search"       element={<SearchInterface />} />
                        <Route path="/reports"      element={<ReportGenerator />} />
                        <Route path="/users"        element={<UserManager />} />

                        {/* Admin-only routes — Configuration */}
                        <Route path="/api-settings"     element={<AdminRoute><ApiConfigSetup /></AdminRoute>} />
                        <Route path="/roles"            element={<AdminRoute><RoleManager /></AdminRoute>} />
                        <Route path="/features"         element={<AdminRoute><FeatureManager /></AdminRoute>} />
                        <Route path="/licenses"         element={<AdminRoute><LicenseManager /></AdminRoute>} />

                        {/* Admin-only routes — System */}
                        <Route path="/webhooks"         element={<AdminRoute><WebhookMonitor /></AdminRoute>} />
                        <Route path="/processor-config" element={<AdminRoute><ProcessorConfig /></AdminRoute>} />
                        <Route path="/settings"         element={<AdminRoute><Settings /></AdminRoute>} />
                        <Route path="/notifications"    element={<AdminRoute><NotificationCenter /></AdminRoute>} />

                        {/* Fallback */}
                        <Route path="*" element={<Navigate to="/dashboard" replace />} />

                      </Routes>
                    </main>
                  </ProtectedRoute>
                }
              />

            </Routes>
          </div>
        </Router>
      </ConfigProvider>
    </AuthProvider>
  );
}

export default App;
