const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const headers = () => ({
  'Content-Type': 'application/json',
});

export const api = {
  get: async (path) => {
    const res = await fetch(`${API_URL}${path}`, { headers: headers() });
    if (!res.ok) throw new Error(`${path} → ${res.status}`);
    return res.json();
  },
  post: async (path, body) => {
    const res = await fetch(`${API_URL}${path}`, {
      method: 'POST',
      headers: headers(),
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(`${path} → ${res.status}`);
    return res.json();
  },
};

// Typed endpoint helpers
export const fetchAccounts       = () => api.get('/api/paper/accounts');
export const fetchPositions      = () => api.get('/api/trading/v2/live-positions');
export const fetchEngineStatus   = () => api.get('/api/engines/status');
export const fetchRegime         = () => api.get('/api/regime/global');
export const fetchTradingStats   = () => api.get('/api/trading/v2/stats');
export const fetchClosedTrades   = () => api.get('/api/trading/v2/closed');
export const fetchOpenTrades     = () => api.get('/api/trading/v2/open');
export const fetchEquityCurve    = (days = 30) => api.get(`/api/analytics/equity-curve?days=${days}`);
export const fetchPerformance    = () => api.get('/api/analytics/performance');
export const fetchSystemHealth   = () => api.get('/api/system/health');
export const toggleEngine        = (name, active) => api.post(`/api/engines/${name}/toggle`, { active });
export const killSwitch          = () => api.post('/api/system/kill-switch', {});
export const fetchSettings       = () => api.get('/api/trading/v2/settings');
export const fetchGovernance     = () => api.get('/api/engine/governance');
