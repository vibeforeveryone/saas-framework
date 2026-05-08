
import React, { useState } from 'react';
import { BrowserRouter, Routes, Route, Link, useLocation } from 'react-router-dom';

function HomePage() {
  return (
    <div style={{ padding: '20px' }}>
      <h2>🏠 Home Page</h2>
      <p>You're on the home page. React Router is working!</p>
      <p>Try clicking the navigation links above.</p>
    </div>
  );
}

function TestPage() {
  const [clicks, setClicks] = useState(0);
  
  return (
    <div style={{ padding: '20px' }}>
      <h2>🧪 Test Page</h2>
      <p>This is a separate page with its own state.</p>
      <p>Button clicks: {clicks}</p>
      <button onClick={() => setClicks(clicks + 1)}>
        Click me! ({clicks})
      </button>
    </div>
  );
}

function Navigation() {
  const location = useLocation();
  
  const linkStyle = {
    padding: '10px 15px',
    margin: '0 5px',
    textDecoration: 'none',
    backgroundColor: '#e5e7eb',
    borderRadius: '5px',
    color: '#374151'
  };
  
  const activeLinkStyle = {
    ...linkStyle,
    backgroundColor: '#2563eb',
    color: 'white'
  };
   
  return (
    <nav style={{ padding: '20px', backgroundColor: '#f9fafb', borderBottom: '1px solid #e5e7eb' }}>
      <h1 style={{ margin: '0 0 15px 0' }}>✅ Step 4: React Router Test</h1>
      <div>
        <Link 
          to="/" 
          style={location.pathname === '/' ? activeLinkStyle : linkStyle}
        >
          Home
        </Link>
        <Link 
          to="/test" 
          style={location.pathname === '/test' ? activeLinkStyle : linkStyle}
        >
          Test Page
        </Link>
      </div>
    </nav>
  );
}

function App() {
  return (
    <BrowserRouter>
      <div>
        <Navigation />
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/test" element={<TestPage />} />
        </Routes>
        <footer style={{ padding: '20px', textAlign: 'center', color: '#6b7280' }}>
          ✅ If navigation works and pages switch, React Router is working!
        </footer>
      </div>
    </BrowserRouter>
  );
}

export default App;