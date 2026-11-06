import React, { createContext, useState, useEffect, useContext, useCallback } from 'react';
import { API_BASE_URL } from '../api';

const AuthContext = createContext(null);

/**
 * Decodes a JWT payload without verifying the signature.
 * Used only to read exp / user data for client-side display.
 */
function decodeJwtPayload(token) {
  try {
    const base64 = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
    const json = decodeURIComponent(
      atob(base64)
        .split('')
        .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
        .join('')
    );
    return JSON.parse(json);
  } catch {
    return null;
  }
}

/**
 * Check if a stored token is expired (with a 60-second buffer).
 */
function isTokenExpired(token) {
  const payload = decodeJwtPayload(token);
  if (!payload?.exp) return true;
  return Date.now() / 1000 > payload.exp - 60;
}

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => {
    const stored = sessionStorage.getItem('token');
    if (stored && isTokenExpired(stored)) {
      sessionStorage.removeItem('token');
      return null;
    }
    return stored;
  });

  const [user, setUser] = useState(() => {
    try {
      const raw = sessionStorage.getItem('user');
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  });

  // Listen for 401 events dispatched from fetchWithAuth
  useEffect(() => {
    const handleAuthError = () => {
      setToken(null);
      setUser(null);
      sessionStorage.removeItem('token');
      sessionStorage.removeItem('user');
    };
    window.addEventListener('auth-error', handleAuthError);
    return () => window.removeEventListener('auth-error', handleAuthError);
  }, []);

  // Check token expiry on tab focus
  useEffect(() => {
    const onFocus = () => {
      if (token && isTokenExpired(token)) {
        setToken(null);
        setUser(null);
        sessionStorage.removeItem('token');
        sessionStorage.removeItem('user');
        window.dispatchEvent(new Event('auth-error'));
      }
    };
    window.addEventListener('focus', onFocus);
    return () => window.removeEventListener('focus', onFocus);
  }, [token]);

  const login = useCallback((newToken, userProfile = null) => {
    sessionStorage.setItem('token', newToken);
    setToken(newToken);

    // Fresh login always clears previous analysis session
    sessionStorage.removeItem('career_platform_analysis');
    localStorage.removeItem('career_platform_analysis');

    // Extract basic profile from token if not explicitly provided
    if (userProfile) {
      sessionStorage.setItem('user', JSON.stringify(userProfile));
      setUser(userProfile);
    } else {
      const payload = decodeJwtPayload(newToken);
      if (payload) {
        const profile = { id: payload.sub };
        sessionStorage.setItem('user', JSON.stringify(profile));
        setUser(profile);
      }
    }
  }, []);

  const logout = useCallback(async () => {
    const curToken = sessionStorage.getItem('token');
    if (curToken) {
      try {
        await fetch(`${API_BASE_URL}/auth/logout`, {
          method: 'POST',
          headers: {
            Authorization: `Bearer ${curToken}`,
          },
        });
      } catch {
        // Safe to ignore network or server failure during client logout
      }
    }
    sessionStorage.removeItem('token');
    sessionStorage.removeItem('user');
    sessionStorage.removeItem('career_platform_analysis');
    localStorage.removeItem('career_platform_analysis');
    setToken(null);
    setUser(null);
  }, []);

  const updateUser = useCallback((updatedProfile) => {
    setUser((prev) => {
      const merged = { ...prev, ...updatedProfile };
      sessionStorage.setItem('user', JSON.stringify(merged));
      return merged;
    });
  }, []);

  const isAuthenticated = !!token && !isTokenExpired(token);

  return (
    <AuthContext.Provider value={{ token, user, isAuthenticated, login, logout, updateUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>');
  return ctx;
}
