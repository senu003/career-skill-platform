import React, { useState } from 'react';
import { Copy, Check, FileText, AlertCircle, HelpCircle, ArrowRight } from 'lucide-react';

export default function CVFeedbackCard({ feedbackList }) {
  if (!feedbackList || feedbackList.length === 0) {
    return (
      <div className="card" style={{ background: 'var(--primary-50)', border: '1px solid var(--primary-200)' }}>
         <h2 className="card-title flex items-center gap-2 mb-2">
          <FileText size={20} style={{ color: 'var(--primary-700)' }} />
          <span>Recommended CV Improvements</span>
        </h2>
        <div className="flex items-center gap-2 text-emerald-700 bg-emerald-50 p-3 rounded" style={{ border: '1px solid #a7f3d0' }}>
          <Check size={18} />
          <span className="text-sm font-semibold">Your CV accurately reflects your skills. No specific wording improvements were suggested.</span>
        </div>
      </div>
    );
  }

  return (
    <div className="card" style={{ background: 'var(--primary-50)', border: '1px solid var(--primary-200)' }}>
      <h2 className="card-title flex items-center gap-2 mb-2">
        <FileText size={20} style={{ color: 'var(--primary-700)' }} />
        <span>Recommended CV Improvements</span>
      </h2>
      <p className="text-sm text-muted mb-4">
        Actionable suggestions to improve how your skills are presented in your CV.
      </p>

      <div className="flex flex-col gap-4">
        {feedbackList.map((item, idx) => (
          <FeedbackItem key={idx} item={item} />
        ))}
      </div>
    </div>
  );
}

function FeedbackItem({ item }) {
  const { skill, actionable_feedback: feedback } = item;
  const [copied, setCopied] = useState(false);
  const [copyFailed, setCopyFailed] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(feedback.suggested_wording);
      setCopied(true);
      setCopyFailed(false);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopyFailed(true);
      setTimeout(() => setCopyFailed(false), 2000);
    }
  };

  const getPriorityStyle = (priority) => {
    switch (priority?.toLowerCase()) {
      case 'high':
        return { bg: 'var(--danger-bg)', color: 'var(--danger-color)', label: 'HIGH PRIORITY' };
      case 'medium':
        return { bg: 'var(--warning-bg)', color: '#b45309', label: 'MEDIUM PRIORITY' };
      case 'low':
        return { bg: 'var(--success-bg)', color: 'var(--success-color)', label: 'LOW PRIORITY' };
      default:
        return { bg: '#f1f5f9', color: '#475569', label: 'SUGGESTION' };
    }
  };

  const pStyle = getPriorityStyle(feedback.priority);

  return (
    <div style={{ padding: '1rem', backgroundColor: '#ffffff', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)' }}>
      {/* Header */}
      <div className="flex justify-between items-start mb-3 flex-wrap gap-2">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="font-bold text-main">{skill}</span>
            <span style={{ backgroundColor: pStyle.bg, color: pStyle.color, padding: '0.15rem 0.4rem', borderRadius: '4px', fontSize: '0.65rem', fontWeight: 700 }}>
              {pStyle.label}
            </span>
            {feedback.section && (
              <span className="badge" style={{ fontSize: '0.65rem', backgroundColor: '#f1f5f9', color: '#475569', border: '1px solid #cbd5e1' }}>
                Section: {feedback.section}
              </span>
            )}
          </div>
          <div className="text-sm text-main font-medium">
            {feedback.explanation}
          </div>
        </div>
      </div>

      {/* Content Grid (Original vs Suggestion) */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-3">
        {/* Original Text Box */}
        {feedback.original_text && (
          <div style={{ padding: '0.75rem', backgroundColor: '#f8fafc', borderRadius: '4px', border: '1px solid #e2e8f0' }}>
            <div className="text-xs font-semibold text-muted mb-1 flex items-center gap-1 uppercase tracking-wider">
              <FileText size={12} /> Original Wording
            </div>
            <div className="text-sm text-main" style={{ whiteSpace: 'pre-wrap' }}>
              {feedback.original_text}
            </div>
          </div>
        )}

        {/* Suggestion / Questions Box */}
        {feedback.suggested_wording ? (
          <div style={{ padding: '0.75rem', backgroundColor: '#f0fdf4', borderRadius: '4px', border: '1px solid #bbf7d0', position: 'relative' }}>
            <div className="text-xs font-semibold text-emerald-800 mb-1 flex items-center justify-between uppercase tracking-wider">
              <div className="flex items-center gap-1">
                <Check size={12} /> Suggested Wording
              </div>
              <button 
                onClick={handleCopy}
                aria-label="Copy suggested wording"
                style={{ background: 'none', border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '0.25rem', color: 'var(--primary-600)', fontSize: '0.7rem' }}
              >
                {copied ? <Check size={12} className="text-emerald-600" /> : <Copy size={12} />}
                <span>{copied ? 'Copied!' : copyFailed ? 'Failed' : 'Copy'}</span>
              </button>
            </div>
            <div className="text-sm text-main" style={{ whiteSpace: 'pre-wrap' }}>
              {feedback.suggested_wording}
            </div>
          </div>
        ) : feedback.follow_up_questions?.length > 0 ? (
          <div style={{ padding: '0.75rem', backgroundColor: '#fffbeb', borderRadius: '4px', border: '1px solid #fde68a' }}>
            <div className="text-xs font-semibold text-amber-800 mb-1 flex items-center gap-1 uppercase tracking-wider">
              <HelpCircle size={12} /> Clarification Needed
            </div>
            <ul className="text-sm text-main pl-4 m-0" style={{ listStyleType: 'disc' }}>
              {feedback.follow_up_questions.map((q, i) => (
                <li key={i} className="mb-1">{q}</li>
              ))}
            </ul>
          </div>
        ) : (
          <div style={{ padding: '0.75rem', backgroundColor: '#fef2f2', borderRadius: '4px', border: '1px solid #fecaca' }}>
            <div className="text-xs font-semibold text-red-800 mb-1 flex items-center gap-1 uppercase tracking-wider">
              <AlertCircle size={12} /> Requirement Not Evidenced
            </div>
            <div className="text-sm text-main">
              No evidence of this skill was found in your CV.
            </div>
          </div>
        )}
      </div>

      {/* Next Action */}
      <div className="flex items-center gap-2 mt-3 pt-3" style={{ borderTop: '1px solid var(--border-color)' }}>
        <ArrowRight size={14} style={{ color: 'var(--primary-600)' }} />
        <span className="text-sm font-semibold" style={{ color: 'var(--primary-700)' }}>
          Next Step: <span className="font-normal text-main">{feedback.next_action}</span>
        </span>
      </div>
    </div>
  );
}
