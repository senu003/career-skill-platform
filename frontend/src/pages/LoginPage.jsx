import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { API_BASE_URL } from '../api';

export default function LoginPage() {
  const [isRegister, setIsRegister] = useState(false);
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleLogin = async (e) => {
    if (e) e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const formData = new URLSearchParams();
      formData.append('username', email);
      formData.append('password', password);

      const response = await fetch(`${API_BASE_URL}/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: formData,
      });

      if (!response.ok) {
        throw new Error('Invalid email or password. Please check your credentials.');
      }

      const data = await response.json();
      login(data.access_token);
      navigate('/dashboard');
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = async (e) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const response = await fetch(`${API_BASE_URL}/users`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: name || 'User',
          email,
          password,
        }),
      });

      if (!response.ok) {
        const d = await response.json();
        throw new Error(d.detail || 'Registration failed. User may already exist.');
      }

      // Automatically login after successful registration
      await handleLogin();
    } catch (err) {
      setError(err.message);
      setLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: '440px', margin: '4rem auto 2rem' }} className="fade-in">
      <div className="text-center mb-4">
        <div style={{ fontSize: '2.5rem', fontWeight: 800, color: 'var(--primary-700)', letterSpacing: '-0.03em' }}>
          CareerSkill<span className="nav-brand-badge" style={{ verticalAlign: 'middle', marginLeft: '0.4rem' }}>AI</span>
        </div>
        <p className="page-subtitle" style={{ marginTop: '0.5rem' }}>
          AI-Powered Career & Skill Assessment Platform
        </p>
      </div>

      <div className="card">
        {/* Toggle Tabs */}
        <div className="flex gap-2 mb-4" style={{ borderBottom: '1px solid var(--border-color)', paddingBottom: '0.75rem' }}>
          <button 
            type="button" 
            className={`btn ${!isRegister ? 'btn-primary' : 'btn-outline'}`}
            style={{ flex: 1 }}
            onClick={() => { setIsRegister(false); setError(null); }}
          >
            Sign In
          </button>
          <button 
            type="button" 
            className={`btn ${isRegister ? 'btn-primary' : 'btn-outline'}`}
            style={{ flex: 1 }}
            onClick={() => { setIsRegister(true); setError(null); }}
          >
            Register
          </button>
        </div>

        {error && <div className="alert-error">{error}</div>}

        <form onSubmit={isRegister ? handleRegister : handleLogin}>
          {isRegister && (
            <div className="form-group">
              <label className="form-label">Full Name</label>
              <input 
                type="text" 
                className="input" 
                placeholder="e.g. Alex Johnson"
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </div>
          )}

          <div className="form-group">
            <label className="form-label">Email Address</label>
            <input 
              type="email" 
              className="input" 
              placeholder="name@example.com"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>

          <div className="form-group">
            <label className="form-label">Password</label>
            <input 
              type="password" 
              className="input" 
              placeholder="••••••••"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>

          <button type="submit" className="btn btn-primary" style={{ width: '100%', marginTop: '0.5rem' }} disabled={loading}>
            {loading ? (isRegister ? 'Creating Account...' : 'Logging in...') : (isRegister ? 'Create Account' : 'Sign In')}
          </button>
        </form>
      </div>
    </div>
  );
}

