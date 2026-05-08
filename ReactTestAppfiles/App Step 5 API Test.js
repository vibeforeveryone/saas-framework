
// FIRST: Make sure you have axios installed
// npm install axios

// Create this file: src/api/config.js
/*
import axios from 'axios';

const api = axios.create({
  baseURL: 'https://jsonplaceholder.typicode.com',
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
});

export { api };
export default api;
*/

// Then replace App.js with this:

import React, { useState, useEffect } from 'react';
import { api } from './api/config';

function App() {
  const [posts, setPosts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const fetchData = async () => {
    try {
      setLoading(true);
      setError('');
      console.log('Fetching data...');
      
      const response = await api.get('/posts?_limit=3');
      console.log('API Response:', response.data);
      
      setPosts(response.data);
    } catch (err) {
      console.error('API Error:', err);
      setError(`Failed to fetch data: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  return (
    <div style={{ padding: '20px', fontFamily: 'Arial, sans-serif' }}>
      <h1 style={{ color: '#2563eb' }}>✅ Step 5: API Test</h1>
      
      <div style={{ marginBottom: '20px' }}>
        <button 
          onClick={fetchData} 
          disabled={loading}
          style={{ 
            padding: '10px 20px', 
            backgroundColor: loading ? '#ccc' : '#2563eb',
            color: 'white',
            border: 'none',
            borderRadius: '5px',
            cursor: loading ? 'not-allowed' : 'pointer'
          }}
        >
          {loading ? '🔄 Loading...' : '🔄 Refresh Data'}
        </button>
      </div>

      {error && (
        <div style={{ 
          padding: '15px', 
          backgroundColor: '#fef2f2', 
          border: '1px solid #fca5a5', 
          borderRadius: '5px',
          color: '#dc2626',
          marginBottom: '20px'
        }}>
          ❌ {error}
        </div>
      )}

      {posts.length > 0 && (
        <div>
          <h3 style={{ color: '#059669' }}>✅ API Working! Sample Data:</h3>
          {posts.map(post => (
            <div key={post.id} style={{ 
              border: '1px solid #e5e7eb', 
              padding: '15px', 
              margin: '10px 0', 
              borderRadius: '8px',
              backgroundColor: '#f9fafb'
            }}>
              <h4 style={{ margin: '0 0 10px 0', color: '#374151' }}>
                {post.id}. {post.title}
              </h4>
              <p style={{ margin: 0, color: '#6b7280' }}>{post.body}</p>
            </div>
          ))}
        </div>
      )}

      {!loading && posts.length === 0 && !error && (
        <p>No data loaded yet. Click refresh to test API.</p>
      )}
    </div>
  );
}

export default App;