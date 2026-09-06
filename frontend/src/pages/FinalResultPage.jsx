import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  Award, 
  CheckCircle2, 
  AlertCircle, 
  AlertTriangle, 
  TrendingUp, 
  Sparkles, 
  BookOpen, 
  ArrowRight, 
  ArrowLeft, 
  RefreshCw, 
  FileText, 
  Target, 
  Check, 
  X, 
  HelpCircle, 
  ShieldCheck, 
  Layers 
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

const WEAKNESS_REASON_MAP = {
  'LEVEL_GAP_AND_LOW_SCORE': 'Level gap identified & low assessment accuracy score. Foundational review required.',
  'LOW_ASSESSMENT_SCORE': 'Assessment score is below passing threshold. Targeted practice recommended.',
  'LEVEL_GAP': 'Assessed level is below required job level standard.',
  'MISSING_SKILL': 'Required skill was not detected in candidate CV evidence.',
  'UNASSESSED_REQUIRED_SKILL': 'Pending technical assessment evaluation.',
  'NONE': 'Requirement satisfied.',
};

const formatWeaknessReason = (reason) => {
  if (!reason || reason === 'NONE') return 'Requirement satisfied.';
  if (WEAKNESS_REASON_MAP[reason]) return WEAKNESS_REASON_MAP[reason];
  return reason.replace(/_/g, ' ').toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase());
};

const getVerdictExplanation = (verdict) => {
  const clean = (verdict || '').toLowerCase();
  if (clean.includes('major upskill')) {
    return 'Model 2 Final Recommendation Engine Verdict: Major Upskill Required. Candidate currently demonstrates critical level gaps and low accuracy scores across core required skills. Comprehensive foundational review and structured training modules are required before technical interview readiness.';
  }
  if (clean.includes('short-term') || clean.includes('prep')) {
    return 'Model 2 Final Recommendation Engine Verdict: Short-Term Prep Required. Candidate possesses foundational knowledge but requires targeted practice and level refinement to fully meet job standards.';
  }
  if (clean.includes('interview') || clean.includes('ready')) {
    return 'Model 2 Final Recommendation Engine Verdict: Interview Ready. Candidate meets or exceeds core job requirements with strong assessment performance. Recommended to proceed to technical interviews.';
  }
  return `Model 2 Final Recommendation Engine Verdict: ${verdict || 'Evaluation Synthesized'}. Aggregated synthesis calculated across CV match evidence, technical assessment results, and skill gap telemetry.`;
};

// Helper to format confidence
const formatConfidence = (conf) => {
  if (conf === null || conf === undefined) return null;
  const num = typeof conf === 'number' ? conf : parseFloat(conf);
  if (isNaN(num)) return null;
  const percent = Math.round(num > 1 ? num : num * 100);
  return `${percent}%`;
};

// Helper to format score
const formatScore = (score) => {
  if (score === null || score === undefined) return 'N/A';
  if (typeof score === 'number') {
    return `${Math.round(score > 1 ? score : score * 100)}%`;
  }
  return score;
};

// Helper to format level
const formatLevel = (lvl) => {
  if (!lvl) return 'N/A';
  return lvl.charAt(0).toUpperCase() + lvl.slice(1).toLowerCase();
};

// Helper for recommendation badge style
const getRecommendationBadgeStyle = (rec) => {
  const cleanRec = (rec || '').toLowerCase().trim();
  if (cleanRec === 'mastered') {
    return {
      backgroundColor: 'var(--success-bg)',
      color: 'var(--success-color)',
      border: '1px solid #a7f3d0',
      icon: <CheckCircle2 size={16} className="text-emerald-500" />
    };
  }
  if (cleanRec === 'speed practice') {
    return {
      backgroundColor: 'var(--primary-light)',
      color: 'var(--primary-700)',
      border: '1px solid var(--primary-200)',
      icon: <TrendingUp size={16} style={{ color: 'var(--primary-600)' }} />
    };
  }
  if (cleanRec === 'upgrade needed') {
    return {
      backgroundColor: 'var(--warning-bg)',
      color: '#b45309',
      border: '1px solid #fde68a',
      icon: <AlertTriangle size={16} style={{ color: '#d97706' }} />
    };
  }
  if (cleanRec === 're-learn basics') {
    return {
      backgroundColor: 'var(--danger-bg)',
      color: 'var(--danger-color)',
      border: '1px solid #fecaca',
      icon: <AlertCircle size={16} style={{ color: 'var(--danger-color)' }} />
    };
  }
  return {
    backgroundColor: '#f1f5f9',
    color: '#475569',
    border: '1px solid #cbd5e1',
    icon: <Sparkles size={16} style={{ color: '#64748b' }} />
  };
};

