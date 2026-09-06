import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Clock, ArrowRight, AlertCircle, RefreshCw, CheckCircle, ArrowLeft } from 'lucide-react';
import { fetchWithAuth } from '../api';
import { useAssessment } from '../context/AssessmentContext';
import { isSupportedSkill } from '../utils/supportedSkills';

export default function AssessmentPage() {
  const { skill } = useParams();
  const navigate = useNavigate();
  const { analysisResult } = useAssessment();

  const normalizedSkill = skill ? decodeURIComponent(skill) : '';

  // Attempt & Backend Assessment State
  const [attemptId, setAttemptId] = useState(null);
  const [requiredLevelState, setRequiredLevelState] = useState('');
  const [questions, setQuestions] = useState([]);
  const [currentIndex, setCurrentIndex] = useState(0);

  // User Interaction State
  const [needsLevelSelection, setNeedsLevelSelection] = useState(false);
  const [selectedAnswer, setSelectedAnswer] = useState('');
  const [timeTakenSeconds, setTimeTakenSeconds] = useState(0);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [submitError, setSubmitError] = useState(null);

  // Format Helper: Capitalize text strings safely
  const formatLevel = (lvl) => {
    if (!lvl) return 'N/A';
    return lvl.charAt(0).toUpperCase() + lvl.slice(1).toLowerCase();
  };

  // Format Helper: Format timer as 00:00 or seconds
  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  // Determine required level from AssessmentContext or return 'unspecified'
  const getRequiredLevel = () => {
    if (!normalizedSkill) return null;
    const skillsList = analysisResult?.skills || [];
    const foundSkill = skillsList.find(
      (s) => s.skill.toLowerCase() === normalizedSkill.toLowerCase()
    );
    const rawLvl = foundSkill?.required_level || foundSkill?.level;
    if (!rawLvl) return null;
    const cleanLvl = rawLvl.toLowerCase().trim();
    if (['basic', 'intermediate', 'advanced'].includes(cleanLvl)) {
      return cleanLvl;
    }
    return 'unspecified';
  };

  // Find next supported skill if current is unsupported, prioritizing identified weakness/missing skills first
  const getNextSupportedSkill = () => {
    const skills = analysisResult?.skills || [
      ...(analysisResult?.matched_skills || []),
      ...(analysisResult?.missing_skills || []),
    ];
    if (!skills || skills.length === 0) return null;

    const currentName = (normalizedSkill || '').toLowerCase().trim();

    const unassessed = skills.filter(
      (s) =>
        (s.skill || '').toLowerCase().trim() !== currentName &&
        !s.assessed_level &&
        isSupportedSkill(s.skill)
    );

    if (unassessed.length === 0) return null;

    const weaknessOrMissing = unassessed.find(
      (s) => s.is_weakness || !s.matched || (s.level_gap !== null && s.level_gap > 0)
    );

    return weaknessOrMissing || unassessed[0];
  };

  const nextSupportedSkill = getNextSupportedSkill();

  // Assessment Setup with specific target level (POST /assessment/start)
  const startAssessmentWithLevel = async (targetLevel) => {
    if (!normalizedSkill || !targetLevel) {
      setError('No skill or level selected for assessment.');
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);
    setSubmitError(null);

    try {
      const data = await fetchWithAuth('/assessment/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          skill: normalizedSkill,
          required_level: targetLevel,
        }),
      });

      if (!data.questions || data.questions.length === 0) {
        throw new Error(`No assessment questions returned for ${normalizedSkill}.`);
      }

      setAttemptId(data.attempt_id);
      setRequiredLevelState(data.required_level || targetLevel);
      setQuestions(data.questions);
      setCurrentIndex(0);
      setSelectedAnswer('');
      setTimeTakenSeconds(0);
      setNeedsLevelSelection(false);
    } catch (err) {
      setError(err.message || 'Failed to start technical assessment. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!normalizedSkill) {
      setError('No skill selected for assessment.');
      setLoading(false);
      return;
    }

    const detectedLevel = getRequiredLevel();
    if (detectedLevel && ['basic', 'intermediate', 'advanced'].includes(detectedLevel)) {
      setNeedsLevelSelection(false);
      startAssessmentWithLevel(detectedLevel);
    } else {
      // Required level is unspecified or not present -> prompt candidate to choose target level
      setNeedsLevelSelection(true);
      setLoading(false);
    }
  }, [skill]);

  // Question Timer Interval (tracks time spent on current question in seconds)
  useEffect(() => {
    if (loading || submitting || error || needsLevelSelection || questions.length === 0) return;

    const timer = setInterval(() => {
      setTimeTakenSeconds((prev) => prev + 1);
    }, 1000);

    return () => clearInterval(timer);
  }, [loading, submitting, error, needsLevelSelection, currentIndex, questions.length]);

  // Current Question Object
  const currentQuestion = questions[currentIndex];
  const isLastQuestion = currentIndex >= questions.length - 1;

  // Submit Answer & Transition Flow (POST /assessment/answer & POST /assessment/{attempt_id}/complete)
  const handleNextOrFinish = async () => {
    if (!selectedAnswer || submitting || !currentQuestion || !attemptId) return;

    setSubmitting(true);
    setSubmitError(null);

    const timeSpent = Math.max(1, timeTakenSeconds);

    try {
      // 1. Submit answer for current question
      const answerRes = await fetchWithAuth('/assessment/answer', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          attempt_id: attemptId,
          question_id: currentQuestion.id,
          selected_answer: selectedAnswer,
          time_taken: timeSpent,
        }),
      });

      // 2. Append new questions if level transition provides next_questions
      let updatedQuestions = [...questions];
      if (answerRes.next_questions && Array.isArray(answerRes.next_questions) && answerRes.next_questions.length > 0) {
        const existingIds = new Set(questions.map((q) => q.id));
        const newQs = answerRes.next_questions.filter((q) => !existingIds.has(q.id));
        updatedQuestions = [...questions, ...newQs];
        setQuestions(updatedQuestions);
      }

      // Check if attempt is completed or all questions in updated queue are answered
      const reachedEnd = currentIndex + 1 >= updatedQuestions.length || answerRes.attempt_completed;

      if (reachedEnd) {
        // 3. Call backend complete endpoint
        await fetchWithAuth(`/assessment/${attemptId}/complete`, {
          method: 'POST',
        });

        // 4. Navigate to individual result page
        navigate(`/results/${encodeURIComponent(normalizedSkill)}`);
      } else {
        // 5. Advance to next question
        setCurrentIndex((prev) => prev + 1);
        setSelectedAnswer('');
        setTimeTakenSeconds(0);
      }
    } catch (err) {
      setSubmitError(err.message || 'Failed to submit answer. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleRetry = () => {
    const detectedLevel = getRequiredLevel();
    if (detectedLevel && ['basic', 'intermediate', 'advanced'].includes(detectedLevel)) {
      startAssessmentWithLevel(detectedLevel);
    } else {
      setNeedsLevelSelection(true);
      setError(null);
    }
  };

  // RENDER 1: Target Level Selection Prompt (When job requirement level is Unspecified)
  if (needsLevelSelection && !loading) {
    return (
      <div className="assessment-container fade-in mt-4" style={{ paddingTop: '1.5rem' }}>
        <div className="page-header text-center mb-6">
          <span className="badge badge-purple mb-2">Technical Assessment</span>
          <h1 className="page-title">{normalizedSkill}</h1>
          <p className="text-muted text-sm mt-1">
            Target proficiency level selection required
          </p>
        </div>

        <div className="card text-center" style={{ padding: '2.5rem 2rem', maxWidth: '680px', margin: '0 auto' }}>
          <div className="badge badge-purple mb-3" style={{ padding: '0.4rem 0.9rem', fontSize: '0.85rem' }}>
            Requirement Level: Unspecified
          </div>
          <h2 className="card-title text-xl mb-2">Select Assessment Level</h2>
          <p className="text-muted text-sm mb-6" style={{ maxWidth: '520px', margin: '0 auto 1.75rem', lineHeight: 1.5 }}>
            The job description did not specify a required proficiency level for <strong>{normalizedSkill}</strong>. Please select the target level you wish to be assessed against:
          </p>

          {error && (
            <div className="alert-error flex items-center justify-center gap-2 mb-6" style={{ margin: '0 auto 1.5rem' }}>
              <AlertCircle size={18} />
              <span>{error}</span>
            </div>
          )}

          <div className="grid grid-cols-3 gap-4 mb-6">
            <button
              type="button"
              onClick={() => startAssessmentWithLevel('basic')}
              className="card option-card text-left"
              style={{
                padding: '1.25rem',
                border: '1.5px solid var(--border-color)',
                cursor: 'pointer',
                transition: 'all 0.2s ease',
                display: 'flex',
                flexDirection: 'column',
                gap: '0.5rem',
                margin: 0
              }}
            >
              <div className="flex items-center justify-between w-full">
                <span className="badge badge-purple" style={{ fontSize: '0.75rem' }}>Basic</span>
                <ArrowRight size={16} style={{ color: 'var(--primary-600)' }} />
              </div>
              <div className="font-semibold text-main text-sm" style={{ marginTop: '0.25rem' }}>Basic Level</div>
              <div className="text-xs text-muted" style={{ lineHeight: 1.4 }}>Core syntax, fundamental concepts, and basic programming logic.</div>
            </button>

            <button
              type="button"
              onClick={() => startAssessmentWithLevel('intermediate')}
              className="card option-card text-left"
              style={{
                padding: '1.25rem',
                border: '1.5px solid var(--border-color)',
                cursor: 'pointer',
                transition: 'all 0.2s ease',
                display: 'flex',
                flexDirection: 'column',
                gap: '0.5rem',
                margin: 0
              }}
            >
              <div className="flex items-center justify-between w-full">
                <span className="badge badge-purple" style={{ fontSize: '0.75rem' }}>Intermediate</span>
                <ArrowRight size={16} style={{ color: 'var(--primary-600)' }} />
              </div>
              <div className="font-semibold text-main text-sm" style={{ marginTop: '0.25rem' }}>Intermediate Level</div>
              <div className="text-xs text-muted" style={{ lineHeight: 1.4 }}>Practical application, standard APIs, and common patterns.</div>
            </button>

            <button
              type="button"
              onClick={() => startAssessmentWithLevel('advanced')}
              className="card option-card text-left"
              style={{
                padding: '1.25rem',
                border: '1.5px solid var(--border-color)',
                cursor: 'pointer',
                transition: 'all 0.2s ease',
                display: 'flex',
                flexDirection: 'column',
                gap: '0.5rem',
                margin: 0
              }}
            >
              <div className="flex items-center justify-between w-full">
                <span className="badge badge-purple" style={{ fontSize: '0.75rem' }}>Advanced</span>
                <ArrowRight size={16} style={{ color: 'var(--primary-600)' }} />
              </div>
              <div className="font-semibold text-main text-sm" style={{ marginTop: '0.25rem' }}>Advanced Level</div>
              <div className="text-xs text-muted" style={{ lineHeight: 1.4 }}>In-depth architecture, performance optimization, and edge cases.</div>
            </button>
          </div>

          <div className="flex justify-center pt-2">
            <button onClick={() => navigate('/dashboard')} className="btn btn-outline">
              <ArrowLeft size={16} />
              <span>Back to Dashboard</span>
            </button>
          </div>
        </div>
      </div>
    );
  }

  // RENDER 2: Loading State
  if (loading) {
    return (
      <div className="assessment-container fade-in text-center mt-4" style={{ paddingTop: '3rem' }}>
        <div className="card" style={{ padding: '3rem 2rem' }}>
          <div className="spinner spinner-dark mb-4" style={{ width: 36, height: 36, borderWidth: 3 }}></div>
          <h2 className="card-title">Preparing Your Technical Assessment</h2>
          <p className="text-muted text-sm">Loading real assessment questions for {normalizedSkill || 'skill'}...</p>
        </div>
      </div>
    );
  }

  // RENDER 3: Initial Start Error State
  if (error) {
    const isUnsupported = !isSupportedSkill(normalizedSkill) || error.toLowerCase().includes('unsupported');
    return (
      <div className="assessment-container fade-in mt-4" style={{ paddingTop: '2rem' }}>
        <div className="card text-center" style={{ padding: '2.5rem 1.75rem' }}>
          <div className="alert-error flex items-center justify-center gap-2 mb-4" style={{ margin: '0 auto 1.5rem', maxWidth: '500px' }}>
            <AlertCircle size={20} />
            <span>{error}</span>
          </div>
          <h2 className="card-title mb-2">Assessment Unavailable</h2>
          <p className="text-muted text-sm mb-6" style={{ maxWidth: '500px', margin: '0 auto 1.5rem' }}>
            {isUnsupported
              ? `Technical MCQ assessment is currently available for JavaScript, React, and PostgreSQL. Assessment for ${normalizedSkill || 'this skill'} is not yet supported.`
              : `Unable to load the assessment for ${normalizedSkill || 'this skill'}.`}
          </p>
          <div className="flex justify-center gap-3 flex-wrap">
            <button onClick={() => navigate('/dashboard')} className="btn btn-outline">
              <ArrowLeft size={16} />
              <span>Back to Dashboard</span>
            </button>

            {isUnsupported ? (
              nextSupportedSkill ? (
                <button onClick={() => navigate(`/assessment/${encodeURIComponent(nextSupportedSkill.skill)}`)} className="btn btn-primary">
                  <span>Assess {nextSupportedSkill.skill}</span>
                  <ArrowRight size={16} />
                </button>
              ) : (
                <button onClick={() => navigate('/recommendation')} className="btn btn-primary">
                  <span>View Final Recommendation</span>
                  <ArrowRight size={16} />
                </button>
              )
            ) : (
              <button onClick={handleRetry} className="btn btn-primary">
                <RefreshCw size={16} />
                <span>Retry</span>
              </button>
            )}
          </div>
        </div>
      </div>
    );
  }

  if (!currentQuestion) return null;

  // Options dictionary (e.g. { A: "text", B: "text" })
  const optionsEntries = Object.entries(currentQuestion.options || {});
  const progressPercent = Math.min(100, Math.round(((currentIndex + 1) / questions.length) * 100));

  return (
    <div className="assessment-container fade-in">
      {/* 1. HEADER SECTION */}
      <div className="page-header text-center mb-6">
        <span className="badge badge-purple mb-2">Technical Assessment</span>
        <h1 className="page-title">{normalizedSkill}</h1>
        <p className="page-subtitle font-semibold" style={{ color: 'var(--primary-700)' }}>
          Required Level: {formatLevel(requiredLevelState)}
        </p>
      </div>

      {/* 2. PROGRESS BAR & INDICATOR */}
      <div className="card mb-4" style={{ padding: '1rem 1.25rem' }}>
        <div className="flex justify-between items-center text-sm font-semibold mb-2" style={{ color: 'var(--text-main)' }}>
          <span>Question {currentIndex + 1} of {questions.length}</span>
          <span className="text-muted text-xs font-normal">{progressPercent}% Completed</span>
        </div>
        <div className="assessment-progress-track">
          <div className="assessment-progress-fill" style={{ width: `${progressPercent}%` }}></div>
        </div>
      </div>

      {/* 3. QUESTION CARD */}
      <div className="card">
        {/* Card Header Info (Difficulty + Timer) */}
        <div className="flex justify-between items-center mb-4 pb-3" style={{ borderBottom: '1px solid var(--border-color)' }}>
          {currentQuestion.level ? (
            <span className="badge badge-purple">
              {formatLevel(currentQuestion.level)} Level
            </span>
          ) : (
            <span />
          )}

          <div className="timer-badge">
            <Clock size={14} />
            <span>{formatTime(timeTakenSeconds)}</span>
          </div>
        </div>

        {/* Question Prompt */}
        <h2 className="font-semibold text-lg text-main mb-4" style={{ lineHeight: 1.4 }}>
          {currentQuestion.question}
        </h2>

        {/* Answer Choices */}
        <div className="options-grid">
          {optionsEntries.map(([key, value]) => {
            const isSelected = selectedAnswer === key;
            return (
              <div
                key={key}
                onClick={() => !submitting && setSelectedAnswer(key)}
                className={`option-card ${isSelected ? 'selected' : ''} ${submitting ? 'disabled' : ''}`}
              >
                <div className="option-badge">{key}</div>
                <div className="option-text">{value}</div>
              </div>
            );
          })}
        </div>

        {/* Submission Error Alert */}
        {submitError && (
          <div className="alert-error mt-4 flex items-center gap-2">
            <AlertCircle size={18} />
            <span>{submitError}</span>
          </div>
        )}

        {/* Navigation Footer */}
        <div className="flex justify-between items-center mt-6 pt-4" style={{ borderTop: '1px solid var(--border-color)' }}>
          <button
            onClick={() => navigate('/dashboard')}
            disabled={submitting}
            className="btn btn-outline text-xs"
            style={{ padding: '0.4rem 0.85rem' }}
          >
            Exit Assessment
          </button>

          <button
            onClick={handleNextOrFinish}
            disabled={!selectedAnswer || submitting}
            className="btn btn-primary"
            style={{ padding: '0.65rem 1.5rem' }}
          >
            {submitting ? (
              <>
                <span className="spinner"></span>
                <span>Submitting...</span>
              </>
            ) : isLastQuestion ? (
              <>
                <span>Finish Assessment</span>
                <CheckCircle size={18} />
              </>
            ) : (
              <>
                <span>Next</span>
                <ArrowRight size={18} />
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
