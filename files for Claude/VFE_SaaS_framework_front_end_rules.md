# VFE SaaS Framework — Frontend Rules
<!-- CLAUDE INSTRUCTION: Apply every rule in this document when generating, modifying, or reviewing React frontend code for any VFE SaaS application. -->

## Overview

The VFE frontend is a **React single-page application** deployed on AWS Amplify. All new screens and components are **additive** — they extend the existing framework files without replacing them.

---

## 1. Core Framework Files (Do Not Replace)

These files are the VFE shell. Always extend; never overwrite.

| File | Role | Rule |
|---|---|---|
| `App.js` | Root router, app shell, `ProtectedRoute` wrapper | Add new `<Route>` entries only |
| `Navigation.js` | Left-side collapsible navigation | Add new nav items using existing section/link patterns |
| `LoginScreen.js` | Authentication screen | Do not modify |
| `design-system.css` | Global CSS variables and base component styles | Import in new components; do not redefine tokens |
| `Navigation.css` | Sidebar styles | Do not modify |
| `config.js` | API base URL and authenticated request helpers | All API calls must use this file |

---

## 2. API Access Rules

### 2.1 All API Calls Must Use `config.js`

Every API call must use the `api` object imported from `config.js`. Direct use of `fetch` or `axios` is not permitted.

```javascript
import api from '../api/config';

// GET request
const response = await api.getWithLog('/some-endpoint', `${import.meta.url.split('/').pop()}`);

// POST request
const response = await api.postWithLog('/some-endpoint', payload, `${import.meta.url.split('/').pop()}`);
```

### 2.2 Response Handling Pattern

All Lambda responses follow this envelope:

```json
{
  "success": true,
  "data": { ... },
  "error": null,
  "timestamp": "2025-01-01T00:00:00.000000"
}
```

Always check `response.data.success` before accessing `response.data.data`:

```javascript
if (response.data.success) {
  const items = response.data.data.items || [];
} else {
  setError(response.data.error || 'Operation failed');
}
```

### 2.3 Error Handling Pattern

```javascript
try {
  const response = await api.getWithLog('/endpoint', `${import.meta.url.split('/').pop()}`);
  if (response.data.success) {
    // handle success
  } else {
    setError(response.data.error || 'Request failed');
  }
} catch (err) {
  console.error('Error:', err);
  if (err.response?.data?.error) {
    setError(err.response.data.error);
  } else {
    setError('Request failed. Please try again.');
  }
} finally {
  setLoading(false);
}
```

---

## 3. Component Standards

### 3.1 File Naming and Location

- One component per file
- PascalCase filenames: `UserManager.js`, `CustomerManagement.js`
- Located in `src/components/`

### 3.2 Component Structure

Use functional components with hooks:

```javascript
import React, { useState, useEffect } from 'react';
import api from '../api/config';

const MyComponent = () => {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    setLoading(true);
    try {
      const response = await api.getWithLog('/endpoint', `${import.meta.url.split('/').pop()}`);
      if (response.data.success) {
        setData(response.data.data.items || []);
      }
    } catch (err) {
      setError('Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="content-wrapper">
      {/* ... */}
    </div>
  );
};

export default MyComponent;
```

### 3.3 Loading and Error States

Every component that fetches data must implement loading and error states:

```javascript
if (loading) {
  return <div className="loading-container">Loading...</div>;
}

{error && (
  <div className="error-message">⚠️ {error}</div>
)}
```

---

## 4. Styling Rules

### 4.1 Use Design System Tokens

Always use CSS variables from `design-system.css`. Never hard-code colors, spacing, or shadows:

```css
/* Correct */
color: var(--text-primary);
padding: var(--space-lg);
border-radius: var(--radius-md);
box-shadow: var(--shadow-sm);

/* Wrong */
color: #2c3e50;
padding: 20px;
```

### 4.2 Available Design Tokens

**Colors:**
```
--primary-blue: #3498db       --primary-blue-dark: #2980b9
--navy: #2c3e50               --success: #27ae60
--warning: #f39c12            --danger: #e74c3c
--gray-lightest: #f8f9fa      --gray-light: #ecf0f1
--gray-medium: #95a5a6        --text-primary: #2c3e50
--text-secondary: #7f8c8d
```

**Spacing:**
```
--space-xs: 8px    --space-sm: 12px   --space-md: 16px
--space-lg: 20px   --space-xl: 24px   --space-xxl: 30px
--space-xxxl: 40px
```

