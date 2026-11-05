import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  ArrowRight,
  RefreshCw,
  AlertCircle,
  TrendingUp,
  Clock,
  Calendar
} from 'lucide-react';

import { fetchWithAuth } from '../../api';
import { SkillIcon } from './SkillIcons';

export default function SkillAnalysisPage() {
  const { skill } = useParams();
  const navigate = useNavigate();

  const [analysisData, setAnalysisData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const loadSkillAnalysis = async () => {
    if (!skill) return;
    setLoading(true);
    setError(null);
    try {
      const data = await fetchWithAuth(`/assessment/interview-prep/skill/${encodeURIComponent(skill)}`);
      setAnalysisData(data);
    } catch (err) {
      console.error('Failed to load skill analysis:', err);
      setError(err.message || 'Unable to retrieve individual skill analysis.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadSkillAnalysis();
  }, [skill]);

  if (loading) {
    return (
      <div className="container text-center" style={{ padding: '4rem 1rem' }}>
        <div className="spinner spinner-dark mb-4" style={{ width: 36, height: 36, margin: '0 auto 1.5rem' }}></div>
        <h2 className="card-title">Loading {skill} Analysis</h2>
        <p className="text-muted text-sm">Evaluating chronological progression and past attempts...</p>
      </div>
    );
  }

  if (error || !analysisData) {
    return (
      <div className="container" style={{ maxWidth: '640px', padding: '3rem 1rem' }}>
        <div className="card text-center" style={{ padding: '2.5rem' }}>
          <div className="alert-error flex items-center justify-center gap-2 mb-4" style={{ margin: '0 auto 1.5rem' }}>
            <AlertCircle size={20} />
            <span>{error || 'Unable to load skill data.'}</span>
          </div>
          <h2 className="card-title mb-2">Analysis Unavailable</h2>
          <p className="text-muted text-sm mb-5">Please verify the requested skill name and retry.</p>
          <div className="flex justify-center gap-3">
            <button onClick={() => navigate('/interview-prep')} className="btn btn-outline">
              <ArrowLeft size={15} />
              <span>Back to All Skills</span>
            </button>
            <button onClick={loadSkillAnalysis} className="btn btn-primary">
              <RefreshCw size={15} />
              <span>Retry</span>
            </button>
          </div>
        </div>
      </div>
    );
  }

  const {
    display_name,
    total_attempts,
    latest_score_pct,
    score_delta_vs_first,

    best_score_pct,
    average_score_pct,
    trend,
    trend_label,
    trend_explanation,
    difficulty_note,
    score_progression = [],
    past_attempts = []
  } = analysisData;

  const hasMultiple = total_attempts >= 2;

  // Progression Chart Coordinates
  const chartHeight = 160;
  const chartWidth = 500;
  const paddingX = 45;
  const paddingY = 25;

  const getChartCoordinates = () => {
    if (score_progression.length === 0) return [];
    if (score_progression.length === 1) {
      return [{ x: chartWidth / 2, y: chartHeight - paddingY - (score_progression[0].score * (chartHeight - 2 * paddingY)), ...score_progression[0] }];
    }
    const stepX = (chartWidth - 2 * paddingX) / (score_progression.length - 1);
    return score_progression.map((item, idx) => {
      const x = paddingX + idx * stepX;
      const normalizedScore = Math.max(0, Math.min(1, item.score > 1 ? item.score / 100 : item.score));
      const y = (chartHeight - paddingY) - normalizedScore * (chartHeight - 2 * paddingY);
      return { x, y, ...item };
    });
  };

  const chartPoints = getChartCoordinates();
  const pathD = chartPoints.length > 1
    ? chartPoints.reduce((acc, pt, idx) => `${acc} ${idx === 0 ? 'M' : 'L'} ${pt.x} ${pt.y}`, '')
    : '';

  const areaD = chartPoints.length > 1
    ? `${pathD} L ${chartPoints[chartPoints.length - 1].x} ${chartHeight - paddingY} L ${chartPoints[0].x} ${chartHeight - paddingY} Z`
    : '';

  return (
    <div className="container" style={{ maxWidth: '1000px', padding: '1.25rem 1rem 3.5rem' }}>
      {/* 1. TOP BACK LINK */}
      <button
        onClick={() => navigate('/interview-prep')}
        className="btn btn-outline text-xs mb-4"
        style={{ padding: '0.35rem 0.75rem', fontWeight: 600, border: 'none', background: 'transparent' }}
      >
        <ArrowLeft size={15} />
        <span>Back to All Skills</span>
      </button>

      {/* 2. HEADER BAR */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          gap: '1rem',
          flexWrap: 'wrap',
          marginBottom: '2rem',
        }}
      >
        <div className="flex items-center gap-3.5">
          <SkillIcon skill={skill} size={46} />
          <div>
            <h1 className="page-title" style={{ fontSize: '1.75rem', margin: 0 }}>
              {display_name || skill}
            </h1>
            <p className="page-subtitle" style={{ margin: '0.15rem 0 0', fontSize: '0.9rem' }}>
              Performance analysis and improvement guide
            </p>
          </div>
        </div>

        <button
          onClick={() => navigate(`/assessment/${encodeURIComponent(skill)}`)}
          className="btn btn-primary"
          style={{
            fontWeight: 600,
            padding: '0.65rem 1.25rem',
            fontSize: '0.875rem',
          }}
        >
          <span>Take Assessment</span>
          <ArrowRight size={15} />
        </button>
      </div>

      {/* 3. FOUR METRIC SUMMARY CARDS */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: '1.25rem',
          marginBottom: '2rem',
        }}
      >
        {/* Card 1: Total Attempts */}
        <div className="card" style={{ padding: '1.25rem 1.5rem', marginBottom: 0 }}>
          <div className="text-xs text-muted font-medium mb-1">Total Attempts</div>
          <div style={{ fontSize: '1.875rem', fontWeight: 800, color: 'var(--text-main)', lineHeight: 1.1 }}>
            {total_attempts}
          </div>
        </div>

        {/* Card 2: Latest Score */}
        <div className="card" style={{ padding: '1.25rem 1.5rem', marginBottom: 0 }}>
          <div className="text-xs text-muted font-medium mb-1">Latest Score</div>
          <div className="flex items-baseline gap-2 flex-wrap">
            <span style={{ fontSize: '1.875rem', fontWeight: 800, color: 'var(--text-main)', lineHeight: 1.1 }}>
              {latest_score_pct !== null ? `${latest_score_pct}%` : '—'}
            </span>
            {hasMultiple && score_delta_vs_first !== null && (
              <span
                className={`badge ${score_delta_vs_first >= 0 ? 'badge-success' : ''}`}
                style={{
                  fontSize: '0.72rem',
                  fontWeight: 700,
                  backgroundColor: score_delta_vs_first < 0 ? '#fee2e2' : undefined,
                  color: score_delta_vs_first < 0 ? '#dc2626' : undefined,
                  border: score_delta_vs_first < 0 ? '1px solid #fecaca' : undefined,
                }}
              >
                {score_delta_vs_first >= 0 ? `↑ +${score_delta_vs_first}% vs first` : `↓ ${score_delta_vs_first}% vs first`}
              </span>
            )}
            {total_attempts === 1 && (
              <span className="badge badge-purple" style={{ fontSize: '0.7rem' }}>
                First attempt
              </span>
            )}
          </div>
        </div>

        {/* Card 3: Best Score */}
        <div className="card" style={{ padding: '1.25rem 1.5rem', marginBottom: 0 }}>
          <div className="text-xs text-muted font-medium mb-1">Best Score</div>
          <div style={{ fontSize: '1.875rem', fontWeight: 800, color: 'var(--text-main)', lineHeight: 1.1 }}>
            {best_score_pct !== null ? `${best_score_pct}%` : '—'}
          </div>
        </div>

        {/* Card 4: Average Score */}
        <div className="card" style={{ padding: '1.25rem 1.5rem', marginBottom: 0 }}>
          <div className="text-xs text-muted font-medium mb-1">Average Score</div>
          <div style={{ fontSize: '1.875rem', fontWeight: 800, color: 'var(--text-main)', lineHeight: 1.1 }}>
            {average_score_pct !== null ? `${average_score_pct}%` : '—'}
          </div>
        </div>
      </div>

      {/* 4. SCORE PROGRESSION & PERFORMANCE TREND SPLIT SECTION */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'minmax(320px, 1.4fr) minmax(280px, 1fr)',
          gap: '1.5rem',
          marginBottom: '2rem',
        }}
      >
        {/* Left: Score Progression Line Chart */}
        <div className="card" style={{ padding: '1.5rem', marginBottom: 0 }}>
          <div className="flex items-center justify-between mb-3">
            <h3 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 700, color: 'var(--text-main)' }}>
              Score Progression
            </h3>
            <span className="text-xs text-muted">Chronological attempts</span>
          </div>

          {score_progression.length >= 2 ? (
            <div style={{ width: '100%', overflowX: 'auto' }}>
              <svg viewBox={`0 0 ${chartWidth} ${chartHeight}`} style={{ width: '100%', height: 'auto', display: 'block' }}>
                <defs>
                  <linearGradient id="prepChartGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#7c3aed" stopOpacity="0.2" />
                    <stop offset="100%" stopColor="#7c3aed" stopOpacity="0.0" />
                  </linearGradient>
                </defs>

                {/* Horizontal reference grid lines */}
                {[1.0, 0.75, 0.5, 0.25, 0.0].map((val) => {
                  const y = (chartHeight - paddingY) - val * (chartHeight - 2 * paddingY);
                  return (
                    <g key={val}>
                      <line x1={paddingX - 10} y1={y} x2={chartWidth - 15} y2={y} stroke="#f1f5f9" strokeWidth="1" />
                      <text x={paddingX - 15} y={y + 3.5} textAnchor="end" fontSize="10" fill="#94a3b8">
                        {Math.round(val * 100)}%
                      </text>
                    </g>
                  );
                })}

                {/* Soft Gradient Area Fill */}
                {areaD && <path d={areaD} fill="url(#prepChartGrad)" />}

                {/* Connecting Trend Line */}
                <path d={pathD} fill="none" stroke="var(--primary-color)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />

                {/* Plot Points & Value Labels */}
                {chartPoints.map((pt) => (
                  <g key={pt.attempt_id}>
                    <circle cx={pt.x} cy={pt.y} r="5" fill="#ffffff" stroke="var(--primary-color)" strokeWidth="2.5" />
                    <text x={pt.x} y={pt.y - 10} textAnchor="middle" fontSize="11" fontWeight="700" fill="var(--text-main)">
                      {pt.score_pct}%
                    </text>
                  </g>
                ))}
              </svg>

              {/* X-axis Attempt Labels */}
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  padding: `0 ${paddingX - 15}px`,
                  marginTop: '0.25rem',
                  fontSize: '0.75rem',
                  color: 'var(--text-muted)',
                  fontWeight: 500,
                }}
              >
                {score_progression.map((item) => (
                  <div key={item.attempt_id} style={{ textAlign: 'center' }}>
                    Attempt {item.attempt_number}
                    <div style={{ fontSize: '0.68rem', color: '#94a3b8' }}>({item.score_pct}%)</div>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div
              style={{
                height: 180,
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                backgroundColor: 'var(--bg-color)',
                borderRadius: '8px',
                border: '1px dashed var(--border-color)',
                padding: '1rem',
                textAlign: 'center',
              }}
            >
              <TrendingUp size={28} style={{ color: 'var(--primary-300)', marginBottom: '0.5rem' }} />
              <p className="text-xs font-semibold text-main mb-1">Insufficient History for Progression Chart</p>
              <p className="text-xs text-muted" style={{ margin: 0, maxWidth: '280px' }}>
                Complete at least two assessments for {display_name} to generate a continuous score progression line.
              </p>
            </div>
          )}
        </div>

        {/* Right: Performance Trend Card */}
        <div
          className="card"
          style={{
            padding: '1.5rem',
            marginBottom: 0,
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'space-between',
          }}
        >
          <div>
            <div className="text-xs uppercase tracking-wider font-semibold text-muted mb-2">
              Performance Trend
            </div>

            <div className="flex items-center gap-2 mb-3">
              {trend === 'improving' ? (
                <span
                  className="badge badge-success"
                  style={{
                    fontWeight: 700,
                    fontSize: '0.85rem',
                    padding: '0.35rem 0.75rem',
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '4px',
                  }}
                >
                  <TrendingUp size={15} />
                  <span>Improving</span>
                </span>
              ) : trend === 'needs_focus' ? (
                <span
                  className="badge badge-warning"
                  style={{
                    fontWeight: 700,
                    fontSize: '0.85rem',
                    padding: '0.35rem 0.75rem',
                  }}
                >
                  ↓ Needs Focus
                </span>
              ) : trend === 'on_track' ? (
                <span
                  className="badge badge-purple"
                  style={{
                    fontWeight: 700,
                    fontSize: '0.85rem',
                    padding: '0.35rem 0.75rem',
                  }}
                >
                  → On Track
                </span>
              ) : (
                <span
                  className="badge badge-purple"
                  style={{
                    fontSize: '0.82rem',
                    padding: '0.35rem 0.65rem',
                  }}
                >
                  {trend_label}
                </span>
              )}
            </div>

            <p style={{ fontSize: '0.875rem', color: 'var(--text-body)', lineHeight: 1.55, margin: '0 0 1rem' }}>
              {trend_explanation}
            </p>
          </div>

          <div
            style={{
              borderTop: '1px solid #f1f5f9',
              paddingTop: '0.85rem',
              fontSize: '0.75rem',
              color: 'var(--text-muted)',
              lineHeight: 1.45,
            }}
          >
            {difficulty_note}
          </div>
        </div>
      </div>

      {/* 5. PAST ATTEMPTS TABLE */}
      <div className="skill-matrix-container">
        <div
          style={{
            padding: '1.25rem 1.5rem',
            borderBottom: '1px solid var(--border-color)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 700, color: 'var(--text-main)' }}>
            Past Attempts
          </h3>
          <span className="text-xs text-muted">{past_attempts.length} completed</span>
        </div>

        {past_attempts.length > 0 ? (
          <table className="skill-matrix-table">
            <thead>
              <tr>
                <th style={{ width: '22%' }}>Date</th>
                <th style={{ width: '18%' }}>Score</th>
                <th style={{ width: '22%' }}>Time per Question</th>
                <th style={{ width: '20%' }}>Assessed Level</th>
                <th style={{ width: '18%', textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {past_attempts.map((att) => (
                <tr key={att.attempt_id}>
                  <td style={{ fontWeight: 600, color: 'var(--text-main)' }}>
                    <div className="flex items-center gap-2">
                      <Calendar size={14} style={{ color: 'var(--primary-400)' }} />
                      <span>{att.date}</span>
                    </div>
                  </td>
                  <td style={{ fontWeight: 700, color: 'var(--text-main)' }}>
                    {att.score_pct}%
                  </td>
                  <td style={{ color: 'var(--text-body)' }}>
                    {att.time_per_question ? (
                      <div className="flex items-center gap-1 text-xs">
                        <Clock size={13} style={{ color: 'var(--primary-400)' }} />
                        <span>{Math.round(att.time_per_question)}s</span>
                      </div>
                    ) : (
                      <span className="text-muted">—</span>
                    )}
                  </td>
                  <td>
                    <span className="badge badge-purple" style={{ fontSize: '0.72rem' }}>
                      {att.assessed_level ? att.assessed_level.toUpperCase() : 'BASIC'}
                    </span>
                  </td>
                  <td style={{ textAlign: 'right' }}>
                    <button
                      onClick={() => navigate(`/interview-prep/attempt/${att.attempt_id}`)}
                      className="btn btn-secondary text-xs"
                      style={{
                        padding: '0.4rem 0.85rem',
                        fontWeight: 600,
                      }}
                    >
                      View Review
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div style={{ padding: '2.5rem 1.5rem', textAlign: 'center', color: 'var(--text-muted)' }}>
            <p className="text-xs mb-3">No past completed attempts recorded for {display_name}.</p>
            <button
              onClick={() => navigate(`/assessment/${encodeURIComponent(skill)}`)}
              className="btn btn-primary text-xs"
              style={{ margin: '0 auto' }}
            >
              Take Assessment Now
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
