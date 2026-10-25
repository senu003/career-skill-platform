import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { 
  CheckCircle2, 
  AlertCircle, 
  AlertTriangle, 
  TrendingUp, 
  Sparkles, 
  BookOpen, 
  ArrowRight, 
  ArrowLeft, 
  RefreshCw, 
  ShieldCheck, 
  HelpCircle, 
  RotateCcw,
  Copy,
  Check,
  ChevronDown,
  ChevronUp,
  FileText,
  Quote
} from 'lucide-react';
import { fetchWithAuth } from '../api';
import { useAssessment } from '../context/AssessmentContext';
import { isSupportedSkill } from '../utils/supportedSkills';

// Recommendation label explanations
const _RECOMMENDATION_EXPLANATIONS = {
  'Mastered': 'Candidate exhibits strong knowledge and high accuracy for this skill.',
  'Upgrade Needed': 'Current demonstrated level is below the job standard. Level upgrade required.',
  'Speed Practice': 'Core concept knowledge is adequate, but problem-solving speed needs practice.',
  'Re-learn Basics': 'Candidate struggled with fundamental concepts. Structured foundational review required.',
  'Verify Skill': 'Skill was not detected in CV evidence. Assessment recommended to demonstrate proficiency.',
  'Verify Proficiency': 'Skill detected in CV evidence (unverified). Assessment recommended to confirm technical proficiency.',
};

const WEAKNESS_REASON_MAP = {
  'LEVEL_GAP_AND_LOW_SCORE': 'Critical level gap & low quiz accuracy score. Foundational review required.',
  'LOW_ASSESSMENT_SCORE': 'Assessment score is below passing threshold. Targeted practice recommended.',
  'LEVEL_GAP': 'Skill level is below required job level standard.',
  'UNVERIFIED_IN_CV': 'Skill not mentioned in candidate CV. Assessment or CV update recommended.',
  'MISSING_SKILL': 'Skill not mentioned in candidate CV. Assessment or CV update recommended.',
  'UNASSESSED_REQUIRED_SKILL': 'Pending technical assessment evaluation.',
  'NONE': 'Requirement fully satisfied.',
};

const formatWeaknessReason = (reason) => {
  if (!reason || reason === 'NONE') return 'Requirement fully satisfied.';
  if (WEAKNESS_REASON_MAP[reason]) return WEAKNESS_REASON_MAP[reason];
  return reason.replace(/_/g, ' ').toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase());
};

const getVerdictExplanation = (verdict, verifiedCount, totalCount, gapCount) => {
  const clean = (verdict || '').toLowerCase();
  if (clean.includes('major upskill')) {
    return 'Candidate demonstrates critical level gaps or missing core competencies. Foundational upskilling on key technical skills is recommended prior to job applications.';
  }
  if (clean.includes('short-term') || clean.includes('prep')) {
    return `Candidate has a solid foundation aligning with target job requirements. Focused effort on ${gapCount > 0 ? `${gapCount} identified skill gap${gapCount > 1 ? 's' : ''}` : 'pending skill verifications'} will achieve complete interview readiness.`;
  }
  if (clean.includes('interview') || clean.includes('ready')) {
    return 'Candidate strongly meets or exceeds core job requirements across CV evidence and technical assessments. Well-prepared to proceed to technical interviews.';
  }
  return `Comprehensive candidate readiness evaluated across ${totalCount} job requirements with ${verifiedCount} directly verified.`;
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
  if (score === null || score === undefined) return null;
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
      icon: <CheckCircle2 size={13} style={{ color: '#059669' }} />
    };
  }
  if (cleanRec === 'speed practice') {
    return {
      backgroundColor: '#eff6ff',
      color: '#2563eb',
      border: '1px solid #bfdbfe',
      icon: <TrendingUp size={13} style={{ color: '#2563eb' }} />
    };
  }
  if (cleanRec === 'upgrade needed') {
    return {
      backgroundColor: '#fffbeb',
      color: '#b45309',
      border: '1px solid #fde68a',
      icon: <AlertTriangle size={13} style={{ color: '#d97706' }} />
    };
  }
  if (cleanRec === 're-learn basics') {
    return {
      backgroundColor: '#fef2f2',
      color: '#dc2626',
      border: '1px solid #fecaca',
      icon: <AlertCircle size={13} style={{ color: '#dc2626' }} />
    };
  }
  return {
    backgroundColor: '#f8fafc',
    color: '#475569',
    border: '1px solid #cbd5e1',
    icon: <HelpCircle size={13} style={{ color: '#64748b' }} />
  };
};

