import React, { useState } from 'react';

function App() {
  const [count, setCount] = useState(0);
  const [message, setMessage] = useState('Hello!');
  const [inputValue, setInputValue] = useState('');

  return (
    <div style={{ padding: '20px', fontFamily: 'Arial, sans-serif' }}>
      <h1 style={{ color: '#2563eb' }}>✅ Step 3: React Hooks Test</h1>
      
      {/* Counter Test */}
      <div style={{ marginBottom: '20px', padding: '15px', backgroundColor: '#f0f9ff', borderRadius: '8px' }}>
        <h3>Counter Test: {count}</h3>
        <button 
          onClick={() => setCount(count + 1)}
          style={{ marginRight: '10px', padding: '5px 10px' }}
        >
          +1
        </button>
        <button 
          onClick={() => setCount(count - 1)}
          style={{ marginRight: '10px', padding: '5px 10px' }}
        >
          -1
        </button>
        <button 
          onClick={() => setCount(0)}
          style={{ padding: '5px 10px' }}
        >
          Reset
        </button>
      </div>

      {/* Input Test */}
      <div style={{ marginBottom: '20px', padding: '15px', backgroundColor: '#f0fdf4', borderRadius: '8px' }}>
        <h3>Input Test</h3>
        <input
          type="text"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          placeholder="Type something..."
          style={{ padding: '8px', marginRight: '10px', width: '200px' }}
        />
        <button 
          onClick={() => setMessage(inputValue)}
          style={{ padding: '8px 15px' }}
        >
          Update Message
        </button>
        <p>Current message: <strong>{message}</strong></p>
      </div>

      <p style={{ color: '#059669' }}>
        ✅ If counter and input work, React hooks are functioning properly!
      </p>
    </div>
  );
}

export default App;