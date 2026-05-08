/*
 * Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
 * Author: Christopher Niven
 */
import React, { createContext, useState, useContext, useEffect } from 'react';

const ConfigContext = createContext();

export const ConfigProvider = ({ children }) => {
  const [isConfigured, setIsConfigured] = useState(false);
  const [apiConfig, setApiConfig] = useState(null);

  useEffect(() => {
    checkConfiguration();
  }, []);

  const checkConfiguration = () => {
    const config = localStorage.getItem('apiConfig');
    if (config) {
      try {
        const parsedConfig = JSON.parse(config);
        setApiConfig(parsedConfig);
        setIsConfigured(true);
      } catch (err) {
        console.error('Error parsing API config:', err);
        setIsConfigured(false);
        setApiConfig(null);
      }
    } else {
      setIsConfigured(false);
      setApiConfig(null);
    }
  };

  const updateConfiguration = (config) => {
    try {
      localStorage.setItem('apiConfig', JSON.stringify(config));
      setApiConfig(config);
      setIsConfigured(true);
    } catch (err) {
      console.error('Error saving API config:', err);
      throw err;
    }
  };

  const clearConfiguration = () => {
    localStorage.removeItem('apiConfig');
    setApiConfig(null);
    setIsConfigured(false);
  };

  const getApiBaseUrl = () => {
    if (apiConfig) {
      const { apiPath, awsRegion, stageName } = apiConfig;
      return `https://${apiPath}.execute-api.${awsRegion}.amazonaws.com/${stageName}`;
    }
    return null;
  };

  return (
    <ConfigContext.Provider
      value={{
        isConfigured,
        apiConfig,
        updateConfiguration,
        clearConfiguration,
        checkConfiguration,
        getApiBaseUrl
      }}
    >
      {children}
    </ConfigContext.Provider>
  );
};

export const useConfig = () => {
  const context = useContext(ConfigContext);
  if (!context) {
    throw new Error('useConfig must be used within a ConfigProvider');
  }
  return context;
};

export default ConfigContext;
