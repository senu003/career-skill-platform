import React, { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  Target,
  ArrowRight,
  TrendingUp,
  AlertCircle,
  CheckCircle2,
  Compass,
  Lightbulb,
  RefreshCw,
  Layers
} from 'lucide-react';

import { fetchWithAuth } from '../../api';
import { SkillIcon } from './SkillIcons';

export default function InterviewPrepHub() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const activeTab = searchParams.get('tab') || 'overview'; // 'overview' | 'guide' | 'next-steps'

  const [summaryData, setSummaryData] = useState(null);
  const [nextStepsData, setNextStepsData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [sum, nxt] = await Promise.all([
        fetchWithAuth('/assessment/interview-prep/summary'),
        fetchWithAuth('/assessment/interview-prep/next-steps'),
      ]);
      setSummaryData(sum);
      setNextStepsData(nxt);
    } catch (err) {
      console.error('Failed to load Interview Prep data:', err);
      setError(err.message || 'Unable to load interview preparation data.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const setTab = (tab) => {
    setSearchParams({ tab });
  };

  const getStatusBadge = (trend) => {
    switch (trend) {
      case 'improving':
        return (
          <span
            className="badge badge-success"
            style={{ fontWeight: 600 }}
          >
            Improving
          </span>
        );
      case 'on_track':
        return (
          <span
            className="badge badge-purple"
            style={{ fontWeight: 600 }}
          >
            On Track
          </span>
        );
      case 'needs_focus':
        return (
          <span
            className="badge badge-warning"
            style={{ fontWeight: 600 }}
          >
            Needs Focus
          </span>
        );
      case 'first_attempt':
      case 'insufficient_data':
        return (
          <span
            className="badge badge-purple"
            style={{ fontWeight: 600 }}
          >
            First Attempt
          </span>
        );
      default:
        return (
          <span
            className="badge"
            style={{ backgroundColor: '#f1f5f9', color: '#64748b', border: '1px solid #e2e8f0', fontWeight: 500 }}
          >
            Not Started
          </span>
        );
    }
  };

  const getProgressBarColor = (trend, scorePct) => {
    if (!scorePct) return '#cbd5e1';
    if (trend === 'improving') return 'var(--success-color)';
    if (trend === 'needs_focus') return 'var(--warning-color)';
    if (scorePct >= 70) return 'var(--primary-color)';
    return 'var(--primary-400)';
  };

  if (loading) {
    return (
      <div className="container text-center" style={{ padding: '4rem 1rem' }}>
        <div className="spinner spinner-dark mb-4" style={{ width: 36, height: 36, margin: '0 auto 1.5rem' }}></div>
        <h2 className="card-title">Loading Interview Prep Hub</h2>
        <p className="text-muted text-sm">Aggregating real assessment history across all technical skills...</p>
      </div>
    );
  }

  if (error || !summaryData) {
    return (
      <div className="container" style={{ maxWidth: '640px', padding: '3rem 1rem' }}>
        <div className="card text-center" style={{ padding: '2.5rem' }}>
          <div className="alert-error flex items-center justify-center gap-2 mb-4" style={{ margin: '0 auto 1.5rem' }}>
            <AlertCircle size={20} />
            <span>{error || 'Could not load prep data.'}</span>
          </div>
          <h2 className="card-title mb-2">Interview Prep Hub Unavailable</h2>
          <p className="text-muted text-sm mb-5">Please check your network connection and retry.</p>
          <button onClick={loadData} className="btn btn-primary" style={{ margin: '0 auto' }}>
            <RefreshCw size={15} />
            <span>Retry</span>
          </button>
        </div>
      </div>
    );
  }

  const { total_attempts, skills_practised, improving_count, skills = [], overall_progress_text, key_takeaways = [] } = summaryData;

  return (
    <div className="container" style={{ maxWidth: '1080px', padding: '1.5rem 1rem 3.5rem' }}>
      {/* 1. TOP HEADER & PROGRESS AT A GLANCE */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          gap: '1.5rem',
          flexWrap: 'wrap',
          marginBottom: '2rem',
        }}
      >
        <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
          <div className="prep-header-icon">
            <Compass size={28} />
          </div>
          <div>
            <h1 className="page-title" style={{ fontSize: '1.75rem', marginBottom: '0.2rem' }}>
              Interview Prep
            </h1>
            <p className="page-subtitle" style={{ margin: 0, fontSize: '0.9rem' }}>
              Practise, understand your mistakes, and track your improvement.
            </p>
          </div>
        </div>

        {/* Progress at a glance card */}
        <div
          className="card"
          style={{
            padding: '1rem 1.5rem',
            marginBottom: 0,
            minWidth: '280px',
          }}
        >
          <div className="text-xs uppercase tracking-wider font-semibold text-muted mb-2">
            Your progress at a glance
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '1.25rem', textAlign: 'center' }}>
            <div>
              <div style={{ fontSize: '1.5rem', fontWeight: 800, color: 'var(--text-main)' }}>
                {total_attempts}
              </div>
              <div className="text-xs text-muted">Total Attempts</div>
            </div>
            <div>
              <div style={{ fontSize: '1.5rem', fontWeight: 800, color: 'var(--text-main)' }}>
                {skills_practised}
              </div>
              <div className="text-xs text-muted">Skills Practised</div>
            </div>
            <div>
              <div style={{ fontSize: '1.5rem', fontWeight: 800, color: 'var(--success-color)' }}>
                {improving_count}
              </div>
              <div className="text-xs text-muted">Improving</div>
            </div>
          </div>
        </div>
      </div>

      {/* 2. SUB-NAVIGATION TABS */}
      <div className="prep-tabs-nav">
        <button
          onClick={() => setTab('overview')}
          className={`prep-tab-button ${activeTab === 'overview' ? 'active' : ''}`}
        >
          <Layers size={16} />
          <span>All Skills Overview</span>
        </button>

        <button
          onClick={() => setTab('guide')}
          className={`prep-tab-button ${activeTab === 'guide' ? 'active' : ''}`}
        >
          <Target size={16} />
          <span>Improvement Guide</span>
        </button>

        <button
          onClick={() => setTab('next-steps')}
          className={`prep-tab-button ${activeTab === 'next-steps' ? 'active' : ''}`}
        >
          <Lightbulb size={16} />
          <span>What to Do Next</span>
          {nextStepsData?.recommendations?.length > 0 && (
            <span className="prep-tab-badge">
              {nextStepsData.recommendations.length}
            </span>
          )}
        </button>
      </div>

      {/* =========================================================================
          SCREEN 1: ALL SKILLS OVERVIEW
         ========================================================================= */}
      {activeTab === 'overview' && (
        <div className="fade-in">
          <div className="flex items-center justify-between mb-4">
            <h2 className="card-title" style={{ fontSize: '1.25rem', margin: 0 }}>
              Your Skills
            </h2>
            <span className="text-xs text-muted">
              {skills.filter((s) => s.attempts_count > 0).length} of {skills.length} assessed
            </span>
          </div>

          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))',
              gap: '1.25rem',
              marginBottom: '2.5rem',
            }}
          >
            {skills.map((skillItem) => {
              const hasAttempts = skillItem.attempts_count > 0;
              const scorePct = skillItem.latest_score_pct || 0;
              const barColor = getProgressBarColor(skillItem.trend, scorePct);

              return (
                <div key={skillItem.skill} className="prep-skill-card">
                  <div>
                    {/* Top row: Icon, Name, and Status Badge */}
                    <div className="flex items-center justify-between gap-2 mb-3">
                      <div className="flex items-center gap-3">
                        <SkillIcon skill={skillItem.skill} size={36} />
                        <div>
                          <h3
                            style={{
                              margin: 0,
                              fontSize: '1.05rem',
                              fontWeight: 700,
                              color: 'var(--text-main)',
                            }}
                          >
                            {skillItem.display_name}
                          </h3>
                          <div className="text-xs text-muted mt-0.5">
                            {hasAttempts
                              ? `${skillItem.attempts_count} ${skillItem.attempts_count === 1 ? 'attempt' : 'attempts'} · Last: ${scorePct}%`
                              : 'No attempts yet'}
                          </div>
                        </div>
                      </div>

                      {getStatusBadge(skillItem.trend)}
                    </div>

                    {/* Progress Bar & Percentage */}
                    <div style={{ marginTop: '1rem', marginBottom: '1.25rem' }}>
                      <div
                        style={{
                          height: 8,
                          backgroundColor: '#f1f5f9',
                          borderRadius: 999,
                          overflow: 'hidden',
                          display: 'flex',
                        }}
                      >
                        <div
                          style={{
                            width: `${Math.min(100, Math.max(0, scorePct))}%`,
                            backgroundColor: barColor,
                            borderRadius: 999,
                            transition: 'width 0.5s ease',
                          }}
                        />
                      </div>
                      <div className="flex justify-between items-center text-xs text-muted mt-1.5">
                        <span>Proficiency</span>
                        <span style={{ fontWeight: 700, color: hasAttempts ? 'var(--text-main)' : '#94a3b8' }}>
                          {hasAttempts ? `${scorePct}%` : '—'}
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Actions */}
                  <div
                    style={{
                      display: 'flex',
                      gap: '0.75rem',
                      borderTop: '1px solid #f1f5f9',
                      paddingTop: '1rem',
                    }}
                  >
                    <button
                      onClick={() => navigate(`/interview-prep/skill/${encodeURIComponent(skillItem.skill)}`)}
                      className="btn btn-outline"
                      style={{
                        flex: 1,
                        padding: '0.55rem 0.75rem',
                        fontSize: '0.82rem',
                        justifyContent: 'center',
                        fontWeight: 600,
                      }}
                    >
                      View Analysis
                    </button>
                    <button
                      onClick={() => navigate(`/assessment/${encodeURIComponent(skillItem.skill)}`)}
                      className="btn btn-primary"
                      style={{
                        flex: 1,
                        padding: '0.55rem 0.75rem',
                        fontSize: '0.82rem',
                        justifyContent: 'center',
                        fontWeight: 600,
                      }}
                    >
                      Take Assessment
                    </button>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Quick teaser to Improvement Guide */}
          <div
            className="card"
            style={{
              padding: '1.5rem',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: '1rem',
              flexWrap: 'wrap',
              background: 'linear-gradient(135deg, var(--surface-color) 0%, var(--primary-light) 100%)',
              borderColor: 'var(--primary-border)',
            }}
          >
            <div className="flex items-center gap-3.5">
              <div
                style={{
                  width: 42,
                  height: 42,
                  borderRadius: '50%',
                  backgroundColor: 'var(--primary-100)',
                  color: 'var(--primary-700)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0,
                  border: '1px solid var(--primary-border)',
                }}
              >
                <Target size={20} />
              </div>
              <div>
                <h4 style={{ margin: 0, fontWeight: 700, color: 'var(--text-main)', fontSize: '0.98rem' }}>
                  Want deep cross-skill improvement insights?
                </h4>
                <p className="text-xs text-muted" style={{ margin: '0.2rem 0 0' }}>
                  Explore your longitudinal trends, recurring error areas, and tailored next steps.
                </p>
              </div>
            </div>

            <button onClick={() => setTab('guide')} className="btn btn-secondary text-xs" style={{ fontWeight: 600 }}>
              <span>View Improvement Guide</span>
              <ArrowRight size={14} />
            </button>
          </div>
        </div>
      )}

      {/* =========================================================================
          SCREEN 4: OVERALL IMPROVEMENT GUIDE
         ========================================================================= */}
      {activeTab === 'guide' && (
        <div className="fade-in">
          {/* Header */}
          <div className="mb-5">
            <div className="flex items-center gap-2 mb-1">
              <Compass size={22} style={{ color: 'var(--primary-600)' }} />
              <h2 className="card-title" style={{ fontSize: '1.4rem', margin: 0 }}>
                Your Improvement Guide
              </h2>
            </div>
            <p className="text-xs text-muted" style={{ margin: 0 }}>
              Based on your latest assessment and overall history
            </p>
          </div>

          {/* Overall Progress Banner */}
          <div className="prep-banner-purple">
            <div className="prep-banner-icon">
              <Target size={22} />
            </div>
            <div>
              <div className="text-xs uppercase tracking-wider font-bold" style={{ color: 'var(--primary-800)' }}>
                Overall Progress
              </div>
              <p style={{ margin: '0.2rem 0 0', fontSize: '0.95rem', color: 'var(--text-main)', fontWeight: 500 }}>
                {overall_progress_text}
              </p>
            </div>
          </div>

          {/* Skill Breakdown Table */}
          <div className="skill-matrix-container" style={{ marginBottom: '1.75rem' }}>
            <div style={{ padding: '1.25rem 1.5rem', borderBottom: '1px solid var(--border-color)' }}>
              <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 700, color: 'var(--text-main)' }}>
                Skill Breakdown
              </h3>
            </div>

            <table className="skill-matrix-table">
              <thead>
                <tr>
                  <th style={{ width: '24%' }}>Skill</th>
                  <th style={{ width: '16%' }}>Latest Score</th>
                  <th style={{ width: '18%' }}>Trend</th>
                  <th style={{ width: '28%' }}>Recommendation</th>
                  <th style={{ width: '14%', textAlign: 'right' }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {skills.map((s) => (
                  <tr key={s.skill}>
                    <td style={{ fontWeight: 700, color: 'var(--text-main)' }}>
                      <div className="flex items-center gap-2.5">
                        <SkillIcon skill={s.skill} size={22} />
                        <span>{s.display_name}</span>
                      </div>
                    </td>
                    <td style={{ fontWeight: 600 }}>
                      {s.attempts_count > 0 ? `${s.latest_score_pct}%` : <span className="text-muted">—</span>}
                    </td>
                    <td>
                      {s.trend === 'improving' ? (
                        <span style={{ color: 'var(--success-color)', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: '3px' }}>
                          ↑ Improving
                        </span>
                      ) : s.trend === 'needs_focus' ? (
                        <span style={{ color: 'var(--danger-color)', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: '3px' }}>
                          ↓ Needs Focus
                        </span>
                      ) : s.trend === 'on_track' ? (
                        <span style={{ color: 'var(--primary-700)', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: '3px' }}>
                          → On Track
                        </span>
                      ) : s.trend === 'first_attempt' || s.trend === 'insufficient_data' ? (
                        <span style={{ color: 'var(--primary-700)', fontWeight: 600 }}>First Attempt</span>
                      ) : (
                        <span style={{ color: '#94a3b8' }}>— Not Started</span>
                      )}
                    </td>
                    <td style={{ color: 'var(--text-body)', fontSize: '0.82rem' }}>
                      {s.recommendation}
                    </td>
                    <td style={{ textAlign: 'right' }}>
                      <button
                        onClick={() => navigate(`/interview-prep/skill/${encodeURIComponent(s.skill)}`)}
                        className="btn btn-secondary text-xs"
                        style={{ padding: '0.35rem 0.75rem', fontWeight: 600 }}
                      >
                        Analyze
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Key Takeaways Card */}
          <div className="card" style={{ padding: '1.5rem', marginBottom: 0 }}>
            <div className="flex items-center gap-2 mb-3">
              <Lightbulb size={18} style={{ color: 'var(--primary-600)' }} />
              <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 700, color: 'var(--text-main)' }}>
                Key Takeaways
              </h3>
            </div>

            <div className="flex flex-col gap-2.5">
              {key_takeaways.map((takeaway, idx) => (
                <div key={idx} className="flex items-start gap-2.5 text-xs text-body">
                  <div
                    style={{
                      width: 6,
                      height: 6,
                      borderRadius: '50%',
                      backgroundColor: 'var(--primary-600)',
                      marginTop: '6px',
                      flexShrink: 0,
                    }}
                  />
                  <span>{takeaway}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* =========================================================================
          SCREEN 5: WHAT TO DO NEXT (PERSONALIZED RECOMMENDATIONS)
         ========================================================================= */}
      {activeTab === 'next-steps' && (
        <div className="fade-in">
          {/* Header */}
          <div className="mb-5">
            <div className="flex items-center gap-2 mb-1">


            </div>

          </div>

          {/* Recommendations List */}
          {nextStepsData?.recommendations && nextStepsData.recommendations.length > 0 ? (
            <div className="flex flex-col gap-3.5 mb-5">
              {nextStepsData.recommendations.map((rec, idx) => {
                const isHigh = rec.priority === 'high';
                const isMedium = rec.priority === 'medium';

                let badgeClass = 'badge-purple';
                if (isHigh) badgeClass = 'badge-warning'; // or missing
                else if (isMedium) badgeClass = 'badge-purple';
                else badgeClass = 'badge-success';

                return (
                  <div
                    key={idx}
                    className="card"
                    style={{
                      padding: '1.25rem 1.5rem',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      gap: '1rem',
                      flexWrap: 'wrap',
                      marginBottom: 0,
                    }}
                  >
                    <div className="flex items-center gap-3.5" style={{ flex: 1, minWidth: '260px' }}>
                      <SkillIcon skill={rec.skill} size={40} />
                      <div>
                        <div className="flex items-center gap-2 flex-wrap mb-1">
                          <h4 style={{ margin: 0, fontWeight: 700, fontSize: '0.98rem', color: 'var(--text-main)' }}>
                            {rec.title}
                          </h4>
                          <span
                            className={`badge ${badgeClass}`}
                            style={{
                              fontSize: '0.68rem',
                              fontWeight: 700,
                            }}
                          >
                            {rec.priority_label}
                          </span>
                        </div>
                        <p className="text-xs text-muted" style={{ margin: 0, lineHeight: 1.45 }}>
                          {rec.context}
                        </p>
                      </div>
                    </div>

                    <button
                      onClick={() => navigate(rec.practice_url)}
                      className="btn btn-primary"
                      style={{
                        padding: '0.55rem 1rem',
                        fontSize: '0.8rem',
                        fontWeight: 600,
                      }}
                    >
                      <span>{rec.action_label}</span>
                      <ArrowRight size={14} />
                    </button>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="card text-center p-5 mb-5">
              <CheckCircle2 size={32} style={{ color: 'var(--success-color)', margin: '0 auto 0.75rem' }} />
              <h3 className="card-title mb-1">No Critical Errors Detected!</h3>
              <p className="text-xs text-muted mb-4">
                You have demonstrated solid accuracy across all completed assessments. Continue challenging yourself
                with additional skills.
              </p>
              <button onClick={() => navigate('/dashboard')} className="btn btn-primary" style={{ margin: '0 auto' }}>
                Explore Skills
              </button>
            </div>
          )}

          {/* Bottom Callout / Tip */}

        </div>
      )}
    </div>
  );
}
