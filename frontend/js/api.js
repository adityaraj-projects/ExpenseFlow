/**
 * ExpenseFlow - Centralized API Client with JWT Interceptors
 */

/**
 * Resolves the backend API base URL.
 * Priority:
 * 1. window.EXPENSEFLOW_API_URL (injected via deployment environment / script tag)
 * 2. localStorage.getItem('expenseflow_api_url') (optional client override)
 * 3. Fallback for decoupled local dev servers (Live Server / Vite on ports 5500, 3000, 5173, 8080) -> 'http://127.0.0.1:8000/api'
 * 4. Relative '/api' (monolithic deployment or reverse proxy where FastAPI serves the app)
 */
function getApiBaseUrl() {
  if (typeof window !== 'undefined' && window.EXPENSEFLOW_API_URL) {
    return window.EXPENSEFLOW_API_URL.replace(/\/+$/, '');
  }
  if (typeof localStorage !== 'undefined') {
    const customUrl = localStorage.getItem('expenseflow_api_url');
    if (customUrl) {
      return customUrl.replace(/\/+$/, '');
    }
  }
  if (typeof window !== 'undefined' && window.location) {
    const port = window.location.port;
    const hostname = window.location.hostname;
    const isDevClientPort = ['5500', '3000', '5173', '8080'].includes(port);
    const isLocalhost = hostname === 'localhost' || hostname === '127.0.0.1';
    if (isDevClientPort && isLocalhost) {
      return 'http://127.0.0.1:8000/api';
    }
    if (isLocalhost && port === '8000') {
      return '/api';
    }
  }
  // Production Cloud Backend on Render
  return 'https://expenseflow-3zl0.onrender.com/api';
}

const API_CONFIG = {
  get BASE_URL() {
    return getApiBaseUrl();
  }
};

class ApiClient {
  /**
   * Internal request dispatcher
   */
  static async request(endpoint, options = {}) {
    const url = endpoint.startsWith('http') ? endpoint : `${API_CONFIG.BASE_URL}${endpoint}`;

    const headers = {
      'Content-Type': 'application/json',
      ...options.headers
    };

    // Attach JWT Bearer Token if logged in
    const token = localStorage.getItem('expenseflow_token');
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    try {
      const response = await fetch(url, {
        ...options,
        headers
      });

      // Session expired or unauthenticated
      if (response.status === 401) {
        localStorage.removeItem('expenseflow_token');
        localStorage.removeItem('expenseflow_user');

        const currentPath = window.location.pathname;
        const isAuthPage = currentPath.includes('login.html') || currentPath.includes('register.html') || currentPath.endsWith('index.html') || currentPath === '/';

        if (!isAuthPage) {
          window.location.href = '/pages/login.html?session_expired=true';
        }
        throw new Error('Session expired. Please log in again.');
      }

      // Handle 204 No Content
      if (response.status === 204) {
        return null;
      }

      const data = await response.json();

      if (!response.ok) {
        const errorMsg = data.message || data.detail || (Array.isArray(data.errors) ? data.errors[0] : 'An unexpected error occurred.');
        throw new Error(errorMsg);
      }

      return data;
    } catch (err) {
      console.error(`[API Error] ${options.method || 'GET'} ${endpoint}:`, err.message);
      throw err;
    }
  }

  static get(endpoint, params = {}) {
    const query = new URLSearchParams();
    Object.entries(params).forEach(([key, val]) => {
      if (val !== undefined && val !== null && val !== '') {
        query.append(key, val);
      }
    });

    const queryString = query.toString();
    const fullEndpoint = queryString ? `${endpoint}?${queryString}` : endpoint;
    return this.request(fullEndpoint, { method: 'GET' });
  }

  static post(endpoint, body) {
    return this.request(endpoint, {
      method: 'POST',
      body: JSON.stringify(body)
    });
  }

  static put(endpoint, body) {
    return this.request(endpoint, {
      method: 'PUT',
      body: JSON.stringify(body)
    });
  }

  static patch(endpoint, body) {
    const options = { method: 'PATCH' };
    if (body !== undefined && body !== null) {
      options.body = JSON.stringify(body);
    }
    return this.request(endpoint, options);
  }

  static delete(endpoint) {
    return this.request(endpoint, { method: 'DELETE' });
  }
}
