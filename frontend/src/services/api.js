import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Holdings API
export const holdingsAPI = {
  getAll: (params = {}) => api.get('/holdings/', { params }),
  getOne: (id) => api.get(`/holdings/${id}`),
  create: (data) => api.post('/holdings/', data),
  update: (id, data) => api.put(`/holdings/${id}`, data),
  delete: (id) => api.delete(`/holdings/${id}`),
  getAccountTypes: () => api.get('/holdings/account-types'),
};

// Transactions API
export const transactionsAPI = {
  getAll: (params = {}) => api.get('/transactions/', { params }),
  getByHolding: (holdingId) => api.get(`/transactions/holding/${holdingId}`),
  create: (data) => api.post('/transactions/', data),
  delete: (id) => api.delete(`/transactions/${id}`),
};

// Prices API
export const pricesAPI = {
  getCurrent: () => api.get('/prices/current'),
  getCached: () => api.get('/prices/cached'),  // Instant response from DB cache
  getBySymbol: (symbol, exchange) => api.get(`/prices/${symbol}`, { params: { exchange } }),
  getHistory: (symbol, exchange, days = 30) => api.get(`/prices/history/${symbol}`, { params: { exchange, days } }),
  refresh: () => api.post('/prices/refresh'),
};

// Analytics API
export const analyticsAPI = {
  // Fast versions use cached prices for instant response
  getPortfolioSummary: (fast = false) => api.get('/analytics/portfolio/summary', { params: { fast } }),
  getAllocation: (fast = false) => api.get('/analytics/allocation', { params: { fast } }),
  getPerformance: (fast = false) => api.get('/analytics/performance', { params: { fast } }),
  getPortfolioValue: (days = 30) => api.get('/analytics/portfolio-value', { params: { days } }),
  getRealizedGains: () => api.get('/analytics/realized-gains'),
  getAccountBreakdown: (fast = true) => api.get('/analytics/account-breakdown', { params: { fast } }),
};

// Snapshots API
export const snapshotsAPI = {
  create: (snapshotDate = null) => api.post('/snapshots/create', { snapshot_date: snapshotDate }),
  getLatest: () => api.get('/snapshots/latest'),
  getByDate: (date) => api.get(`/snapshots/${date}`),
  getHistory: (days = 30) => api.get('/portfolio/history', { params: { days } }),
  backfill: (startDate, endDate = null) => api.post('/snapshots/backfill', null, {
    params: { start_date: startDate, end_date: endDate }
  }),
};

// Import API
export const importAPI = {
  getFormats: () => api.get('/import/formats'),
  preview: (data) => api.post('/import/preview', data),
  import: (data) => api.post('/import/transactions', data),
  uploadPreview: (file, platform, accountType = null) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('platform', platform);
    if (accountType) {
      formData.append('account_type', accountType);
    }
    return api.post('/import/upload/preview', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  uploadImport: (file, platform, accountType = null, skipDuplicates = true) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('platform', platform);
    if (accountType) {
      formData.append('account_type', accountType);
    }
    formData.append('skip_duplicates', skipDuplicates);
    return api.post('/import/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  uploadBulkImport: (files, platform, accountType = null, skipDuplicates = true) => {
    const formData = new FormData();
    files.forEach(file => formData.append('files', file));
    formData.append('platform', platform);
    if (accountType) {
      formData.append('account_type', accountType);
    }
    formData.append('skip_duplicates', skipDuplicates);
    return api.post('/import/upload/bulk', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
};

// Health check
export const healthCheck = () => api.get('/health');

// App status (loading state)
export const appStatus = () => api.get('/status');

export default api;
