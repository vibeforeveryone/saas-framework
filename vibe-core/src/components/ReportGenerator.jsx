/*
 * Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
 * Author: Christopher Niven
 */
import React, { useState } from 'react';
import { apiReady } from '../api/config';  // NEW: apiReady is a Promise that resolves to the configured axios instance

import './ReportGenerator.css';

const ReportGenerator = () => {
  const [reportType, setReportType] = useState('transactions');
  const [dateRange, setDateRange] = useState({
    start: '',
    end: ''
  });
  const [format, setFormat] = useState('csv');
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const reportTypes = [
    { value: 'transactions', label: '💳 Transactions Report', description: 'Payment transaction history with amounts and statuses' },
    { value: 'subscriptions', label: '📋 Subscriptions Report', description: 'Customer subscriptions including status and license tiers' },
    { value: 'customers', label: '👥 Customers Report', description: 'Customer information with contact details and revenue' },
    { value: 'revenue', label: '💰 Revenue Report', description: 'Revenue breakdown by application and license tier' },
    { value: 'usage', label: '📊 Usage Analytics', description: 'Detailed usage statistics by customer and application' },
    { value: 'disputes', label: '⚠️ Disputes Report', description: 'Chargeback and dispute tracking with resolutions' }
  ];

  const exportFormats = [
    { value: 'csv', label: 'CSV (Comma-Separated Values)' },
    { value: 'xlsx', label: 'Excel (XLSX)' },
    { value: 'json', label: 'JSON' }
  ];

  const generateReport = async () => {
    if (!dateRange.start || !dateRange.end) {
      setError('Please select both start and end dates');
      return;
    }

    try {
      setGenerating(true);
      setError('');
      setSuccess('');

      const api = await apiReady;
      const response = await api.postWithLog('/export', {
        report_type: reportType,
        start_date: dateRange.start,
        end_date: dateRange.end,
        format: format
      },
      `${import.meta.url.split('/').pop()}`);
      
      if (response.data.success) {
        setSuccess(`Report generated successfully! ${response.data.data.message || ''}`);
        
        // Handle download URL from response
        if (response.data.data.download_url) {
          window.open(response.data.data.download_url, '_blank');
        } 
        // Handle direct data download
        else if (response.data.data.report_data) {
          const mimeTypes = {
            csv: 'text/csv',
            xlsx: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            json: 'application/json'
          };

          const blob = new Blob([response.data.data.report_data], { type: mimeTypes[format] || 'text/plain' });
          const url = window.URL.createObjectURL(blob);
          const a = document.createElement('a');
          a.href = url;
          a.download = `${reportType}-report-${dateRange.start}-to-${dateRange.end}.${format}`;
          document.body.appendChild(a);
          a.click();
          document.body.removeChild(a);
          window.URL.revokeObjectURL(url);
        }
        // Handle S3 URL
        else if (response.data.data.file_url) {
          window.open(response.data.data.file_url, '_blank');
        }
      } else {
        setError(response.data.error || 'Report generation failed');
      }
    } catch (err) {
      console.error('Report generation error:', err);
      setError(err.response?.data?.error || 'Report generation failed. Please try again.');
    } finally {
      setGenerating(false);
    }
  };

  const handleDateChange = (e) => {
    const { name, value } = e.target;
    setDateRange(prev => ({ ...prev, [name]: value }));
  };

  const setQuickDateRange = (days) => {
    const end = new Date();
    const start = new Date();
    start.setDate(start.getDate() - days);
    
    setDateRange({
      start: start.toISOString().split('T')[0],
      end: end.toISOString().split('T')[0]
    });
  };

  const selectedReportInfo = reportTypes.find(r => r.value === reportType);

  return (
    <div className="content-wrapper">
      <div className="page-header primary">
        <h1>📊 Report Generator</h1>
        <p>Generate and download custom reports</p>
      </div>

      {error && (
        <div className="alert alert-danger">
          <strong>Error:</strong> {error}
          <button onClick={() => setError('')} style={{ background: 'none', border: 'none', float: 'right', cursor: 'pointer', fontSize: '20px' }}>×</button>
        </div>
      )}

      {success && (
        <div className="alert alert-success">
          <strong>Success!</strong> {success}
          <button onClick={() => setSuccess('')} style={{ background: 'none', border: 'none', float: 'right', cursor: 'pointer', fontSize: '20px' }}>×</button>
        </div>
      )}

      {/* Configuration Card */}
      <div className="card">
        <div className="card-section">
          <h2>⚙️ Report Configuration</h2>
          
          <div className="form-grid">
            <div className="form-group">
              <label htmlFor="report_type">Report Type <span className="required">*</span></label>
              <select 
                id="report_type"
                value={reportType} 
                onChange={(e) => setReportType(e.target.value)}
                className="form-control"
              >
                {reportTypes.map(type => (
                  <option key={type.value} value={type.value}>
                    {type.label}
                  </option>
                ))}
              </select>
              {selectedReportInfo && (
                <small style={{ color: '#666', display: 'block', marginTop: '5px' }}>
                  {selectedReportInfo.description}
                </small>
              )}
            </div>

            <div className="form-group">
              <label htmlFor="format">Export Format</label>
              <select 
                id="format"
                value={format} 
                onChange={(e) => setFormat(e.target.value)}
                className="form-control"
              >
                {exportFormats.map(fmt => (
                  <option key={fmt.value} value={fmt.value}>
                    {fmt.label}
                  </option>
                ))}
              </select>
            </div>

            <div className="form-group">
              <label htmlFor="start_date">Start Date <span className="required">*</span></label>
              <input
                id="start_date"
                type="date"
                name="start"
                value={dateRange.start}
                onChange={handleDateChange}
                className="form-control"
                required
              />
            </div>

            <div className="form-group">
              <label htmlFor="end_date">End Date <span className="required">*</span></label>
              <input
                id="end_date"
                type="date"
                name="end"
                value={dateRange.end}
                onChange={handleDateChange}
                className="form-control"
                required
              />
            </div>
          </div>

          {/* Quick Date Range Buttons */}
          <div style={{ marginTop: '15px', marginBottom: '15px' }}>
            <label style={{ display: 'block', marginBottom: '8px', fontSize: '14px', fontWeight: '500' }}>
              Quick Select:
            </label>
            <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
              <button type="button" className="btn btn-sm btn-secondary" onClick={() => setQuickDateRange(7)}>
                Last 7 Days
              </button>
              <button type="button" className="btn btn-sm btn-secondary" onClick={() => setQuickDateRange(30)}>
                Last 30 Days
              </button>
              <button type="button" className="btn btn-sm btn-secondary" onClick={() => setQuickDateRange(90)}>
                Last 90 Days
              </button>
              <button type="button" className="btn btn-sm btn-secondary" onClick={() => setQuickDateRange(365)}>
                Last Year
              </button>
            </div>
          </div>

          <div style={{ marginTop: '20px' }}>
            <button 
              className="btn btn-primary" 
              onClick={generateReport} 
              disabled={generating || !dateRange.start || !dateRange.end}
            >
              {generating ? '🔄 Generating Report...' : '📥 Generate & Download Report'}
            </button>
          </div>
        </div>
      </div>

      {/* Report Descriptions */}
      <div className="card">
        <div className="card-section">
          <h2>📋 Available Reports</h2>
          <div className="report-descriptions">
            {reportTypes.map(type => (
              <div key={type.value} className="report-desc-item">
                <h4>{type.label}</h4>
                <p>{type.description}</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Export Format Info */}
      <div className="card">
        <div className="card-section">
          <h2>ℹ️ Export Format Information</h2>
          <div className="report-descriptions">
            <div className="report-desc-item">
              <h4>CSV (Comma-Separated Values)</h4>
              <p>Compatible with Excel, Google Sheets, and most spreadsheet applications. Best for data analysis and importing into other systems.</p>
            </div>
            <div className="report-desc-item">
              <h4>Excel (XLSX)</h4>
              <p>Native Excel format with formatting, multiple sheets, and formulas. Best for professional reports and presentations.</p>
            </div>
            <div className="report-desc-item">
              <h4>JSON</h4>
              <p>Machine-readable format for programmatic access. Best for developers and API integrations.</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ReportGenerator;
