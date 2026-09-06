import React, { createContext, useState, useEffect, useContext } from 'react';

const AuthContext = createContext();

export function AuthProvider({ children }) {
  const [token, setToken] = useState(sessionStorage.getItem('token'));

  useEffect(() => {
    const handleAuthError = () => {
      setToken(null);
      sessionStorage.removeItem('token');
    };
    window.addEventListener('auth-error', handleAuthError);
    return () => window.removeEventListener('auth-error', handleAuthError);
  }, []);

  const login = (newToken) => {
    sessionStorage.setItem('token', newToken);
    setToken(newToken);
  };

  const logout = () => {
    sessionStorage.removeItem('token');
    setToken(null);
  };

  const isAuthenticated = !!token;

  return (
    <AuthContext.Provider value={{ token, isAuthenticated, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
