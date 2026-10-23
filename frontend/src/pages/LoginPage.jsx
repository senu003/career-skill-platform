import React, { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { GoogleOAuthProvider, GoogleLogin } from '@react-oauth/google';
import { useAuth } from '../context/AuthContext';
import {
  loginWithPassword,
  registerWithPassword,
  loginWithGoogle,
  demoLogin,
  forgotPassword,
  resetPassword,
} from '../api';

const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID || '';
const isGoogleConfigured = Boolean(
  GOOGLE_CLIENT_ID &&
  !GOOGLE_CLIENT_ID.includes('your_google_client_id') &&
  !GOOGLE_CLIENT_ID.includes('placeholder') &&
  GOOGLE_CLIENT_ID.trim().length > 15
);

// ── Password strength indicator ───────────────────────────────────────────────
function PasswordStrength({ password }) {
  if (!password) return null;
  const checks = [
    { label: '8+ characters', ok: password.length >= 8 },
    { label: 'Has a letter', ok: /[a-zA-Z]/.test(password) },
    { label: 'Has a digit', ok: /\d/.test(password) },
  ];
  const score = checks.filter((c) => c.ok).length;
  const bar = ['#ef4444', '#f97316', '#22c55e'];
  return (
    <div style={{ marginTop: '0.4rem' }}>
      <div style={{ display: 'flex', gap: '4px', marginBottom: '0.4rem' }}>
        {[0, 1, 2].map((i) => (
          <div
            key={i}
            style={{
              flex: 1,
              height: '4px',
              borderRadius: '9999px',
              background: i < score ? bar[score - 1] : 'var(--border-color)',
              transition: 'background 0.3s',
            }}
          />
        ))}
      </div>
      <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
        {checks.map((c) => (
          <span
            key={c.label}
            style={{
              fontSize: '0.72rem',
              color: c.ok ? '#22c55e' : 'var(--text-muted)',
              display: 'flex',
              alignItems: 'center',
              gap: '0.2rem',
            }}
          >
            {c.ok ? '✓' : '○'} {c.label}
          </span>
        ))}
      </div>
    </div>
  );
}

// ── View modes ────────────────────────────────────────────────────────────────
const VIEW = {
  LOGIN: 'login',
  REGISTER: 'register',
  FORGOT: 'forgot',
  RESET: 'reset',
  RESET_DONE: 'reset_done',
};

export default function LoginPage() {
  const [view, setView] = useState(VIEW.LOGIN);
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [resetToken, setResetToken] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [loading, setLoading] = useState(false);
  const [devResetToken, setDevResetToken] = useState(null);

  const { login, isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  // Auto-fill reset token from URL (?token=xxx)
  useEffect(() => {
    const urlToken = searchParams.get('token');
    if (urlToken) {
      setResetToken(urlToken);
      setView(VIEW.RESET);
    }
  }, [searchParams]);

  // Redirect if already authenticated
  useEffect(() => {
    if (isAuthenticated) navigate('/dashboard', { replace: true });
  }, [isAuthenticated, navigate]);

  const clearMessages = () => { setError(null); setSuccess(null); };

  const handleAuthSuccess = (data) => {
    login(data.access_token, data.user || null);
    navigate('/dashboard', { replace: true });
  };

  // ── Standard login ──────────────────────────────────────────────────────────
  const handleLogin = async (e) => {
    e.preventDefault();
    clearMessages();
    setLoading(true);
    try {
      const data = await loginWithPassword(email.trim(), password);
      handleAuthSuccess(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // ── Register ────────────────────────────────────────────────────────────────
  const handleRegister = async (e) => {
    e.preventDefault();
    clearMessages();
    if (password !== confirmPassword) {
      setError('Passwords do not match.');
      return;
    }
    setLoading(true);
    try {
      const data = await registerWithPassword(name.trim(), email.trim(), password);
      handleAuthSuccess(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // ── Google OAuth ────────────────────────────────────────────────────────────
  const handleGoogleSuccess = async (credentialResponse) => {
    clearMessages();
    setLoading(true);
    try {
      const data = await loginWithGoogle(credentialResponse.credential);
      handleAuthSuccess(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleError = () => {
    setError('Google sign-in was cancelled or failed. Please try again.');
  };

  // ── Instant Demo Login ──────────────────────────────────────────────────────
  const handleDemoLogin = async () => {
    clearMessages();
    setLoading(true);
    try {
      const data = await demoLogin();
      handleAuthSuccess(data);
    } catch (err) {
      setError(err.message || 'Demo login failed.');
    } finally {
      setLoading(false);
    }
  };

  // ── Forgot password ─────────────────────────────────────────────────────────
  const handleForgotPassword = async (e) => {
    e.preventDefault();
    clearMessages();
    setLoading(true);
    try {
      const data = await forgotPassword(email.trim());
      setSuccess(data.message || 'Reset link sent! Check your email.');
      if (data.dev_reset_token) {
        setDevResetToken(data.dev_reset_token);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // ── Reset password ──────────────────────────────────────────────────────────
  const handleResetPassword = async (e) => {
    e.preventDefault();
    clearMessages();
    if (!resetToken.trim()) { setError('Please enter or paste your reset token.'); return; }
    setLoading(true);
    try {
      await resetPassword(resetToken.trim(), newPassword);
      setView(VIEW.RESET_DONE);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // ── Shared styles ───────────────────────────────────────────────────────────
  const inputStyle = {
    width: '100%',
    padding: '0.65rem 0.9rem',
    background: 'var(--surface-2, #1e293b)',
    border: '1.5px solid var(--border-color)',
    borderRadius: '0.5rem',
    color: 'var(--text-primary)',
    fontSize: '0.95rem',
    outline: 'none',
    transition: 'border-color 0.2s',
    boxSizing: 'border-box',
  };

  const labelStyle = {
    display: 'block',
    fontSize: '0.82rem',
    fontWeight: 600,
    color: 'var(--text-secondary)',
    marginBottom: '0.35rem',
    letterSpacing: '0.02em',
  };

  const dividerStyle = {
    display: 'flex',
    alignItems: 'center',
    gap: '0.75rem',
    margin: '1.25rem 0',
    color: 'var(--text-muted)',
    fontSize: '0.8rem',
  };

  const isLoginOrReg = view === VIEW.LOGIN || view === VIEW.REGISTER;

  return (
    <div
      className="fade-in"
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '2rem 1rem',
        background: 'var(--bg-primary)',
      }}
    >
      <div style={{ width: '100%', maxWidth: '420px' }}>
        {/* ── Brand ── */}
        <div className="text-center" style={{ marginBottom: '2rem' }}>
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.5rem',
              fontSize: '2rem',
              fontWeight: 800,
              color: 'var(--primary-700)',
              letterSpacing: '-0.03em',
            }}
          >
            CareerSkill
            <span
              style={{
                background: 'linear-gradient(135deg, var(--primary-500), var(--primary-700))',
                color: '#fff',
                fontSize: '0.7rem',
                fontWeight: 700,
                padding: '0.15rem 0.45rem',
                borderRadius: '0.35rem',
                letterSpacing: '0.05em',
              }}
            >
              AI
            </span>
          </div>
          <p style={{ color: 'var(--text-muted)', marginTop: '0.4rem', fontSize: '0.9rem' }}>
            {view === VIEW.FORGOT && 'Reset your password'}
            {view === VIEW.RESET && 'Set a new password'}
            {view === VIEW.RESET_DONE && 'Password updated!'}
            {isLoginOrReg && 'AI-powered career & skill gap analysis'}
          </p>
        </div>

        <div
          className="card"
          style={{ padding: '2rem', boxShadow: '0 8px 40px rgba(0,0,0,0.35)', borderRadius: '1rem' }}
        >
          {/* ── Tabs (Login / Register) ── */}
          {isLoginOrReg && (
            <div
              style={{
                display: 'flex',
                background: 'var(--surface-2, rgba(255,255,255,0.05))',
                borderRadius: '0.6rem',
                padding: '3px',
                marginBottom: '1.5rem',
              }}
            >
              {[
                { id: VIEW.LOGIN, label: 'Sign In' },
                { id: VIEW.REGISTER, label: 'Register' },
              ].map((tab) => (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => { setView(tab.id); clearMessages(); }}
                  style={{
                    flex: 1,
                    padding: '0.55rem',
                    border: 'none',
                    borderRadius: '0.45rem',
                    cursor: 'pointer',
                    fontWeight: 600,
                    fontSize: '0.88rem',
                    transition: 'all 0.2s',
                    background: view === tab.id ? 'var(--primary-600)' : 'transparent',
                    color: view === tab.id ? '#fff' : 'var(--text-muted)',
                  }}
                >
                  {tab.label}
                </button>
              ))}
            </div>
          )}

          {/* ── Error / Success banners ── */}
          {error && (
            <div
              style={{
                background: 'rgba(239,68,68,0.12)',
                border: '1px solid rgba(239,68,68,0.4)',
                borderRadius: '0.5rem',
                padding: '0.65rem 0.9rem',
                color: '#f87171',
                fontSize: '0.88rem',
                marginBottom: '1rem',
                display: 'flex',
                alignItems: 'flex-start',
                gap: '0.5rem',
              }}
            >
              <span style={{ marginTop: '1px' }}>⚠</span>
              <span>{error}</span>
            </div>
          )}
          {success && (
            <div
              style={{
                background: 'rgba(34,197,94,0.1)',
                border: '1px solid rgba(34,197,94,0.3)',
                borderRadius: '0.5rem',
                padding: '0.65rem 0.9rem',
                color: '#4ade80',
                fontSize: '0.88rem',
                marginBottom: '1rem',
              }}
            >
              ✓ {success}
            </div>
          )}

          {/* ─────────── LOGIN ─────────── */}
          {view === VIEW.LOGIN && (
            <>
              {/* One-Click Quick Demo Login (ideal for instant testing) */}
              <button
                type="button"
                onClick={handleDemoLogin}
                disabled={loading}
                style={{
                  width: '100%',
                  padding: '0.75rem',
                  marginBottom: '1rem',
                  border: '1px solid rgba(99, 102, 241, 0.4)',
                  borderRadius: '0.5rem',
                  background: 'linear-gradient(135deg, rgba(99, 102, 241, 0.15), rgba(168, 85, 247, 0.15))',
                  color: '#c7d2fe',
                  fontWeight: 600,
                  fontSize: '0.9rem',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '0.5rem',
                  transition: 'all 0.2s',
                }}
              >
                <span>⚡</span>
                <span>One-Click Test Login (Alex Chen - Demo Candidate)</span>
              </button>

              {/* Google Sign-In */}
              {isGoogleConfigured ? (
                <>
                  <GoogleOAuthProvider clientId={GOOGLE_CLIENT_ID}>
                    <div style={{ display: 'flex', justifyContent: 'center' }}>
                      <GoogleLogin
                        onSuccess={handleGoogleSuccess}
                        onError={handleGoogleError}
                        theme="filled_black"
                        shape="rectangular"
                        size="large"
                        width="360"
                        text="signin_with"
                      />
                    </div>
                  </GoogleOAuthProvider>
                  <div style={dividerStyle}>
                    <div style={{ flex: 1, height: '1px', background: 'var(--border-color)' }} />
                    <span>or continue with email</span>
                    <div style={{ flex: 1, height: '1px', background: 'var(--border-color)' }} />
                  </div>
                </>
              ) : (
                <div
                  style={{
                    background: 'rgba(59, 130, 246, 0.08)',
                    border: '1px dashed rgba(59, 130, 246, 0.3)',
                    borderRadius: '0.5rem',
                    padding: '0.65rem 0.85rem',
                    marginBottom: '1rem',
                    fontSize: '0.8rem',
                    color: 'var(--text-secondary)',
                    lineHeight: '1.4',
                  }}
                >
                  <strong style={{ color: '#60a5fa' }}>ℹ Google OAuth:</strong> To use real Google accounts, set your Client ID in <code style={{ color: '#93c5fd' }}>.env</code>. To test immediately, use the <strong>One-Click Test Login</strong> above or email/password below.
                </div>
              )}

              <form onSubmit={handleLogin}>
                <div style={{ marginBottom: '1rem' }}>
                  <label style={labelStyle}>Email Address</label>
                  <input
                    type="email"
                    required
                    placeholder="name@example.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    style={inputStyle}
                    autoComplete="email"
                  />
                </div>

                <div style={{ marginBottom: '0.5rem' }}>
                  <label style={labelStyle}>Password</label>
                  <div style={{ position: 'relative' }}>
                    <input
                      type={showPassword ? 'text' : 'password'}
                      required
                      placeholder="••••••••"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      style={{ ...inputStyle, paddingRight: '2.8rem' }}
                      autoComplete="current-password"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword((p) => !p)}
                      style={{
                        position: 'absolute',
                        right: '0.75rem',
                        top: '50%',
                        transform: 'translateY(-50%)',
                        background: 'none',
                        border: 'none',
                        cursor: 'pointer',
                        color: 'var(--text-muted)',
                        fontSize: '1rem',
                      }}
                      aria-label={showPassword ? 'Hide password' : 'Show password'}
                    >
                      {showPassword ? '🙈' : '👁'}
                    </button>
                  </div>
                </div>

                <div style={{ textAlign: 'right', marginBottom: '1.25rem' }}>
                  <button
                    type="button"
                    onClick={() => { setView(VIEW.FORGOT); clearMessages(); }}
                    style={{
                      background: 'none',
                      border: 'none',
                      color: 'var(--primary-400)',
                      cursor: 'pointer',
                      fontSize: '0.8rem',
                      fontWeight: 500,
                    }}
                  >
                    Forgot password?
                  </button>
                </div>

                <button
                  type="submit"
                  disabled={loading}
                  style={{
                    width: '100%',
                    padding: '0.75rem',
                    background: loading ? 'var(--primary-800)' : 'var(--primary-600)',
                    color: '#fff',
                    border: 'none',
                    borderRadius: '0.5rem',
                    fontWeight: 700,
                    fontSize: '0.95rem',
                    cursor: loading ? 'not-allowed' : 'pointer',
                    transition: 'background 0.2s',
                  }}
                >
                  {loading ? 'Signing in…' : 'Sign In'}
                </button>
              </form>
            </>
          )}

          {/* ─────────── REGISTER ─────────── */}
          {view === VIEW.REGISTER && (
            <>
              {GOOGLE_CLIENT_ID && (
                <>
                  <GoogleOAuthProvider clientId={GOOGLE_CLIENT_ID}>
                    <div style={{ display: 'flex', justifyContent: 'center' }}>
                      <GoogleLogin
                        onSuccess={handleGoogleSuccess}
                        onError={handleGoogleError}
                        theme="filled_black"
                        shape="rectangular"
                        size="large"
                        width="360"
                        text="signup_with"
                      />
                    </div>
                  </GoogleOAuthProvider>
                  <div style={dividerStyle}>
                    <div style={{ flex: 1, height: '1px', background: 'var(--border-color)' }} />
                    <span>or sign up with email</span>
                    <div style={{ flex: 1, height: '1px', background: 'var(--border-color)' }} />
                  </div>
                </>
              )}

              <form onSubmit={handleRegister}>
                <div style={{ marginBottom: '1rem' }}>
                  <label style={labelStyle}>Full Name</label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Alex Johnson"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    style={inputStyle}
                    autoComplete="name"
                  />
                </div>

                <div style={{ marginBottom: '1rem' }}>
                  <label style={labelStyle}>Email Address</label>
                  <input
                    type="email"
                    required
                    placeholder="name@example.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    style={inputStyle}
                    autoComplete="email"
                  />
                </div>

                <div style={{ marginBottom: '1rem' }}>
                  <label style={labelStyle}>Password</label>
                  <div style={{ position: 'relative' }}>
                    <input
                      type={showPassword ? 'text' : 'password'}
                      required
                      placeholder="Min. 8 chars, 1 letter, 1 digit"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      style={{ ...inputStyle, paddingRight: '2.8rem' }}
                      autoComplete="new-password"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword((p) => !p)}
                      style={{
                        position: 'absolute',
                        right: '0.75rem',
                        top: '50%',
                        transform: 'translateY(-50%)',
                        background: 'none',
                        border: 'none',
                        cursor: 'pointer',
                        color: 'var(--text-muted)',
                      }}
                      aria-label={showPassword ? 'Hide password' : 'Show password'}
                    >
                      {showPassword ? '🙈' : '👁'}
                    </button>
                  </div>
                  <PasswordStrength password={password} />
                </div>

                <div style={{ marginBottom: '1.25rem' }}>
                  <label style={labelStyle}>Confirm Password</label>
                  <input
                    type="password"
                    required
                    placeholder="Repeat password"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    style={{
                      ...inputStyle,
                      borderColor:
                        confirmPassword && confirmPassword !== password
                          ? '#ef4444'
                          : undefined,
                    }}
                    autoComplete="new-password"
                  />
                  {confirmPassword && confirmPassword !== password && (
                    <p style={{ color: '#ef4444', fontSize: '0.78rem', marginTop: '0.25rem' }}>
                      Passwords do not match
                    </p>
                  )}
                </div>

                <button
                  type="submit"
                  disabled={loading}
                  style={{
                    width: '100%',
                    padding: '0.75rem',
                    background: loading ? 'var(--primary-800)' : 'var(--primary-600)',
                    color: '#fff',
                    border: 'none',
                    borderRadius: '0.5rem',
                    fontWeight: 700,
                    fontSize: '0.95rem',
                    cursor: loading ? 'not-allowed' : 'pointer',
                    transition: 'background 0.2s',
                  }}
                >
                  {loading ? 'Creating Account…' : 'Create Account'}
                </button>
              </form>
            </>
          )}

          {/* ─────────── FORGOT PASSWORD ─────────── */}
          {view === VIEW.FORGOT && (
            <form onSubmit={handleForgotPassword}>
              <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginBottom: '1.25rem', lineHeight: 1.5 }}>
                Enter the email linked to your account and we'll send you a reset link.
              </p>
              <div style={{ marginBottom: '1.25rem' }}>
                <label style={labelStyle}>Email Address</label>
                <input
                  type="email"
                  required
                  placeholder="name@example.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  style={inputStyle}
                />
              </div>

              <button
                type="submit"
                disabled={loading}
                style={{
                  width: '100%',
                  padding: '0.75rem',
                  background: loading ? 'var(--primary-800)' : 'var(--primary-600)',
                  color: '#fff',
                  border: 'none',
                  borderRadius: '0.5rem',
                  fontWeight: 700,
                  fontSize: '0.95rem',
                  cursor: loading ? 'not-allowed' : 'pointer',
                }}
              >
                {loading ? 'Sending…' : 'Send Reset Link'}
              </button>

              {/* Dev-only: display the raw token so you can test without email */}
              {devResetToken && (
                <div
                  style={{
                    marginTop: '1rem',
                    background: 'rgba(251,191,36,0.1)',
                    border: '1px solid rgba(251,191,36,0.4)',
                    borderRadius: '0.5rem',
                    padding: '0.75rem',
                  }}
                >
                  <p style={{ color: '#fbbf24', fontSize: '0.78rem', fontWeight: 700, marginBottom: '0.35rem' }}>
                    🔧 DEV MODE — Reset Token (remove in production):
                  </p>
                  <code
                    style={{
                      fontSize: '0.75rem',
                      wordBreak: 'break-all',
                      color: '#fcd34d',
                      cursor: 'pointer',
                    }}
                    onClick={() => {
                      setResetToken(devResetToken);
                      setView(VIEW.RESET);
                    }}
                    title="Click to use this token"
                  >
                    {devResetToken}
                  </code>
                  <p style={{ color: '#fbbf24', fontSize: '0.72rem', marginTop: '0.35rem' }}>
                    Click the token to proceed to password reset.
                  </p>
                </div>
              )}

              <button
                type="button"
                onClick={() => { setView(VIEW.LOGIN); clearMessages(); setDevResetToken(null); }}
                style={{
                  marginTop: '0.75rem',
                  width: '100%',
                  padding: '0.6rem',
                  background: 'transparent',
                  border: '1.5px solid var(--border-color)',
                  borderRadius: '0.5rem',
                  color: 'var(--text-secondary)',
                  cursor: 'pointer',
                  fontWeight: 500,
                  fontSize: '0.9rem',
                }}
              >
                ← Back to Sign In
              </button>
            </form>
          )}

          {/* ─────────── RESET PASSWORD ─────────── */}
          {view === VIEW.RESET && (
            <form onSubmit={handleResetPassword}>
              <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginBottom: '1.25rem' }}>
                Paste your reset token and set a new password.
              </p>

              {!searchParams.get('token') && (
                <div style={{ marginBottom: '1rem' }}>
                  <label style={labelStyle}>Reset Token</label>
                  <input
                    type="text"
                    required
                    placeholder="Paste token from email"
                    value={resetToken}
                    onChange={(e) => setResetToken(e.target.value)}
                    style={inputStyle}
                  />
                </div>
              )}

              <div style={{ marginBottom: '1rem' }}>
                <label style={labelStyle}>New Password</label>
                <input
                  type="password"
                  required
                  placeholder="Min. 8 chars, 1 letter, 1 digit"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  style={inputStyle}
                  autoComplete="new-password"
                />
                <PasswordStrength password={newPassword} />
              </div>

              <button
                type="submit"
                disabled={loading}
                style={{
                  width: '100%',
                  padding: '0.75rem',
                  background: loading ? 'var(--primary-800)' : 'var(--primary-600)',
                  color: '#fff',
                  border: 'none',
                  borderRadius: '0.5rem',
                  fontWeight: 700,
                  fontSize: '0.95rem',
                  cursor: loading ? 'not-allowed' : 'pointer',
                }}
              >
                {loading ? 'Updating…' : 'Update Password'}
              </button>
            </form>
          )}

          {/* ─────────── RESET DONE ─────────── */}
          {view === VIEW.RESET_DONE && (
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>✅</div>
              <h3 style={{ color: '#4ade80', fontWeight: 700, marginBottom: '0.5rem' }}>
                Password Updated!
              </h3>
              <p style={{ color: 'var(--text-secondary)', marginBottom: '1.5rem', fontSize: '0.9rem' }}>
                Your password has been changed. Please sign in with your new credentials.
              </p>
              <button
                type="button"
                onClick={() => { setView(VIEW.LOGIN); clearMessages(); setPassword(''); setNewPassword(''); setResetToken(''); }}
                style={{
                  width: '100%',
                  padding: '0.75rem',
                  background: 'var(--primary-600)',
                  color: '#fff',
                  border: 'none',
                  borderRadius: '0.5rem',
                  fontWeight: 700,
                  fontSize: '0.95rem',
                  cursor: 'pointer',
                }}
              >
                Go to Sign In
              </button>
            </div>
          )}
        </div>

        {/* ── Footer ── */}
        <p style={{ textAlign: 'center', marginTop: '1.5rem', color: 'var(--text-muted)', fontSize: '0.78rem' }}>
          By continuing, you agree to our{' '}
          <span style={{ color: 'var(--primary-400)', cursor: 'pointer' }}>Terms of Service</span>
          {' '}and{' '}
          <span style={{ color: 'var(--primary-400)', cursor: 'pointer' }}>Privacy Policy</span>.
        </p>
      </div>
    </div>
  );
}
