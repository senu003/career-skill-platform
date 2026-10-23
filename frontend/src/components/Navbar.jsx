import React, { useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useAssessment } from '../context/AssessmentContext';
import { fetchWithAuth } from '../api';

export default function Navbar() {
  const { isAuthenticated, user, logout } = useAuth();
  const { clearAnalysis } = useAssessment();
  const navigate = useNavigate();
  const [showDropdown, setShowDropdown] = useState(false);

  if (!isAuthenticated) return null;

  const handleLogout = async () => {
    // Fire-and-forget audit log
    try { await fetchWithAuth('/auth/logout', { method: 'POST' }); } catch { /* ignore */ }
    logout();
    clearAnalysis();
    navigate('/login');
  };

  const initials = user?.name
    ? user.name.split(' ').map((w) => w[0]).join('').toUpperCase().slice(0, 2)
    : '?';

  return (
    <nav className="navbar">
      <div className="nav-brand" onClick={() => navigate('/dashboard')} style={{ cursor: 'pointer' }}>
        <span>CareerSkill</span>
        <span className="nav-brand-badge">AI</span>
      </div>

      <div className="nav-links">
        <NavLink to="/dashboard" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
          Dashboard
        </NavLink>
        <NavLink to="/recommendation" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
          Full Report
        </NavLink>
        <NavLink to="/history" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
          History
        </NavLink>

        {/* User Avatar / Dropdown */}
        <div style={{ position: 'relative' }}>
          <button
            onClick={() => setShowDropdown((p) => !p)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
              background: 'var(--surface-2, rgba(255,255,255,0.08))',
              border: '1.5px solid var(--border-color)',
              borderRadius: '2rem',
              padding: '0.3rem 0.75rem 0.3rem 0.4rem',
              cursor: 'pointer',
              color: 'var(--text-primary)',
              fontWeight: 600,
              fontSize: '0.85rem',
              transition: 'all 0.2s',
            }}
            aria-label="User menu"
          >
            {user?.avatar_url ? (
              <img
                src={user.avatar_url}
                alt={user.name || 'User'}
                style={{ width: '26px', height: '26px', borderRadius: '50%', objectFit: 'cover' }}
                referrerPolicy="no-referrer"
              />
            ) : (
              <div
                style={{
                  width: '26px',
                  height: '26px',
                  borderRadius: '50%',
                  background: 'linear-gradient(135deg, var(--primary-500), var(--primary-700))',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '0.72rem',
                  color: '#fff',
                  fontWeight: 700,
                }}
              >
                {initials}
              </div>
            )}
            <span style={{ maxWidth: '100px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {user?.name || 'Account'}
            </span>
            <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)', marginLeft: '-0.2rem' }}>▾</span>
          </button>

          {showDropdown && (
            <>
              {/* Backdrop */}
              <div
                style={{ position: 'fixed', inset: 0, zIndex: 99 }}
                onClick={() => setShowDropdown(false)}
              />
              <div
                style={{
                  position: 'absolute',
                  right: 0,
                  top: 'calc(100% + 0.5rem)',
                  background: 'var(--surface-1, #1e293b)',
                  border: '1px solid var(--border-color)',
                  borderRadius: '0.6rem',
                  minWidth: '200px',
                  zIndex: 100,
                  boxShadow: '0 8px 30px rgba(0,0,0,0.4)',
                  overflow: 'hidden',
                }}
              >
                {user?.email && (
                  <div style={{ padding: '0.75rem 1rem', borderBottom: '1px solid var(--border-color)' }}>
                    <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', margin: 0 }}>Signed in as</p>
                    <p style={{
                      fontSize: '0.82rem',
                      color: 'var(--text-secondary)',
                      fontWeight: 600,
                      margin: '0.15rem 0 0',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    }}>
                      {user.email}
                    </p>
                    {user.oauth_provider === 'google' && (
                      <span style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '0.25rem',
                        fontSize: '0.7rem',
                        color: '#4ade80',
                        background: 'rgba(34,197,94,0.1)',
                        padding: '0.1rem 0.4rem',
                        borderRadius: '0.25rem',
                        marginTop: '0.3rem',
                      }}>
                        🔗 Google account
                      </span>
                    )}
                  </div>
                )}
                <button
                  onClick={handleLogout}
                  style={{
                    width: '100%',
                    padding: '0.75rem 1rem',
                    background: 'transparent',
                    border: 'none',
                    textAlign: 'left',
                    color: '#f87171',
                    cursor: 'pointer',
                    fontSize: '0.88rem',
                    fontWeight: 500,
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.5rem',
                    transition: 'background 0.15s',
                  }}
                  onMouseEnter={(e) => e.currentTarget.style.background = 'rgba(239,68,68,0.1)'}
                  onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
                >
                  🚪 Sign Out
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </nav>
  );
}
