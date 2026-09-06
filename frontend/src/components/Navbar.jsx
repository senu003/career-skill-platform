import React from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useAssessment } from '../context/AssessmentContext';

export default function Navbar() {
  const { isAuthenticated, logout } = useAuth();
  const { clearAnalysis } = useAssessment();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    clearAnalysis();
    navigate('/login');
  };

  if (!isAuthenticated) return null;

  return (
    <nav className="navbar">
      <div className="nav-brand" onClick={() => navigate('/dashboard')}>
        <span>CareerSkill</span>
        <span className="nav-brand-badge">AI</span>
      </div>

      <div className="nav-links">
        <NavLink 
          to="/dashboard" 
          className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
        >
          Dashboard
        </NavLink>
        <NavLink 
          to="/recommendation" 
          className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
        >
          Recommendation
        </NavLink>
        <NavLink 
          to="/history" 
          className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
        >
          History & Profile
        </NavLink>
        <button onClick={handleLogout} className="btn btn-outline" style={{ padding: '0.35rem 0.85rem', fontSize: '0.85rem' }}>
          Logout
        </button>
      </div>
    </nav>
  );
}

