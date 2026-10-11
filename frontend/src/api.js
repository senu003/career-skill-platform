export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

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
        errorMsg = errorData.detail.map(err => err.msg || JSON.stringify(err)).join(', ');
      } else if (errorData.detail) {
        errorMsg = JSON.stringify(errorData.detail);
      }
    } catch (e) {
      // JSON parse failed
    }
    const err = new Error(errorMsg);
    err.status = response.status;
    throw err;
  }

  return response.json();
}
