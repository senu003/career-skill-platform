import React from 'react';

export function SkillIcon({ skill, size = 32, style = {} }) {
  const s = (skill || '').toLowerCase().trim();

  if (s.includes('python') || s === 'py') {
    return (
      <svg width={size} height={size} viewBox="0 0 128 128" style={style}>
        <linearGradient id="pyA" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#387eb8" />
          <stop offset="100%" stopColor="#366994" />
        </linearGradient>
        <linearGradient id="pyB" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#ffe873" />
          <stop offset="100%" stopColor="#ffd43b" />
        </linearGradient>
        <path
          fill="url(#pyA)"
          d="M63.5 8c-26 0-24.5 11.3-24.5 11.3l.03 11.7h25v3.5H24.3C13.2 34.5 3 44.8 3 61.2c0 16.5 9.7 26 21.3 26h6.7v-9.3c0-13.3 11.4-25 24.8-25h24.8c11 0 20-8.9 20-20V19.3S102.5 8 63.5 8zM49.8 17.5c2.9 0 5.2 2.3 5.2 5.2 0 2.9-2.3 5.2-5.2 5.2-2.9 0-5.2-2.3-5.2-5.2 0-2.9 2.3-5.2 5.2-5.2z"
        />
        <path
          fill="url(#pyB)"
          d="M64.5 120c26 0 24.5-11.3 24.5-11.3l-.03-11.7h-25v-3.5h39.7c11.1 0 21.3-10.3 21.3-26.7 0-16.5-9.7-26-21.3-26h-6.7v9.3c0 13.3-11.4 25-24.8 25H37.4c-11 0-20 8.9-20 20v13.6S25.5 120 64.5 120zm13.7-9.5c-2.9 0-5.2-2.3-5.2-5.2 0-2.9 2.3-5.2 5.2-5.2 2.9 0 5.2 2.3 5.2 5.2 0 2.9-2.3 5.2-5.2 5.2z"
        />
      </svg>
    );
  }

  if (s.includes('react')) {
    return (
      <svg width={size} height={size} viewBox="-11.5 -10.23174 23 20.46348" style={style}>
        <circle cx="0" cy="0" r="2.05" fill="#61dafb" />
        <g stroke="#61dafb" strokeWidth="1" fill="none">
          <ellipse rx="11" ry="4.2" />
          <ellipse rx="11" ry="4.2" transform="rotate(60)" />
          <ellipse rx="11" ry="4.2" transform="rotate(120)" />
        </g>
      </svg>
    );
  }

  if (s.includes('javascript') || s === 'js') {
    return (
      <svg width={size} height={size} viewBox="0 0 128 128" style={style}>
        <rect width="128" height="128" rx="16" fill="#f7df1e" />
        <path
          fill="#000000"
          d="M39.6 109.8c6.6 3.8 14.8 5.9 22.8 5.9 19.8 0 32.7-9.9 32.7-29.2v-47.5h-15.5v47.5c0 11.2-6.5 16.4-16.7 16.4-6.8 0-12.2-2.2-16.5-4.8l-6.8 11.7zm50.8-70.8h15.5v76.7H90.4V39z"
        />
        <path
          fill="#000000"
          d="M67.3 100.8c-7.9 0-14.3-3.8-18.7-9.3l11.4-7c3.1 3.9 6.2 6.5 10.7 6.5 5.5 0 9.1-2.7 9.1-6.7 0-4.6-3.7-6.3-12.2-10-12.3-5.3-20.5-11.8-20.5-24.3 0-13.6 10.4-23.7 26.6-23.7 10.6 0 18.2 3.6 23.6 11.6l-11.6 7.4c-2.8-4.5-5.9-6.6-11.8-6.6-5.1 0-8.4 2.7-8.4 6.2 0 4.1 3.3 5.8 10.8 9.1 14.4 6.2 22.2 12.5 22.2 25.1 0 15.6-11.3 25.1-31.2 25.1z"
        />
      </svg>
    );
  }

  if (s.includes('postgre') || s.includes('sql')) {
    return (
      <svg width={size} height={size} viewBox="0 0 128 128" style={style}>
        <rect width="128" height="128" rx="16" fill="#f0fdf4" stroke="#86efac" strokeWidth="2" />
        <ellipse cx="64" cy="32" rx="42" ry="16" fill="#336791" />
        <path
          fill="#336791"
          d="M22 32v32c0 8.8 18.8 16 42 16s42-7.2 42-16V32c0 8.8-18.8 16-42 16S22 40.8 22 32z"
        />
        <path
          fill="#336791"
          d="M22 64v32c0 8.8 18.8 16 42 16s42-7.2 42-16V64c0 8.8-18.8 16-42 16S22 72.8 22 64z"
        />
      </svg>
    );
  }

  if (s.includes('docker') || s.includes('container')) {
    return (
      <svg width={size} height={size} viewBox="0 0 128 128" style={style}>
        <rect width="128" height="128" rx="16" fill="#f0f9ff" stroke="#bae6fd" strokeWidth="2" />
        <path
          fill="#0db7ed"
          d="M116.5 61.4c-1.3-.9-6.2-3.8-14.3-1.8-.7-5.1-4.4-9.6-9.6-11.3l-2.4-.8-.9 2.4c-2.3 5.8-1.5 12.3 2.1 17.3-3.2 1.8-7.5 3.1-12.7 3.6-2-8.5-9.6-14.8-18.7-14.8H50.5v-10h-10v10H30.5v-10h-10v10H10v10h10.5v10H10v10h10.5v10H10v10h10.5c.3 16.5 13.8 29.8 30.5 29.8 32.5 0 54.8-19.8 62.5-35.8 5.7-11.7 4.1-18.2 2.5-19.9z"
        />
        <rect x="36" y="44" width="8" height="8" rx="1" fill="#0db7ed" />
        <rect x="47" y="44" width="8" height="8" rx="1" fill="#0db7ed" />
        <rect x="58" y="44" width="8" height="8" rx="1" fill="#0db7ed" />
        <rect x="47" y="33" width="8" height="8" rx="1" fill="#0db7ed" />
        <rect x="58" y="33" width="8" height="8" rx="1" fill="#0db7ed" />
      </svg>
    );
  }

  // Fallback icon
  return (
    <div
      style={{
        width: size,
        height: size,
        borderRadius: '8px',
        backgroundColor: '#f1f5f9',
        border: '1.5px solid #cbd5e1',
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontWeight: 700,
        fontSize: size * 0.45,
        color: '#475569',
        ...style,
      }}
    >
      {skill ? skill.charAt(0).toUpperCase() : '?'}
    </div>
  );
}
