import React from 'react';
import { AlertTriangle, RefreshCw, Home } from 'lucide-react';

/**
 * Global React Error Boundary with user-friendly recovery actions.
 * Catches runtime JavaScript render errors, displays support reference if available,
 * and allows the user to reload the page or return to the dashboard.
 */
export class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
    };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    this.setState({ errorInfo });
    console.error('Unhandled React Error:', error, errorInfo);
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null, errorInfo: null });
    if (this.props.onReset) {
      this.props.onReset();
    }
  };

  handleReload = () => {
    window.location.reload();
  };

  handleGoHome = () => {
    this.setState({ hasError: false, error: null, errorInfo: null });
    window.location.href = '/dashboard';
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback({
          error: this.state.error,
          reset: this.handleReset,
          reload: this.handleReload,
        });
      }

      const errorMessage = this.state.error?.message || 'An unexpected rendering error occurred.';
      const supportRef = this.state.error?.requestId || this.state.error?.supportReference || null;

      return (
        <div
          role="alert"
          style={{
            maxWidth: '640px',
            margin: '4rem auto',
            padding: '2rem',
            background: '#ffffff',
            borderRadius: '12px',
            boxShadow: '0 8px 24px rgba(0, 0, 0, 0.08)',
            border: '1px solid #fee2e2',
            textAlign: 'center',
            fontFamily: 'inherit',
          }}
        >
          <div
            style={{
              display: 'inline-flex',
              padding: '1rem',
              borderRadius: '50%',
              background: '#fee2e2',
              color: '#dc2626',
              marginBottom: '1rem',
            }}
          >
            <AlertTriangle size={40} />
          </div>

          <h2 style={{ fontSize: '1.5rem', fontWeight: 700, color: '#1f2937', marginBottom: '0.5rem' }}>
            Something went wrong
          </h2>

          <p style={{ color: '#4b5563', fontSize: '0.95rem', lineHeight: 1.5, marginBottom: '1.25rem' }}>
            An unexpected error occurred while rendering this view. You can retry the current action, reload the application, or return to your dashboard.
          </p>

          <div
            style={{
              background: '#f9fafb',
              border: '1px solid #e5e7eb',
              borderRadius: '8px',
              padding: '0.75rem 1rem',
              marginBottom: '1.5rem',
              fontSize: '0.85rem',
              color: '#374151',
              textAlign: 'left',
              wordBreak: 'break-word',
            }}
          >
            <strong>Error:</strong> {errorMessage}
            {supportRef && (
              <div style={{ marginTop: '0.5rem', color: '#6b7280', fontFamily: 'monospace' }}>
                Support Reference: <strong>{supportRef}</strong>
              </div>
            )}
          </div>

          <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'center', flexWrap: 'wrap' }}>
            <button
              type="button"
              onClick={this.handleReload}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.5rem',
                padding: '0.625rem 1.25rem',
                background: '#2563eb',
                color: '#ffffff',
                border: 'none',
                borderRadius: '6px',
                fontWeight: 600,
                fontSize: '0.9rem',
                cursor: 'pointer',
              }}
            >
              <RefreshCw size={16} /> Reload Page
            </button>
            <button
              type="button"
              onClick={this.handleGoHome}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.5rem',
                padding: '0.625rem 1.25rem',
                background: '#f3f4f6',
                color: '#374151',
                border: '1px solid #d1d5db',
                borderRadius: '6px',
                fontWeight: 600,
                fontSize: '0.9rem',
                cursor: 'pointer',
              }}
            >
              <Home size={16} /> Return to Dashboard
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
