import React, { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
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
  ShieldCheck, 
  Layers, 
  HelpCircle, 
  Check,
  RotateCcw
} from 'lucide-react';
import { fetchWithAuth } from '../api';
import { useAssessment } from '../context/AssessmentContext';
import { isSupportedSkill } from '../utils/supportedSkills';
import CVFeedbackCard from '../components/CVFeedbackCard';

// Static explanation mapping for Model 1 recommendation labels
const RECOMMENDATION_EXPLANATIONS = {
  'Mastered': 'Candidate exhibits strong knowledge and high accuracy for this skill.',
  'Upgrade Needed': 'Current demonstrated level is below the job standard. Level upgrade required.',
  'Speed Practice': 'Core concept knowledge is adequate, but problem-solving speed needs practice.',
  'Re-learn Basics': 'Candidate struggled with fundamental concepts. Structured foundational review required.',
  'Verify Skill': 'Skill was not detected in CV evidence. Assessment recommended to demonstrate proficiency.',
};

const WEAKNESS_REASON_MAP = {
  'LEVEL_GAP_AND_LOW_SCORE': 'Critical level gap & low quiz accuracy score. Foundational review required.',
  'LOW_ASSESSMENT_SCORE': 'Assessment score is below passing threshold. Targeted practice recommended.',
  'LEVEL_GAP': 'Skill level is below required job level standard.',
  'UNVERIFIED_IN_CV': 'Skill not mentioned in candidate CV. Assessment recommended to verify true proficiency.',
  'MISSING_SKILL': 'Skill not mentioned in candidate CV. Assessment recommended to verify true proficiency.',
  'UNASSESSED_REQUIRED_SKILL': 'Pending technical assessment evaluation.',
  'NONE': 'Requirement fully satisfied.',
};

const formatWeaknessReason = (reason) => {
  if (!reason || reason === 'NONE') return 'Requirement fully satisfied.';
  if (WEAKNESS_REASON_MAP[reason]) return WEAKNESS_REASON_MAP[reason];
  return reason.replace(/_/g, ' ').toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase());
};

const getVerdictExplanation = (verdict) => {
  const clean = (verdict || '').toLowerCase();
  if (clean.includes('major upskill')) {
    return 'Candidate demonstrates critical level gaps or missing core competencies. Foundational upskilling and structured learning modules are recommended prior to technical interviews.';
  }
  if (clean.includes('short-term') || clean.includes('prep')) {
    return 'Candidate possesses foundational knowledge aligned with target job requirements. Targeted practice on identified skill gaps will achieve full interview readiness.';
  }
  if (clean.includes('interview') || clean.includes('ready')) {
    return 'Candidate strongly meets or exceeds core job requirements with demonstrated proficiency. Recommended to proceed to technical interviews with confidence.';
  }
  return `Comprehensive evaluation synthesized across CV match evidence, technical assessment results, and skill gap telemetry.`;
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
  const clean = String(lvl).trim().toLowerCase();
  if (clean === 'unspecified' || clean === 'none') return 'Any Level';
  return clean.charAt(0).toUpperCase() + clean.slice(1);
};

// Helper for recommendation badge style
const getRecommendationBadgeStyle = (rec) => {
  const cleanRec = (rec || '').toLowerCase().trim();
  if (cleanRec === 'mastered') {
    return {
      backgroundColor: '#ecfdf5',
      color: '#059669',
      border: '1px solid #a7f3d0',
      icon: <CheckCircle2 size={15} style={{ color: '#059669' }} />
    };
  }
  if (cleanRec === 'speed practice') {
    return {
      backgroundColor: '#eff6ff',
      color: '#2563eb',
      border: '1px solid #bfdbfe',
      icon: <TrendingUp size={15} style={{ color: '#2563eb' }} />
    };
  }
  if (cleanRec === 'upgrade needed') {
    return {
      backgroundColor: '#fffbeb',
      color: '#b45309',
      border: '1px solid #fde68a',
      icon: <AlertTriangle size={15} style={{ color: '#d97706' }} />
    };
  }
  if (cleanRec === 're-learn basics') {
    return {
      backgroundColor: '#fef2f2',
      color: '#dc2626',
      border: '1px solid #fecaca',
      icon: <AlertCircle size={15} style={{ color: '#dc2626' }} />
    };
  }
  if (cleanRec === 'verify skill' || cleanRec === 'verify proficiency') {
    return {
      backgroundColor: '#f8fafc',
      color: '#475569',
      border: '1px solid #cbd5e1',
      icon: <HelpCircle size={15} style={{ color: '#64748b' }} />
    };
  }
  return {
    backgroundColor: '#f1f5f9',
    color: '#475569',
    border: '1px solid #cbd5e1',
    icon: <Sparkles size={15} style={{ color: '#64748b' }} />
  };
};