export default function FinalResultPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { analysisResult, setAnalysisResult, clearAnalysis, refreshAnalysis, isRefreshing } = useAssessment();

  const urlAnalysisId = searchParams.get('analysis_id');
  const activeAnalysisId = urlAnalysisId || analysisResult?.analysis_id;

  // Tabs for the compact skill matrix: 'action' (default), 'verified', 'all'
  const [matrixFilter, setMatrixFilter] = useState('action');
  const [aggregationData, setAggregationData] = useState(null);
  const [loadingAgg, setLoadingAgg] = useState(false);
  const [refreshError, setRefreshError] = useState(null);

  // Expandable states for evidence and CV suggestions to prevent screen clutter
  const [expandedCvSuggest, setExpandedCvSuggest] = useState({});
  const [expandedEvidence, setExpandedEvidence] = useState({});
  const [copiedKey, setCopiedKey] = useState(null);

  const toggleCvSuggest = (key) => {
    setExpandedCvSuggest(prev => ({ ...prev, [key]: !prev[key] }));
  };

  const toggleEvidence = (key) => {
    setExpandedEvidence(prev => ({ ...prev, [key]: !prev[key] }));
  };

  const handleCopyText = async (key, text) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedKey(key);
      setTimeout(() => setCopiedKey(null), 2000);
    } catch (e) {
      console.warn('Copy failed', e);
    }
  };

  // Auto-restore session from backend if urlAnalysisId provided OR if analysisResult is empty
  useEffect(() => {
    let isCancelled = false;
    if (urlAnalysisId && String(analysisResult?.analysis_id) !== String(urlAnalysisId)) {
      const fetchSession = async () => {
        setLoadingAgg(true);
        try {
          const detailRes = await fetchWithAuth(`/cv/sessions/${urlAnalysisId}`);
          if (!isCancelled && detailRes) {
            setAnalysisResult(detailRes);
          }
        } catch (err) {
          console.warn('Could not restore session for analysis_id:', err);
        } finally {
          if (!isCancelled) setLoadingAgg(false);
        }
      };
      fetchSession();
    } else if (!analysisResult) {
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

  const skillsList = useMemo(() => analysisResult?.skills || [
    ...(analysisResult?.matched_skills || []),
    ...(analysisResult?.missing_skills || []),
  ] || [], [analysisResult]);

  // Fetch backend aggregation stats when analysisResult is present
  const fetchAggregation = useCallback(async () => {
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
  }, [skillsList]);

  useEffect(() => {
    if (skillsList.length > 0) {
      fetchAggregation();
    }
  }, [fetchAggregation, skillsList.length]);

  const handleManualRefresh = async () => {
    if (activeAnalysisId) {
      await refreshAnalysis(activeAnalysisId);
    }
    await fetchAggregation();
  };

  // 4-state skill categorization
  const assessedSkills = useMemo(() => skillsList.filter((s) => s.assessed_level !== null && s.assessed_level !== undefined), [skillsList]);
  const verifiedMasteredSkills = useMemo(() => skillsList.filter((s) => {
    const isAssessed = s.assessed_level !== null && s.assessed_level !== undefined;
    return isAssessed && !s.is_weakness && (s.level_gap === null || s.level_gap === 0);
  }), [skillsList]);
  const confirmedGapSkills = useMemo(() => skillsList.filter((s) => {
    const isAssessed = s.assessed_level !== null && s.assessed_level !== undefined;
    return isAssessed && (s.is_weakness || (s.level_gap !== null && s.level_gap > 0) || (s.total_score !== null && s.total_score < 0.40));
  }), [skillsList]);
  const cvEvidencedSkills = useMemo(() => skillsList.filter((s) => {
    const isAssessed = s.assessed_level !== null && s.assessed_level !== undefined;
    return !isAssessed && s.matched && s.cv_match_status !== 'Missing';
  }), [skillsList]);
  const missingCvSkills = useMemo(() => skillsList.filter((s) => {
    const isAssessed = s.assessed_level !== null && s.assessed_level !== undefined;
    return !isAssessed && (!s.matched || s.cv_match_status === 'Missing');
  }), [skillsList]);

  // Actionable Skills: items with confirmed gap, missing from CV, or unassessed required skills
  const actionableSkills = useMemo(() => skillsList.filter((s) => {
    const isAssessed = s.assessed_level !== null && s.assessed_level !== undefined;
    if (isAssessed) {
      return s.is_weakness || (s.level_gap !== null && s.level_gap > 0) || (s.total_score !== null && s.total_score < 0.40);
    }
    return !s.matched || s.cv_match_status === 'Missing' || (s.importance || 'required').toLowerCase() !== 'preferred';
  }), [skillsList]);

  const verifiedAndMatchedSkills = useMemo(() => skillsList.filter((s) => {
    const isAssessed = s.assessed_level !== null && s.assessed_level !== undefined;
    if (isAssessed) {
      return !s.is_weakness && (s.level_gap === null || s.level_gap === 0);
    }
    return s.matched && s.cv_match_status !== 'Missing';
  }), [skillsList]);

  // Authoritative Verdict & Overall Status Resolution
  const finalVerdict = analysisResult?.readiness_verdict || analysisResult?.final_verdict || aggregationData?.readiness_verdict || aggregationData?.final_verdict || 'Evaluation Complete';
  const overallConfidenceDisplay = formatConfidence(aggregationData?.recommendation_confidence || analysisResult?.recommendation_confidence || 0.85);
  const isPreliminary = Boolean(analysisResult?.is_preliminary ?? aggregationData?.is_preliminary ?? (assessedSkills.length === 0));

  const overallMatchScore = analysisResult?.score_data?.score !== undefined 
    ? `${Math.round(analysisResult.score_data.score)}%` 
    : (aggregationData?.overall_score !== null && aggregationData?.overall_score !== undefined 
        ? `${Math.round(aggregationData.overall_score * 100)}%` 
        : '80%');

  const totalSkillsCount = aggregationData?.total_skills || skillsList.length;

  // CONSOLIDATED ACTION ROADMAP:
  // Deduplicated high-impact items that need candidate action (Gaps, Missing, or Wording suggestions)
  const consolidatedActionItems = useMemo(() => {
    const itemMap = new Map();

    // 1. Confirmed gaps from assessment quiz
    confirmedGapSkills.forEach((s) => {
      itemMap.set(s.skill, {
        ...s,
        priorityRank: 1,
        priorityBadge: 'HIGH PRIORITY',
        priorityColor: '#dc2626',
        priorityBg: '#fef2f2',
        priorityBorder: '#fecaca',
        title: `Bridge Assessment Gap in ${s.skill}`,
        summary: s.weakness_reason && s.weakness_reason !== 'NONE'
          ? formatWeaknessReason(s.weakness_reason)
          : `Demonstrated quiz level (${formatLevel(s.assessed_level)}) is below the required ${formatLevel(s.required_level || s.level)} level.`,
      });
    });

    // 2. Missing from CV
    missingCvSkills.forEach((s) => {
      if (!itemMap.has(s.skill)) {
        const isRequired = (s.importance || 'required').toLowerCase() !== 'preferred';
        itemMap.set(s.skill, {
          ...s,
          priorityRank: isRequired ? 1 : 2,
          priorityBadge: isRequired ? 'HIGH PRIORITY' : 'RECOMMENDED',
          priorityColor: isRequired ? '#dc2626' : '#b45309',
          priorityBg: isRequired ? '#fef2f2' : '#fffbeb',
          priorityBorder: isRequired ? '#fecaca' : '#fde68a',
          title: `Demonstrate ${s.skill} Proficiency`,
          summary: `Not mentioned in your CV. Take the quiz to verify your proficiency or include relevant project experience.`,
        });
      }
    });

    // 3. Skills with actionable CV wording suggestions
    skillsList.filter(s => s.actionable_feedback).forEach((s) => {
      const existing = itemMap.get(s.skill);
      if (existing) {
        existing.actionable_feedback = s.actionable_feedback;
      } else {
        const isHigh = s.actionable_feedback?.priority?.toLowerCase() === 'high';
        itemMap.set(s.skill, {
          ...s,
          priorityRank: isHigh ? 2 : 3,
          priorityBadge: isHigh ? 'CV REFINEMENT' : 'RECOMMENDED',
          priorityColor: '#0369a1',
          priorityBg: '#f0f9ff',
          priorityBorder: '#bae6fd',
          title: `Enhance CV Presentation for ${s.skill}`,
          summary: s.actionable_feedback.explanation || `Refine phrasing in your CV to align with expected industry standards.`,
        });
      }
    });

    // 4. Key required skills that are unassessed but have available technical quizzes
    skillsList
      .filter(s => isSupportedSkill(s.skill) && !s.assessed_level && (s.importance || 'required').toLowerCase() !== 'preferred')
      .forEach((s) => {
        if (!itemMap.has(s.skill)) {
          itemMap.set(s.skill, {
            ...s,
            priorityRank: 3,
            priorityBadge: 'VERIFY PROFICIENCY',
            priorityColor: '#4f46e5',
            priorityBg: '#eef2ff',
            priorityBorder: '#c7d2fe',
            title: `Verify ${s.skill} Technical Proficiency`,
            summary: `Found in CV (${formatLevel(s.cv_level)}). Verify with a 5-minute assessment to confirm for technical interviews.`,
          });
        }
      });

    return Array.from(itemMap.values()).sort((a, b) => a.priorityRank - b.priorityRank);
  }, [confirmedGapSkills, missingCvSkills, skillsList]);

  // Skills to display in the compact matrix based on active filter
  const displayedMatrixSkills = useMemo(() => {
    if (matrixFilter === 'action') {
      return actionableSkills;
    }
    if (matrixFilter === 'verified') {
      return verifiedAndMatchedSkills;
    }
    return skillsList;
  }, [matrixFilter, actionableSkills, verifiedAndMatchedSkills, skillsList]);

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

  // Dynamic banner theme
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
      gradient: 'linear-gradient(135deg, #4338ca 0%, #6366f1 100%)',
      badgeBg: 'rgba(255, 255, 255, 0.2)',
      icon: <TrendingUp size={24} style={{ color: '#e0e7ff' }} />
    };
  };

  const bannerTheme = getBannerTheme(finalVerdict);

  const targetAssessmentPath = (skillName) => {
    const encoded = encodeURIComponent(skillName);
    return activeAnalysisId
      ? `/assessment/${encoded}?analysis_id=${encodeURIComponent(activeAnalysisId)}`
      : `/assessment/${encoded}`;
  };

  // Visual proportions for the single progress strip
  const totalCount = Math.max(1, totalSkillsCount);
  const pctVerified = Math.round((verifiedMasteredSkills.length / totalCount) * 100);
  const pctEvidenced = Math.round((cvEvidencedSkills.length / totalCount) * 100);
  const pctGaps = 100 - pctVerified - pctEvidenced;

  return (
    <div className="fade-in" style={{ maxWidth: '1000px', margin: '0 auto', paddingBottom: '3.5rem', width: '100%', boxSizing: 'border-box', overflowX: 'hidden' }}>
      {/* PAGE HEADER */}
      <div className="flex justify-between items-center mb-5 flex-wrap gap-4 pb-3" style={{ borderBottom: '1px solid var(--border-color)' }}>
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="badge badge-purple" style={{ fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
              Executive Evaluation Summary
            </span>
            {activeAnalysisId && (
              <span className="text-xs text-muted">
                Session #{activeAnalysisId}
              </span>
            )}
          </div>
          <h1 className="page-title text-2xl font-extrabold text-main" style={{ margin: 0 }}>
            Candidate Readiness & Summary
          </h1>
          <p className="text-xs text-muted mt-1">
            Synthesized overview of your job alignment, direct assessment results, and high-impact next steps.
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
            <span>{loadingAgg || isRefreshing ? 'Updating...' : 'Refresh'}</span>
          </button>
          <button
            type="button"
            onClick={() => navigate(activeAnalysisId ? `/dashboard?analysis_id=${activeAnalysisId}` : '/dashboard')}
            className="btn btn-outline flex items-center gap-1.5 text-xs"
            style={{ padding: '0.5rem 0.9rem' }}
          >
            <ArrowLeft size={13} />
            <span>Diagnostic Dashboard</span>
          </button>
        </div>
      </div>

      {refreshError && (
        <div className="alert-error flex items-center gap-2 mb-4 p-3 rounded text-xs">
          <AlertCircle size={15} />
          <span>{refreshError}</span>
        </div>
      )}

      {/* 1. EXECUTIVE READINESS HERO BANNER */}
      <div
        className="match-score-card mb-4"
        style={{
          background: bannerTheme.gradient,
          borderRadius: 'var(--radius)',
          padding: '1.75rem 2rem',
          boxShadow: '0 8px 20px -4px rgba(0, 0, 0, 0.12)',
        }}
      >
        <div style={{ flex: '1 1 340px' }}>
          <div className="flex items-center gap-2 mb-2 flex-wrap" style={{ opacity: 0.95, fontSize: '0.78rem', textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 700 }}>
            <div className="flex items-center gap-1.5">
              {bannerTheme.icon}
              <span>Overall Candidate Readiness Verdict</span>
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
          <div className="font-extrabold text-2xl md:text-3xl" style={{ letterSpacing: '-0.02em', lineHeight: 1.2, color: '#ffffff' }}>
            {finalVerdict}
          </div>
          <p className="text-xs mt-2" style={{ opacity: 0.95, maxWidth: '600px', lineHeight: 1.6, color: 'rgba(255, 255, 255, 0.95)' }}>
            {isPreliminary 
              ? 'Preliminary evaluation based on CV text claims. Candidate has completed 0 quiz assessments; technical proficiency remains unverified. Complete the priority assessments below to verify capability.' 
              : getVerdictExplanation(finalVerdict, verifiedMasteredSkills.length, totalSkillsCount, confirmedGapSkills.length + missingCvSkills.length)}
          </p>
        </div>

        {/* High-level metrics */}
        <div className="flex items-center gap-3 flex-wrap">
          <div className="match-stat-item" style={{ backgroundColor: bannerTheme.badgeBg }}>
            <div className="text-xs" style={{ color: 'rgba(255,255,255,0.85)', fontSize: '0.72rem', textTransform: 'uppercase', fontWeight: 600 }}>
              CV Match
            </div>
            <div className="font-extrabold text-xl mt-0.5">{overallMatchScore}</div>
          </div>

          <div className="match-stat-item" style={{ backgroundColor: bannerTheme.badgeBg }}>
            <div className="text-xs" style={{ color: 'rgba(255,255,255,0.85)', fontSize: '0.72rem', textTransform: 'uppercase', fontWeight: 600 }}>
              Verified Skills
            </div>
            <div className="font-extrabold text-xl mt-0.5">
              {verifiedMasteredSkills.length} / {totalSkillsCount}
            </div>
          </div>

          {overallConfidenceDisplay && (
            <div className="match-stat-item" style={{ backgroundColor: bannerTheme.badgeBg }}>
              <div className="text-xs" style={{ color: 'rgba(255,255,255,0.85)', fontSize: '0.72rem', textTransform: 'uppercase', fontWeight: 600 }}>
                Confidence
              </div>
              <div className="font-extrabold text-xl mt-0.5">{overallConfidenceDisplay}</div>
            </div>
          )}
        </div>
      </div>

      {/* 2. CONSOLIDATED READINESS STATUS STRIP (Replaces 6 redundant cards) */}
      <div
        className="card mb-6"
        style={{
          padding: '1.25rem 1.5rem',
          backgroundColor: '#ffffff',
          border: '1px solid var(--border-color)',
        }}
      >
        <div className="flex justify-between items-center mb-2 flex-wrap gap-2">
          <div className="text-xs font-bold uppercase tracking-wider text-muted flex items-center gap-1.5">
            <ShieldCheck size={14} style={{ color: 'var(--primary-600)' }} />
            <span>Readiness Distribution Across {totalSkillsCount} Requirements</span>
          </div>
          <div className="text-xs text-muted">
            {assessedSkills.length} of {totalSkillsCount} technical assessments completed
          </div>
        </div>

        {/* Visual Progress Bar */}
        <div
          style={{
            height: '10px',
            width: '100%',
            backgroundColor: '#e2e8f0',
            borderRadius: '9999px',
            display: 'flex',
            overflow: 'hidden',
            marginBottom: '0.85rem',
          }}
        >
          {pctVerified > 0 && (
            <div
              title={`Verified Mastered: ${verifiedMasteredSkills.length} (${pctVerified}%)`}
              style={{ width: `${pctVerified}%`, backgroundColor: '#10b981' }}
            />
          )}
          {pctEvidenced > 0 && (
            <div
              title={`CV Evidenced (Unverified): ${cvEvidencedSkills.length} (${pctEvidenced}%)`}
              style={{ width: `${pctEvidenced}%`, backgroundColor: '#0ea5e9' }}
            />
          )}
          {pctGaps > 0 && (
            <div
              title={`Needs Attention: ${confirmedGapSkills.length + missingCvSkills.length} (${pctGaps}%)`}
              style={{ width: `${pctGaps}%`, backgroundColor: '#f43f5e' }}
            />
          )}
        </div>

        {/* Legend Summary Pills */}
        <div className="flex items-center gap-3 flex-wrap text-xs">
          <div className="flex items-center gap-1.5">
            <span style={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: '#10b981', display: 'inline-block' }}></span>
            <span className="font-semibold text-main">{verifiedMasteredSkills.length} Verified Mastered</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span style={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: '#0ea5e9', display: 'inline-block' }}></span>
            <span className="font-semibold text-main">{cvEvidencedSkills.length} Evidenced in CV</span>
            <span className="text-muted">(Awaiting Quiz)</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span style={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: '#f43f5e', display: 'inline-block' }}></span>
            <span className="font-semibold text-main">{confirmedGapSkills.length + missingCvSkills.length} Action Needed</span>
            <span className="text-muted">({confirmedGapSkills.length} Gaps, {missingCvSkills.length} Missing)</span>
          </div>
        </div>
      </div>

      {/* 3. CONSOLIDATED ACTION ROADMAP (Single unified section replacing redundant Action Plan & CV Improvements) */}
      <div className="card mb-6" style={{ padding: '1.5rem', backgroundColor: '#ffffff', border: '1px solid var(--border-color)' }}>
        <div className="mb-4">
          <div className="flex items-center gap-2 mb-0.5">
            <BookOpen size={18} style={{ color: 'var(--primary-700)' }} />
            <h2 className="card-title text-lg font-bold" style={{ margin: 0 }}>
              Priority Action Roadmap
            </h2>
          </div>
          <p className="text-xs text-muted" style={{ margin: 0 }}>
            Clear, prioritized actions to eliminate skill gaps, verify capabilities, and refine your CV for this role.
          </p>
        </div>

        {consolidatedActionItems.length === 0 ? (
          <div className="flex items-center gap-2.5 text-emerald-800 bg-emerald-50 p-4 rounded" style={{ border: '1px solid #a7f3d0' }}>
            <CheckCircle2 size={20} className="text-emerald-600 flex-shrink-0" />
            <div className="text-xs">
              <strong className="block text-sm">All Job Requirements Satisfied!</strong>
              Your qualifications and verified assessment scores fully meet the requirements for this role. You are prepared for technical interviews.
            </div>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem', width: '100%' }}>
            {consolidatedActionItems.slice(0, 5).map((item, idx) => {
              const supported = isSupportedSkill(item.skill);
              const isCvExpanded = Boolean(expandedCvSuggest[item.skill]);
              const feedback = item.actionable_feedback;
              const isCopied = copiedKey === item.skill;

              return (
                <div
                  key={idx}
                  style={{
                    backgroundColor: '#f8fafc',
                    borderRadius: 'var(--radius-sm)',
                    border: '1px solid var(--border-color)',
                    padding: '1.15rem 1.25rem',
                  }}
                >
                  {/* Top Header Row */}
                  <div className="flex justify-between items-start gap-3 flex-wrap">
                    <div>
                      <div className="flex items-center gap-2 mb-1 flex-wrap">
                        <span
                          style={{
                            backgroundColor: item.priorityBg,
                            color: item.priorityColor,
                            border: `1px solid ${item.priorityBorder}`,
                            padding: '0.15rem 0.5rem',
                            borderRadius: '4px',
                            fontSize: '0.68rem',
                            fontWeight: 700,
                            letterSpacing: '0.03em',
                          }}
                        >
                          {item.priorityBadge}
                        </span>
                        <span className="font-bold text-main text-base">{item.skill}</span>
                        <span className="badge" style={{ fontSize: '0.68rem', backgroundColor: '#ffffff', border: '1px solid #cbd5e1' }}>
                          Standard: {formatLevel(item.required_level || item.level)}
                        </span>
                        {item.importance === 'preferred' && (
                          <span className="badge" style={{ fontSize: '0.68rem', backgroundColor: '#ffffff', color: '#64748b', border: '1px solid #e2e8f0' }}>
                            Nice to Have
                          </span>
                        )}
                      </div>

                      <div className="text-xs text-main font-medium mt-1">
                        {item.summary}
                      </div>
                    </div>

                    {/* Action Buttons */}
                    <div className="flex items-center gap-2 flex-wrap">
                      {feedback && (
                        <button
                          type="button"
                          onClick={() => toggleCvSuggest(item.skill)}
                          className="btn btn-outline text-xs flex items-center gap-1.5"
                          style={{
                            padding: '0.4rem 0.75rem',
                            backgroundColor: isCvExpanded ? '#f1f5f9' : '#ffffff',
                          }}
                        >
                          <FileText size={13} style={{ color: 'var(--primary-600)' }} />
                          <span>{isCvExpanded ? 'Hide CV Suggestion' : 'View CV Suggestion'}</span>
                          {isCvExpanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                        </button>
                      )}

                      {supported && (
                        <button
                          type="button"
                          onClick={() => navigate(targetAssessmentPath(item.skill))}
                          className={item.assessed_level ? 'btn btn-outline text-xs flex items-center gap-1.5' : 'btn btn-primary text-xs flex items-center gap-1.5'}
                          style={{ padding: '0.4rem 0.85rem' }}
                        >
                          {item.assessed_level ? (
                            <>
                              <RotateCcw size={12} />
                              <span>Retake Quiz</span>
                            </>
                          ) : (
                            <>
                              <Sparkles size={12} />
                              <span>Take 5-Min Quiz</span>
                              <ArrowRight size={12} />
                            </>
                          )}
                        </button>
                      )}
                    </div>
                  </div>

                  {/* Expandable CV Wording Box (Integrated without duplicating skills!) */}
                  {isCvExpanded && feedback && (
                    <div
                      className="fade-in"
                      style={{
                        marginTop: '0.85rem',
                        padding: '1rem',
                        backgroundColor: '#ffffff',
                        border: '1px solid #bbf7d0',
                        borderRadius: 'var(--radius-sm)',
                      }}
                    >
                      <div className="flex justify-between items-center mb-1.5">
                        <div className="text-xs font-bold text-emerald-800 uppercase tracking-wider flex items-center gap-1.5">
                          <Check size={13} />
                          <span>Suggested CV Phrasing ({feedback.section || 'Experience'} Section)</span>
                        </div>
                        {feedback.suggested_wording && (
                          <button
                            type="button"
                            onClick={() => handleCopyText(item.skill, feedback.suggested_wording)}
                            className="btn btn-outline text-xs flex items-center gap-1"
                            style={{ padding: '0.2rem 0.6rem', color: '#059669', borderColor: '#a7f3d0' }}
                          >
                            {isCopied ? <Check size={12} /> : <Copy size={12} />}
                            <span>{isCopied ? 'Copied to Clipboard!' : 'Copy Text'}</span>
                          </button>
                        )}
                      </div>

                      {feedback.suggested_wording ? (
                        <blockquote
                          style={{
                            margin: '0.5rem 0',
                            padding: '0.6rem 0.85rem',
                            backgroundColor: '#f0fdf4',
                            borderLeft: '3px solid #10b981',
                            fontSize: '0.825rem',
                            color: '#1e293b',
                            lineHeight: 1.5,
                          }}
                        >
                          "{feedback.suggested_wording}"
                        </blockquote>
                      ) : (
                        <p className="text-xs text-muted italic my-1">
                          No specific wording replacement generated. Highlight your direct experience with {item.skill} in your CV.
                        </p>
                      )}

                      {feedback.original_text && (
                        <div className="text-xs text-muted mt-2 pt-2" style={{ borderTop: '1px dashed #e2e8f0' }}>
                          <span className="font-semibold text-slate-600">Current text in CV: </span>
                          <span className="italic">"{feedback.original_text}"</span>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* 4. COMPACT SKILL STATUS & VERIFICATION MATRIX (Scannable, Clean, No Massive Wall of Cards) */}
      <div className="card mb-6" style={{ padding: '1.5rem', backgroundColor: '#ffffff', border: '1px solid var(--border-color)' }}>
        <div className="flex justify-between items-center mb-4 flex-wrap gap-3 pb-3" style={{ borderBottom: '1px solid var(--border-color)' }}>
          <div>
            <h2 className="card-title text-lg font-bold flex items-center gap-2" style={{ margin: 0 }}>
              <Sparkles size={17} style={{ color: 'var(--primary-600)' }} />
              <span>Skill Verification Matrix</span>
            </h2>
            <p className="text-muted text-xs mt-0.5" style={{ margin: 0 }}>
              Status of all {skillsList.length} job requirements. Matched skills take a single compact row.
            </p>
          </div>

          {/* Clean Segmented Filter Chips */}
          <div className="filter-chips" role="group" aria-label="Filter skill matrix">
            <button
              type="button"
              className={`filter-chip ${matrixFilter === 'action' ? 'active' : ''}`}
              onClick={() => setMatrixFilter('action')}
            >
              <span>Needs Attention</span>
              <span className="filter-chip-count">{actionableSkills.length}</span>
            </button>
            <button
              type="button"
              className={`filter-chip ${matrixFilter === 'verified' ? 'active' : ''}`}
              onClick={() => setMatrixFilter('verified')}
            >
              <span>Verified & Met</span>
              <span className="filter-chip-count">{verifiedAndMatchedSkills.length}</span>
            </button>
            <button
              type="button"
              className={`filter-chip ${matrixFilter === 'all' ? 'active' : ''}`}
              onClick={() => setMatrixFilter('all')}
            >
              <span>All Requirements</span>
              <span className="filter-chip-count">{skillsList.length}</span>
            </button>
          </div>
        </div>

        {/* Compact Scannable Table */}
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.85rem' }}>
            <thead>
              <tr style={{ borderBottom: '2px solid var(--border-color)', color: 'var(--text-muted)', fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                <th style={{ padding: '0.65rem 0.75rem', fontWeight: 700 }}>Skill</th>
                <th style={{ padding: '0.65rem 0.75rem', fontWeight: 700 }}>Required</th>
                <th style={{ padding: '0.65rem 0.75rem', fontWeight: 700 }}>Demonstration Status</th>
                <th style={{ padding: '0.65rem 0.75rem', fontWeight: 700 }}>Quiz Result</th>
                <th style={{ padding: '0.65rem 0.75rem', fontWeight: 700 }}>Recommendation</th>
                <th style={{ padding: '0.65rem 0.75rem', fontWeight: 700, textAlign: 'right' }}>Action</th>
              </tr>
            </thead>
            <tbody>
              {displayedMatrixSkills.length === 0 ? (
                <tr>
                  <td colSpan={6} style={{ padding: '2rem 1rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                    No skills in this category.
                  </td>
                </tr>
              ) : (
                displayedMatrixSkills.map((item, idx) => {
                  const supported = isSupportedSkill(item.skill);
                  const isAssessed = item.assessed_level !== null && item.assessed_level !== undefined;
                  const isVerifiedMastered = isAssessed && !item.is_weakness && (item.level_gap === null || item.level_gap === 0);
                  const isVerifiedGap = isAssessed && (item.is_weakness || (item.level_gap !== null && item.level_gap > 0) || (item.total_score !== null && item.total_score < 0.40));
                  const isCvEvidenced = !isAssessed && item.matched && item.cv_match_status !== 'Missing';
                  const isMissingInCv = !isAssessed && (!item.matched || item.cv_match_status === 'Missing');

                  const reqLvl = formatLevel(item.required_level || item.level);
                  const assessedLvl = formatLevel(item.assessed_level);
                  const cvLvlDisplay = item.cv_level && item.cv_level !== 'not_found'
                    ? formatLevel(item.cv_level)
                    : (item.matched ? 'In CV' : 'Not Found');

                  let recLabel = item.skill_recommendation;
                  if (!recLabel) {
                    if (isVerifiedMastered) recLabel = 'Mastered';
                    else if (isVerifiedGap) recLabel = 'Upgrade Needed';
                    else if (isMissingInCv) recLabel = 'Verify Skill';
                    else recLabel = 'Verify Proficiency';
                  }

                  const badgeStyle = getRecommendationBadgeStyle(recLabel);
                  const isQuoteExpanded = Boolean(expandedEvidence[item.skill]);

                  return (
                    <React.Fragment key={idx}>
                      <tr
                        style={{
                          borderBottom: isQuoteExpanded ? 'none' : '1px solid var(--border-color)',
                          backgroundColor: idx % 2 === 0 ? '#ffffff' : '#fafafa',
                        }}
                      >
                        {/* Skill Name */}
                        <td style={{ padding: '0.75rem', fontWeight: 600, color: 'var(--text-main)' }}>
                          <div className="flex items-center gap-1.5 flex-wrap">
                            <span>{item.skill}</span>
                            {item.importance === 'preferred' && (
                              <span style={{ fontSize: '0.65rem', color: '#64748b', backgroundColor: '#f1f5f9', padding: '0.1rem 0.35rem', borderRadius: '3px' }}>
                                Preferred
                              </span>
                            )}
                            {item.evidence && (
                              <button
                                type="button"
                                onClick={() => toggleEvidence(item.skill)}
                                title="Toggle CV evidence text"
                                style={{
                                  background: 'none',
                                  border: 'none',
                                  cursor: 'pointer',
                                  padding: '0.15rem',
                                  color: isQuoteExpanded ? 'var(--primary-600)' : '#94a3b8',
                                  display: 'inline-flex',
                                  alignItems: 'center',
                                }}
                              >
                                <Quote size={12} />
                              </button>
                            )}
                          </div>
                        </td>

                        {/* Required Level */}
                        <td style={{ padding: '0.75rem', color: '#334155' }}>
                          {reqLvl}
                        </td>

                        {/* Demonstration Status */}
                        <td style={{ padding: '0.75rem' }}>
                          {isVerifiedMastered && (
                            <span className="badge" style={{ backgroundColor: '#ecfdf5', color: '#059669', border: '1px solid #a7f3d0', fontSize: '0.7rem', fontWeight: 600 }}>
                              ✓ Verified: {assessedLvl}
                            </span>
                          )}
                          {isVerifiedGap && (
                            <span className="badge" style={{ backgroundColor: '#fef2f2', color: '#dc2626', border: '1px solid #fecaca', fontSize: '0.7rem', fontWeight: 600 }}>
                              ⚠ Level Gap: {assessedLvl}
                            </span>
                          )}
                          {isCvEvidenced && (
                            <span className="badge" style={{ backgroundColor: '#f0f9ff', color: '#0369a1', border: '1px solid #bae6fd', fontSize: '0.7rem' }}>
                              📄 In CV ({cvLvlDisplay})
                            </span>
                          )}
                          {isMissingInCv && (
                            <span className="badge" style={{ backgroundColor: '#f8fafc', color: '#64748b', border: '1px solid #cbd5e1', fontSize: '0.7rem' }}>
                              ✕ Not Found in CV
                            </span>
                          )}
                        </td>

                        {/* Quiz Result */}
                        <td style={{ padding: '0.75rem', fontWeight: 600 }}>
                          {isAssessed ? (
                            <span style={{ color: item.total_score >= 0.7 ? '#059669' : '#dc2626' }}>
                              {formatScore(item.total_score)}
                            </span>
                          ) : (
                            <span className="text-muted" style={{ fontWeight: 400, fontSize: '0.75rem' }}>
                              {supported ? 'Pending' : 'N/A'}
                            </span>
                          )}
                        </td>

                        {/* Recommendation */}
                        <td style={{ padding: '0.75rem' }}>
                          <span
                            style={{
                              ...badgeStyle,
                              padding: '0.15rem 0.5rem',
                              borderRadius: '9999px',
                              fontSize: '0.7rem',
                              fontWeight: 600,
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '0.25rem',
                            }}
                          >
                            {badgeStyle.icon}
                            <span>{recLabel}</span>
                          </span>
                        </td>

                        {/* Action CTA */}
                        <td style={{ padding: '0.75rem', textAlign: 'right' }}>
                          {supported ? (
                            <button
                              type="button"
                              onClick={() => navigate(targetAssessmentPath(item.skill))}
                              className="btn btn-outline text-xs"
                              style={{ padding: '0.25rem 0.65rem' }}
                            >
                              {isAssessed ? 'Retake' : 'Take Quiz'}
                            </button>
                          ) : (
                            <span className="text-muted text-xs" style={{ fontStyle: 'italic' }}>
                              Self-Study
                            </span>
                          )}
                        </td>
                      </tr>

                      {/* Optional Expandable Quote Row (Tucked away, no screen takeover!) */}
                      {isQuoteExpanded && item.evidence && (
                        <tr style={{ backgroundColor: '#f8fafc', borderBottom: '1px solid var(--border-color)' }}>
                          <td colSpan={6} style={{ padding: '0.5rem 1rem 0.75rem 1.5rem' }}>
                            <div className="text-xs text-muted" style={{ display: 'flex', alignItems: 'flex-start', gap: '0.5rem' }}>
                              <Quote size={13} style={{ color: 'var(--primary-600)', flexShrink: 0, marginTop: '0.15rem' }} />
                              <div>
                                <span className="font-semibold text-slate-600">CV Evidence Quote: </span>
                                <span className="italic">"{item.evidence}"</span>
                              </div>
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* 5. BOTTOM NAVIGATION */}
      <div className="flex justify-between items-center flex-wrap gap-4 pt-2">
        <button
          onClick={() => navigate(activeAnalysisId ? `/dashboard?analysis_id=${activeAnalysisId}` : '/dashboard')}
          className="btn btn-outline flex items-center gap-2"
        >
          <ArrowLeft size={16} />
          <span>Diagnostic Dashboard</span>
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
