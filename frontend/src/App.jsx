import React, { useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import { AssessmentProvider } from './context/AssessmentContext';
import ErrorBoundary from './components/ErrorBoundary';
import PrivateRoute from './components/PrivateRoute';
import Navbar from './components/Navbar';
import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';
import AssessmentPage from './pages/AssessmentPage';
import ResultsPage from './pages/ResultsPage';
import FinalResultPage from './pages/FinalResultPage';
import HistoryPage from './pages/HistoryPage';
import InterviewPrepHub from './pages/interview-prep/InterviewPrepHub';
import SkillAnalysisPage from './pages/interview-prep/SkillAnalysisPage';
import AssessmentReviewPage from './pages/interview-prep/AssessmentReviewPage';
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
    <ErrorBoundary>
      <AuthProvider>
        <AssessmentProvider>
          <BrowserRouter>
            <ProfileHydrator />
            <div className="app-layout">
              <Navbar />
              <main className="main-content container">
                <ErrorBoundary>
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
                      path="/interview-prep"
                      element={<PrivateRoute><InterviewPrepHub /></PrivateRoute>}
                    />
                    <Route
                      path="/interview-prep/skill/:skill"
                      element={<PrivateRoute><SkillAnalysisPage /></PrivateRoute>}
                    />
                    <Route
                      path="/interview-prep/attempt/:attemptId"
                      element={<PrivateRoute><AssessmentReviewPage /></PrivateRoute>}
                    />
                    <Route
                      path="/interview-prep/review/:attemptId"
                      element={<PrivateRoute><AssessmentReviewPage /></PrivateRoute>}
                    />
                    <Route
                      path="/assessment/review/:attemptId"
                      element={<PrivateRoute><AssessmentReviewPage /></PrivateRoute>}
                    />
                    <Route
                      path="/results/:skill"
                      element={<PrivateRoute><ResultsPage /></PrivateRoute>}
                    />
                    <Route
                      path="/results/attempt/:attemptId"
                      element={<PrivateRoute><AssessmentReviewPage /></PrivateRoute>}
                    />
                    <Route
                      path="/results"
                      element={<PrivateRoute><InterviewPrepHub /></PrivateRoute>}
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
                </ErrorBoundary>
              </main>
            </div>
          </BrowserRouter>
        </AssessmentProvider>
      </AuthProvider>
    </ErrorBoundary>
  );
}

export default App;
