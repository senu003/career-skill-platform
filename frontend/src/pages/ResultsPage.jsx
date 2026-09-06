import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import { CheckCircle2, AlertCircle, ArrowRight, RefreshCw, ArrowLeft, Award, Target, TrendingUp, Sparkles, AlertTriangle, Calendar, RotateCcw } from 'lucide-react';
import { fetchWithAuth } from '../api';
import { useAssessment } from '../context/AssessmentContext';
import { isSupportedSkill } from '../utils/supportedSkills';

// Static explanation mapping for Model 1 recommendation labels
const RECOMMENDATION_EXPLANATIONS = {
  'Mastered': 'Your current performance is strong for this skill.',
  'Upgrade Needed': 'Your current level needs improvement to reach the target level.',
  'Speed Practice': 'Your knowledge is adequate, but answering speed needs improvement.',
  'Re-learn Basics': 'Review the fundamentals before progressing.',
};

export default function ResultsPage() {
  const { skill, attemptId } = useParams();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { analysisResult, setAnalysisResult, updateSkillResult } = useAssessment();

  const queryAttemptId = searchParams.get('attempt_id') || searchParams.get('attemptId');
  const targetAttemptId = attemptId || queryAttemptId;
  const rawSkill = skill ? decodeURIComponent(skill) : '';
  const normalizedSkill = rawSkill || resultData?.skill || '';

  const [resultData, setResultData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Auto-restore latest session from backend if analysisResult is empty
  useEffect(() => {
    if (!analysisResult) {
      const restoreLatestSession = async () => {
        try {
          const sessRes = await fetchWithAuth('/cv/sessions');
          if (sessRes?.sessions && sessRes.sessions.length > 0) {
            const latestSess = sessRes.sessions[0];
            const detailRes = await fetchWithAuth(`/cv/sessions/${latestSess.analysis_id}`);
            if (detailRes) {
              setAnalysisResult(detailRes);
            }
          }
        } catch (err) {
          console.warn('Could not restore session on ResultsPage:', err);
        }
      };
      restoreLatestSession();
    }
  }, [analysisResult]);

  const fetchResult = async () => {
    if (!rawSkill && !targetAttemptId) {
      setError('No skill or attempt specified.');
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      let endpoint;
      if (targetAttemptId) {
        endpoint = `/assessment/${targetAttemptId}/result`;
      } else {
        endpoint = `/assessment/result/${encodeURIComponent(rawSkill)}`;
      }

      const data = await fetchWithAuth(endpoint);
      setResultData(data);
      if (updateSkillResult && data?.skill) {
        updateSkillResult(data.skill, data);
      }
    } catch (err) {
      setError(err.message || 'Failed to load assessment result.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchResult();
  }, [skill, targetAttemptId]);

  // Format Helper: Capitalize level text
  const formatLevel = (lvl) => {
    if (!lvl) return 'N/A';
    return lvl.charAt(0).toUpperCase() + lvl.slice(1).toLowerCase();
  };

  // Find remaining required skills that are supported for assessment and have not been assessed yet.
  // Prioritizes identified weaknesses/missing skills first!
  const getNextUnassessedSkill = () => {
    const skills = analysisResult?.skills || [
      ...(analysisResult?.matched_skills || []),
      ...(analysisResult?.missing_skills || []),
    ];
    if (!skills || skills.length === 0) return null;

    const currentName = (normalizedSkill || resultData?.skill || '').toLowerCase().trim();

    // Filter to unassessed supported skills excluding current skill
    const unassessed = skills.filter((s) => {
      const sName = (s.skill || '').toLowerCase().trim();
      return sName !== currentName && !s.assessed_level && isSupportedSkill(s.skill);
    });

    if (unassessed.length === 0) return null;

    // Prioritize identified weaknesses or missing skills first
    const weaknessOrMissing = unassessed.find(
      (s) => s.is_weakness || !s.matched || (s.level_gap !== null && s.level_gap > 0)
    );

    return weaknessOrMissing || unassessed[0];
  };

  const nextSkill = getNextUnassessedSkill();

  // Helper to format score
  const formatScore = (score) => {
    if (score === null || score === undefined) return 'N/A';
    if (typeof score === 'number') {
      return `${Math.round(score > 1 ? score : score * 100)}%`;
    }
    return score;
  };

  // Helper to format confidence
  const formatConfidence = (conf) => {
    if (conf === null || conf === undefined) return null;
    const num = typeof conf === 'number' ? conf : parseFloat(conf);
    if (isNaN(num)) return null;
    const percent = Math.round(num > 1 ? num : num * 100);
    return `${percent}%`;
  };

  // Helper for recommendation badge color styling
  const getRecommendationBadgeClass = (rec) => {
    const cleanRec = (rec || '').toLowerCase().trim();
    if (cleanRec === 'mastered') {
      return {
        badgeStyle: { backgroundColor: 'var(--success-bg)', color: 'var(--success-color)', border: '1px solid #a7f3d0' },
        icon: <CheckCircle2 size={20} className="text-emerald-500" />
      };
    }
    if (cleanRec === 'speed practice') {
      return {
        badgeStyle: { backgroundColor: 'var(--primary-light)', color: 'var(--primary-700)', border: '1px solid var(--primary-200)' },
        icon: <TrendingUp size={20} style={{ color: 'var(--primary-600)' }} />
      };
    }
    if (cleanRec === 'upgrade needed') {
      return {
        badgeStyle: { backgroundColor: 'var(--warning-bg)', color: '#b45309', border: '1px solid #fde68a' },
        icon: <AlertTriangle size={20} style={{ color: '#d97706' }} />
      };
    }
    // Re-learn Basics or fallback
    return {
      badgeStyle: { backgroundColor: 'var(--danger-bg)', color: 'var(--danger-color)', border: '1px solid #fecaca' },
      icon: <AlertCircle size={20} style={{ color: 'var(--danger-color)' }} />
    };
  };

  // 1. Loading State
  if (loading) {
    return (
      <div className="assessment-container fade-in text-center mt-4" style={{ paddingTop: '3rem' }}>
        <div className="card" style={{ padding: '3rem 2rem' }}>
          <div className="spinner spinner-dark mb-4" style={{ width: 36, height: 36, borderWidth: 3 }}></div>
          <h2 className="card-title">Loading Assessment Result</h2>
          <p className="text-muted text-sm">Retrieving completed assessment details for {normalizedSkill || 'skill'}...</p>
        </div>
      </div>
    );
  }

  // 2. Error State
  if (error || !resultData) {
    const isNotFound = error && error.toLowerCase().includes('not found');
    return (
      <div className="assessment-container fade-in mt-4" style={{ paddingTop: '2rem' }}>
        <div className="card text-center" style={{ padding: '2.5rem 1.75rem' }}>
          <div className="alert-error flex items-center justify-center gap-2 mb-4" style={{ margin: '0 auto 1.5rem', maxWidth: '500px' }}>
            <AlertCircle size={20} />
            <span>{isNotFound ? `No completed assessment found for '${normalizedSkill}'.` : 'Unable to retrieve assessment result.'}</span>
          </div>
          <h2 className="card-title mb-2">
            {isNotFound ? 'Assessment Not Completed' : 'Unable to Load Result'}
          </h2>
          <p className="text-muted text-sm mb-6" style={{ maxWidth: '480px', margin: '0 auto 1.5rem' }}>
            {isNotFound
              ? `You have not yet completed the technical assessment for ${normalizedSkill}. Please take the assessment to view your results.`
              : 'An error occurred while fetching your assessment result. Please try again.'}
          </p>
          <div className="flex justify-center gap-3">
            <button onClick={() => navigate('/dashboard')} className="btn btn-outline">
              <ArrowLeft size={16} />
              <span>Back to Dashboard</span>
            </button>
            {isNotFound ? (
              <button onClick={() => navigate(`/assessment/${encodeURIComponent(normalizedSkill)}`)} className="btn btn-primary">
                <span>Take Assessment</span>
                <ArrowRight size={16} />
              </button>
            ) : (
              <button onClick={fetchResult} className="btn btn-primary">
                <RefreshCw size={16} />
                <span>Retry</span>
              </button>
            )}
          </div>
        </div>
      </div>
    );
  }

  // Recommendation label resolution (Model 1 output)
  const recommendationLabel = resultData.skill_recommendation || resultData.recommendation || 'Assessment Completed';
  
  // Explanation resolution: prefer static mapping for the four known Model 1 recommendations, or backend recommendation_reason if present
  const explanationText =
    RECOMMENDATION_EXPLANATIONS[recommendationLabel] ||
    ((resultData.recommendation_reason && resultData.recommendation_reason !== 'NONE' && resultData.recommendation_reason.trim())
      ? resultData.recommendation_reason
      : 'Assessment completed successfully.');

  const confidenceDisplay = formatConfidence(resultData.recommendation_confidence);
  const badgeConfig = getRecommendationBadgeClass(recommendationLabel);

  return (
    <div className="assessment-container fade-in">
      {/* 1. PAGE HEADER */}
      <div className="page-header text-center mb-6">
        <div className="flex items-center justify-center gap-2 mb-2 flex-wrap">
          <span className="badge badge-purple">Skill Assessment Result</span>
          {targetAttemptId && (
            <span className="badge" style={{ backgroundColor: 'var(--primary-light)', color: 'var(--primary-700)', border: '1px solid var(--primary-200)' }}>
              Historical Record (Attempt #{targetAttemptId})
            </span>
          )}
        </div>
        <h1 className="page-title">{resultData.skill || rawSkill}</h1>
        <p className="text-muted text-sm mt-1">
          {targetAttemptId && resultData.completed_at
            ? `Completed on ${new Date(resultData.completed_at).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}`
            : 'Detailed evaluation score and recommendation breakdown'}
        </p>
      </div>

      {/* 2. MAIN RESULT CARD */}
      <div className="card">
        {/* Recommendation Banner / Status */}
        <div
          style={{
            ...badgeConfig.badgeStyle,
            padding: '1.25rem 1.5rem',
            borderRadius: 'var(--radius-sm)',
            marginBottom: '1.5rem',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: '1rem',
          }}
        >
          <div className="flex items-center gap-3">
            {badgeConfig.icon}
            <div>
              <div className="text-xs uppercase tracking-wider font-semibold opacity-90">
                Evaluation Recommendation
              </div>
              <div className="font-bold text-xl mt-0.5" style={{ lineHeight: 1.2 }}>
                {recommendationLabel}
              </div>
            </div>
          </div>

          {confidenceDisplay && (
            <div
              style={{
                backgroundColor: 'rgba(255, 255, 255, 0.65)',
                padding: '0.35rem 0.75rem',
                borderRadius: '9999px',
                fontSize: '0.8rem',
                fontWeight: 600,
                boxShadow: 'var(--shadow-sm)'
              }}
            >
              Recommendation confidence: <strong>{confidenceDisplay}</strong>
            </div>
          )}
        </div>

        {/* Level & Score Grid */}
        <div className="grid grid-cols-3 gap-4 mb-6">
          {/* Required Level */}
          <div
            style={{
              padding: '1.25rem 1rem',
              backgroundColor: 'var(--primary-50)',
              border: '1px solid var(--primary-200)',
              borderRadius: 'var(--radius-sm)',
              textAlign: 'center',
            }}
          >
            <div className="flex items-center justify-center gap-1.5 text-xs text-muted font-medium mb-1">
              <Target size={14} style={{ color: 'var(--primary-600)' }} />
              <span>Required Level</span>
            </div>
            <div className="font-bold text-lg text-main">
              {formatLevel(resultData.required_level)}
            </div>
          </div>

          {/* Assessed Level */}
          <div
            style={{
              padding: '1.25rem 1rem',
              backgroundColor: 'var(--primary-50)',
              border: '1px solid var(--primary-200)',
              borderRadius: 'var(--radius-sm)',
              textAlign: 'center',
            }}
          >
            <div className="flex items-center justify-center gap-1.5 text-xs text-muted font-medium mb-1">
              <Award size={14} style={{ color: 'var(--primary-600)' }} />
              <span>Assessed Level</span>
            </div>
            <div className="font-bold text-lg text-main">
              {formatLevel(resultData.assessed_level)}
            </div>
          </div>

          {/* Assessment Score */}
          <div
            style={{
              padding: '1.25rem 1rem',
              backgroundColor: 'var(--primary-50)',
              border: '1px solid var(--primary-200)',
              borderRadius: 'var(--radius-sm)',
              textAlign: 'center',
            }}
          >
            <div className="flex items-center justify-center gap-1.5 text-xs text-muted font-medium mb-1">
              <Sparkles size={14} style={{ color: 'var(--primary-600)' }} />
              <span>Assessment Score</span>
            </div>
            <div className="font-bold text-lg text-main">
              {formatScore(resultData.total_score)}
            </div>
          </div>
        </div>

        {/* Explanation Section */}
        <div
          style={{
            padding: '1.25rem',
            backgroundColor: '#ffffff',
            border: '1px solid var(--border-color)',
            borderRadius: 'var(--radius-sm)',
            marginBottom: '1.5rem',
          }}
        >
          <div className="text-xs uppercase tracking-wider font-semibold text-muted mb-1">
            Explanation
          </div>
          <p className="text-sm font-medium text-main" style={{ lineHeight: 1.5 }}>
            {explanationText}
          </p>
        </div>

        {/* Next Identified Skill Callout Banner */}
        {nextSkill ? (
          <div
            style={{
              padding: '1.25rem 1.5rem',
              backgroundColor: 'var(--primary-50)',
              border: '1.5px solid var(--primary-300)',
              borderRadius: 'var(--radius-sm)',
              marginBottom: '1.5rem',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: '1rem',
              flexWrap: 'wrap',
            }}
          >
            <div>
              <div className="flex items-center gap-2 mb-1">
                <span className="badge badge-purple" style={{ fontSize: '0.75rem' }}>Up Next</span>
                <span className="font-bold text-main text-base">
                  Next Identified Skill: <strong>{nextSkill.skill}</strong>
                </span>
              </div>
              <p className="text-xs text-muted" style={{ margin: 0 }}>
                {nextSkill.is_weakness || !nextSkill.matched
                  ? `Identified as a priority skill gap. Complete the ${nextSkill.skill} technical assessment next to build your candidate profile.`
                  : `Continue taking remaining technical MCQ assessments to finish evaluating your job match compatibility.`}
              </p>
            </div>
            <button
              onClick={() => navigate(`/assessment/${encodeURIComponent(nextSkill.skill)}`)}
              className="btn btn-primary"
              style={{ padding: '0.6rem 1.25rem', fontSize: '0.875rem' }}
            >
              <span>Start {nextSkill.skill} Assessment</span>
              <ArrowRight size={16} />
            </button>
          </div>
        ) : (
          <div
            style={{
              padding: '1rem 1.25rem',
              backgroundColor: 'var(--success-bg)',
              border: '1px solid #a7f3d0',
              borderRadius: 'var(--radius-sm)',
              marginBottom: '1.5rem',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: '1rem',
              flexWrap: 'wrap',
            }}
          >
            <div className="flex items-center gap-2">
              <CheckCircle2 size={18} className="text-emerald-600" />
              <span className="text-xs font-semibold text-emerald-800">
                All technical skill assessments completed! Proceed to view your final recommendation summary.
              </span>
            </div>
            <button
              onClick={() => navigate('/recommendation')}
              className="btn btn-primary"
              style={{ padding: '0.5rem 1rem', fontSize: '0.8rem' }}
            >
              <span>View Recommendation</span>
              <ArrowRight size={14} />
            </button>
          </div>
        )}

        {/* Next Action Footer */}
        <div
          className="flex justify-between items-center pt-4 gap-2 flex-wrap"
          style={{ borderTop: '1px solid var(--border-color)' }}
        >
          <div className="flex gap-2">
            <button
              onClick={() => navigate('/history')}
              className="btn btn-outline text-xs flex items-center gap-1.5"
              style={{ padding: '0.55rem 0.95rem' }}
            >
              <ArrowLeft size={16} />
              <span>History & Profile</span>
            </button>
            <button
              onClick={() => navigate('/dashboard')}
              className="btn btn-outline text-xs flex items-center gap-1.5"
              style={{ padding: '0.55rem 0.95rem' }}
            >
              <span>Dashboard</span>
            </button>
          </div>

          <div className="flex gap-2 items-center">
            <button
              onClick={() => navigate(`/assessment/${encodeURIComponent(resultData.skill || rawSkill)}`)}
              className="btn btn-outline text-xs flex items-center gap-1.5"
              style={{ padding: '0.55rem 0.95rem', borderColor: 'var(--primary-300)', color: 'var(--primary-700)', backgroundColor: 'var(--primary-50)' }}
            >
              <RotateCcw size={14} />
              <span>Re-do Assessment</span>
            </button>

            {nextSkill ? (
              <button
                onClick={() => navigate(`/assessment/${encodeURIComponent(nextSkill.skill)}`)}
                className="btn btn-primary"
                style={{ padding: '0.6rem 1.25rem' }}
              >
                <span>Next Assessment ({nextSkill.skill})</span>
                <ArrowRight size={16} />
              </button>
            ) : (
              <button
                onClick={() => navigate('/recommendation')}
                className="btn btn-primary"
                style={{ padding: '0.6rem 1.25rem' }}
              >
                <span>View Recommendation</span>
                <ArrowRight size={16} />
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