export default function FinalResultPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { analysisResult, setAnalysisResult, clearAnalysis, refreshAnalysis, isRefreshing } = useAssessment();

  const urlAnalysisId = searchParams.get('analysis_id');
  const activeAnalysisId = urlAnalysisId || analysisResult?.analysis_id;

  const [activeTab, setActiveTab] = useState('all'); // 'all' | 'gaps' | 'assessed' | 'cv_verified'
  const [aggregationData, setAggregationData] = useState(null);
  const [loadingAgg, setLoadingAgg] = useState(false);
  const [refreshError, setRefreshError] = useState(null);

  // Auto-restore session from backend if analysisResult is empty
  useEffect(() => {
    let isCancelled = false;
    if (!analysisResult) {
      const restoreLatestSession = async () => {
        setLoadingAgg(true);
        try {
          const sessRes = await fetchWithAuth('/cv/sessions');
          if (isCancelled) return;
          if (sessRes?.sessions && sessRes.sessions.length > 0) {
            const latestSess = urlAnalysisId
              ? sessRes.sessions.find(s => String(s.analysis_id) === String(urlAnalysisId)) || sessRes.sessions[0]
              : sessRes.sessions[0];
            const detailRes = await fetchWithAuth(`/cv/sessions/${latestSess.analysis_id}`);
            if (isCancelled) return;
            if (detailRes) {
              setAnalysisResult(detailRes);
            }
          }
        } catch (err) {
          console.warn('Could not restore latest session:', err);
        } finally {
          if (!isCancelled) setLoadingAgg(false);
        }
      };
      restoreLatestSession();
    }
    return () => {
      isCancelled = true;
    };
  }, [analysisResult, urlAnalysisId, setAnalysisResult]);

  const skillsList = analysisResult?.skills || [
    ...(analysisResult?.matched_skills || []),
    ...(analysisResult?.missing_skills || []),
  ] || [];

  // Fetch backend aggregation stats when analysisResult is present
  const fetchAggregation = async () => {
    if (!skillsList || skillsList.length === 0) return;
    setLoadingAgg(true);
    setRefreshError(null);
    try {
      const payloadSkills = skillsList.map((s) => ({
        skill: s.skill,
        level: s.level || s.required_level,
        required_level: s.required_level || s.level || 'basic',
        importance: s.importance || 'required',
        matched: s.matched !== undefined ? s.matched : true,
        cv_level: s.cv_level || null,
        cv_match_status: s.cv_match_status || (s.matched ? 'Match' : 'Missing'),
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
      setRefreshError('Unable to refresh aggregated metrics. Displaying cached session results.');
    } finally {
      setLoadingAgg(false);
    }
  };

  useEffect(() => {
    if (skillsList.length > 0) {
      fetchAggregation();
    }
  }, [analysisResult?.analysis_id, skillsList.length]);

  const handleManualRefresh = async () => {
    if (activeAnalysisId) {
      await refreshAnalysis(activeAnalysisId);
    }
    await fetchAggregation();
  };

  // Guard: Loading State while fetching latest session
  if (loadingAgg && !analysisResult) {
    return (
      <div className="fade-in text-center mt-6" style={{ maxWidth: '640px', margin: '3rem auto' }}>
        <div className="card" style={{ padding: '3.5rem 2rem' }}>
          <div className="spinner spinner-dark mb-4" style={{ width: 40, height: 40, borderWidth: 3, margin: '0 auto 1.5rem' }}></div>
          <h2 className="card-title text-xl mb-2">Synthesizing Candidate Evaluation</h2>
          <p className="text-muted text-sm">Aggregating CV evidence, quiz scores, and Model 2 readiness recommendations...</p>
        </div>
      </div>
    );
  }

  // Guard: No analysis available state
  if (!analysisResult || skillsList.length === 0) {
    return (
      <div className="fade-in text-center mt-6" style={{ maxWidth: '640px', margin: '2rem auto' }}>
        <div className="card" style={{ padding: '3rem 2rem' }}>
          <div className="badge badge-purple mb-3">Candidate Evaluation</div>
          <h2 className="card-title text-xl mb-2">No Active Job Analysis Found</h2>
          <p className="text-muted text-sm mb-6" style={{ lineHeight: 1.5 }}>
            To generate a comprehensive candidate evaluation and Model 2 recommendation, upload your CV and a job description on the dashboard.
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

  // Skill categorization
  const assessedSkills = skillsList.filter((s) => s.assessed_level !== null && s.assessed_level !== undefined);
  const cvVerifiedSkills = skillsList.filter((s) => s.matched && !s.assessed_level && !s.is_weakness);
  const gapSkills = skillsList.filter((s) => s.is_weakness || !s.matched || (s.level_gap !== null && s.level_gap > 0));

  // Filter skills list based on active tab
  const filteredSkills = skillsList.filter((s) => {
    if (activeTab === 'gaps') return s.is_weakness || !s.matched || (s.level_gap !== null && s.level_gap > 0);
    if (activeTab === 'assessed') return s.assessed_level !== null && s.assessed_level !== undefined;
    if (activeTab === 'cv_verified') return s.matched && !s.assessed_level;
    return true;
  });

  // Verdict & overall status resolution
  const finalVerdict = aggregationData?.final_verdict || analysisResult?.final_verdict || aggregationData?.readiness_status || 'Evaluation Complete';
  const overallConfidenceDisplay = formatConfidence(aggregationData?.recommendation_confidence || analysisResult?.recommendation_confidence || 0.85);
  const isPreliminary = aggregationData?.is_preliminary || analysisResult?.is_preliminary || assessedSkills.length === 0;

  const overallMatchScore = analysisResult?.score_data?.score !== undefined 
    ? `${Math.round(analysisResult.score_data.score)}%` 
    : (aggregationData?.overall_score !== null && aggregationData?.overall_score !== undefined 
        ? `${Math.round(aggregationData.overall_score * 100)}%` 
        : '80%');

  const skillsMetCount = aggregationData 
    ? aggregationData.skills_meeting_requirement 
    : skillsList.filter(s => s.matched && !s.is_weakness).length;

  const totalSkillsCount = aggregationData?.total_skills || skillsList.length;

  // Dynamic banner colors based on verdict
  const getBannerTheme = (v) => {
    const s = String(v).toLowerCase();
    if (s.includes('interview') || s.includes('ready')) {
      return {
        gradient: 'linear-gradient(135deg, #065f46 0%, #047857 100%)',
        badgeBg: 'rgba(255, 255, 255, 0.2)',
        icon: <CheckCircle2 size={24} style={{ color: '#a7f3d0' }} />
      };
    }
    if (s.includes('major') || s.includes('upskill')) {
      return {
        gradient: 'linear-gradient(135deg, #881337 0%, #be123c 100%)',
        badgeBg: 'rgba(255, 255, 255, 0.2)',
        icon: <AlertTriangle size={24} style={{ color: '#fecaca' }} />
      };
    }
    return {
      gradient: 'linear-gradient(135deg, #4c1d95 0%, #6d28d9 100%)',
      badgeBg: 'rgba(255, 255, 255, 0.2)',
      icon: <TrendingUp size={24} style={{ color: '#fbcfe8' }} />
    };
  };

  const bannerTheme = getBannerTheme(finalVerdict);

  const targetAssessmentPath = (skillName) => {
    const encoded = encodeURIComponent(skillName);
    return activeAnalysisId
      ? `/assessment/${encoded}?analysis_id=${encodeURIComponent(activeAnalysisId)}`
      : `/assessment/${encoded}`;
  };

  return (
    <div className="fade-in" style={{ maxWidth: '1000px', margin: '0 auto', paddingBottom: '3rem' }}>
      {/* HEADER & WELCOME */}
      <div className="flex justify-between items-center mb-6 flex-wrap gap-4 pb-4" style={{ borderBottom: '1px solid var(--border-color)' }}>
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="badge badge-purple" style={{ fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
              Final Candidate Evaluation
            </span>
            {activeAnalysisId && (
              <span className="text-xs text-muted">
                Session #{activeAnalysisId}
              </span>
            )}
          </div>
          <h1 className="page-title text-2xl font-extrabold text-main" style={{ margin: 0 }}>
            Final Recommendation & Summary
          </h1>
          <p className="text-xs text-muted mt-1">
            Synthesized across JD requirements, CV evidence matching, and technical MCQ assessments.
          </p>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          <button
            type="button"
            onClick={handleManualRefresh}
            disabled={loadingAgg || isRefreshing}
            className="btn btn-outline flex items-center gap-1.5 text-xs"
            style={{ padding: '0.5rem 0.9rem' }}
            title="Recalculate Model 2 synthesis"
          >
            <RefreshCw size={13} className={loadingAgg || isRefreshing ? 'animate-spin' : ''} />
            <span>{loadingAgg || isRefreshing ? 'Updating...' : 'Refresh Synthesis'}</span>
          </button>
          <button
            type="button"
            onClick={() => navigate(activeAnalysisId ? `/dashboard?analysis_id=${activeAnalysisId}` : '/dashboard')}
            className="btn btn-outline flex items-center gap-1.5 text-xs"
            style={{ padding: '0.5rem 0.9rem' }}
          >
            <ArrowLeft size={13} />
            <span>Skill Matrix Grid</span>
          </button>
        </div>
      </div>

      {refreshError && (
        <div className="alert-error flex items-center gap-2 mb-4 p-3 rounded text-xs">
          <AlertCircle size={15} />
          <span>{refreshError}</span>
        </div>
      )}

      {/* 1. OVERALL EXECUTIVE RECOMMENDATION HERO BANNER */}
      <div
        className="match-score-card mb-6"
        style={{
          background: bannerTheme.gradient,
          borderRadius: 'var(--radius)',
          padding: '2rem',
          boxShadow: '0 10px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1)',
        }}
      >
        <div style={{ flex: '1 1 340px' }}>
          <div className="flex items-center gap-2 mb-2 flex-wrap" style={{ opacity: 0.95, fontSize: '0.78rem', textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 700 }}>
            <div className="flex items-center gap-1.5">
              {bannerTheme.icon}
              <span>Model 2 Candidate Readiness Verdict</span>
            </div>
            {isPreliminary && (
              <span
                style={{
                  backgroundColor: 'rgba(255, 255, 255, 0.22)',
                  color: '#ffffff',
                  padding: '0.15rem 0.55rem',
                  borderRadius: '9999px',
                  fontSize: '0.68rem',
                  fontWeight: 700,
                  letterSpacing: '0.04em',
                  border: '1px solid rgba(255, 255, 255, 0.4)',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '0.25rem',
                }}
              >
                <HelpCircle size={11} />
                <span>Preliminary (0 Quizzes Completed)</span>
              </span>
            )}
          </div>
          <div className="font-extrabold text-3xl" style={{ letterSpacing: '-0.02em', lineHeight: 1.2, color: '#ffffff' }}>
            {finalVerdict}
            {isPreliminary && (
              <span style={{ fontSize: '1.1rem', fontWeight: 600, opacity: 0.9, marginLeft: '0.5rem' }}>
                (Preliminary)
              </span>
            )}
          </div>
          <p className="text-xs mt-2.5" style={{ opacity: 0.95, maxWidth: '560px', lineHeight: 1.6, color: 'rgba(255, 255, 255, 0.95)' }}>
            {isPreliminary 
              ? 'Preliminary evaluation synthesized from CV evidence. Candidate has completed 0 quiz assessments; technical proficiency has not yet been verified. Take technical assessments below to demonstrate proficiency.' 
              : getVerdictExplanation(finalVerdict)}
          </p>
        </div>

        <div className="flex items-center gap-3 flex-wrap">
          {overallConfidenceDisplay && (
            <div className="match-stat-item" style={{ backgroundColor: bannerTheme.badgeBg }}>
              <div className="text-xs" style={{ color: 'rgba(255,255,255,0.85)', fontSize: '0.72rem', textTransform: 'uppercase', fontWeight: 600 }}>
                Confidence
              </div>
              <div className="font-extrabold text-xl mt-0.5">{overallConfidenceDisplay}</div>
            </div>
          )}

          <div className="match-stat-item" style={{ backgroundColor: bannerTheme.badgeBg }}>
            <div className="text-xs" style={{ color: 'rgba(255,255,255,0.85)', fontSize: '0.72rem', textTransform: 'uppercase', fontWeight: 600 }}>
              Job Readiness
            </div>
            <div className="font-extrabold text-xl mt-0.5">{overallMatchScore}</div>
          </div>

          <div className="match-stat-item" style={{ backgroundColor: bannerTheme.badgeBg }}>
            <div className="text-xs" style={{ color: 'rgba(255,255,255,0.85)', fontSize: '0.72rem', textTransform: 'uppercase', fontWeight: 600 }}>
              Requirements Met
            </div>
            <div className="font-extrabold text-xl mt-0.5">{skillsMetCount} / {totalSkillsCount}</div>
          </div>
        </div>
      </div>

      {/* 2. AGGREGATED METRICS GRID (Responsive, pristine layout) */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))',
          gap: '1rem',
          marginBottom: '1.75rem',
        }}
      >
        <div className="card" style={{ padding: '1.25rem 1.5rem', margin: 0, border: '1px solid var(--border-color)' }}>
          <div className="text-xs text-muted font-bold uppercase tracking-wider mb-1 flex items-center gap-1.5">
            <Layers size={14} style={{ color: 'var(--primary-600)' }} />
            <span>Total Job Skills</span>
          </div>
          <div className="font-extrabold text-2xl text-main">{totalSkillsCount}</div>
          <div className="text-xs text-muted mt-1">Identified from job description</div>
        </div>

        <div className="card" style={{ padding: '1.25rem 1.5rem', margin: 0, border: '1px solid var(--border-color)' }}>
          <div className="text-xs text-muted font-bold uppercase tracking-wider mb-1 flex items-center gap-1.5">
            <ShieldCheck size={14} style={{ color: '#059669' }} />
            <span>Assessed via Quiz</span>
          </div>
          <div className="font-extrabold text-2xl text-main">{assessedSkills.length}</div>
          <div className="text-xs text-muted mt-1">
            {assessedSkills.length === 0 ? 'None completed yet' : `${assessedSkills.length} skill quiz attempted`}
          </div>
        </div>

        <div className="card" style={{ padding: '1.25rem 1.5rem', margin: 0, border: '1px solid var(--border-color)' }}>
          <div className="text-xs text-muted font-bold uppercase tracking-wider mb-1 flex items-center gap-1.5">
            <CheckCircle2 size={14} style={{ color: '#2563eb' }} />
            <span>CV Verified Skills</span>
          </div>
          <div className="font-extrabold text-2xl text-main">{cvVerifiedSkills.length}</div>
          <div className="text-xs text-muted mt-1">Satisfied from CV evidence</div>
        </div>

        <div className="card" style={{ padding: '1.25rem 1.5rem', margin: 0, border: '1px solid var(--border-color)' }}>
          <div className="text-xs text-muted font-bold uppercase tracking-wider mb-1 flex items-center gap-1.5">
            <AlertTriangle size={14} style={{ color: '#d97706' }} />
            <span>Growth Skill Gaps</span>
          </div>
          <div className="font-extrabold text-2xl text-main">{gapSkills.length}</div>
          <div className="text-xs text-muted mt-1">
            {gapSkills.length === 0 ? 'Zero gaps detected' : 'Require practice or CV update'}
          </div>
        </div>
      </div>

      {/* 3. SKILL-BY-SKILL RECOMMENDATIONS SECTION */}
      <div className="card mb-6" style={{ padding: '1.5rem', backgroundColor: '#ffffff', border: '1px solid var(--border-color)' }}>
        <div className="flex justify-between items-center mb-5 flex-wrap gap-3 pb-3" style={{ borderBottom: '1px solid var(--border-color)' }}>
          <div>
            <h2 className="card-title mb-0.5 text-lg font-bold flex items-center gap-2">
              <Sparkles size={18} style={{ color: 'var(--primary-600)' }} />
              <span>Skill-by-Skill Recommendations</span>
            </h2>
            <p className="text-muted text-xs">
              Detailed breakdown of required proficiency, candidate verification status, and Model 1 AI recommendations.
            </p>
          </div>

          {/* Filter Chips */}
          <div className="filter-chips" role="group" aria-label="Filter skill recommendations">
            {[
              { id: 'all', label: 'All Skills', count: skillsList.length },
              { id: 'gaps', label: 'Gaps Only', count: gapSkills.length },
              { id: 'assessed', label: 'Assessed', count: assessedSkills.length },
              { id: 'cv_verified', label: 'CV Verified', count: cvVerifiedSkills.length },
            ].map((chip) => (
              <button
                key={chip.id}
                type="button"
                className={`filter-chip ${activeTab === chip.id ? 'active' : ''}`}
                onClick={() => setActiveTab(chip.id)}
              >
                <span>{chip.label}</span>
                <span className="filter-chip-count">{chip.count}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Skills List Cards */}
        <div className="skills-list">
          {filteredSkills.length === 0 ? (
            <div className="text-center py-8 text-muted text-sm">
              No skills match the selected "{activeTab}" filter.
            </div>
          ) : (
            filteredSkills.map((item, idx) => {
              const supported = isSupportedSkill(item.skill);
              const isAssessed = item.assessed_level !== null && item.assessed_level !== undefined;
              const reqLvl = formatLevel(item.required_level || item.level);
              const assessedLvl = formatLevel(item.assessed_level);
              const cvLvlDisplay = item.cv_level && item.cv_level !== 'not_found'
                ? formatLevel(item.cv_level)
                : (item.matched ? 'Mentioned in CV' : 'Not in CV');

              // Status badge determination
              const hasGap = item.is_weakness || !item.matched || (item.level_gap !== null && item.level_gap > 0);
              const isMissingInCv = !item.matched || item.cv_match_status === 'Missing';

              // Model 1 Recommendation label
              let recLabel = item.skill_recommendation;
              if (!recLabel) {
                if (isAssessed) {
                  recLabel = hasGap ? 'Upgrade Needed' : 'Mastered';
                } else if (isMissingInCv) {
                  recLabel = 'Verify Skill';
                } else if (hasGap) {
                  recLabel = 'Upgrade Needed';
                } else {
                  recLabel = 'Mastered';
                }
              }

              const badgeStyle = getRecommendationBadgeStyle(recLabel);
              const confDisplay = formatConfidence(item.recommendation_confidence || 0.85);

              // Explanation text
              const explanation =
                RECOMMENDATION_EXPLANATIONS[recLabel] ||
                item.recommendation_reason ||
                item.recommendation ||
                (isAssessed ? 'Assessment quiz completed.' : 'Evaluated against CV evidence.');

              return (
                <div
                  key={idx}
                  className="card"
                  style={{
                    padding: '1.25rem 1.5rem',
                    marginBottom: '1rem',
                    backgroundColor: '#ffffff',
                    border: '1px solid var(--border-color)',
                    borderLeft: hasGap ? '4px solid #f59e0b' : '4px solid #10b981',
                  }}
                >
                  {/* Top Bar: Skill Name + Tags */}
                  <div className="flex justify-between items-center mb-3 flex-wrap gap-2">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-bold text-lg text-main">{item.skill}</span>
                      <span
                        className="badge"
                        style={{
                          fontSize: '0.7rem',
                          fontWeight: 600,
                          backgroundColor: item.importance === 'preferred' ? '#ffffff' : '#f1f5f9',
                          color: item.importance === 'preferred' ? '#64748b' : '#1e293b',
                          border: item.importance === 'preferred' ? '1px solid #e2e8f0' : '1px solid #cbd5e1',
                        }}
                      >
                        {item.importance === 'preferred' ? 'Nice to Have' : 'Required'}
                      </span>

                      {/* Verification Status Pill */}
                      {isAssessed ? (
                        <span
                          className="badge"
                          style={{
                            fontSize: '0.72rem',
                            fontWeight: 600,
                            backgroundColor: hasGap ? '#fffbeb' : '#ecfdf5',
                            color: hasGap ? '#b45309' : '#059669',
                            border: hasGap ? '1px solid #fde68a' : '1px solid #a7f3d0',
                          }}
                        >
                          ✓ Quiz Assessed: {assessedLvl}
                        </span>
                      ) : (
                        <span
                          className="badge"
                          style={{
                            fontSize: '0.72rem',
                            fontWeight: 600,
                            backgroundColor: isMissingInCv ? '#f8fafc' : (hasGap ? '#fffbeb' : '#f1f5f9'),
                            color: isMissingInCv ? '#64748b' : (hasGap ? '#b45309' : '#475569'),
                            border: isMissingInCv ? '1px solid #e2e8f0' : (hasGap ? '1px solid #fde68a' : '1px solid #cbd5e1'),
                          }}
                        >
                          {isMissingInCv ? 'Not on CV (Unverified)' : (hasGap ? 'CV Level Gap' : 'CV Verified')}
                        </span>
                      )}

                      {!supported && (
                        <span className="badge" style={{ fontSize: '0.68rem', backgroundColor: '#f8fafc', color: '#64748b', border: '1px solid #e2e8f0' }}>
                          No Quiz in DB
                        </span>
                      )}
                    </div>

                    {/* Recommendation Badge */}
                    <div className="flex items-center gap-2">
                      {confDisplay && (
                        <span className="text-xs text-muted font-medium">
                          Confidence: <strong>{confDisplay}</strong>
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

                  {/* Level & Quiz Score Grid */}
                  <div
                    style={{
                      display: 'grid',
                      gridTemplateColumns: 'repeat(3, 1fr)',
                      gap: '0.75rem',
                      padding: '0.85rem 1rem',
                      backgroundColor: '#f8fafc',
                      borderRadius: 'var(--radius-sm)',
                      marginBottom: '0.75rem',
                      border: '1px solid #f1f5f9',
                    }}
                  >
                    <div>
                      <div className="text-xs text-muted font-semibold uppercase tracking-wider">Required Level</div>
                      <div className="font-bold text-main text-sm mt-0.5">{reqLvl}</div>
                    </div>

                    <div>
                      <div className="text-xs text-muted font-semibold uppercase tracking-wider">
                        {isAssessed ? 'Assessed Level' : 'Current (CV) Level'}
                      </div>
                      <div className="font-bold text-main text-sm mt-0.5">
                        {isAssessed ? assessedLvl : cvLvlDisplay}
                      </div>
                    </div>

                    <div>
                      <div className="text-xs text-muted font-semibold uppercase tracking-wider">Topic Quiz Score</div>
                      <div className="font-bold text-main text-sm mt-0.5">
                        {isAssessed ? formatScore(item.total_score) : (supported ? 'Not Assessed' : 'N/A (CV Match)')}
                      </div>
                    </div>
                  </div>

                  {/* ML Summary & Action Row */}
                  <div style={{ padding: '0.75rem 1rem', backgroundColor: '#ffffff', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)' }}>
                    <div className="text-xs font-bold uppercase tracking-wider text-muted mb-1">
                      ML Summary & Guidance
                    </div>
                    <p className="text-xs text-main" style={{ lineHeight: 1.5, margin: 0 }}>
                      {explanation}
                    </p>

                    {item.evidence && (
                      <div className="text-xs text-muted mt-2 pt-2" style={{ borderTop: '1px dashed var(--border-color)', fontStyle: 'italic' }}>
                        CV Evidence Quote: "{item.evidence}"
                      </div>
                    )}

                    {/* Action Prompt */}
                    <div className="mt-3 pt-2 flex justify-between items-center flex-wrap gap-2" style={{ borderTop: '1px solid var(--border-color)' }}>
                      <span className="text-xs text-muted">
                        {supported
                          ? (isAssessed ? 'Retake technical assessment to improve score.' : `Interactive technical MCQ quiz available for ${item.skill}.`)
                          : `Self-directed learning recommended for ${item.skill}.`}
                      </span>

                      {supported && (
                        <button
                          type="button"
                          onClick={() => navigate(targetAssessmentPath(item.skill))}
                          className={isAssessed ? 'btn btn-outline text-xs' : 'btn btn-primary text-xs'}
                          style={{ padding: '0.35rem 0.85rem' }}
                        >
                          {isAssessed ? (
                            <>
                              <RotateCcw size={12} />
                              <span>Retake Assessment</span>
                            </>
                          ) : (
                            <>
                              <span>Take Assessment</span>
                              <ArrowRight size={13} />
                            </>
                          )}
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* 4. RECOMMENDED CV IMPROVEMENTS */}
      <div className="mb-6">
        <CVFeedbackCard feedbackList={skillsList.filter(s => s.actionable_feedback)} />
      </div>

      {/* 5. TAILORED CANDIDATE ACTION PLAN */}
      <div className="card mb-6" style={{ background: '#f8fafc', border: '1px solid var(--border-color)' }}>
        <h2 className="card-title flex items-center gap-2 mb-1 text-lg font-bold">
          <BookOpen size={18} style={{ color: 'var(--primary-700)' }} />
          <span>Tailored Candidate Action Plan</span>
        </h2>
        <p className="text-xs text-muted mb-4">
          Priority-ranked action items to bridge skill gaps and maximize job match readiness.
        </p>

        <div className="flex flex-col gap-2.5">
          {skillsList.filter(s => s.is_weakness || s.priority === 'HIGH' || !s.matched).length > 0 ? (
            skillsList
              .filter(s => s.is_weakness || s.priority === 'HIGH' || !s.matched)
              .sort((a, b) => {
                const aHigh = a.priority === 'HIGH' || (a.importance || 'required').toLowerCase() !== 'preferred';
                const bHigh = b.priority === 'HIGH' || (b.importance || 'required').toLowerCase() !== 'preferred';
                return bHigh - aHigh;
              })
              .map((s, idx) => (
                <div
                  key={idx}
                  className="flex items-start justify-between gap-3 flex-wrap"
                  style={{
                    padding: '0.85rem 1.15rem',
                    backgroundColor: '#ffffff',
                    borderRadius: 'var(--radius-sm)',
                    border: '1px solid var(--border-color)',
                  }}
                >
                  <div className="flex items-start gap-3">
                    <span
                      style={{
                        backgroundColor: s.priority === 'HIGH' ? '#fef2f2' : '#fffbeb',
                        color: s.priority === 'HIGH' ? '#dc2626' : '#b45309',
                        border: s.priority === 'HIGH' ? '1px solid #fecaca' : '1px solid #fde68a',
                        padding: '0.2rem 0.5rem',
                        borderRadius: '4px',
                        fontSize: '0.7rem',
                        fontWeight: 700,
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {s.priority || 'HIGH'} PRIORITY
                    </span>
                    <div>
                      <div className="font-bold text-sm text-main">
                        Focus on {s.skill} ({formatLevel(s.required_level || s.level)} Standard)
                      </div>
                      <div className="text-xs text-muted mt-0.5">
                        {formatWeaknessReason(s.weakness_reason)}
                      </div>
                    </div>
                  </div>

                  {isSupportedSkill(s.skill) && (
                    <button
                      type="button"
                      onClick={() => navigate(targetAssessmentPath(s.skill))}
                      className="btn btn-outline text-xs"
                      style={{ padding: '0.25rem 0.65rem' }}
                    >
                      {s.assessed_level ? 'Retake Quiz' : 'Take Assessment'}
                    </button>
                  )}
                </div>
              ))
          ) : (
            <div className="flex items-center gap-2 text-emerald-700 bg-emerald-50 p-4 rounded" style={{ border: '1px solid #a7f3d0' }}>
              <CheckCircle2 size={20} />
              <span className="text-sm font-semibold">
                No critical skill weaknesses identified! Candidate strongly meets core job qualifications.
              </span>
            </div>
          )}
        </div>
      </div>

      {/* 6. PAGE FOOTER NAVIGATION */}
      <div className="flex justify-between items-center flex-wrap gap-4 pt-2">
        <button
          onClick={() => navigate(activeAnalysisId ? `/dashboard?analysis_id=${activeAnalysisId}` : '/dashboard')}
          className="btn btn-outline flex items-center gap-2"
        >
          <ArrowLeft size={16} />
          <span>Back to Skill Matrix Grid</span>
        </button>

        <button
          onClick={() => {
            clearAnalysis();
            navigate('/dashboard');
          }}
          className="btn btn-primary flex items-center gap-2"
        >
          <RefreshCw size={16} />
          <span>Analyze Another Job</span>
        </button>
      </div>
    </div>
  );
}