export default function FinalResultPage() {
  const navigate = useNavigate();
  const { analysisResult, setAnalysisResult, clearAnalysis } = useAssessment();

  const [activeTab, setActiveTab] = useState('all'); // 'all' | 'assessed' | 'unavailable'
  const [aggregationData, setAggregationData] = useState(null);
  const [loadingAgg, setLoadingAgg] = useState(false);

  // Auto-restore latest session if analysisResult is empty
  useEffect(() => {
    if (!analysisResult) {
      const restoreLatestSession = async () => {
        setLoadingAgg(true);
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
          console.warn('Could not restore latest session:', err);
        } finally {
          setLoadingAgg(false);
        }
      };
      restoreLatestSession();
    }
  }, [analysisResult]);

  const skillsList = analysisResult?.skills || [
    ...(analysisResult?.matched_skills || []),
    ...(analysisResult?.missing_skills || []),
  ] || [];

  // Fetch backend aggregation stats when analysisResult is present
  useEffect(() => {
    if (!skillsList || skillsList.length === 0) return;

    const fetchAggregation = async () => {
      setLoadingAgg(true);
      try {
        const payloadSkills = skillsList.map((s) => ({
          skill: s.skill,
          level: s.level || s.required_level,
          required_level: s.required_level || s.level || 'basic',
          importance: s.importance || 'required',
          matched: s.matched !== undefined ? s.matched : true,
          cv_level: s.cv_level || null,
          assessed_level: s.assessed_level || null,
          ml_predicted_level: s.ml_predicted_level || null,
          level_gap: s.level_gap !== undefined ? s.level_gap : null,
          total_score: s.total_score !== undefined ? s.total_score : null,
          is_weakness: s.is_weakness || false,
          weakness_reason: s.weakness_reason || 'NONE',
          priority: s.priority || 'MEDIUM',
          recommendation: s.recommendation || null,
          recommendation_reason: s.recommendation_reason || null,
          skill_recommendation: s.skill_recommendation || null,
          recommendation_confidence: s.recommendation_confidence || null,
          evidence: s.evidence || null,
          improvement_probability: s.improvement_probability || null,
        }));

        const res = await fetchWithAuth('/assessment/aggregate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ skills: payloadSkills }),
        });
        setAggregationData(res);
      } catch (err) {
        console.error('Failed to fetch backend aggregation stats:', err);
      } finally {
        setLoadingAgg(false);
      }
    };

    fetchAggregation();
  }, [analysisResult]);

  // Guard: Loading State while fetching latest session
  if (loadingAgg && !analysisResult) {

    return (
      <div className="fade-in text-center mt-6" style={{ maxWidth: '640px', margin: '3rem auto' }}>
        <div className="card" style={{ padding: '3.5rem 2rem' }}>
          <div className="spinner spinner-dark mb-4" style={{ width: 40, height: 40, borderWidth: 3 }}></div>
          <h2 className="card-title text-xl mb-2">Loading Candidate Recommendation</h2>
          <p className="text-muted text-sm">Retrieving analysis data and synthesizing ML recommendation metrics...</p>
        </div>
      </div>
    );
  }

  // Guard: No analysis available state
  if (!analysisResult || skillsList.length === 0) {
    return (
      <div className="fade-in text-center mt-6" style={{ maxWidth: '640px', margin: '2rem auto' }}>
        <div className="card" style={{ padding: '3rem 2rem' }}>
          <div className="badge badge-purple mb-3">Final Recommendation</div>
          <h2 className="card-title text-xl mb-2">No Active Assessment Data</h2>
          <p className="text-muted text-sm mb-6" style={{ lineHeight: 1.5 }}>
            To view comprehensive candidate recommendations, please upload a CV and job description on the dashboard first.
          </p>
          <div className="flex justify-center">
            <button onClick={() => navigate('/dashboard')} className="btn btn-primary">
              <ArrowLeft size={16} />
              <span>Go to Dashboard</span>
            </button>
          </div>
        </div>
      </div>
    );
  }


  // Count skills by status
  const assessedSkills = skillsList.filter((s) => s.assessed_level !== null && s.assessed_level !== undefined);
  const unsupportedSkills = skillsList.filter((s) => !isSupportedSkill(s.skill));
  const supportedPendingSkills = skillsList.filter((s) => isSupportedSkill(s.skill) && !s.assessed_level);

  // Filter skills list based on active tab
  const filteredSkills = skillsList.filter((s) => {
    if (activeTab === 'assessed') return s.assessed_level !== null && s.assessed_level !== undefined;
    if (activeTab === 'unavailable') return !isSupportedSkill(s.skill);
    return true;
  });

  // Verdict & overall status
  const finalVerdict = aggregationData?.final_verdict || analysisResult?.final_verdict || aggregationData?.readiness_status || 'Assessment Synthesized';
  const overallConfidenceDisplay = formatConfidence(aggregationData?.recommendation_confidence || analysisResult?.recommendation_confidence);
  const overallMatchScore = analysisResult?.score_data?.score !== undefined 
    ? `${Math.round(analysisResult.score_data.score)}%` 
    : (aggregationData?.overall_score !== null && aggregationData?.overall_score !== undefined 
        ? `${Math.round(aggregationData.overall_score * 100)}%` 
        : 'N/A');

  return (
    <div className="fade-in" style={{ maxWidth: '980px', margin: '0 auto' }}>
      {/* 1. HEADER & WELCOME */}
      <div className="page-header text-center mb-6">
        <span className="badge badge-purple mb-2">Final Candidate Evaluation</span>
        <h1 className="page-title">Final Recommendation & Summary</h1>
        <p className="page-subtitle">
          Comprehensive synthesis of candidate skill levels, individual ML recommendations, and tailored growth action plans.
        </p>
      </div>

      {/* 2. OVERALL EXECUTIVE RECOMMENDATION BANNER */}
      <div className="match-score-card mb-6">
        <div style={{ flex: '1 1 300px' }}>
          <div className="flex items-center gap-2 mb-1" style={{ opacity: 0.9, fontSize: '0.8rem', textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: 600 }}>
            <Award size={16} />
            <span>Model 2 Final Recommendation Engine</span>
          </div>
          <div className="font-bold text-2xl" style={{ fontSize: '1.85rem', lineHeight: 1.2 }}>
            {finalVerdict}
          </div>
          <p className="text-xs mt-2" style={{ opacity: 0.9, maxWidth: '520px', lineHeight: 1.45 }}>
            {getVerdictExplanation(finalVerdict)}
          </p>
        </div>

        <div className="flex items-center gap-4 flex-wrap">
          {overallConfidenceDisplay && (
            <div className="match-stat-item">
              <div className="text-xs text-muted" style={{ color: 'rgba(255,255,255,0.8)' }}>Verdict Confidence</div>
              <div className="font-bold text-lg">{overallConfidenceDisplay}</div>
            </div>
          )}

          <div className="match-stat-item">
            <div className="text-xs text-muted" style={{ color: 'rgba(255,255,255,0.8)' }}>Overall Match</div>
            <div className="font-bold text-lg">{overallMatchScore}</div>
          </div>

          <div className="match-stat-item">
            <div className="text-xs text-muted" style={{ color: 'rgba(255,255,255,0.8)' }}>Skills Met</div>
            <div className="font-bold text-lg">
              {aggregationData ? `${aggregationData.skills_meeting_requirement}/${aggregationData.total_skills}` : `${skillsList.filter(s => s.matched && !s.is_weakness).length}/${skillsList.length}`}
            </div>
          </div>
        </div>
      </div>

      {/* 3. AGGREGATED STATS GRID */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        <div className="card" style={{ padding: '1.1rem', textAlign: 'center', margin: 0 }}>
          <div className="text-xs text-muted font-medium mb-1 flex items-center justify-center gap-1">
            <Layers size={14} style={{ color: 'var(--primary-600)' }} />
            <span>Total Skills Analyzed</span>
          </div>
          <div className="font-bold text-xl text-main">{skillsList.length}</div>
        </div>

        <div className="card" style={{ padding: '1.1rem', textAlign: 'center', margin: 0 }}>
          <div className="text-xs text-muted font-medium mb-1 flex items-center justify-center gap-1">
            <ShieldCheck size={14} style={{ color: 'var(--success-color)' }} />
            <span>Assessed Skills</span>
          </div>
          <div className="font-bold text-xl text-main">{assessedSkills.length}</div>
        </div>

        <div className="card" style={{ padding: '1.1rem', textAlign: 'center', margin: 0 }}>
          <div className="text-xs text-muted font-medium mb-1 flex items-center justify-center gap-1">
            <HelpCircle size={14} style={{ color: '#d97706' }} />
            <span>No Question Bank (DB)</span>
          </div>
          <div className="font-bold text-xl text-main">{unsupportedSkills.length}</div>
        </div>

        <div className="card" style={{ padding: '1.1rem', textAlign: 'center', margin: 0 }}>
          <div className="text-xs text-muted font-medium mb-1 flex items-center justify-center gap-1">
            <AlertTriangle size={14} style={{ color: 'var(--danger-color)' }} />
            <span>Growth Weaknesses</span>
          </div>
          <div className="font-bold text-xl text-main">
            {skillsList.filter((s) => s.is_weakness).length}
          </div>
        </div>
      </div>

      {/* 4. INDIVIDUAL SKILL ML RECOMMENDATIONS SECTION */}
      <div className="card">
        <div className="flex justify-between items-center mb-4 flex-wrap gap-3">
          <div>
            <h2 className="card-title mb-1 flex items-center gap-2">
              <Sparkles size={20} style={{ color: 'var(--primary-600)' }} />
              <span>Skill-by-Skill ML Recommendations</span>
            </h2>
            <p className="text-muted text-xs">
              Detailed evaluation score breakdown, Model 1 ML recommendations, and assessment question bank availability.
            </p>
          </div>

          {/* Filter Tab Buttons */}
          <div className="flex items-center gap-1" style={{ backgroundColor: 'var(--primary-50)', padding: '0.25rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--primary-200)' }}>
            <button
              onClick={() => setActiveTab('all')}
              className={`btn ${activeTab === 'all' ? 'btn-primary' : 'btn-outline'}`}
              style={{ padding: '0.25rem 0.75rem', fontSize: '0.75rem', border: 'none' }}
            >
              All ({skillsList.length})
            </button>
            <button
              onClick={() => setActiveTab('assessed')}
              className={`btn ${activeTab === 'assessed' ? 'btn-primary' : 'btn-outline'}`}
              style={{ padding: '0.25rem 0.75rem', fontSize: '0.75rem', border: 'none' }}
            >
              Assessed ({assessedSkills.length})
            </button>
            <button
              onClick={() => setActiveTab('unavailable')}
              className={`btn ${activeTab === 'unavailable' ? 'btn-primary' : 'btn-outline'}`}
              style={{ padding: '0.25rem 0.75rem', fontSize: '0.75rem', border: 'none' }}
            >
              No Question Bank ({unsupportedSkills.length})
            </button>
          </div>
        </div>

        {/* Skills List Cards */}
        <div className="skills-list">
          {filteredSkills.map((item, idx) => {
            const supported = isSupportedSkill(item.skill);
            const isAssessed = item.assessed_level !== null && item.assessed_level !== undefined;
            const reqLvl = formatLevel(item.required_level || item.level);
            const assessedLvl = formatLevel(item.assessed_level);
            const cvLvlDisplay = item.cv_level ? formatLevel(item.cv_level) : (item.matched ? 'Detected in CV' : 'Not found in CV');
            
            // Model 1 Recommendation resolution
            const recLabel = item.skill_recommendation || item.recommendation || (isAssessed ? 'Assessment Completed' : (supported ? 'Assessment Pending' : 'CV Evaluation Only'));
            const badgeStyle = getRecommendationBadgeStyle(recLabel);
            const confDisplay = formatConfidence(item.recommendation_confidence);
            
            // Explanation text resolution
            const explanation = 
              RECOMMENDATION_EXPLANATIONS[recLabel] ||
              ((item.recommendation_reason && item.recommendation_reason !== 'NONE') ? item.recommendation_reason : null) ||
              (!supported ? 'No MCQ technical question bank available in database. Evaluated using NLP match algorithms.' : 'Technical assessment completed.');

            return (
              <div 
                key={idx} 
                className="card" 
                style={{ 
                  padding: '1.25rem 1.5rem', 
                  marginBottom: '1rem',
                  borderLeft: item.is_weakness ? '4px solid var(--danger-color)' : (isAssessed ? '4px solid var(--success-color)' : '4px solid var(--border-color)'),
                }}
              >
                {/* Header Row: Skill Name + Status Badges */}
                <div className="flex justify-between items-center mb-3 flex-wrap gap-2">
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-lg text-main">{item.skill}</span>
                    <span className={`badge ${item.importance === 'preferred' ? 'badge-purple' : 'badge-purple'}`} style={{ fontSize: '0.7rem' }}>
                      {item.importance || 'Required'}
                    </span>

                    {!supported && (
                      <span 
                        className="badge" 
                        style={{ 
                          backgroundColor: '#f1f5f9', 
                          color: '#475569', 
                          border: '1px solid #cbd5e1', 
                          fontSize: '0.7rem' 
                        }}
                      >
                        No Question Bank in Database
                      </span>
                    )}

                    {isAssessed && (
                      <span className="badge badge-success" style={{ fontSize: '0.7rem' }}>
                        Assessed
                      </span>
                    )}
                  </div>

                  {/* Recommendation Badge */}
                  <div className="flex items-center gap-2">
                    {confDisplay && (
                      <span className="text-xs text-muted font-medium">
                        Conf: <strong>{confDisplay}</strong>
                      </span>
                    )}

                    <div
                      style={{
                        ...badgeStyle,
                        padding: '0.3rem 0.75rem',
                        borderRadius: '9999px',
                        fontSize: '0.8rem',
                        fontWeight: 600,
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '0.35rem',
                      }}
                    >
                      {badgeStyle.icon}
                      <span>{recLabel}</span>
                    </div>
                  </div>
                </div>

                {/* Level & Telemetry Grid */}
                <div className="grid grid-cols-3 gap-3 mb-3" style={{ backgroundColor: 'var(--primary-50)', padding: '0.85rem 1rem', borderRadius: 'var(--radius-sm)' }}>
                  <div>
                    <div className="text-xs text-muted font-medium">Required Level</div>
                    <div className="font-semibold text-main text-sm">{reqLvl}</div>
                  </div>

                  <div>
                    <div className="text-xs text-muted font-medium">Assessed / CV Level</div>
                    <div className="font-semibold text-main text-sm">
                      {isAssessed ? assessedLvl : cvLvlDisplay}
                    </div>
                  </div>

                  <div>
                    <div className="text-xs text-muted font-medium">Score / Score Status</div>
                    <div className="font-semibold text-main text-sm">
                      {isAssessed ? formatScore(item.total_score) : (supported ? 'Not Assessed' : 'N/A (CV Match)')}
                    </div>
                  </div>
                </div>

                {/* ML Explanation & Recommendation Context */}
                <div style={{ padding: '0.75rem 1rem', backgroundColor: '#ffffff', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)' }}>
                  <div className="text-xs font-semibold uppercase tracking-wider text-muted mb-1">
                    ML Summary & Guidance
                  </div>
                  <p className="text-sm font-medium text-main" style={{ lineHeight: 1.45 }}>
                    {explanation}
                  </p>

                  {/* Context snippet if unsupported or evidence present */}
                  {!supported && item.evidence && (
                    <div className="text-xs text-muted mt-2 pt-2" style={{ borderTop: '1px dashed var(--border-color)', fontStyle: 'italic' }}>
                      CV Evidence: "{item.evidence}"
                    </div>
                  )}

                  {!supported && !item.evidence && (
                    <div className="text-xs text-muted mt-2 pt-2" style={{ borderTop: '1px dashed var(--border-color)' }}>
                      Assessment question bank unavailable for {item.skill}. Recommended focus: self-guided practical projects and manual technical review.
                    </div>
                  )}

                  {/* Pending supported assessment prompt */}
                  {supported && !isAssessed && (
                    <div className="mt-3 flex justify-between items-center pt-2" style={{ borderTop: '1px solid var(--border-color)' }}>
                      <span className="text-xs text-muted">Technical MCQ assessment questions are available for {item.skill}.</span>
                      <button
                        onClick={() => navigate(`/assessment/${encodeURIComponent(item.skill)}`)}
                        className="btn btn-primary"
                        style={{ padding: '0.35rem 0.85rem', fontSize: '0.8rem' }}
                      >
                        <span>Take Assessment</span>
                        <ArrowRight size={14} />
                      </button>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* 5. CONSOLIDATED ACTIONABLE GROWTH PLAN */}
      <div className="card" style={{ background: 'var(--primary-50)', border: '1px solid var(--primary-200)' }}>
        <h2 className="card-title flex items-center gap-2 mb-2">
          <BookOpen size={20} style={{ color: 'var(--primary-700)' }} />
          <span>Tailored Candidate Action Plan</span>
        </h2>
        <p className="text-sm text-muted mb-4">
          Priority-ranked action items to bridge skill gaps and maximize job match compatibility.
        </p>

        <div className="flex flex-col gap-3">
          {skillsList.filter(s => s.is_weakness || s.priority === 'HIGH').length > 0 ? (
            skillsList
              .filter(s => s.is_weakness || s.priority === 'HIGH')
              .map((s, idx) => (
                <div key={idx} className="flex items-start gap-3" style={{ padding: '0.85rem 1rem', backgroundColor: '#ffffff', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)' }}>
                  <div style={{ backgroundColor: 'var(--danger-bg)', color: 'var(--danger-color)', padding: '0.25rem 0.5rem', borderRadius: '4px', fontSize: '0.75rem', fontWeight: 700, whitespace: 'nowrap' }}>
                    HIGH PRIORITY
                  </div>
                  <div>
                    <div className="font-semibold text-sm text-main">Focus on {s.skill} ({formatLevel(s.required_level || s.level)} Level)</div>
                    <div className="text-xs text-muted mt-0.5">
                      {formatWeaknessReason(s.weakness_reason)}
                    </div>
                  </div>
                </div>
              ))
          ) : (
            <div className="flex items-center gap-2 text-emerald-700 bg-emerald-50 p-3 rounded" style={{ border: '1px solid #a7f3d0' }}>
              <CheckCircle2 size={18} />
              <span className="text-sm font-semibold">No critical skill weaknesses identified! Candidate strongly meets core job requirements.</span>
            </div>
          )}
        </div>
      </div>

      {/* 6. PAGE FOOTER NAVIGATION */}
      <div className="flex justify-between items-center mb-8">
        <button onClick={() => navigate('/dashboard')} className="btn btn-outline">
          <ArrowLeft size={16} />
          <span>Back to Dashboard</span>
        </button>

        <button
          onClick={() => {
            clearAnalysis();
            navigate('/dashboard');
          }}
          className="btn btn-primary"
        >
          <RefreshCw size={16} />
          <span>Analyze Another Job</span>
        </button>
      </div>
    </div>
  );
}