**Other:**
```
--radius-sm: 4px   --radius-md: 6px   --radius-lg: 8px
--shadow-sm        --shadow-md        --transition-normal: 0.3s ease
```

### 4.3 Standard CSS Classes (from design-system.css)

Use these classes for consistent layout and components:

```
.app-shell          .content-wrapper      .main-content
.page-header        .page-header.primary  .page-header.danger
.card               .card-section         .form-grid
.form-group         .btn                  .btn-primary
.btn-secondary      .btn-success          .btn-danger
.btn-sm             .loading-container    .no-data
.error-message
```

---

## 5. Routing Rules

### 5.1 Adding New Routes

New routes are added to `App.js` inside the existing `<Routes>` block inside `<ProtectedRoute>`. Do not create new Router instances:

```javascript
// In App.js — add inside the existing inner <Routes>
<Route path="/my-new-screen" element={<MyNewComponent />} />
```

### 5.2 Authentication

- `ProtectedRoute` wraps all routes except `/login`
- Auth state is stored in `localStorage`:
  - `localStorage.getItem('token')` — JWT token
  - `localStorage.getItem('user')` — JSON stringified user object
- The `LoginScreen.js` handles token storage after successful auth (`/auth` POST)

### 5.3 Navigation Between Screens

Use `react-router-dom` hooks — never `window.location`:

```javascript
import { useNavigate } from 'react-router-dom';
const navigate = useNavigate();
navigate('/dashboard');
```

---

## 6. Navigation Rules

### 6.1 Adding Navigation Items

New items are added inside `Navigation.js` within the existing section structure. Match the existing pattern:

**Simple link:**
```jsx
<li>
  <Link to="/my-screen" className={isActive('/my-screen') ? 'active' : ''}>
    <span className="nav-icon">📋</span> My Screen
  </Link>
</li>
```

**New collapsible section:**
```jsx
<li className="nav-section">
  <button className="nav-section-header" onClick={() => toggleSection('mySection')}>
    <span className="nav-icon">🔧</span> My Section
    <span className={`accordion-arrow ${openSections.mySection ? 'open' : ''}`}>▼</span>
  </button>
  {openSections.mySection && (
    <ul className="nav-submenu">
      <li>
        <Link to="/my-screen" className={isActive('/my-screen') ? 'active' : ''}>
          My Screen
        </Link>
      </li>
    </ul>
  )}
</li>
```

Add new section state to the `openSections` object in `Navigation.js`:
```javascript
const [openSections, setOpenSections] = useState({
  // ... existing sections ...
  mySection: true
});
```

---

## 7. Form Standards

### 7.1 Required Field Indicator

```jsx
<label htmlFor="field_name">Field Label <span className="required">*</span></label>
```

### 7.2 Form Layout

Use `.form-grid` for multi-column forms:

```jsx
<div className="form-grid">
  <div className="form-group">
    <label>Field 1</label>
    <input type="text" value={field1} onChange={e => setField1(e.target.value)} />
  </div>
  <div className="form-group">
    <label>Field 2</label>
    <input type="text" value={field2} onChange={e => setField2(e.target.value)} />
  </div>
</div>
```

### 7.3 Submit Buttons

Always disable submit buttons during loading:

```jsx
<button
  className={`btn btn-primary ${loading ? 'loading' : ''}`}
  disabled={loading}
  onClick={handleSubmit}
>
  {loading ? '🔄 Saving...' : '💾 Save'}
</button>
```

---

## 8. Page Layout Standard

All page components follow this wrapper structure:

```jsx
return (
  <div className="content-wrapper">
    <div className="page-header primary">
      <h1>🔧 Page Title</h1>
      <p>Page subtitle or description</p>
    </div>

    {error && <div className="error-message">⚠️ {error}</div>}

    <div className="card">
      <div className="card-section">
        {/* page content */}
      </div>
    </div>
  </div>
);
```

---

## 9. Deployment

- Deployed to AWS Amplify via Git push
- Environment-specific API base URL is configured in `config.js` (or via Amplify environment variables)
- No server-side rendering — this is a fully client-side SPA
- Build command: `npm run build`
- Build output directory: `dist` (Vite) or `build` (Create React App)

---

## 10. Reference Files

When building new components, reference these existing implementations:

| Reference file | Demonstrates |
|---|---|
| `LoginScreen.js` | Form handling, API post, token storage, redirect on auth |
| `Navigation.js` | Collapsible sections, active link detection, dynamic items, logout |
| `App.js` | Route registration, ProtectedRoute, import pattern |
