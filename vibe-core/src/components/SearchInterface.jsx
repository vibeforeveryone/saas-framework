/*
 * Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
 * Author: Christopher Niven
 */
import React, { useState } from 'react';
import { apiReady } from '../api/config';  // NEW: apiReady is a Promise that resolves to the configured axios instance

import './SearchInterface.css';

const SearchInterface = () => {
  const [searchType, setSearchType] = useState('transactions');
  const [query, setQuery] = useState('');
  const [advancedFilters, setAdvancedFilters] = useState({
    customer_email: '',
    processor_transaction_id: '',
    order_id: '',
    amount_exact: '',
    date_range_days: '30'
  });
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [showAdvanced, setShowAdvanced] = useState(false);

  const searchTypes = [
    { value: 'transactions', label: '💳 Transactions', endpoint: '/transactions/search' },
    { value: 'customers', label: '👥 Customers', endpoint: '/customers/search' },
    { value: 'subscriptions', label: '📋 Subscriptions', endpoint: '/subscriptions/search' }
  ];

  const handleSearch = async (e) => {
    e.preventDefault();
    
    if (!query.trim() && !advancedFilters.customer_email && !advancedFilters.processor_transaction_id) {
      setError('Please enter a search term or use advanced filters');
      return;
    }

    try {
      setLoading(true);
      setError('');

      const selectedType = searchTypes.find(t => t.value === searchType);
      
      // Build request body with search parameters
      const searchParams = {
        search_text: query.trim(),
        limit: 100,
        ...advancedFilters
      };

      // Remove empty values
      Object.keys(searchParams).forEach(key => {
        if (!searchParams[key]) delete searchParams[key];
      });

      const api = await apiReady;
      const response = await api.postWithLog(selectedType.endpoint, searchParams,
          `${import.meta.url.split('/').pop()}`);
      
      if (response.data.success) {
        setResults(response.data.data.results || []);
      } else {
        setError(response.data.error || 'Search failed');
      }
    } catch (err) {
      console.error('Search error:', err);
      setError(err.response?.data?.error || 'Search failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleFilterChange = (e) => {
    const { name, value } = e.target;
    setAdvancedFilters(prev => ({ ...prev, [name]: value }));
  };

  const clearSearch = () => {
    setQuery('');
    setAdvancedFilters({
      customer_email: '',
      processor_transaction_id: '',
      order_id: '',
      amount_exact: '',
      date_range_days: '30'
    });
    setResults([]);
    setError('');
  };

  const formatResultData = (result) => {
    if (searchType === 'transactions') {
      return {
        id: result.transaction_id,
        primary: `Transaction: ${result.transaction_id}`,
        secondary: `${result.customer_name || result.customer_id} - ${result.currency} ${result.amount}`,
        status: result.status,
        date: result.created_at
      };
    } else if (searchType === 'customers') {
      return {
        id: result.customer_id,
        primary: result.company_name || result.customer_id,
        secondary: result.email,
        status: result.status || 'active',
        date: result.created_at
      };
    } else if (searchType === 'subscriptions') {
      return {
        id: result.customer_id + '-' + result.app_key,
        primary: `${result.company_name || result.customer_id} - ${result.app_name || result.app_key}`,
        secondary: `License: ${result.license_tier || 'N/A'}`,
        status: result.status,
        date: result.subscription_start_date
      };
    }
    return result;
  };

  return (
    <div className="content-wrapper">
      <div className="page-header primary">
        <h1>🔍 Search</h1>
        <p>Find transactions, customers, and subscriptions</p>
      </div>

      {error && (
        <div className="alert alert-danger">
          <strong>Error:</strong> {error}
          <button onClick={() => setError('')} style={{ background: 'none', border: 'none', float: 'right', cursor: 'pointer', fontSize: '20px' }}>×</button>
        </div>
      )}

      {/* Search Form Card */}
      <div className="card">
        <div className="card-section">
          <h2>🔎 Search Criteria</h2>
          
          <form onSubmit={handleSearch}>
            {/* Search Type Selector */}
            <div className="search-type-selector" style={{ marginBottom: '20px' }}>
              {searchTypes.map(type => (
                <label key={type.value} style={{ marginRight: '20px', cursor: 'pointer' }}>
                  <input 
                    type="radio" 
                    value={type.value} 
                    checked={searchType === type.value}
                    onChange={(e) => setSearchType(e.target.value)}
                    style={{ marginRight: '8px' }}
                  />
                  {type.label}
                </label>
              ))}
            </div>

            {/* Main Search Input */}
            <div className="form-group">
              <label htmlFor="search_query">Search Text</label>
              <input
                id="search_query"
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder={`Search ${searchType} by name, email, ID, or transaction details...`}
                className="form-control"
              />
              <small style={{ color: '#666', display: 'block', marginTop: '5px' }}>
                Search across multiple fields including names, emails, IDs, and descriptions
              </small>
            </div>

            {/* Advanced Filters Toggle */}
            <div style={{ marginBottom: '15px' }}>
              <button 
                type="button"
                onClick={() => setShowAdvanced(!showAdvanced)}
                className="btn btn-sm btn-secondary"
              >
                {showAdvanced ? '▼ Hide Advanced Filters' : '▶ Show Advanced Filters'}
              </button>
            </div>

            {/* Advanced Filters */}
            {showAdvanced && (
              <div style={{ marginBottom: '20px', padding: '15px', background: '#f8f9fa', borderRadius: '4px' }}>
                <h4 style={{ marginTop: '0', marginBottom: '15px', fontSize: '16px' }}>Advanced Filters</h4>
                <div className="form-grid">
                  <div className="form-group">
                    <label htmlFor="customer_email">Customer Email</label>
                    <input
                      id="customer_email"
                      type="email"
                      name="customer_email"
                      value={advancedFilters.customer_email}
                      onChange={handleFilterChange}
                      placeholder="exact@email.com"
                      className="form-control"
                    />
                  </div>

                  <div className="form-group">
                    <label htmlFor="processor_transaction_id">Processor Transaction ID</label>
                    <input
                      id="processor_transaction_id"
                      type="text"
                      name="processor_transaction_id"
                      value={advancedFilters.processor_transaction_id}
                      onChange={handleFilterChange}
                      placeholder="proc_12345"
                      className="form-control"
                    />
                  </div>

                  <div className="form-group">
                    <label htmlFor="order_id">Order ID</label>
                    <input
                      id="order_id"
                      type="text"
                      name="order_id"
                      value={advancedFilters.order_id}
                      onChange={handleFilterChange}
                      placeholder="ORD-12345"
                      className="form-control"
                    />
                  </div>

                  <div className="form-group">
                    <label htmlFor="amount_exact">Exact Amount</label>
                    <input
                      id="amount_exact"
                      type="number"
                      name="amount_exact"
                      value={advancedFilters.amount_exact}
                      onChange={handleFilterChange}
                      placeholder="99.99"
                      step="0.01"
                      className="form-control"
                    />
                  </div>

                  <div className="form-group">
                    <label htmlFor="date_range_days">Date Range (days)</label>
                    <select
                      id="date_range_days"
                      name="date_range_days"
                      value={advancedFilters.date_range_days}
                      onChange={handleFilterChange}
                      className="form-control"
                    >
                      <option value="7">Last 7 days</option>
                      <option value="30">Last 30 days</option>
                      <option value="90">Last 90 days</option>
                      <option value="180">Last 6 months</option>
                      <option value="365">Last year</option>
                    </select>
                  </div>
                </div>
              </div>
            )}

            {/* Action Buttons */}
            <div style={{ display: 'flex', gap: '10px' }}>
              <button 
                type="submit" 
                className="btn btn-primary" 
                disabled={loading}
              >
                {loading ? '🔄 Searching...' : '🔍 Search'}
              </button>
              <button 
                type="button" 
                onClick={clearSearch} 
                className="btn btn-secondary"
                disabled={loading}
              >
                🧹 Clear
              </button>
            </div>
          </form>
        </div>
      </div>

      {/* Results Card */}
      {loading && (
        <div style={{ textAlign: 'center', padding: '40px' }}>
          <div className="loading-spinner">🔄 Searching...</div>
        </div>
      )}

      {!loading && results.length > 0 && (
        <div className="card">
          <div className="card-section">
            <h2>📋 Search Results ({results.length})</h2>
            <div className="results-list">
              {results.map((result, idx) => {
                const formatted = formatResultData(result);
                return (
                  <div key={formatted.id || idx} className="result-item">
                    <div className="result-header">
                      <strong>{formatted.primary}</strong>
                      {formatted.status && (
                        <span className={`badge badge-${formatted.status === 'active' || formatted.status === 'completed' ? 'success' : 'secondary'}`}>
                          {formatted.status}
                        </span>
                      )}
                    </div>
                    <div className="result-details">
                      <p>{formatted.secondary}</p>
                      {formatted.date && (
                        <small style={{ color: '#666' }}>
                          {new Date(formatted.date).toLocaleString()}
                        </small>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {!loading && results.length === 0 && (query || advancedFilters.customer_email) && (
        <div className="card">
          <div className="card-section" style={{ textAlign: 'center', padding: '40px' }}>
            <p style={{ fontSize: '48px', margin: '0 0 20px 0' }}>🔍</p>
            <p style={{ color: '#666' }}>No results found matching your search criteria.</p>
            <button onClick={clearSearch} className="btn btn-secondary" style={{ marginTop: '10px' }}>
              Try a different search
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default SearchInterface;
