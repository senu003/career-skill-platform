import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import {
  CheckCircle2,
  XCircle,
  AlertCircle,
  ArrowRight,
  ArrowLeft,
  RotateCcw,
  RefreshCw,
  Lightbulb,
  BookOpen,
  Target,
  Sparkles,
  Clock,
  ChevronDown,
  ChevronUp,
  Compass
} from 'lucide-react';
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
  const { analysisResult } = useAssessment();


  const queryAttemptId = searchParams.get('attempt_id') || searchParams.get('attemptId');
  const analysisId = searchParams.get('analysis_id') || analysisResult?.analysis_id;
  const targetAttemptId = attemptId || queryAttemptId;
  const rawSkill = skill ? decodeURIComponent(skill) : '';

  const [resultData, setResultData] = useState(null);
  const [reviewData, setReviewData] = useState(null);
  const [reviewLoading, setReviewLoading] = useState(false);
  const [weaknessData, setWeaknessData] = useState(null);
  const [reviewFilter, setReviewFilter] = useState('all'); // 'all' | 'incorrect' | 'correct'
  const [expandedQuestions, setExpandedQuestions] = useState({});

  const hasResultRef = React.useRef(false);
  const hasReviewRef = React.useRef(false);

  const fallbackSkill = React.useMemo(() => {
    const skills = analysisResult?.skills || [];
    const assessed = skills.find((s) => s.assessed_level) || skills[0];
    return assessed?.skill || '';
  }, [analysisResult]);

  const normalizedSkill = rawSkill || resultData?.skill || fallbackSkill || '';
  const [loading, setLoading] = useState(!resultData);
  const [error, setError] = useState(null);

  const fetchResult = React.useCallback(async () => {
    let effectiveSkill = rawSkill;
    let effectiveAttempt = targetAttemptId;

    if (!effectiveSkill && !effectiveAttempt) {
      effectiveSkill = fallbackSkill;
    }

    // If still no skill or attempt, attempt auto-resolution from user's latest assessment history
    if (!effectiveSkill && !effectiveAttempt) {
      try {
        const hist = await fetchWithAuth('/assessment/history/me');
        if (hist && typeof hist === 'object') {
          let latestObs = null;
          Object.entries(hist).forEach(([sk, obsList]) => {
            if (Array.isArray(obsList)) {
              obsList.forEach((obs) => {
                if (!latestObs || new Date(obs.timestamp) > new Date(latestObs.timestamp)) {
                  latestObs = { ...obs, skill: sk };
                }
              });
            }
          });
          if (latestObs) {
            effectiveSkill = latestObs.skill;
            if (latestObs.attempt_id) {
              effectiveAttempt = latestObs.attempt_id;
            }
          }
        }
      } catch (histErr) {
        console.warn('Could not auto-resolve from assessment history:', histErr);
      }
    }

    if (!effectiveSkill && !effectiveAttempt) {
      setError('No skill or attempt specified. Complete an assessment to view detailed review and results.');
      setLoading(false);
      return;
    }

    // Only display full-screen loading spinner if we don't have results yet
    if (!hasResultRef.current) {
      setLoading(true);
    }
    setError(null);

    try {
      let endpoint;
      if (effectiveAttempt) {
        endpoint = `/assessment/${effectiveAttempt}/result`;
      } else {
        endpoint = `/assessment/result/${encodeURIComponent(effectiveSkill)}${
          analysisId ? `?analysis_id=${encodeURIComponent(analysisId)}` : ''
        }`;
      }

      const data = await fetchWithAuth(endpoint);
      setResultData(data);
      hasResultRef.current = true;

      // Fetch Question-by-Question Review if attempt_id is available
      const effectiveAttemptId = effectiveAttempt || data?.attempt_id;
      if (effectiveAttemptId) {
        try {
          if (!hasReviewRef.current) {
            setReviewLoading(true);
          }
          const rev = await fetchWithAuth(`/assessment/${effectiveAttemptId}/review`);
          setReviewData(rev);
          hasReviewRef.current = true;

          // Preserve user's collapse/expand states; only initialize if empty
          if (rev?.questions) {
            setExpandedQuestions((prev) => {
              if (prev && Object.keys(prev).length > 0) return prev;
              const initialExpanded = {};
              rev.questions.forEach((q) => {
                initialExpanded[q.question_id] = true;
              });
              return initialExpanded;
            });
          }
        } catch (revErr) {
          console.warn('Could not load review:', revErr);
        } finally {
          setReviewLoading(false);
        }
      }

      // Fetch personal weakness analysis
      try {
        const weak = await fetchWithAuth('/assessment/revision/weaknesses');
        setWeaknessData(weak);
      } catch (weakErr) {
        console.warn('Could not load weaknesses:', weakErr);
      }
    } catch (err) {
      setError(err.message || 'Failed to load assessment result.');
    } finally {
      setLoading(false);
    }
  }, [rawSkill, targetAttemptId, analysisId, fallbackSkill]);

  useEffect(() => {
    fetchResult();
  }, [fetchResult]);

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

  const reviewQuestions = reviewData?.questions || [];
  const correctCount = reviewQuestions.filter((q) => q.is_correct).length;
  const incorrectCount = reviewQuestions.length - correctCount;

  const filteredQuestions = reviewQuestions.filter((q) => {
    if (reviewFilter === 'correct') return q.is_correct;
    if (reviewFilter === 'incorrect') return !q.is_correct;
    return true;
  });

  const currentSkillName = (resultData?.skill || rawSkill || '').toLowerCase();
  const currentSkillWeakTopics = (weaknessData?.weak_topics || []).filter((w) => {
    const s = (w.skill || '').toLowerCase();
    return (
      s === currentSkillName ||
      (currentSkillName === 'sql' && s === 'postgresql') ||
      (currentSkillName === 'postgresql' && s === 'sql')
    );
  });

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
        <button
          onClick={() => navigate(`/interview-prep/skill/${encodeURIComponent(resultData.skill || rawSkill)}`)}
          className="btn btn-outline text-xs mt-3"
          style={{
            margin: '0.65rem auto 0',
            fontWeight: 600,
            display: 'inline-flex',
            alignItems: 'center',
            gap: '0.4rem',
            borderColor: '#bfdbfe',
            color: '#1d4ed8',
            backgroundColor: '#eff6ff',
          }}
        >
          <Compass size={14} />
          <span>Open in Interview Prep Hub</span>
        </button>
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

        {/* 4. TARGETED REVISION & WEAKNESS RECOMMENDATIONS */}
        <div
          style={{
            backgroundColor: '#f8fafc',
            border: '1px solid #e2e8f0',
            borderRadius: 'var(--radius-sm)',
            padding: '1.25rem 1.5rem',
            marginBottom: '1.75rem',
          }}
        >
          <div className="flex items-center justify-between gap-2 mb-3 flex-wrap">
            <div className="flex items-center gap-2">
              <div
                style={{
                  width: 28,
                  height: 28,
                  borderRadius: '50%',
                  backgroundColor: '#fee2e2',
                  color: '#dc2626',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <Target size={16} />
              </div>
              <div>
                <h3 className="font-bold text-main text-base" style={{ margin: 0 }}>
                  Targeted Revision Recommendations
                </h3>
                <span className="text-xs text-muted">
                  Rule-based weakness identification and explainable practice paths
                </span>
              </div>
            </div>
          </div>

          {currentSkillWeakTopics && currentSkillWeakTopics.length > 0 ? (
            <div className="flex flex-col gap-2.5 mt-2">
              {currentSkillWeakTopics.map((topicItem, idx) => (
                <div
                  key={idx}
                  style={{
                    backgroundColor: '#ffffff',
                    border: '1px solid #fecaca',
                    borderRadius: 'var(--radius-sm)',
                    padding: '0.85rem 1rem',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    flexWrap: 'wrap',
                    gap: '0.75rem',
                  }}
                >
                  <div style={{ flex: 1, minWidth: '220px' }}>
                    <div className="flex items-center gap-2 mb-1 flex-wrap">
                      <span className="font-bold text-sm text-main">{topicItem.topic}</span>
                      <span
                        className="badge"
                        style={{
                          backgroundColor: '#fee2e2',
                          color: '#991b1b',
                          fontSize: '0.7rem',
                          fontWeight: 600,
                        }}
                      >
                        Needs Revision
                      </span>
                      {topicItem.priority === 'high' && (
                        <span
                          className="badge"
                          style={{
                            backgroundColor: '#fef2f2',
                            color: '#b91c1c',
                            border: '1px solid #fca5a5',
                            fontSize: '0.68rem',
                          }}
                        >
                          High Priority
                        </span>
                      )}
                      <span className="text-xs text-muted">
                        Accuracy: {Math.round(topicItem.accuracy_pct || topicItem.accuracy * 100)}% ({topicItem.incorrect_count} missed)
                      </span>
                    </div>
                    <p className="text-xs text-body" style={{ margin: 0, color: '#475569' }}>
                      {topicItem.reason || topicItem.recommendation}
                    </p>
                  </div>

                  <button
                    onClick={() =>
                      navigate(
                        `/assessment/${encodeURIComponent(topicItem.skill)}?topic=${encodeURIComponent(
                          topicItem.topic
                        )}${analysisId ? `&analysis_id=${encodeURIComponent(analysisId)}` : ''}`
                      )
                    }
                    className="btn btn-outline text-xs flex items-center gap-1.5"
                    style={{
                      borderColor: 'var(--primary-600)',
                      color: 'var(--primary-700)',
                      backgroundColor: '#eff6ff',
                      fontWeight: 600,
                      padding: '0.45rem 0.85rem',
                    }}
                    title={`Practice questions on ${topicItem.topic}`}
                  >
                    <span>Practice Topic</span>
                    <ArrowRight size={13} />
                  </button>
                </div>
              ))}
            </div>
          ) : (
            <div
              style={{
                backgroundColor: '#f0fdf4',
                border: '1px solid #bbf7d0',
                borderRadius: 'var(--radius-sm)',
                padding: '0.75rem 1rem',
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem',
                color: '#166534',
                fontSize: '0.85rem',
              }}
            >
              <CheckCircle2 size={16} />
              <span>
                No weak topics detected for this skill! All tested concepts demonstrated strong performance.
              </span>
            </div>
          )}
        </div>

        {/* 5. QUESTION-BY-QUESTION REVIEW WITH EXPLANATIONS */}
        {reviewLoading && !reviewData ? (
          <div className="card text-center p-5 mb-6" style={{ padding: '2rem' }}>
            <div className="spinner spinner-dark mb-2" style={{ width: 24, height: 24 }}></div>
            <p className="text-xs text-muted">Loading detailed question review...</p>
          </div>
        ) : reviewQuestions.length > 0 ? (
          <div style={{ marginBottom: '1.75rem' }}>
            {/* Review Section Header & Filters */}
            <div
              className="flex items-center justify-between gap-3 mb-4 pb-2 flex-wrap"
              style={{ borderBottom: '1px solid #e2e8f0' }}
            >
              <div className="flex items-center gap-2">
                <BookOpen size={18} style={{ color: 'var(--primary-600)' }} />
                <h3 className="font-bold text-main text-base" style={{ margin: 0 }}>
                  Question-by-Question Review
                </h3>
                <span className="badge" style={{ backgroundColor: '#f1f5f9', color: '#475569', fontSize: '0.75rem' }}>
                  {reviewQuestions.length} Questions
                </span>
              </div>

              {/* Filter Tabs & Toggle */}
              <div className="flex items-center gap-2 flex-wrap">
                <div
                  style={{
                    display: 'flex',
                    backgroundColor: '#f1f5f9',
                    padding: '2px',
                    borderRadius: '6px',
                    fontSize: '0.75rem',
                  }}
                >
                  <button
                    onClick={() => setReviewFilter('all')}
                    style={{
                      padding: '3px 8px',
                      borderRadius: '4px',
                      border: 'none',
                      cursor: 'pointer',
                      fontWeight: 600,
                      backgroundColor: reviewFilter === 'all' ? '#ffffff' : 'transparent',
                      color: reviewFilter === 'all' ? '#0f172a' : '#64748b',
                      boxShadow: reviewFilter === 'all' ? '0 1px 2px rgba(0,0,0,0.06)' : 'none',
                    }}
                  >
                    All ({reviewQuestions.length})
                  </button>
                  <button
                    onClick={() => setReviewFilter('incorrect')}
                    style={{
                      padding: '3px 8px',
                      borderRadius: '4px',
                      border: 'none',
                      cursor: 'pointer',
                      fontWeight: 600,
                      backgroundColor: reviewFilter === 'incorrect' ? '#ffffff' : 'transparent',
                      color: reviewFilter === 'incorrect' ? '#dc2626' : '#64748b',
                      boxShadow: reviewFilter === 'incorrect' ? '0 1px 2px rgba(0,0,0,0.06)' : 'none',
                    }}
                  >
                    Incorrect ({incorrectCount})
                  </button>
                  <button
                    onClick={() => setReviewFilter('correct')}
                    style={{
                      padding: '3px 8px',
                      borderRadius: '4px',
                      border: 'none',
                      cursor: 'pointer',
                      fontWeight: 600,
                      backgroundColor: reviewFilter === 'correct' ? '#ffffff' : 'transparent',
                      color: reviewFilter === 'correct' ? '#16a34a' : '#64748b',
                      boxShadow: reviewFilter === 'correct' ? '0 1px 2px rgba(0,0,0,0.06)' : 'none',
                    }}
                  >
                    Correct ({correctCount})
                  </button>
                </div>

                <button
                  onClick={() => {
                    const allExpanded = Object.values(expandedQuestions).every(Boolean);
                    if (allExpanded) {
                      setExpandedQuestions({});
                    } else {
                      const all = {};
                      reviewQuestions.forEach((q) => {
                        all[q.question_id] = true;
                      });
                      setExpandedQuestions(all);
                    }
                  }}
                  className="btn btn-outline text-xs"
                  style={{ padding: '0.3rem 0.6rem', fontSize: '0.72rem' }}
                >
                  {Object.values(expandedQuestions).every(Boolean) ? 'Collapse All' : 'Expand All'}
                </button>
              </div>
            </div>

            {/* Questions List */}
            <div className="flex flex-col gap-3">
              {filteredQuestions.map((q, idx) => {
                const isExpanded = expandedQuestions[q.question_id] ?? true;
                const optionsEntries = Object.entries(q.options || {});

                return (
                  <div
                    key={q.question_id || idx}
                    style={{
                      backgroundColor: '#ffffff',
                      border: `1.5px solid ${q.is_correct ? '#bbf7d0' : '#fecaca'}`,
                      borderRadius: 'var(--radius-sm)',
                      overflow: 'hidden',
                      transition: 'all 0.2s',
                    }}
                  >
                    {/* Question Header Bar */}
                    <div
                      role="button"
                      tabIndex={0}
                      onClick={(e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        setExpandedQuestions((prev) => ({
                          ...prev,
                          [q.question_id]: !prev[q.question_id],
                        }));
                      }}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault();
                          setExpandedQuestions((prev) => ({
                            ...prev,
                            [q.question_id]: !prev[q.question_id],
                          }));
                        }
                      }}
                      style={{
                        padding: '0.85rem 1rem',
                        backgroundColor: q.is_correct ? '#f0fdf4' : '#fef2f2',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        cursor: 'pointer',
                        gap: '0.5rem',
                      }}
                    >
                      <div className="flex items-center gap-2.5 flex-wrap">
                        <div
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            width: 22,
                            height: 22,
                            borderRadius: '50%',
                            backgroundColor: q.is_correct ? '#dcfce7' : '#fee2e2',
                            color: q.is_correct ? '#16a34a' : '#dc2626',
                          }}
                        >
                          {q.is_correct ? <CheckCircle2 size={15} /> : <XCircle size={15} />}
                        </div>
                        <span className="font-bold text-sm text-main">
                          Q{idx + 1}. {q.topic || q.skill}
                        </span>
                        {q.level && (
                          <span
                            className="badge"
                            style={{
                              backgroundColor: '#e2e8f0',
                              color: '#334155',
                              fontSize: '0.68rem',
                            }}
                          >
                            {formatLevel(q.level)}
                          </span>
                        )}
                        {q.time_taken !== null && q.time_taken !== undefined && (
                          <span
                            className="text-xs text-muted flex items-center gap-1"
                            style={{ fontSize: '0.72rem' }}
                          >
                            <Clock size={12} />
                            <span>{Math.round(q.time_taken)}s</span>
                          </span>
                        )}
                      </div>

                      <div className="flex items-center gap-2">
                        <span
                          className="badge"
                          style={{
                            backgroundColor: q.is_correct ? '#dcfce7' : '#fee2e2',
                            color: q.is_correct ? '#166534' : '#991b1b',
                            fontSize: '0.7rem',
                            fontWeight: 700,
                          }}
                        >
                          {q.is_correct ? 'Correct' : 'Incorrect'}
                        </span>
                        <div style={{ color: '#64748b' }}>
                          {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                        </div>
                      </div>
                    </div>

                    {/* Question Content (Collapsible) */}
                    {isExpanded && (
                      <div style={{ padding: '1rem 1.25rem' }}>
                        {/* Question Prompt */}
                        <p
                          className="font-semibold text-main text-sm mb-3"
                          style={{ lineHeight: 1.5, margin: '0 0 0.85rem' }}
                        >
                          {q.question}
                        </p>

                        {/* Options Grid */}
                        <div className="flex flex-col gap-1.5 mb-3">
                          {optionsEntries.map(([optKey, optText]) => {
                            const isUserChoice = (q.selected_answer || '').toUpperCase() === optKey.toUpperCase();
                            const isCorrectChoice = (q.correct_answer || '').toUpperCase() === optKey.toUpperCase();

                            let bgColor = '#ffffff';
                            let borderColor = '#e2e8f0';
                            let textColor = '#334155';
                            let indicator = null;

                            if (isUserChoice && q.is_correct) {
                              bgColor = '#f0fdf4';
                              borderColor = '#86efac';
                              textColor = '#166534';
                              indicator = (
                                <span className="flex items-center gap-1 text-xs font-semibold text-green-700">
                                  <CheckCircle2 size={13} /> Your Answer (Correct)
                                </span>
                              );
                            } else if (isUserChoice && !q.is_correct) {
                              bgColor = '#fef2f2';
                              borderColor = '#fca5a5';
                              textColor = '#991b1b';
                              indicator = (
                                <span className="flex items-center gap-1 text-xs font-semibold text-red-700">
                                  <XCircle size={13} /> Your Answer (Incorrect)
                                </span>
                              );
                            } else if (isCorrectChoice && !q.is_correct) {
                              bgColor = '#f0fdf4';
                              borderColor = '#86efac';
                              textColor = '#166534';
                              indicator = (
                                <span className="flex items-center gap-1 text-xs font-semibold text-green-700">
                                  <CheckCircle2 size={13} /> Correct Answer
                                </span>
                              );
                            }

                            return (
                              <div
                                key={optKey}
                                style={{
                                  display: 'flex',
                                  alignItems: 'center',
                                  justifyContent: 'space-between',
                                  padding: '0.55rem 0.85rem',
                                  borderRadius: '6px',
                                  backgroundColor: bgColor,
                                  border: `1.5px solid ${borderColor}`,
                                  fontSize: '0.82rem',
                                  color: textColor,
                                  gap: '0.5rem',
                                }}
                              >
                                <div className="flex items-center gap-2">
                                  <span
                                    style={{
                                      width: 20,
                                      height: 20,
                                      borderRadius: '4px',
                                      backgroundColor: isCorrectChoice ? '#bbf7d0' : isUserChoice ? '#fecaca' : '#f1f5f9',
                                      display: 'inline-flex',
                                      alignItems: 'center',
                                      justifyContent: 'center',
                                      fontWeight: 700,
                                      fontSize: '0.72rem',
                                    }}
                                  >
                                    {optKey}
                                  </span>
                                  <span>{optText}</span>
                                </div>
                                {indicator}
                              </div>
                            );
                          })}
                        </div>

                        {/* RATIONALE & INSIGHTS CARDS */}
                        <div className="flex flex-col gap-2 mt-3 pt-2" style={{ borderTop: '1px solid #f1f5f9' }}>
                          {/* 1. Explanation */}
                          {q.explanation && (
                            <div
                              style={{
                                backgroundColor: '#f8fafc',
                                border: '1px solid #e2e8f0',
                                borderRadius: '6px',
                                padding: '0.65rem 0.85rem',
                                display: 'flex',
                                gap: '0.5rem',
                                alignItems: 'flex-start',
                              }}
                            >
                              <Lightbulb size={15} style={{ color: '#0284c7', marginTop: '2px', flexShrink: 0 }} />
                              <div>
                                <span className="font-bold text-xs" style={{ color: '#0369a1' }}>
                                  Explanation:{' '}
                                </span>
                                <span className="text-xs" style={{ color: '#334155', lineHeight: 1.45 }}>
                                  {q.explanation}
                                </span>
                              </div>
                            </div>
                          )}

                          {/* 2. Misconception */}
                          {q.misconception && (
                            <div
                              style={{
                                backgroundColor: '#fffbeb',
                                border: '1px solid #fde68a',
                                borderRadius: '6px',
                                padding: '0.65rem 0.85rem',
                                display: 'flex',
                                gap: '0.5rem',
                                alignItems: 'flex-start',
                              }}
                            >
                              <AlertCircle size={15} style={{ color: '#d97706', marginTop: '2px', flexShrink: 0 }} />
                              <div>
                                <span className="font-bold text-xs" style={{ color: '#b45309' }}>
                                  Common Misconception:{' '}
                                </span>
                                <span className="text-xs" style={{ color: '#78350f', lineHeight: 1.45 }}>
                                  {q.misconception}
                                </span>
                              </div>
                            </div>
                          )}

                          {/* 3. Interview Tip */}
                          {q.interview_tip && (
                            <div
                              style={{
                                backgroundColor: '#f0fdf4',
                                border: '1px solid #bbf7d0',
                                borderRadius: '6px',
                                padding: '0.65rem 0.85rem',
                                display: 'flex',
                                gap: '0.5rem',
                                alignItems: 'flex-start',
                              }}
                            >
                              <Sparkles size={15} style={{ color: '#16a34a', marginTop: '2px', flexShrink: 0 }} />
                              <div>
                                <span className="font-bold text-xs" style={{ color: '#15803d' }}>
                                  Interview Pro-Tip:{' '}
                                </span>
                                <span className="text-xs" style={{ color: '#14532d', lineHeight: 1.45 }}>
                                  {q.interview_tip}
                                </span>
                              </div>
                            </div>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        ) : null}

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
