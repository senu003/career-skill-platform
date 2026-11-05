import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  ChevronLeft,
  ChevronRight,
  CheckCircle2,
  XCircle,
  Lightbulb,
  AlertCircle,
  Sparkles,
  Clock,
  Calendar,
  RefreshCw
} from 'lucide-react';

import { fetchWithAuth } from '../../api';

export default function AssessmentReviewPage() {
  const { attemptId } = useParams();
  const navigate = useNavigate();

  const [reviewData, setReviewData] = useState(null);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const loadReview = async () => {
    if (!attemptId) return;
    setLoading(true);
    setError(null);
    try {
      const data = await fetchWithAuth(`/assessment/${attemptId}/review`);
      setReviewData(data);
      setCurrentIndex(0);
    } catch (err) {
      console.error('Failed to load attempt review:', err);
      setError(err.message || 'Unable to retrieve assessment review details.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadReview();
  }, [attemptId]);

  if (loading) {
    return (
      <div className="container text-center" style={{ padding: '4rem 1rem' }}>
        <div className="spinner spinner-dark mb-4" style={{ width: 36, height: 36, margin: '0 auto 1.5rem' }}></div>
        <h2 className="card-title">Loading Attempt #{attemptId} Review</h2>
        <p className="text-muted text-sm">Retrieving verified question rationale, tips, and submitted responses...</p>
      </div>
    );
  }

  if (error || !reviewData || !reviewData.questions || reviewData.questions.length === 0) {
    return (
      <div className="container" style={{ maxWidth: '640px', padding: '3rem 1rem' }}>
        <div className="card text-center" style={{ padding: '2.5rem' }}>
          <div className="alert-error flex items-center justify-center gap-2 mb-4" style={{ margin: '0 auto 1.5rem' }}>
            <AlertCircle size={20} />
            <span>{error || 'No review data found for this attempt.'}</span>
          </div>
          <h2 className="card-title mb-2">Review Not Found</h2>
          <p className="text-muted text-sm mb-5">
            Unable to load question-by-question review for Attempt #{attemptId}.
          </p>
          <div className="flex justify-center gap-3">
            <button onClick={() => navigate('/interview-prep')} className="btn btn-outline">
              <ArrowLeft size={15} />
              <span>Back to Interview Prep</span>
            </button>
            <button onClick={loadReview} className="btn btn-primary">
              <RefreshCw size={15} />
              <span>Retry</span>
            </button>
          </div>
        </div>
      </div>
    );
  }

  const {
    skill,
    total_score,
    accuracy,
    avg_time_per_question,
    completed_at,
    questions = []
  } = reviewData;

  const currentQ = questions[currentIndex] || questions[0];
  const totalQuestions = questions.length;
  const isFirst = currentIndex === 0;
  const isLast = currentIndex === totalQuestions - 1;

  const scoreDisplay = total_score !== null && total_score !== undefined
    ? Math.round(total_score > 1 ? total_score : total_score * 100)
    : Math.round(accuracy * 100);

  const formattedDate = completed_at
    ? new Date(completed_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
    : 'Recent';

  const timeDisplay = avg_time_per_question !== null && avg_time_per_question !== undefined
    ? `${Math.round(avg_time_per_question)}s/question`
    : null;

  const optionsEntries = Object.entries(currentQ.options || {});

  return (
    <div className="container" style={{ maxWidth: '840px', padding: '1.25rem 1rem 3.5rem' }}>
      {/* 1. TOP BACK LINK */}
      <button
        onClick={() => navigate(`/interview-prep/skill/${encodeURIComponent(skill)}`)}
        className="btn btn-outline text-xs mb-4"
        style={{ padding: '0.35rem 0.75rem', fontWeight: 600, border: 'none', background: 'transparent' }}
      >
        <ArrowLeft size={15} />
        <span>Back to {skill} Analysis</span>
      </button>

      {/* 2. HEADER BAR & NAVIGATION */}
      <div className="card" style={{ padding: '1.25rem 1.5rem', marginBottom: '1.5rem' }}>
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <div>
            <h1 className="page-title" style={{ fontSize: '1.45rem', margin: 0 }}>
              Attempt #{attemptId} Review
            </h1>
            <div className="flex items-center gap-3 text-xs text-muted mt-1.5 flex-wrap">
              <span className="flex items-center gap-1 font-medium text-body">
                <Calendar size={13} style={{ color: 'var(--primary-400)' }} />
                <span>{formattedDate}</span>
              </span>
              <span>•</span>
              <span className="font-bold text-main">
                Score: {scoreDisplay}%
              </span>
              {timeDisplay && (
                <>
                  <span>•</span>
                  <span className="flex items-center gap-1">
                    <Clock size={13} style={{ color: 'var(--primary-400)' }} />
                    <span>Time: {timeDisplay}</span>
                  </span>
                </>
              )}
            </div>
          </div>

          {/* Previous / Next Controls */}
          <div className="flex items-center gap-2">
            <button
              onClick={() => setCurrentIndex((prev) => Math.max(0, prev - 1))}
              disabled={isFirst}
              className="btn btn-outline text-xs"
              style={{
                padding: '0.45rem 0.85rem',
                fontWeight: 600,
                opacity: isFirst ? 0.45 : 1,
                cursor: isFirst ? 'not-allowed' : 'pointer',
              }}
            >
              <ChevronLeft size={16} />
              <span>Previous</span>
            </button>
            <button
              onClick={() => setCurrentIndex((prev) => Math.min(totalQuestions - 1, prev + 1))}
              disabled={isLast}
              className="btn btn-primary text-xs"
              style={{
                padding: '0.45rem 0.95rem',
                fontWeight: 600,
                opacity: isLast ? 0.45 : 1,
                cursor: isLast ? 'not-allowed' : 'pointer',
              }}
            >
              <span>Next</span>
              <ChevronRight size={16} />
            </button>
          </div>
        </div>

        {/* Question Selector Pills */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.45rem',
            marginTop: '1.25rem',
            paddingTop: '1rem',
            borderTop: '1px solid var(--border-color)',
            overflowX: 'auto',
          }}
        >
          <span className="text-xs text-muted font-semibold mr-1">Questions:</span>
          {questions.map((q, idx) => {
            const isActive = idx === currentIndex;
            const isCorrect = q.is_correct;

            let pillStyle = {
              backgroundColor: isCorrect ? '#f0fdf4' : '#fef2f2',
              color: isCorrect ? '#166534' : '#b91c1c',
              borderColor: isCorrect ? '#bbf7d0' : '#fecaca',
            };

            return (
              <button
                key={q.question_id || idx}
                onClick={() => setCurrentIndex(idx)}
                className={`prep-question-pill ${isActive ? 'active' : ''}`}
                style={!isActive ? pillStyle : {}}
                title={`Question ${idx + 1}: ${isCorrect ? 'Correct' : 'Incorrect'}`}
              >
                Q{idx + 1}
              </button>
            );
          })}
        </div>
      </div>

      {/* 3. ACTIVE QUESTION CARD */}
      <div className="card" style={{ padding: '1.75rem', marginBottom: '1.5rem' }}>
        {/* Status Badge & Question Header */}
        <div className="flex items-center justify-between gap-2 mb-3.5 flex-wrap">
          <div className="flex items-center gap-2">
            <span
              className={`badge ${currentQ.is_correct ? 'badge-success' : ''}`}
              style={{
                fontWeight: 700,
                fontSize: '0.78rem',
                padding: '0.25rem 0.65rem',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '4px',
                backgroundColor: !currentQ.is_correct ? '#fee2e2' : undefined,
                color: !currentQ.is_correct ? '#991b1b' : undefined,
                border: !currentQ.is_correct ? '1px solid #fecaca' : undefined,
              }}
            >
              {currentQ.is_correct ? <CheckCircle2 size={14} /> : <XCircle size={14} />}
              <span>{currentQ.is_correct ? 'Correct' : 'Incorrect'}</span>
            </span>

            {currentQ.topic && (
              <span className="badge badge-purple" style={{ fontSize: '0.72rem' }}>
                {currentQ.topic}
              </span>
            )}

            {currentQ.level && (
              <span
                className="badge"
                style={{ backgroundColor: '#f8fafc', color: 'var(--text-muted)', fontSize: '0.72rem', border: '1px solid var(--border-color)' }}
              >
                {currentQ.level.toUpperCase()}
              </span>
            )}
          </div>

          <span className="text-xs text-muted font-medium">
            Question {currentIndex + 1} of {totalQuestions}
          </span>
        </div>

        {/* Question Prompt */}
        <h2
          style={{
            fontSize: '1.15rem',
            fontWeight: 700,
            color: 'var(--text-main)',
            lineHeight: 1.5,
            margin: '0 0 1.25rem',
          }}
        >
          {currentQ.question}
        </h2>

        {/* Options List */}
        <div className="flex flex-col gap-2 mb-5">
          {optionsEntries.map(([optKey, optText]) => {
            const isExpected = (currentQ.correct_answer || '').toUpperCase() === optKey.toUpperCase();
            const isSelected = (currentQ.selected_answer || '').toUpperCase() === optKey.toUpperCase();

            let optionBg = '#ffffff';
            let optionBorder = 'var(--border-color)';
            let optionTextColor = 'var(--text-body)';
            let indicator = null;

            if (isExpected) {
              optionBg = '#f0fdf4';
              optionBorder = '#86efac';
              optionTextColor = '#166534';
              indicator = (
                <span className="flex items-center gap-1 text-xs font-semibold" style={{ color: 'var(--success-color)' }}>
                  <CheckCircle2 size={14} /> Expected Answer
                </span>
              );
            } else if (isSelected && !currentQ.is_correct) {
              optionBg = '#fef2f2';
              optionBorder = '#fca5a5';
              optionTextColor = '#991b1b';
              indicator = (
                <span className="flex items-center gap-1 text-xs font-semibold" style={{ color: 'var(--danger-color)' }}>
                  <XCircle size={14} /> Selected
                </span>
              );
            }

            return (
              <div
                key={optKey}
                style={{
                  padding: '0.75rem 1rem',
                  borderRadius: 'var(--radius-sm)',
                  backgroundColor: optionBg,
                  border: `1.5px solid ${optionBorder}`,
                  fontSize: '0.875rem',
                  color: optionTextColor,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: '0.75rem',
                  transition: 'all 0.15s ease',
                }}
              >
                <div className="flex items-center gap-2.5">
                  <span
                    style={{
                      width: 22,
                      height: 22,
                      borderRadius: '50%',
                      backgroundColor: isExpected ? '#bbf7d0' : isSelected ? '#fecaca' : '#f1f5f9',
                      color: isExpected ? '#15803d' : isSelected ? '#b91c1c' : '#475569',
                      display: 'inline-flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontSize: '0.75rem',
                      fontWeight: 700,
                      flexShrink: 0,
                    }}
                  >
                    {optKey}
                  </span>
                  <span style={{ fontWeight: isExpected || isSelected ? 600 : 400 }}>{optText}</span>
                </div>
                {indicator}
              </div>
            );
          })}
        </div>

        {/* Your Answer Section */}
        <div
          style={{
            backgroundColor: currentQ.is_correct ? '#f0fdf4' : '#fef2f2',
            border: `1px solid ${currentQ.is_correct ? '#bbf7d0' : '#fecaca'}`,
            borderRadius: 'var(--radius-sm)',
            padding: '0.85rem 1.15rem',
            marginBottom: '1.25rem',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '0.75rem',
            flexWrap: 'wrap',
          }}
        >
          <div>
            <div className="text-xs uppercase tracking-wider font-bold text-muted mb-0.5">Your answer</div>
            <div className="text-sm font-semibold" style={{ color: currentQ.is_correct ? '#166534' : '#991b1b' }}>
              {currentQ.selected_answer}
              {currentQ.selected_option_text ? `: ${currentQ.selected_option_text}` : ''}
            </div>
          </div>

          <span
            className="flex items-center gap-1 text-xs font-bold"
            style={{ color: currentQ.is_correct ? '#15803d' : '#b91c1c' }}
          >
            {currentQ.is_correct ? <CheckCircle2 size={15} /> : <XCircle size={15} />}
            <span>{currentQ.is_correct ? 'Correct' : 'Incorrect'}</span>
          </span>
        </div>

        {/* EXPLANATIONS, COMMON MISTAKES & INTERVIEW PRO-TIPS */}
        <div className="flex flex-col gap-2.5">
          {/* 1. Explanation */}
          {currentQ.explanation && (
            <div
              style={{
                backgroundColor: 'var(--primary-light)',
                border: '1px solid var(--primary-border)',
                borderRadius: 'var(--radius-sm)',
                padding: '0.85rem 1rem',
                display: 'flex',
                gap: '0.75rem',
                alignItems: 'flex-start',
              }}
            >
              <Lightbulb size={18} style={{ color: 'var(--primary-600)', marginTop: '2px', flexShrink: 0 }} />
              <div>
                <div className="font-bold text-xs uppercase tracking-wider mb-1" style={{ color: 'var(--primary-700)' }}>
                  Explanation
                </div>
                <p className="text-xs text-body" style={{ margin: 0, lineHeight: 1.55 }}>
                  {currentQ.explanation}
                </p>
              </div>
            </div>
          )}

          {/* 2. Common Mistake */}
          {currentQ.misconception && (
            <div
              style={{
                backgroundColor: '#fffbeb',
                border: '1px solid #fde68a',
                borderRadius: 'var(--radius-sm)',
                padding: '0.85rem 1rem',
                display: 'flex',
                gap: '0.75rem',
                alignItems: 'flex-start',
              }}
            >
              <AlertCircle size={18} style={{ color: '#d97706', marginTop: '2px', flexShrink: 0 }} />
              <div>
                <div className="font-bold text-xs uppercase tracking-wider mb-1" style={{ color: '#b45309' }}>
                  Common Mistake
                </div>
                <p className="text-xs text-body" style={{ margin: 0, lineHeight: 1.55, color: '#78350f' }}>
                  {currentQ.misconception}
                </p>
              </div>
            </div>
          )}

          {/* 3. Interview Tip */}
          {currentQ.interview_tip && (
            <div
              style={{
                backgroundColor: '#f0fdf4',
                border: '1px solid #bbf7d0',
                borderRadius: 'var(--radius-sm)',
                padding: '0.85rem 1rem',
                display: 'flex',
                gap: '0.75rem',
                alignItems: 'flex-start',
              }}
            >
              <Sparkles size={18} style={{ color: 'var(--success-color)', marginTop: '2px', flexShrink: 0 }} />
              <div>
                <div className="font-bold text-xs uppercase tracking-wider mb-1" style={{ color: '#15803d' }}>
                  Interview Tip
                </div>
                <p className="text-xs text-body" style={{ margin: 0, lineHeight: 1.55, color: '#14532d' }}>
                  {currentQ.interview_tip}
                </p>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* 4. BOTTOM NAVIGATION FOOTER */}
      <div className="flex items-center justify-between">
        <button
          onClick={() => setCurrentIndex((prev) => Math.max(0, prev - 1))}
          disabled={isFirst}
          className="btn btn-outline text-xs"
          style={{ opacity: isFirst ? 0.45 : 1, cursor: isFirst ? 'not-allowed' : 'pointer' }}
        >
          <ChevronLeft size={15} />
          <span>Previous Question</span>
        </button>

        <button
          onClick={() => {
            if (isLast) {
              navigate(`/interview-prep/skill/${encodeURIComponent(skill)}`);
            } else {
              setCurrentIndex((prev) => Math.min(totalQuestions - 1, prev + 1));
            }
          }}
          className="btn btn-primary text-xs"
        >
          <span>{isLast ? `Back to ${skill} Analysis` : 'Next Question'}</span>
          <ChevronRight size={15} />
        </button>
      </div>
    </div>
  );
}
