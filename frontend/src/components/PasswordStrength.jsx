import React from 'react';

/**
 * Reusable password strength meter displaying visual score bars and rule checklist.
 */
export default function PasswordStrength({ password }) {
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
