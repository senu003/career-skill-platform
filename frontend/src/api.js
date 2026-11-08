export const API_BASE_URL = typeof import.meta.env.VITE_API_BASE_URL === 'string'
  ? import.meta.env.VITE_API_BASE_URL
  : (import.meta.env.DEV ? 'http://localhost:8000' : '');

/**
 * Extracts and normalizes structured API error information from response.
 * Preserves backward compatibility while attaching request_id, supportReference,
 * and stable error codes.
 */
export async function parseErrorResponse(response) {
  const requestId =
    response.headers.get('x-request-id') ||
    response.headers.get('X-Request-ID') ||
    null;

  let errorMsg = response.status === 502
    ? 'The AI analysis service is temporarily unavailable (502 Bad Gateway). Please try again in a few moments.'
    : 'An error occurred';
  let errorCode = null;
  let validationErrors = null;

  try {
    const errorData = await response.json();
    if (typeof errorData.detail === 'string') {
      errorMsg = errorData.detail;
    } else if (Array.isArray(errorData.detail)) {
      validationErrors = errorData.detail;
      errorMsg = errorData.detail.map((err) => err.msg || JSON.stringify(err)).join(', ');
    } else if (errorData.detail) {
      errorMsg = JSON.stringify(errorData.detail);
    }

    errorCode = errorData.error_code || errorData.error?.code || null;
    if (errorData.request_id) {
      // Body request_id takes precedence or falls back to header
      // (both should match)
    }
  } catch {
    // Non-JSON response payload
  }

  const err = new Error(errorMsg);
  err.status = response.status;
  err.code = errorCode;
  err.requestId = requestId;
  err.supportReference = requestId;
  err.validationErrors = validationErrors;
  return err;
}

/**
 * Core authenticated fetch wrapper.
 * - Catches network connectivity failures cleanly
 * - Attaches Bearer token from sessionStorage
 * - Dispatches 'auth-error' event on 401/403 with session details
 * - Extracts request ID, stable error codes, and detail messages
 */
export async function fetchWithAuth(url, options = {}) {
  const token = sessionStorage.getItem('token');
  const headers = new Headers(options.headers || {});

  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  let response;
  try {
    response = await fetch(`${API_BASE_URL}${url}`, {
      ...options,
      headers,
    });
  } catch (_networkErr) {
    const err = new Error(
      'Network error: Unable to connect to the server. Please check your connection or try again later.'
    );
    err.status = 0;
    err.isNetworkError = true;
    err.requestId = null;
    err.supportReference = null;
    throw err;
  }

  const requestId =
    response.headers.get('x-request-id') ||
    response.headers.get('X-Request-ID') ||
    null;

  // 401 Unauthorized indicates an expired/invalid session and clears credentials.
  // 403 Forbidden indicates an authorization/permission failure on a specific resource;
  // the user remains authenticated and should not be logged out.
  if (response.status === 401) {
    sessionStorage.removeItem('token');
    sessionStorage.removeItem('user');
    window.dispatchEvent(new CustomEvent('auth-error', {
      detail: { status: response.status, requestId }
    }));
  }

  if (!response.ok) {
    const err = await parseErrorResponse(response);
    throw err;
  }

  return response.json();
}

/**
 * POST /auth/login — standard email/password
 */
export async function loginWithPassword(email, password) {
  const formData = new URLSearchParams();
  formData.append('username', email);
  formData.append('password', password);

  let response;
  try {
    response = await fetch(`${API_BASE_URL}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: formData,
    });
  } catch (_networkErr) {
    const err = new Error('Network error: Unable to connect to the server.');
    err.status = 0;
    err.isNetworkError = true;
    throw err;
  }

  if (!response.ok) {
    const err = await parseErrorResponse(response);
    if (!err.message || err.message === 'An error occurred') {
      err.message = 'Invalid email or password.';
    }
    throw err;
  }

  return response.json(); // { access_token, token_type, user }
}

/**
 * POST /auth/register — email/password registration
 */
export async function registerWithPassword(name, email, password) {
  let response;
  try {
    response = await fetch(`${API_BASE_URL}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, email, password }),
    });
  } catch (_networkErr) {
    const err = new Error('Network error: Unable to connect to the server.');
    err.status = 0;
    err.isNetworkError = true;
    throw err;
  }

  if (!response.ok) {
    const err = await parseErrorResponse(response);
    if (!err.message || err.message === 'An error occurred') {
      err.message = 'Registration failed.';
    }
    throw err;
  }

  return response.json(); // { access_token, token_type, user }
}

