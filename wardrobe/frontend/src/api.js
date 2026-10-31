export const api = async (path, opts = {}) => {
  const headers = opts.headers || {};
  
  // Auto-set Content-Type for JSON unless FormData
  if (opts.body && !(opts.body instanceof FormData) && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json';
  }

  const response = await fetch(path, {
    ...opts,
    headers,
    credentials: 'include'
  });

  if (response.status === 401) {
    // Pages a logged-out visitor must reach; redirecting them would be a loop.
    const publicPaths = ['/login', '/signup', '/forgot', '/reset'];
    if (!publicPaths.some((p) => window.location.pathname.startsWith(p))) {
      window.location.href = '/login';
    }
    const errData = await response.json().catch(() => ({ detail: 'Not authenticated' }));
    throw new Error(errData.detail || 'Not authenticated');
  }

  if (!response.ok) {
    const errData = await response.json().catch(() => ({ detail: 'Request failed' }));
    throw new Error(errData.detail || `Request failed with status ${response.status}`);
  }

  return response.json();
};
