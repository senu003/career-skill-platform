import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import { CheckCircle2, AlertCircle, ArrowRight, ArrowLeft, RotateCcw, RefreshCw } from 'lucide-react';
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
  const { analysisResult, setAnalysisResult, updateSkillResult, refreshAnalysis } = useAssessment();

  const queryAttemptId = searchParams.get('attempt_id') || searchParams.get('attemptId');
  const analysisId = searchParams.get('analysis_id') || analysisResult?.analysis_id;
  const targetAttemptId = attemptId || queryAttemptId;
  const rawSkill = skill ? decodeURIComponent(skill) : '';

  const [resultData, setResultData] = useState(null);
  const normalizedSkill = rawSkill || resultData?.skill || '';
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Auto-restore latest session from backend if analysisResult is empty
  useEffect(() => {
    let isCancelled = false;
    if (!analysisResult) {
      const restoreLatestSession = async () => {
        try {
          const sessRes = await fetchWithAuth('/cv/sessions');
          if (isCancelled) return;
          if (sessRes?.sessions && sessRes.sessions.length > 0) {
            const latestSess = sessRes.sessions[0];
            const detailRes = await fetchWithAuth(`/cv/sessions/${latestSess.analysis_id}`);
            if (isCancelled) return;
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
    return () => {
      isCancelled = true;
    };
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
        endpoint = `/assessment/result/${encodeURIComponent(rawSkill)}${
          analysisId ? `?analysis_id=${encodeURIComponent(analysisId)}` : ''
        }`;
      }

      const data = await fetchWithAuth(endpoint);
      setResultData(data);
      if (updateSkillResult && data?.skill) {
        await updateSkillResult(data.skill, data);
      }
    } catch (err) {
      setError(err.message || 'Failed to load assessment result.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchResult();
  }, [skill, targetAttemptId, analysisId]);

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
            <button onClick={() => navigate(analysisId ? `/dashboard?analysis_id=${encodeURIComponent(analysisId)}` : '/dashboard')} className="btn btn-outline">
              <ArrowLeft size={16} />
              <span>Back to Skill Grid</span>
            </button>
            {isNotFound ? (
              <button onClick={() => navigate(`/assessment/${encodeURIComponent(normalizedSkill)}${analysisId ? `?analysis_id=${encodeURIComponent(analysisId)}` : ''}`)} className="btn btn-primary">
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
  
  // Explanation resolution
  const explanationText =
    RECOMMENDATION_EXPLANATIONS[recommendationLabel] ||
    ((resultData.recommendation_reason && resultData.recommendation_reason !== 'NONE' && resultData.recommendation_reason.trim())
      ? resultData.recommendation_reason
      : 'Assessment completed successfully.');

  const confidenceDisplay = formatConfidence(resultData.recommendation_confidence);
  const isMastered = (recommendationLabel || '').toLowerCase().trim() === 'mastered';

  return (
    <div className="assessment-container fade-in" style={{ maxWidth: '720px', margin: '0 auto' }}>
      {/* 1. Header */}
      <div className="page-header text-center mb-6">
        <div className="flex items-center justify-center gap-2 mb-2 flex-wrap">
          <span className="badge" style={{ backgroundColor: '#f1f5f9', color: '#475569', border: '1px solid #cbd5e1' }}>
            Skill Verification
          </span>
          {targetAttemptId && (
            <span className="badge" style={{ backgroundColor: '#f8fafc', color: '#64748b', border: '1px solid #e2e8f0' }}>
              Attempt #{targetAttemptId}
            </span>
          )}
        </div>
        <h1 className="page-title">{resultData.skill || rawSkill}</h1>
        <p className="text-muted text-sm mt-1">
          {targetAttemptId && resultData.completed_at
            ? `Completed on ${new Date(resultData.completed_at).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}`
            : 'Technical assessment score and evaluation summary'}
        </p>
      </div>

      {/* 2. Main Scorecard */}
      <div className="card" style={{ padding: '2rem' }}>
        {/* Outcome Status Banner */}
        <div
          style={{
            backgroundColor: '#f8fafc',
            border: '1px solid #e2e8f0',
            borderRadius: 'var(--radius-sm)',
            padding: '1.25rem 1.5rem',
            marginBottom: '1.5rem',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: '1rem',
          }}
        >
          <div className="flex items-center gap-3">
            <div
              style={{
                width: 36,
                height: 36,
                borderRadius: '50%',
                backgroundColor: isMastered ? '#dcfce7' : '#fef3c7',
                color: isMastered ? '#166534' : '#92400e',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              {isMastered ? <CheckCircle2 size={20} /> : <AlertCircle size={20} />}
            </div>
            <div>
              <div className="text-xs uppercase tracking-wider font-semibold text-muted">
                Evaluation Outcome
              </div>
              <div className="font-bold text-lg text-main" style={{ lineHeight: 1.2 }}>
                {recommendationLabel}
              </div>
            </div>
          </div>

          {confidenceDisplay && (
            <div
              style={{
                fontSize: '0.8rem',
                color: '#64748b',
                backgroundColor: '#ffffff',
                padding: '0.35rem 0.75rem',
                borderRadius: '9999px',
                border: '1px solid #e2e8f0',
                fontWeight: 500,
              }}
            >
              Confidence: <strong style={{ color: '#1e293b' }}>{confidenceDisplay}</strong>
            </div>
          )}
        </div>

        {/* 3 Metrics: Target Level | Assessed Level | Score */}
        <div className="grid grid-cols-3 gap-3 mb-5">
          <div
            style={{
              padding: '1rem',
              backgroundColor: '#ffffff',
              border: '1px solid #e2e8f0',
              borderRadius: 'var(--radius-sm)',
              textAlign: 'center',
            }}
          >
            <div className="text-xs text-muted font-medium mb-1">Target Level</div>
            <div className="font-bold text-lg text-main">
              {formatLevel(resultData.required_level)}
            </div>
          </div>

          <div
            style={{
              padding: '1rem',
              backgroundColor: '#ffffff',
              border: '1px solid #e2e8f0',
              borderRadius: 'var(--radius-sm)',
              textAlign: 'center',
            }}
          >
            <div className="text-xs text-muted font-medium mb-1">Assessed Level</div>
            <div className="font-bold text-lg text-main">
              {formatLevel(resultData.assessed_level)}
            </div>
          </div>

          <div
            style={{
              padding: '1rem',
              backgroundColor: '#ffffff',
              border: '1px solid #e2e8f0',
              borderRadius: 'var(--radius-sm)',
              textAlign: 'center',
            }}
          >
            <div className="text-xs text-muted font-medium mb-1">Score</div>
            <div className="font-bold text-lg text-main">
              {formatScore(resultData.total_score)}
            </div>
          </div>
        </div>

        {/* Feedback / Explanation */}
        <div
          style={{
            padding: '1rem 1.25rem',
            backgroundColor: '#ffffff',
            border: '1px solid #e2e8f0',
            borderRadius: 'var(--radius-sm)',
            marginBottom: '1.75rem',
          }}
        >
          <div className="text-xs uppercase tracking-wider font-semibold text-muted mb-1">
            Feedback & Insight
          </div>
          <p className="text-sm text-body" style={{ margin: 0, lineHeight: 1.5 }}>
            {explanationText}
          </p>
        </div>

        {/* Action Bar: Back to Grid, Retake, and Single Next Skill Button */}
        <div
          className="flex justify-between items-center pt-4 gap-3 flex-wrap"
          style={{ borderTop: '1px solid #e2e8f0' }}
        >
          <div className="flex items-center gap-2">
            <button
              onClick={() => navigate(analysisId ? `/dashboard?analysis_id=${encodeURIComponent(analysisId)}` : '/dashboard')}
              className="btn btn-outline text-xs flex items-center gap-1.5"
            >
              <ArrowLeft size={15} />
              <span>Back to Skill Grid</span>
            </button>
            <button
              onClick={() => navigate(`/assessment/${encodeURIComponent(resultData.skill || rawSkill)}${analysisId ? `?analysis_id=${encodeURIComponent(analysisId)}` : ''}`)}
              className="btn btn-outline text-xs flex items-center gap-1.5"
              style={{ color: 'var(--text-muted)' }}
              title="Retake assessment for this skill"
            >
              <RotateCcw size={14} />
              <span>Retake</span>
            </button>
          </div>

          <div>
            {nextSkill ? (
              <button
                onClick={() => navigate(`/assessment/${encodeURIComponent(nextSkill.skill)}${analysisId ? `?analysis_id=${encodeURIComponent(analysisId)}` : ''}`)}
                className="btn btn-primary"
                style={{ padding: '0.6rem 1.25rem', fontSize: '0.875rem' }}
              >
                <span>Next: Verify {nextSkill.skill}</span>
                <ArrowRight size={15} />
              </button>
            ) : (
              <button
                onClick={() => navigate(analysisId ? `/recommendation?analysis_id=${encodeURIComponent(analysisId)}` : '/recommendation')}
                className="btn btn-primary"
                style={{ padding: '0.6rem 1.25rem', fontSize: '0.875rem' }}
              >
                <span>View Career Recommendation</span>
                <ArrowRight size={15} />
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
