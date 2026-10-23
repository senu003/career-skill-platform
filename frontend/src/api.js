export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

/**
 * Core authenticated fetch wrapper.
 * - Attaches Bearer token from sessionStorage
 * - Dispatches 'auth-error' event on 401/403 so AuthContext can clear state
 * - Parses FastAPI error detail payloads into human-readable strings
 */
export async function fetchWithAuth(url, options = {}) {
  const token = sessionStorage.getItem('token');
  const headers = new Headers(options.headers || {});

  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  const response = await fetch(`${API_BASE_URL}${url}`, {
    ...options,
    headers,
  });

  if (response.status === 401 || response.status === 403) {
    sessionStorage.removeItem('token');
    sessionStorage.removeItem('user');
    window.dispatchEvent(new Event('auth-error'));
  }

  if (!response.ok) {
    let errorMsg = response.status === 502
      ? 'The AI analysis service is temporarily unavailable (502 Bad Gateway). Please try again in a few moments.'
      : 'An error occurred';
    try {
      const errorData = await response.json();
      if (typeof errorData.detail === 'string') {
        errorMsg = errorData.detail;
      } else if (Array.isArray(errorData.detail)) {
        errorMsg = errorData.detail.map((err) => err.msg || JSON.stringify(err)).join(', ');
      } else if (errorData.detail) {
        errorMsg = JSON.stringify(errorData.detail);
      }
    } catch {
      // JSON parse failed — use status-based message
    }
    const err = new Error(errorMsg);
    err.status = response.status;
    throw err;
  }

  return response.json();
}

/**
 * POST /auth/login  — standard email/password
 */
export async function loginWithPassword(email, password) {
  const formData = new URLSearchParams();
  formData.append('username', email);
  formData.append('password', password);

  const response = await fetch(`${API_BASE_URL}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: formData,
  });

  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.detail || 'Invalid email or password.');
  }

  return response.json(); // { access_token, token_type, user }
}

/**
 * POST /auth/register  — email/password registration
 */
export async function registerWithPassword(name, email, password) {
  const response = await fetch(`${API_BASE_URL}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, email, password }),
  });

  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.detail || 'Registration failed.');
  }

  return response.json(); // { access_token, token_type, user }
}

/**
 * POST /auth/google  — Google ID token exchange
 */
export async function loginWithGoogle(credential) {
  const response = await fetch(`${API_BASE_URL}/auth/google`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ credential }),
  });

  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.detail || 'Google login failed.');
  }

  return response.json(); // { access_token, token_type, user }
}

/**
 * POST /auth/demo-login  — Instant candidate demo login
 */
export async function demoLogin() {
  const response = await fetch(`${API_BASE_URL}/auth/demo-login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  });

  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.detail || 'Demo login failed.');
  }

  return response.json(); // { access_token, token_type, user }
}

/**
 * POST /auth/forgot-password
 */
export async function forgotPassword(email) {
  const response = await fetch(`${API_BASE_URL}/auth/forgot-password`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email }),
  });

  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.detail || 'Request failed.');
  }

  return response.json();
}

/**
 * POST /auth/reset-password
 */
export async function resetPassword(token, newPassword) {
  const response = await fetch(`${API_BASE_URL}/auth/reset-password`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token, new_password: newPassword }),
  });

  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.detail || 'Password reset failed.');
  }

  return response.json();
}
