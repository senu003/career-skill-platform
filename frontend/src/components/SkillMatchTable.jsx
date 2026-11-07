import React, { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, ChevronDown, X, FileText } from 'lucide-react';
import { isSupportedSkill } from '../utils/supportedSkills';
import {
  formatLevel,
  translateRequiredLevel,
  translateCvLevel
} from '../utils/formatters';
import './SkillMatchTable.css';

const LEVEL_MAP = { basic: 1, intermediate: 2, advanced: 3 };



export function parseSkillRow(item, supportedSkills = []) {
  const skillName = item.skill || 'Unknown';

  // Priority: Required vs Optional
  const rawImportance = String(item.importance || 'required').toLowerCase();
  const isOptional = rawImportance === 'preferred' || rawImportance === 'optional';
  const priority = isOptional ? 'Optional' : 'Required';

  // Job Target Level
  const reqRaw = String(item.required_level || item.level || 'intermediate').trim().toLowerCase();
  const reqVal = LEVEL_MAP[reqRaw] || 2;
  const jobTarget = translateRequiredLevel(reqRaw);

  // CV Evidence
  const cvStatus = item.cv_match_status || (item.matched ? 'Match' : 'Missing');
  const cvRaw = String(item.cv_level || '').trim().toLowerCase();
  const hasCvEvidence = Boolean(item.matched && cvStatus !== 'Missing' && cvRaw !== 'not_found' && cvRaw !== '');
  const cvVal = LEVEL_MAP[cvRaw] || (hasCvEvidence ? 2 : 0);
  const cvEvidence = hasCvEvidence ? translateCvLevel(cvRaw, true) : 'None found';

  // Availability in assessment quiz system
  const isAvailable = isSupportedSkill(skillName, supportedSkills);

  // Assessment
  const isAssessed = item.assessed_level !== null && item.assessed_level !== undefined && String(item.assessed_level).trim() !== '';
  const assRaw = isAssessed ? String(item.assessed_level).trim().toLowerCase() : '';
  const assVal = LEVEL_MAP[assRaw] || 0;

  let assessmentDisplay = 'Unavailable';
  if (isAssessed) {
    const rawScore = item.total_score !== null && item.total_score !== undefined ? Number(item.total_score) : null;
    const scorePct = rawScore !== null ? Math.round(rawScore <= 1.0 && rawScore > 0 ? rawScore * 100 : rawScore) : 0;
    const assLevelStr = formatLevel(assRaw);
    assessmentDisplay = `${assLevelStr} (${scorePct}%)`;
  } else if (!isAvailable) {
    assessmentDisplay = 'Unavailable';
  } else if (isOptional) {
    assessmentDisplay = 'Not verified';
  } else {
    assessmentDisplay = 'Not taken';
  }

  // Status mapping
  let status = 'Needs verification';
  let badgeStyle = { backgroundColor: '#FEF9C3', color: '#854D0E' }; // Soft yellow

  if (!hasCvEvidence) {
    status = 'No CV evidence';
    badgeStyle = { backgroundColor: '#FEE2E2', color: '#DC2626' }; // Soft pink/red
  } else if (isAssessed) {
    if (assVal >= reqVal) {
      status = 'Meets target';
      badgeStyle = { backgroundColor: '#DCFCE7', color: '#166534' }; // Soft green
    } else {
      status = 'Skill gap';
      badgeStyle = { backgroundColor: '#FEF3C7', color: '#92400E' }; // Soft amber
    }
  } else {
    // Unassessed
    if (isOptional) {
      status = 'CV evidence only';
      badgeStyle = { backgroundColor: '#DBEAFE', color: '#1D4ED8' }; // Soft blue
    } else if (cvVal < reqVal) {
      status = 'Skill gap';
      badgeStyle = { backgroundColor: '#FEF3C7', color: '#92400E' }; // Soft amber
    } else {
      status = 'Needs verification';
      badgeStyle = { backgroundColor: '#FEF9C3', color: '#854D0E' }; // Soft yellow
    }
  }

  // Action mapping
  let action = '—';
  let isActionable = false;
  if (isAssessed && isAvailable) {
    action = 'Retake test';
    isActionable = true;
  } else if (!isAssessed && isAvailable && hasCvEvidence && !isOptional) {
    action = 'Verify level';
    isActionable = true;
  } else {
    action = '—';
    isActionable = false;
  }

  return {
    raw: item,
    skill: skillName,
    priority,
    isOptional,
    jobTarget,
    hasCvEvidence,
    cvEvidence,
    isAssessed,
    assessmentDisplay,
    status,
    badgeStyle,
    action,
    isActionable,
    evidenceQuote: item.evidence || '',
    attemptId: item.attempt_id || null,
    completedAt: item.completed_at || null,
  };
}

