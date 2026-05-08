import React from 'react';

function App() {
  return (
    <div style={{ padding: '20px', fontFamily: 'Arial, sans-serif' }}>
      <h1 style={{ color: '#2563eb' }}>✅ Step 2: JSX and Styling Test</h1>
      <p>If you see this with blue heading and proper spacing, JSX and inline styles work!</p>
      <div style={{ 
        backgroundColor: '#f0f0f0', 
        padding: '15px', 
        borderRadius: '8px',
        margin: '10px 0'
      }}>
        <h3>Styled Box</h3>
        <p>This tests CSS styling capabilities</p>
      </div>
      <button style={{
        backgroundColor: '#2563eb',
        color: 'white',
        padding: '10px 20px',
        border: 'none',
        borderRadius: '5px',
        cursor: 'pointer'
      }}>
        Test Button
      </button>
    </div>
  );
}

export default App;