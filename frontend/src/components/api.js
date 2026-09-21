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