export default function SkillMatchTable({
  skills = [],
  supportedSkills = [],
  analysisId = null,
  title = 'Skill match',
  subtitle = null,
  icon = null,
  showHeader = true,
  className = '',
  onActionClick = null,
}) {
  const navigate = useNavigate();

  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('All statuses');
  const [priorityFilter, setPriorityFilter] = useState('All priorities');
  const [evidenceModalItem, setEvidenceModalItem] = useState(null);

  // Parse all incoming skills
  const parsedRows = useMemo(() => {
    const list = Array.isArray(skills) && skills.length > 0 ? skills : [];
    return list.map((item) => parseSkillRow(item, supportedSkills));
  }, [skills, supportedSkills]);

  // Apply Search, Status, and Priority Filters
  const filteredRows = useMemo(() => {
    return parsedRows.filter((row) => {
      // 1. Search Query Filter
      if (searchQuery.trim()) {
        const query = searchQuery.trim().toLowerCase();
        if (!row.skill.toLowerCase().includes(query)) {
          return false;
        }
      }

      // 2. Status Filter
      if (statusFilter !== 'All statuses') {
        if (row.status !== statusFilter) {
          return false;
        }
      }

      // 3. Priority Filter
      if (priorityFilter !== 'All priorities') {
        if (row.priority !== priorityFilter) {
          return false;
        }
      }

      return true;
    });
  }, [parsedRows, searchQuery, statusFilter, priorityFilter]);

  // Handle action link click
  const handleAction = (row) => {
    if (onActionClick) {
      onActionClick(row);
      return;
    }
    const path = `/assessment/${encodeURIComponent(row.skill)}`;
    const fullPath = analysisId ? `${path}?analysis_id=${encodeURIComponent(analysisId)}` : path;
    navigate(fullPath);
  };

  return (
    <div
      className={`skill-match-card ${className}`}
      style={{
        backgroundColor: '#ffffff',
        border: '1px solid #e2e8f0',
        borderRadius: '12px',
        padding: '1.5rem 1.75rem',
        boxShadow: '0 1px 3px 0 rgba(0, 0, 0, 0.04)',
        width: '100%',
        boxSizing: 'border-box',
      }}
    >
      {/* Header with Title and Controls */}
      {showHeader && (
        <div
          className="skill-match-header"
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: '1rem',
            marginBottom: '1.25rem',
          }}
        >
          <div>
            <div className="flex items-center gap-2 mb-0.5">
              {icon}
              <h2
                className="card-title text-lg font-bold skill-match-title"
                style={{
                  fontSize: '1.125rem',
                  fontWeight: 700,
                  color: 'var(--text-main)',
                  letterSpacing: '-0.01em',
                  margin: 0,
                  lineHeight: 1.3,
                }}
              >
                {title}
              </h2>
            </div>
            {subtitle && (
              <p className="text-xs text-muted" style={{ margin: 0 }}>
                {subtitle}
              </p>
            )}
          </div>

          <div
            className="skill-match-controls"
            style={{
              display: 'flex',
              alignItems: 'center',
              flexWrap: 'wrap',
              gap: '0.65rem',
            }}
          >
            {/* Search Input */}
            <div
              className="skill-match-search-wrapper"
              style={{
                position: 'relative',
                display: 'inline-flex',
                alignItems: 'center',
              }}
            >
              <Search
                size={16}
                className="skill-match-search-icon"
                style={{
                  position: 'absolute',
                  left: '12px',
                  color: '#94a3b8',
                  pointerEvents: 'none',
                }}
              />
              <input
                type="text"
                placeholder="Search skills"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="skill-match-search-input"
                style={{
                  border: '1.5px solid #e2e8f0',
                  borderRadius: '8px',
                  padding: '0.5rem 0.85rem 0.5rem 2.25rem',
                  fontSize: '0.88rem',
                  color: '#0f172a',
                  backgroundColor: '#ffffff',
                  width: '220px',
                  outline: 'none',
                  fontFamily: 'inherit',
                  boxSizing: 'border-box',
                }}
                aria-label="Search skills"
              />
            </div>

            {/* Status Dropdown */}
            <div
              className="skill-match-select-wrapper"
              style={{
                position: 'relative',
                display: 'inline-flex',
                alignItems: 'center',
              }}
            >
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="skill-match-select"
                style={{
                  border: '1.5px solid #e2e8f0',
                  borderRadius: '8px',
                  backgroundColor: '#ffffff',
                  padding: '0.5rem 2.25rem 0.5rem 0.85rem',
                  fontSize: '0.88rem',
                  fontWeight: 500,
                  color: '#0f172a',
                  appearance: 'none',
                  WebkitAppearance: 'none',
                  MozAppearance: 'none',
                  cursor: 'pointer',
                  outline: 'none',
                  fontFamily: 'inherit',
                  boxSizing: 'border-box',
                }}
                aria-label="Filter by status"
              >
                <option value="All statuses">All statuses</option>
                <option value="Skill gap">Skill gap</option>
                <option value="Needs verification">Needs verification</option>
                <option value="No CV evidence">No CV evidence</option>
                <option value="Meets target">Meets target</option>
                <option value="CV evidence only">CV evidence only</option>
              </select>
              <ChevronDown
                size={15}
                className="skill-match-select-icon"
                style={{
                  position: 'absolute',
                  right: '10px',
                  color: '#64748b',
                  pointerEvents: 'none',
                }}
              />
            </div>

            {/* Priority Dropdown */}
            <div
              className="skill-match-select-wrapper"
              style={{
                position: 'relative',
                display: 'inline-flex',
                alignItems: 'center',
              }}
            >
              <select
                value={priorityFilter}
                onChange={(e) => setPriorityFilter(e.target.value)}
                className="skill-match-select"
                style={{
                  border: '1.5px solid #e2e8f0',
                  borderRadius: '8px',
                  backgroundColor: '#ffffff',
                  padding: '0.5rem 2.25rem 0.5rem 0.85rem',
                  fontSize: '0.88rem',
                  fontWeight: 500,
                  color: '#0f172a',
                  appearance: 'none',
                  WebkitAppearance: 'none',
                  MozAppearance: 'none',
                  cursor: 'pointer',
                  outline: 'none',
                  fontFamily: 'inherit',
                  boxSizing: 'border-box',
                }}
                aria-label="Filter by priority"
              >
                <option value="All priorities">All priorities</option>
                <option value="Required">Required</option>
                <option value="Optional">Optional</option>
              </select>
              <ChevronDown
                size={15}
                className="skill-match-select-icon"
                style={{
                  position: 'absolute',
                  right: '10px',
                  color: '#64748b',
                  pointerEvents: 'none',
                }}
              />
            </div>
          </div>
        </div>
      )}

      {/* Main Table */}
      <div
        className="skill-match-table-container"
        style={{
          overflowX: 'auto',
          width: '100%',
        }}
      >
        <table
          className="skill-match-table"
          style={{
            width: '100%',
            borderCollapse: 'collapse',
            textAlign: 'left',
          }}
          aria-label="Skill Match Matrix"
        >
          <thead>
            <tr>
              <th style={{ width: '22%', padding: '0.75rem 1rem', fontSize: '0.78rem', fontWeight: 600, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.04em', borderBottom: '1.5px solid #f1f5f9', background: 'transparent', whiteSpace: 'nowrap' }}>
                Skill
              </th>
              <th style={{ width: '16%', padding: '0.75rem 1rem', fontSize: '0.78rem', fontWeight: 600, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.04em', borderBottom: '1.5px solid #f1f5f9', background: 'transparent', whiteSpace: 'nowrap' }}>
                Job target
              </th>
              <th style={{ width: '16%', padding: '0.75rem 1rem', fontSize: '0.78rem', fontWeight: 600, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.04em', borderBottom: '1.5px solid #f1f5f9', background: 'transparent', whiteSpace: 'nowrap' }}>
                CV evidence
              </th>
              <th style={{ width: '18%', padding: '0.75rem 1rem', fontSize: '0.78rem', fontWeight: 600, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.04em', borderBottom: '1.5px solid #f1f5f9', background: 'transparent', whiteSpace: 'nowrap' }}>
                Assessment
              </th>
              <th style={{ width: '16%', padding: '0.75rem 1rem', fontSize: '0.78rem', fontWeight: 600, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.04em', borderBottom: '1.5px solid #f1f5f9', background: 'transparent', whiteSpace: 'nowrap' }}>
                Status
              </th>
              <th style={{ width: '12%', padding: '0.75rem 1rem', fontSize: '0.78rem', fontWeight: 600, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.04em', borderBottom: '1.5px solid #f1f5f9', background: 'transparent', whiteSpace: 'nowrap' }}>
                Action
              </th>
            </tr>
          </thead>
          <tbody>
            {filteredRows.length === 0 ? (
              <tr>
                <td colSpan={6} style={{ textAlign: 'center', padding: '3.5rem 1rem', color: '#64748b' }}>
                  <p style={{ margin: 0, fontSize: '0.95rem', fontWeight: 500 }}>No skills match your filters.</p>
                  {(searchQuery || statusFilter !== 'All statuses' || priorityFilter !== 'All priorities') && (
                    <button
                      type="button"
                      onClick={() => {
                        setSearchQuery('');
                        setStatusFilter('All statuses');
                        setPriorityFilter('All priorities');
                      }}
                      className="btn btn-outline text-xs mt-3"
                      style={{ padding: '0.4rem 0.95rem' }}
                    >
                      Clear Filters
                    </button>
                  )}
                </td>
              </tr>
            ) : (
              filteredRows.map((row) => (
                <tr
                  key={row.skill}
                  style={{
                    borderBottom: '1px solid #f1f5f9',
                    transition: 'background-color 0.15s ease',
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.backgroundColor = '#fbfcfe';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.backgroundColor = 'transparent';
                  }}
                >
                  {/* 1. Skill Name & Priority */}
                  <td style={{ padding: '0.95rem 1rem', verticalAlign: 'middle' }}>
                    <div
                      className="skill-name-cell"
                      style={{
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '2px',
                      }}
                    >
                      <span
                        className="skill-name-text"
                        style={{
                          fontWeight: 600,
                          fontSize: '0.92rem',
                          color: '#0f172a',
                          lineHeight: 1.3,
                        }}
                      >
                        {row.skill}
                      </span>
                      <span
                        className="skill-priority-text"
                        style={{
                          fontSize: '0.75rem',
                          color: '#64748b',
                          fontWeight: 400,
                        }}
                      >
                        {row.priority}
                      </span>
                    </div>
                  </td>

                  {/* 2. Job Target */}
                  <td style={{ padding: '0.95rem 1rem', verticalAlign: 'middle', fontSize: '0.88rem', color: '#334155' }}>
                    <span>{row.jobTarget}</span>
                  </td>

                  {/* 3. CV Evidence */}
                  <td style={{ padding: '0.95rem 1rem', verticalAlign: 'middle' }}>
                    {row.hasCvEvidence ? (
                      <button
                        type="button"
                        className="cv-evidence-link"
                        onClick={() => setEvidenceModalItem(row)}
                        title="Click to view candidate CV context"
                        style={{
                          background: 'none',
                          backgroundColor: 'transparent',
                          border: 'none',
                          outline: 'none',
                          boxShadow: 'none',
                          padding: 0,
                          margin: 0,
                          color: '#2563eb',
                          textDecoration: 'underline',
                          textUnderlineOffset: '3px',
                          cursor: 'pointer',
                          fontSize: '0.88rem',
                          fontWeight: 500,
                          fontFamily: 'inherit',
                        }}
                      >
                        {row.cvEvidence}
                      </button>
                    ) : (
                      <span
                        className="cv-evidence-none"
                        style={{
                          color: '#64748b',
                          fontSize: '0.88rem',
                        }}
                      >
                        None found
                      </span>
                    )}
                  </td>

                  {/* 4. Assessment */}
                  <td style={{ padding: '0.95rem 1rem', verticalAlign: 'middle', fontSize: '0.88rem', color: '#334155' }}>
                    <span>{row.assessmentDisplay}</span>
                  </td>

                  {/* 5. Status Pill */}
                  <td style={{ padding: '0.95rem 1rem', verticalAlign: 'middle' }}>
                    <span
                      className="skill-status-pill"
                      style={{
                        ...row.badgeStyle,
                        display: 'inline-block',
                        padding: '0.25rem 0.85rem',
                        borderRadius: '9999px',
                        fontSize: '0.75rem',
                        fontWeight: 600,
                        whiteSpace: 'nowrap',
                        lineHeight: 1.4,
                        textAlign: 'center',
                      }}
                    >
                      {row.status}
                    </span>
                  </td>

                  {/* 6. Action */}
                  <td style={{ padding: '0.95rem 1rem', verticalAlign: 'middle' }}>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                      {row.isAssessed && row.raw?.attempt_id && (
                        <button
                          type="button"
                          className="skill-review-link"
                          onClick={() => navigate(`/assessment/review/${row.raw.attempt_id}`)}
                          style={{
                            background: 'none',
                            backgroundColor: 'transparent',
                            border: 'none',
                            outline: 'none',
                            boxShadow: 'none',
                            padding: 0,
                            margin: 0,
                            color: '#475569',
                            textDecoration: 'underline',
                            textUnderlineOffset: '3px',
                            cursor: 'pointer',
                            fontSize: '0.82rem',
                            fontWeight: 500,
                            fontFamily: 'inherit',
                            textAlign: 'left',
                          }}
                          title={`Review answers for Attempt #${row.raw.attempt_id}`}
                        >
                          Review answers
                        </button>
                      )}
                      {row.isActionable ? (
                        <button
                          type="button"
                          className="skill-action-link"
                          onClick={() => handleAction(row)}
                          style={{
                            background: 'none',
                            backgroundColor: 'transparent',
                            border: 'none',
                            outline: 'none',
                            boxShadow: 'none',
                            padding: 0,
                            margin: 0,
                            color: '#2563eb',
                            textDecoration: 'underline',
                            textUnderlineOffset: '3px',
                            cursor: 'pointer',
                            fontSize: '0.85rem',
                            fontWeight: 500,
                            fontFamily: 'inherit',
                            textAlign: 'left',
                          }}
                        >
                          {row.action}
                        </button>
                      ) : (
                        !row.isAssessed && (
                          <span
                            className="skill-action-empty"
                            style={{
                              color: '#94a3b8',
                              fontSize: '0.85rem',
                            }}
                          >
                            —
                          </span>
                        )
                      )}
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* CV Evidence Detail Modal */}
      {evidenceModalItem && (
        <div
          className="skill-evidence-modal-backdrop"
          onClick={() => setEvidenceModalItem(null)}
          role="dialog"
          aria-modal="true"
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(15, 23, 42, 0.45)',
            backdropFilter: 'blur(3px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
            padding: '1rem',
          }}
        >
          <div
            className="skill-evidence-modal"
            onClick={(e) => e.stopPropagation()}
            style={{
              background: '#ffffff',
              borderRadius: '12px',
              maxWidth: '540px',
              width: '100%',
              padding: '1.75rem',
              boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.05)',
              border: '1px solid #e2e8f0',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.25rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <FileText size={20} style={{ color: '#2563eb' }} />
                <h3 style={{ margin: 0, fontSize: '1.15rem', fontWeight: 700, color: '#0f172a' }}>
                  CV Evidence — {evidenceModalItem.skill}
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setEvidenceModalItem(null)}
                style={{
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  padding: '4px',
                  color: '#64748b',
                  borderRadius: '6px',
                  display: 'flex',
                  alignItems: 'center',
                }}
                aria-label="Close modal"
              >
                <X size={20} />
              </button>
            </div>

            <div style={{ display: 'flex', gap: '1.5rem', marginBottom: '1.25rem', padding: '0.75rem 1rem', background: '#f8fafc', borderRadius: '8px' }}>
              <div>
                <span style={{ fontSize: '0.75rem', textTransform: 'uppercase', color: '#64748b', fontWeight: 600 }}>Detected Level</span>
                <div style={{ fontWeight: 700, color: '#0f172a', fontSize: '0.95rem' }}>{evidenceModalItem.cvEvidence}</div>
              </div>
              <div style={{ borderLeft: '1px solid #e2e8f0', paddingLeft: '1.5rem' }}>
                <span style={{ fontSize: '0.75rem', textTransform: 'uppercase', color: '#64748b', fontWeight: 600 }}>Job Requirement</span>
                <div style={{ fontWeight: 700, color: '#0f172a', fontSize: '0.95rem' }}>{evidenceModalItem.jobTarget} ({evidenceModalItem.priority})</div>
              </div>
            </div>

            <div style={{ marginBottom: '1.5rem' }}>
              <div style={{ fontSize: '0.8rem', fontWeight: 600, color: '#475569', marginBottom: '0.4rem' }}>
                Resume Context / Excerpt:
              </div>
              <div
                style={{
                  padding: '1rem',
                  background: '#f1f5f9',
                  borderRadius: '8px',
                  borderLeft: '3px solid #2563eb',
                  fontSize: '0.9rem',
                  lineHeight: 1.5,
                  color: '#1e293b',
                  fontStyle: 'italic',
                }}
              >
                {evidenceModalItem.evidenceQuote && evidenceModalItem.evidenceQuote.trim()
                  ? `"${evidenceModalItem.evidenceQuote}"`
                  : 'Skill was verified as present in the parsed resume structure.'}
              </div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
              {evidenceModalItem.isActionable && (
                <button
                  type="button"
                  className="btn btn-primary text-xs"
                  style={{ padding: '0.5rem 1rem' }}
                  onClick={() => {
                    const item = evidenceModalItem;
                    setEvidenceModalItem(null);
                    handleAction(item);
                  }}
                >
                  {evidenceModalItem.action} →
                </button>
              )}
              <button
                type="button"
                className="btn btn-outline text-xs"
                style={{ padding: '0.5rem 1rem' }}
                onClick={() => setEvidenceModalItem(null)}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