/**
 * POST /auth/google — Google ID token exchange
 */
export async function loginWithGoogle(credential) {
  let response;
  try {
    response = await fetch(`${API_BASE_URL}/auth/google`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ credential }),
    });
  } catch (_networkErr) {
    const err = new Error('Network error: Unable to connect to the server.');
    err.status = 0;
    err.isNetworkError = true;
    throw err;
  }

  if (!response.ok) {
    const err = await parseErrorResponse(response);
    if (!err.message || err.message === 'An error occurred') {
      err.message = 'Google login failed.';
    }
    throw err;
  }

  return response.json(); // { access_token, token_type, user }
}

/**
 * POST /auth/demo-login — Instant candidate demo login
 */
export async function demoLogin() {
  let response;
  try {
    response = await fetch(`${API_BASE_URL}/auth/demo-login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    });
  } catch (_networkErr) {
    const err = new Error('Network error: Unable to connect to the server.');
    err.status = 0;
    err.isNetworkError = true;
    throw err;
  }

  if (!response.ok) {
    const err = await parseErrorResponse(response);
    if (!err.message || err.message === 'An error occurred') {
      err.message = 'Demo login failed.';
    }
    throw err;
  }

  return response.json(); // { access_token, token_type, user }
}

/**
 * GET /auth/password-reset/status
 */
export async function getPasswordResetStatus() {
  try {
    const response = await fetch(`${API_BASE_URL}/auth/password-reset/status`);
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      return {
        enabled: false,
        message: data.detail || 'Password reset is currently unavailable in this environment.',
      };
    }
    return await response.json();
  } catch {
    return {
      enabled: false,
      message: 'Password reset service status could not be verified.',
    };
  }
}

/**
 * POST /auth/forgot-password
 */
export async function forgotPassword(email) {
  let response;
  try {
    response = await fetch(`${API_BASE_URL}/auth/forgot-password`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email }),
    });
  } catch (_networkErr) {
    const err = new Error('Network error: Unable to connect to the server.');
    err.status = 0;
    err.isNetworkError = true;
    throw err;
  }

  if (!response.ok) {
    const err = await parseErrorResponse(response);
    if (!err.message || err.message === 'An error occurred') {
      err.message = 'Request failed.';
    }
    throw err;
  }

  return response.json();
}

/**
 * POST /auth/reset-password
 */
export async function resetPassword(token, newPassword) {
  let response;
  try {
    response = await fetch(`${API_BASE_URL}/auth/reset-password`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token, new_password: newPassword }),
    });
  } catch (_networkErr) {
    const err = new Error('Network error: Unable to connect to the server.');
    err.status = 0;
    err.isNetworkError = true;
    throw err;
  }

  if (!response.ok) {
    const err = await parseErrorResponse(response);
    if (!err.message || err.message === 'An error occurred') {
      err.message = 'Password reset failed.';
    }
    throw err;
  }

  return response.json();
}

/**
 * Downloads or previews an uploaded CV file as a blob.
 */
export async function downloadCvFile(cvId, filename) {
  const token = sessionStorage.getItem('token');
  const headers = {};
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  let response;
  try {
    response = await fetch(`${API_BASE_URL}/cv/${cvId}/download`, { headers });
  } catch (_networkErr) {
    const err = new Error('Network error: Unable to download CV file.');
    err.status = 0;
    err.isNetworkError = true;
    throw err;
  }

  if (!response.ok) {
    const err = await parseErrorResponse(response);
    if (!err.message || err.message === 'An error occurred') {
      err.message = 'Failed to download CV file.';
    }
    throw err;
  }

  const blob = await response.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename || 'resume.pdf';
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
}
