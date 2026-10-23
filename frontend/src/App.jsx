import React, { useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import { AssessmentProvider } from './context/AssessmentContext';
import PrivateRoute from './components/PrivateRoute';
import Navbar from './components/Navbar';
import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';
import AssessmentPage from './pages/AssessmentPage';
import ResultsPage from './pages/ResultsPage';
import FinalResultPage from './pages/FinalResultPage';
import HistoryPage from './pages/HistoryPage';
import { fetchWithAuth } from './api';
import './App.css';

/**
 * Hydrates the authenticated user's profile from the backend
 * if a token exists but no user profile is stored yet.
 */
function ProfileHydrator() {
  const { token, user, updateUser } = useAuth();

  useEffect(() => {
    if (!token) return;
    // Only fetch if we don't already have the user profile in memory
    if (user?.email) return;

    fetchWithAuth('/auth/me')
      .then((profile) => {
        if (profile) updateUser(profile);
      })
      .catch(() => {
        // Silently ignore — token may have just expired; auth-error event handles cleanup
      });
  }, [token]); // eslint-disable-line react-hooks/exhaustive-deps

  return null;
}

function App() {
  return (
    <AuthProvider>
      <AssessmentProvider>
        <BrowserRouter>
          <ProfileHydrator />
          <div className="app-layout">
            <Navbar />
            <main className="main-content container">
              <Routes>
                <Route path="/login" element={<LoginPage />} />
                <Route
                  path="/dashboard"
                  element={<PrivateRoute><DashboardPage /></PrivateRoute>}
                />
                <Route
                  path="/assessment/:skill"
                  element={<PrivateRoute><AssessmentPage /></PrivateRoute>}
                />
                <Route
                  path="/assessment"
                  element={<PrivateRoute><AssessmentPage /></PrivateRoute>}
                />
                <Route
                  path="/results/:skill"
                  element={<PrivateRoute><ResultsPage /></PrivateRoute>}
                />
                <Route
                  path="/results/attempt/:attemptId"
                  element={<PrivateRoute><ResultsPage /></PrivateRoute>}
                />
                <Route
                  path="/results"
                  element={<PrivateRoute><ResultsPage /></PrivateRoute>}
                />
                <Route
                  path="/recommendation"
                  element={<PrivateRoute><FinalResultPage /></PrivateRoute>}
                />
                <Route path="/final-results" element={<Navigate to="/recommendation" replace />} />
                <Route
                  path="/history"
                  element={<PrivateRoute><HistoryPage /></PrivateRoute>}
                />
                <Route path="/" element={<Navigate to="/dashboard" replace />} />
                <Route path="*" element={<Navigate to="/dashboard" replace />} />
              </Routes>
            </main>
          </div>
        </BrowserRouter>
      </AssessmentProvider>
    </AuthProvider>
  );
}

export default App;
