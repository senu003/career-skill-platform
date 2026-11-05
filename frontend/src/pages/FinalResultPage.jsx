import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  Sparkles,
  ArrowLeft,
  RefreshCw,
  RotateCcw,
  CheckCircle2,
  AlertCircle,
  AlertTriangle,
  Target,
  Cpu,
  Lightbulb,
  FileText,
  Copy,
  Check,
  ChevronDown,
  ChevronUp,
  BookOpen,
  Award,
  TrendingUp,
  Zap,
  HelpCircle,
  Layers,
  ArrowRight,
  ShieldCheck,
  Flame,
  CheckCircle,
  Brain,
} from 'lucide-react';
import { fetchWithAuth } from '../api';
import { useAssessment } from '../context/AssessmentContext';
import { isSupportedSkill } from '../utils/supportedSkills';
import SkillMatchTable from '../components/SkillMatchTable';
import {
  formatLevel,
  translateRequiredLevel,
  translateCvLevel,
  formatScore,
  formatConfidence,
} from '../utils/formatters';

export default function FinalResultPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { analysisResult, setAnalysisResult, clearAnalysis, refreshAnalysis, isRefreshing } = useAssessment();

  const urlAnalysisId = searchParams.get('analysis_id');
  const activeAnalysisId = urlAnalysisId || analysisResult?.analysis_id;

  // Backend Data States
  const [aggregationData, setAggregationData] = useState(null);
  const [loadingAgg, setLoadingAgg] = useState(false);
  const [refreshError, setRefreshError] = useState(null);

  // Weakness / Question Diagnostics State (from /assessment/revision/weaknesses)
  const [weaknessData, setWeaknessData] = useState(null);
  const [loadingWeakness, setLoadingWeakness] = useState(false);

  // Model 1 Skill Filter State
  const [model1Filter, setModel1Filter] = useState('All');

  // Supported skills list
  const [supportedSkillsList, setSupportedSkillsList] = useState([]);

  // Copyable bullet state
  const [expandedCvSuggest, setExpandedCvSuggest] = useState({});
  const [copiedKey, setCopiedKey] = useState(null);

  // 1. Fetch Supported Skills
  useEffect(() => {
    let isMounted = true;
    const fetchSupportedSkills = async () => {
      try {
        const res = await fetchWithAuth('/assessment/supported-skills');
        if (isMounted && res && Array.isArray(res.supported_skills)) {
          setSupportedSkillsList(res.supported_skills);
        }
      } catch (err) {
        console.warn('Could not fetch supported skills list:', err);
      }
    };
    fetchSupportedSkills();
    return () => { isMounted = false; };
  }, []);

  // 2. Load Session Detail if URL analysis_id is provided
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
    }
    return () => { isCancelled = true; };
  }, [urlAnalysisId, analysisResult?.analysis_id, setAnalysisResult]);

  // 3. Extract Skills List
  const skillsList = useMemo(() => analysisResult?.skills || [
    ...(analysisResult?.matched_skills || []),
    ...(analysisResult?.missing_skills || []),
  ] || [], [analysisResult]);

  // 4. Fetch Question-Level Weakness Diagnostics
  const fetchWeaknessData = useCallback(async () => {
    setLoadingWeakness(true);
    try {
      const res = await fetchWithAuth('/assessment/revision/weaknesses');
      if (res) {
        setWeaknessData(res);
      }
    } catch (err) {
      console.warn('Could not fetch quiz weakness diagnostics:', err);
    } finally {
      setLoadingWeakness(false);
    }
  }, []);

  useEffect(() => {
    fetchWeaknessData();
  }, [fetchWeaknessData]);

  // 5. Fetch Backend Aggregation Metrics (Model 2 + Model 1 counts)
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
      console.error('Failed to fetch backend aggregation metrics:', err);
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
    await Promise.all([fetchAggregation(), fetchWeaknessData()]);
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

  const toggleCvSuggest = (key) => {
    setExpandedCvSuggest(prev => ({ ...prev, [key]: !prev[key] }));
  };

  const isSkillAvailable = (skillName) => {
    return isSupportedSkill(skillName, supportedSkillsList);
  };

  const targetAssessmentPath = (skillName) => {
    const encoded = encodeURIComponent(skillName);
    return activeAnalysisId
      ? `/assessment/${encoded}?analysis_id=${encodeURIComponent(activeAnalysisId)}`
      : `/assessment/${encoded}`;
  };

  // Model 1 Skill Evaluator classification helper
  const getModel1Status = (s) => {
    if (s.skill_recommendation) {
      return {
        label: s.skill_recommendation,
        confidence: s.recommendation_confidence || 0.88,
      };
    }
    const isAssessed = s.assessed_level !== null && s.assessed_level !== undefined;
    if (!isAssessed) {
      return {
        label: 'Pending Quiz',
        confidence: null,
      };
    }
    const score = s.total_score !== null && s.total_score !== undefined ? s.total_score : 0.5;
    const normalizedScore = score > 1 ? score / 100 : score;
    const gap = s.level_gap || 0;

    if (normalizedScore < 0.40) {
      return { label: 'Re-learn Basics', confidence: 0.90 };
    } else if (gap > 0 || normalizedScore < 0.65) {
      return { label: 'Upgrade Needed', confidence: 0.85 };
    } else {
      return { label: 'Mastered', confidence: 0.88 };
    }
  };

  // Categorize skills based on Model 1
  const masteredSkills = useMemo(() => skillsList.filter(s => getModel1Status(s).label === 'Mastered'), [skillsList]);
  const upgradeSkills = useMemo(() => skillsList.filter(s => getModel1Status(s).label === 'Upgrade Needed'), [skillsList]);
  const speedSkills = useMemo(() => skillsList.filter(s => getModel1Status(s).label === 'Speed Practice'), [skillsList]);
  const relearnSkills = useMemo(() => skillsList.filter(s => getModel1Status(s).label === 'Re-learn Basics'), [skillsList]);
  const unassessedSkills = useMemo(() => skillsList.filter(s => s.assessed_level === null || s.assessed_level === undefined), [skillsList]);

  // Verified Strengths vs Blockers for synthesis
  const verifiedStrengths = useMemo(() => skillsList.filter((s) => {
    const isAssessed = s.assessed_level !== null && s.assessed_level !== undefined;
    if (!isAssessed) return false;
    return !s.is_weakness && (s.level_gap === null || s.level_gap <= 0) && (s.total_score === null || s.total_score >= 0.50);
  }), [skillsList]);

  const interviewBlockers = useMemo(() => skillsList.filter((s) => {
    const isAssessed = s.assessed_level !== null && s.assessed_level !== undefined;
    if (isAssessed) {
      return s.is_weakness || (s.level_gap !== null && s.level_gap > 0) || (s.total_score !== null && s.total_score < 0.50);
    }
    return !s.matched || s.cv_match_status === 'Missing';
  }), [skillsList]);

  const missingCvSkills = useMemo(() => skillsList.filter((s) => !s.matched || s.cv_match_status === 'Missing'), [skillsList]);
  const skillsWithCvFeedback = useMemo(() => skillsList.filter((s) => s.actionable_feedback?.suggested_wording), [skillsList]);

  // Filtered skills for Model 1 grid
  const filteredModel1Skills = useMemo(() => {
    if (model1Filter === 'All') return skillsList;
    if (model1Filter === 'Mastered') return masteredSkills;
    if (model1Filter === 'Upgrade') return upgradeSkills;
    if (model1Filter === 'Speed') return speedSkills;
    if (model1Filter === 'Relearn') return relearnSkills;
    if (model1Filter === 'Unassessed') return unassessedSkills;
    return skillsList;
  }, [skillsList, model1Filter, masteredSkills, upgradeSkills, speedSkills, relearnSkills, unassessedSkills]);

  // Model 2 Final Verdict & Reasons
  const finalVerdict = analysisResult?.readiness_verdict || analysisResult?.final_verdict || aggregationData?.readiness_verdict || aggregationData?.final_verdict || 'Short-Term Prep';
  const assessedSkillsCount = useMemo(() => skillsList.filter((s) => s.assessed_level !== null && s.assessed_level !== undefined).length, [skillsList]);
  const isPreliminary = Boolean(analysisResult?.is_preliminary ?? aggregationData?.is_preliminary ?? (assessedSkillsCount === 0));

  const model2ConfidenceDisplay = formatConfidence(aggregationData?.recommendation_confidence || analysisResult?.recommendation_confidence || 0.86);

  const verificationStatusText = aggregationData?.verification_status || (isPreliminary
    ? 'Unverified (Preliminary CV Evidence Only)'
    : assessedSkillsCount < skillsList.length
      ? `Partially Verified (${assessedSkillsCount}/${skillsList.length} Quizzes Completed)`
      : 'Fully Assessment Verified');

  // Model 2 Explainable Reasons
  const readinessReasons = useMemo(() => {
    if (aggregationData?.readiness_reasons && Array.isArray(aggregationData.readiness_reasons) && aggregationData.readiness_reasons.length > 0) {
      return aggregationData.readiness_reasons;
    }
    if (analysisResult?.readiness_reasons && Array.isArray(analysisResult.readiness_reasons) && analysisResult.readiness_reasons.length > 0) {
      return analysisResult.readiness_reasons;
    }
    // Dynamic synthesized fallback reasons
    const totalReq = skillsList.filter(s => (s.importance || 'required').toLowerCase() !== 'preferred').length || skillsList.length;
    const missingCount = interviewBlockers.length;
    const foundCount = Math.max(0, totalReq - missingCount);
    return [
      `Found qualification evidence for ${foundCount} of ${totalReq} core requirements in your CV profile.`,
      isPreliminary
        ? 'Technical proficiency has not yet been verified via assessments (0 completed attempts).'
        : `Identified ${missingCount} priority skill area${missingCount !== 1 ? 's' : ''} requiring practice before technical rounds.`,
      isPreliminary
        ? 'Complete recommended 5-minute technical quizzes below to transform keyword claims into verified strengths.'
        : 'Targeted preparation on your identified question-level misconceptions will elevate readiness for technical interviews.',
    ];
  }, [aggregationData, analysisResult, skillsList, interviewBlockers, isPreliminary]);

  const overallMatchScore = analysisResult?.score_data?.score !== undefined
    ? `${Math.round(analysisResult.score_data.score)}%`
    : (aggregationData?.overall_score !== null && aggregationData?.overall_score !== undefined
      ? `${Math.round(aggregationData.overall_score * 100)}%`
      : '60%');

  // Filter weak topics matching this job's skills
  const jobSkillNames = useMemo(() => new Set(skillsList.map(s => s.skill.toLowerCase().trim())), [skillsList]);
  const jobRelevantWeakTopics = useMemo(() => {
    if (!weaknessData?.weak_topics || !Array.isArray(weaknessData.weak_topics)) return [];
    const directMatches = weaknessData.weak_topics.filter(wt => jobSkillNames.has((wt.skill || '').toLowerCase().trim()));
    return directMatches.length > 0 ? directMatches : weaknessData.weak_topics;
  }, [weaknessData, jobSkillNames]);

  // Group weak topics by skill for clean, actionable display (simply state which skill & subtopics to learn)
  const weakTopicsBySkill = useMemo(() => {
    const map = new Map();
    jobRelevantWeakTopics.forEach((item) => {
      const skillName = item.skill || 'Other';
      if (!map.has(skillName)) {
        map.set(skillName, {
          skill: skillName,
          suggested_level: item.suggested_level,
          subtopics: [],
        });
      }
      const group = map.get(skillName);
      const subtopic = (item.topic || 'General Concepts').trim();
      if (!group.subtopics.includes(subtopic)) {
        group.subtopics.push(subtopic);
      }
    });
    return Array.from(map.values());
  }, [jobRelevantWeakTopics]);

  const displayJobTitle = analysisResult?.job_title || 'Your target job';
  const effectiveCompany = analysisResult?.company || '';
  const displayCompany = effectiveCompany ? ` at ${effectiveCompany}` : '';
  const displayCvName = analysisResult?.cv_filename || analysisResult?.file_name || 'Uploaded Resume';

  // Badge styling for Model 1 recommendations
  const getModel1BadgeStyle = (recLabel) => {
    switch (recLabel) {
      case 'Mastered':
        return { backgroundColor: '#ecfdf5', color: '#059669', border: '1px solid #a7f3d0' };
      case 'Upgrade Needed':
        return { backgroundColor: '#fffbeb', color: '#b45309', border: '1px solid #fde68a' };
      case 'Speed Practice':
        return { backgroundColor: '#eff6ff', color: '#1d4ed8', border: '1px solid #bfdbfe' };
      case 'Re-learn Basics':
        return { backgroundColor: '#fef2f2', color: '#dc2626', border: '1px solid #fecaca' };
      default:
        return { backgroundColor: '#f8fafc', color: '#64748b', border: '1px solid #cbd5e1' };
    }
  };

  // Verdict theme color
  const getVerdictTheme = (v) => {
    const clean = String(v || '').toLowerCase();
    if (clean.includes('ready')) {
      return { borderTop: '4px solid #16a34a', bg: '#f0fdf4', badgeBg: '#dcfce7', badgeColor: '#15803d', badgeBorder: '#bbf7d0' };
    }
    if (clean.includes('major')) {
      return { borderTop: '4px solid #dc2626', bg: '#fef2f2', badgeBg: '#fee2e2', badgeColor: '#b91c1c', badgeBorder: '#fecaca' };
    }
    return { borderTop: '4px solid #ea580c', bg: '#fffbeb', badgeBg: '#fef3c7', badgeColor: '#92400e', badgeBorder: '#fde68a' };
  };

  const verdictTheme = getVerdictTheme(finalVerdict);

  // Loading Guard
  if (loadingAgg && !analysisResult) {
    return (
      <div className="fade-in text-center mt-6" style={{ maxWidth: '640px', margin: '3rem auto' }}>
        <div className="card" style={{ padding: '3.5rem 2rem' }}>
          <div className="spinner spinner-dark mb-4" style={{ width: 40, height: 40, borderWidth: 3, margin: '0 auto 1.5rem' }}></div>
          <h2 className="card-title text-xl mb-2">Synthesizing Candidate Evaluation</h2>
          <p className="text-muted text-sm">Aggregating CV evidence, quiz answer telemetry, and ML readiness models...</p>
        </div>
      </div>
    );
  }

  // Empty Analysis Guard
  if (!analysisResult || skillsList.length === 0) {
    return (
      <div className="fade-in text-center mt-6" style={{ maxWidth: '640px', margin: '2rem auto' }}>
        <div className="card" style={{ padding: '3rem 2rem' }}>
          <div className="badge badge-purple mb-3">Candidate Evaluation</div>
          <h2 className="card-title text-xl mb-2">No Active Job Analysis Found</h2>
          <p className="text-muted text-sm mb-6" style={{ lineHeight: 1.5 }}>
            To generate a comprehensive candidate evaluation and ML model recommendations, upload your CV and a job description on the dashboard.
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

  return (
    <div
      className="fade-in"
      style={{
        paddingBottom: '3.5rem',
        width: '100%',
        boxSizing: 'border-box',
      }}
    >
      {/* =========================================================================
          1. TOP HERO: Consistent with Dashboard & Interview Prep Hub
         ========================================================================= */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          gap: '1.5rem',
          flexWrap: 'wrap',
          marginBottom: '2rem',
        }}
      >
        {/* Left Column: Icon + Badges + Title + Subtitle + Action Buttons */}
        <div style={{ display: 'flex', gap: '1rem', alignItems: 'flex-start', flex: '1 1 360px', minWidth: '300px' }}>
          <div className="prep-header-icon" style={{ marginTop: '0.2rem' }}>
            <Sparkles size={28} />
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.35rem', flexWrap: 'wrap' }}>
              <span className="badge badge-purple" style={{ fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                Full AI Report & Candidate Dossier
              </span>
              <span className="text-xs text-muted">
                Session ID #{activeAnalysisId || 'Active'}
              </span>
            </div>
            <h1 className="page-title" style={{ fontSize: '1.75rem', fontWeight: 800, margin: '0 0 0.35rem 0', color: 'var(--text-main)', lineHeight: 1.25 }}>
              {displayJobTitle}{displayCompany}
            </h1>
            <p className="page-subtitle" style={{ margin: '0 0 1rem 0', fontSize: '0.9rem', color: 'var(--text-muted)' }}>
              Matched against: <strong style={{ color: 'var(--text-main)' }}>{displayCvName}</strong>
            </p>

            <div className="flex items-center gap-2 flex-wrap">
              <button
                type="button"
                onClick={() => navigate(activeAnalysisId ? `/dashboard?analysis_id=${activeAnalysisId}` : '/dashboard')}
                className="btn btn-outline flex items-center gap-1.5"
                style={{ padding: '0.55rem 1rem', fontSize: '0.85rem' }}
              >
                <ArrowLeft size={14} />
                <span>Back to Dashboard</span>
              </button>
              <button
                type="button"
                onClick={() => {
                  clearAnalysis();
                  navigate('/dashboard', { replace: true });
                }}
                className="btn btn-outline flex items-center gap-1.5"
                id="btn-analyze-another"
                style={{ padding: '0.55rem 1rem', fontSize: '0.85rem' }}
              >
                <RefreshCw size={14} />
                <span>Analyze Another Job</span>
              </button>
              <button
                type="button"
                onClick={handleManualRefresh}
                disabled={loadingAgg || isRefreshing}
                className="btn btn-primary flex items-center gap-1.5"
                style={{ padding: '0.55rem 1.15rem', fontSize: '0.85rem', fontWeight: 600 }}
                title="Recalculate AI evaluation dossier"
              >
                <Sparkles size={15} className={loadingAgg || isRefreshing ? 'animate-spin' : ''} />
                <span>{loadingAgg || isRefreshing ? 'Recalculating...' : 'Refresh Report'}</span>
              </button>
            </div>
          </div>
        </div>

        {/* Right Column: Glance Card (Consistent with Interview Prep Hub & Dashboard) */}
        <div
          className="card"
          style={{
            padding: '1rem 1.5rem',
            marginBottom: 0,
            minWidth: '340px',
            flex: '0 1 440px',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem', gap: '0.5rem', flexWrap: 'wrap' }}>
            <span className="text-xs uppercase tracking-wider font-semibold text-muted">
              Evaluation at a glance
            </span>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
              <span
                className="badge badge-purple"
                style={{ fontSize: '0.72rem', fontWeight: 700, padding: '0.15rem 0.5rem' }}
                title="Model 2 final readiness verdict"
              >
                {finalVerdict}
              </span>
              {isPreliminary && (
                <span
                  className="badge"
                  style={{
                    fontSize: '0.68rem',
                    padding: '0.15rem 0.5rem',
                    backgroundColor: '#fef3c7',
                    color: '#92400e',
                    border: '1px solid #fde68a',
                    fontWeight: 700,
                  }}
                  title="Technical proficiency unverified"
                >
                  Preliminary
                </span>
              )}
            </div>
          </div>

          {/* 4 Stats Columns */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '0.75rem', textAlign: 'center' }}>
            <div>
              <div style={{ fontSize: '1.35rem', fontWeight: 700, color: 'var(--text-main)', letterSpacing: '-0.01em' }}>
                {overallMatchScore}
              </div>
              <div className="text-xs text-muted">Resume Match</div>
            </div>

            <div>
              <div style={{ fontSize: '1.35rem', fontWeight: 700, color: 'var(--success-color)' }}>
                {verifiedStrengths.length}
              </div>
              <div className="text-xs text-muted">Verified Proof</div>
            </div>

            <div>
              <div style={{ fontSize: '1.35rem', fontWeight: 700, color: 'var(--warning-color)' }}>
                {interviewBlockers.length}
              </div>
              <div className="text-xs text-muted">Blocker Gaps</div>
            </div>

            <div>
              <div style={{ fontSize: '1.35rem', fontWeight: 700, color: 'var(--primary-600)' }}>
                {model2ConfidenceDisplay}
              </div>
              <div className="text-xs text-muted">Model 2 Conf.</div>
            </div>
          </div>

          {/* Verification Status Footer */}
          <div
            style={{
              marginTop: '0.75rem',
              paddingTop: '0.5rem',
              borderTop: '1px solid var(--border-color)',
              fontSize: '0.72rem',
              color: 'var(--text-muted)',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              gap: '0.5rem',
              flexWrap: 'wrap',
            }}
          >
            <span>{verificationStatusText}</span>
            <span>{skillsList.length} skills in profile</span>
          </div>
        </div>
      </div>

      {refreshError && (
        <div className="alert-error flex items-center gap-2 mb-4 p-3 rounded text-xs">
          <AlertCircle size={15} />
          <span>{refreshError}</span>
        </div>
      )}

      {/* =========================================================================
          2. ML MODEL 2: CANDIDATE READINESS SYNTHESIS & HIRING VERDICT
         ========================================================================= */}
      <div
        className="card mb-6"
        style={{
          padding: '1.5rem 1.75rem',
          backgroundColor: '#ffffff',
          border: '1px solid var(--border-color)',
          ...verdictTheme,
        }}
      >
        <div className="flex justify-between items-start gap-4 flex-wrap mb-3">
          <div>
            <div className="flex items-center gap-2 mb-1 flex-wrap">
              <span className="text-xs uppercase tracking-wider font-bold text-muted flex items-center gap-1.5">
                <Brain size={14} style={{ color: 'var(--primary-600)' }} />
                <span>ML Model 2 • Authoritative Candidate Readiness Verdict</span>
              </span>
              <span
                className="badge"
                style={{
                  backgroundColor: verdictTheme.badgeBg,
                  color: verdictTheme.badgeColor,
                  border: `1px solid ${verdictTheme.badgeBorder}`,
                  fontWeight: 700,
                  fontSize: '0.75rem',
                }}
              >
                {finalVerdict}
              </span>
              {isPreliminary && (
                <span
                  className="badge"
                  style={{
                    backgroundColor: '#fef3c7',
                    color: '#92400e',
                    border: '1px solid #fde68a',
                    fontWeight: 700,
                    fontSize: '0.7rem',
                  }}
                >
                  Preliminary Evaluation (0 Quizzes Completed)
                </span>
              )}
            </div>

            <h2 className="card-title text-lg font-bold text-main mb-1" style={{ margin: 0, letterSpacing: '-0.01em' }}>
              {finalVerdict === 'Interview Ready'
                ? 'High Competency Match: Ready for Technical Screening'
                : finalVerdict === 'Short-Term Prep'
                  ? 'Viable Candidate Alignment: Targeted Review Recommended'
                  : 'Foundational Skill Gap: Structured Upskilling Required'}
            </h2>
          </div>

          <div className="text-right">
            <div className="text-xs text-muted">Model 2 Decision Confidence</div>
            <div className="font-bold text-lg" style={{ color: 'var(--primary-700)' }}>
              {model2ConfidenceDisplay}
            </div>
          </div>
        </div>

        {/* Model 2 Explainable Rationale */}
        <div
          style={{
            backgroundColor: '#f8fafc',
            border: '1px solid #e2e8f0',
            borderRadius: 'var(--radius-sm)',
            padding: '1rem 1.25rem',
            marginTop: '0.75rem',
          }}
        >
          <div className="text-xs font-semibold text-slate-700 uppercase tracking-wider mb-2 flex items-center gap-1.5">
            <Flame size={14} style={{ color: '#ea580c' }} />
            <span>Model 2 Decision Drivers & Assessment Signals:</span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.45rem' }}>
            {readinessReasons.map((reason, idx) => (
              <div key={idx} className="flex items-start gap-2 text-xs text-slate-700" style={{ lineHeight: 1.5 }}>
                <span style={{ color: 'var(--primary-600)', fontWeight: 800, marginTop: '-1px' }}>•</span>
                <span>{reason}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* =========================================================================
          3. SECTION 1: SPECIFIC AREAS TO IMPROVE BY SKILL
             (Identified from user's technical assessment answers)
         ========================================================================= */}
      <div className="card mb-6" style={{ padding: '1.5rem 1.75rem', backgroundColor: '#ffffff', border: '1px solid var(--border-color)' }}>
        <div className="flex justify-between items-start gap-3 flex-wrap mb-4">
          <div>
            <div className="flex items-center gap-2 mb-0.5">
              <Target size={18} style={{ color: 'var(--primary-700)' }} />
              <h2 className="card-title text-lg font-bold" style={{ margin: 0 }}>
                Specific Areas to Improve
              </h2>
            </div>
            <p className="text-xs text-muted" style={{ margin: 0 }}>
              Specific subtopics identified from your assessments that need focused learning and practice.
            </p>
          </div>

          {weaknessData?.total_assessments_completed > 0 && (
            <div className="flex items-center gap-2">
              <span className="badge" style={{ backgroundColor: '#f1f5f9', color: '#334155', border: '1px solid #cbd5e1', fontSize: '0.72rem' }}>
                {weaknessData.total_questions_analyzed} Questions Evaluated
              </span>
              <span className="badge" style={{ backgroundColor: '#eff6ff', color: '#1e40af', border: '1px solid #bfdbfe', fontSize: '0.72rem', fontWeight: 700 }}>
                {Math.round((weaknessData.overall_accuracy || 0) * 100)}% Quiz Accuracy
              </span>
            </div>
          )}
        </div>

        {/* State A: User has real question-level weaknesses from completed assessments */}
        {weakTopicsBySkill.length > 0 ? (
          <div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '1rem' }}>
              {weakTopicsBySkill.map((group, idx) => {
                const supported = isSkillAvailable(group.skill);
                const skillMeta = skillsList.find((s) => s.skill.toLowerCase() === group.skill.toLowerCase());
                const targetLevel = skillMeta?.required_level || skillMeta?.level || group.suggested_level;

                return (
                  <div
                    key={idx}
                    style={{
                      padding: '1.25rem 1.35rem',
                      backgroundColor: '#ffffff',
                      border: '1px solid #e2e8f0',
                      borderRadius: 'var(--radius-sm)',
                      display: 'flex',
                      flexDirection: 'column',
                      justifyContent: 'space-between',
                      boxShadow: '0 1px 3px rgba(0,0,0,0.03)',
                    }}
                  >
                    <div>
                      {/* Skill Name & Subtopic Count */}
                      <div className="flex justify-between items-center gap-2 mb-3">
                        <div className="flex items-center gap-2">
                          <span style={{ fontSize: '0.92rem', fontWeight: 600, color: '#0f172a' }}>
                            {group.skill}
                          </span>
                          {targetLevel && (
                            <span className="text-xs text-muted">
                              Target: {formatLevel(targetLevel)}
                            </span>
                          )}
                        </div>
                        <span
                          className="badge"
                          style={{
                            backgroundColor: '#fff7ed',
                            color: '#c2410c',
                            border: '1px solid #ffedd5',
                            fontSize: '0.72rem',
                            fontWeight: 600,
                            padding: '0.2rem 0.55rem',
                          }}
                        >
                          {group.subtopics.length} {group.subtopics.length === 1 ? 'subtopic to learn' : 'subtopics to learn'}
                        </span>
                      </div>

                      {/* Subtopics List */}
                      <div className="mb-2">
                        <span style={{ fontSize: '0.75rem', fontWeight: 500, color: '#64748b', display: 'block', marginBottom: '0.45rem' }}>
                          Subtopics to learn:
                        </span>
                        <div className="flex flex-wrap gap-2">
                          {group.subtopics.map((subtopic, sIdx) => (
                            <span
                              key={sIdx}
                              className="badge"
                              style={{
                                backgroundColor: '#f8fafc',
                                border: '1px solid #cbd5e1',
                                color: '#1e293b',
                                fontSize: '0.78rem',
                                padding: '0.35rem 0.65rem',
                                fontWeight: 500,
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: '0.4rem',
                                borderRadius: '6px',
                              }}
                            >
                              <span
                                style={{
                                  width: 6,
                                  height: 6,
                                  borderRadius: '50%',
                                  backgroundColor: '#ea580c',
                                  display: 'inline-block',
                                }}
                              />
                              {subtopic}
                            </span>
                          ))}
                        </div>
                      </div>
                    </div>

                    {/* Actions */}
                    <div
                      className="mt-4 pt-3 flex items-center justify-between gap-2"
                      style={{ borderTop: '1px solid #f1f5f9' }}
                    >
                      <div>
                        {skillMeta?.attempt_id && (
                          <button
                            type="button"
                            onClick={() => navigate(`/assessment/review/${skillMeta.attempt_id}`)}
                            className="btn btn-outline text-xs flex items-center gap-1"
                            style={{ padding: '0.25rem 0.65rem', borderColor: '#cbd5e1', color: '#475569' }}
                          >
                            <FileText size={12} />
                            <span>Review Answers</span>
                          </button>
                        )}
                      </div>

                      {supported && (
                        <button
                          type="button"
                          onClick={() => navigate(targetAssessmentPath(group.skill))}
                          className="btn btn-outline text-xs flex items-center gap-1"
                          style={{ padding: '0.25rem 0.65rem', borderColor: '#cbd5e1', color: '#1e293b', fontWeight: 600 }}
                        >
                          <RotateCcw size={12} />
                          <span>Retake {group.skill} Quiz</span>
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Confirmed Strong Topics Pill Strip */}
            {weaknessData?.strong_topics && weaknessData.strong_topics.length > 0 && (
              <div className="mt-4 pt-3 flex items-center gap-2 flex-wrap text-xs text-muted" style={{ borderTop: '1px solid var(--border-color)' }}>
                <span className="font-bold text-slate-700 flex items-center gap-1">
                  <CheckCircle size={14} className="text-emerald-600" />
                  <span>Strong Topics Confirmed:</span>
                </span>
                {weaknessData.strong_topics.slice(0, 6).map((st, sIdx) => (
                  <span
                    key={sIdx}
                    className="badge"
                    style={{ backgroundColor: '#ecfdf5', color: '#047857', border: '1px solid #a7f3d0', fontSize: '0.72rem', padding: '0.2rem 0.55rem' }}
                  >
                    ✓ {st.skill}: {st.topic}
                  </span>
                ))}
              </div>
            )}
          </div>
        ) : weaknessData?.total_assessments_completed > 0 ? (
          /* State B: User has completed assessments with NO weak topics identified */
          <div
            style={{
              backgroundColor: '#f0fdf4',
              border: '1px solid #bbf7d0',
              borderRadius: 'var(--radius-sm)',
              padding: '1.25rem 1.5rem',
            }}
          >
            <div className="flex items-center gap-2 mb-1">
              <CheckCircle2 size={18} className="text-emerald-600" />
              <span className="font-bold text-sm text-emerald-900">
                No Critical Knowledge Gaps Identified
              </span>
            </div>
            <p className="text-xs text-emerald-800" style={{ margin: 0 }}>
              Great job! You achieved solid accuracy across all tested subtopics in your completed technical assessments.
            </p>
            {weaknessData?.strong_topics && weaknessData.strong_topics.length > 0 && (
              <div className="mt-3 flex items-center gap-2 flex-wrap text-xs">
                <span className="font-bold text-emerald-900">Demonstrated Strengths:</span>
                {weaknessData.strong_topics.map((st, sIdx) => (
                  <span
                    key={sIdx}
                    className="badge"
                    style={{ backgroundColor: '#ffffff', color: '#047857', border: '1px solid #a7f3d0', fontSize: '0.72rem' }}
                  >
                    ✓ {st.skill}: {st.topic}
                  </span>
                ))}
              </div>
            )}
          </div>
        ) : (
          /* State B: User has 0 completed assessments (Preliminary state) */
          <div
            style={{
              backgroundColor: '#f8fafc',
              border: '1px solid #e2e8f0',
              borderRadius: 'var(--radius-sm)',
              padding: '1.5rem',
            }}
          >
            <div className="flex items-start gap-3 mb-4">
              <div
                style={{
                  width: 38,
                  height: 38,
                  borderRadius: '8px',
                  backgroundColor: '#eff6ff',
                  color: 'var(--primary-600)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0,
                }}
              >
                <HelpCircle size={22} />
              </div>
              <div>
                <h3 className="font-bold text-sm text-slate-900 mb-0.5">
                  Technical Proficiency Unverified (0 Quizzes Completed)
                </h3>
                <p className="text-xs text-muted" style={{ margin: 0, lineHeight: 1.5 }}>
                  You have not completed technical assessment quizzes for this job's competencies yet. Without direct quiz answers, Model 1 and error telemetry cannot pinpoint question-level misconceptions. Take the priority quizzes below to unlock empirical error diagnosis.
                </p>
              </div>
            </div>

            <div className="text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">
              Priority Skills to Verify for this Job:
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '0.75rem' }}>
              {skillsList.slice(0, 4).map((item, idx) => {
                const supported = isSkillAvailable(item.skill);
                return (
                  <div
                    key={idx}
                    style={{
                      padding: '0.85rem 1rem',
                      backgroundColor: '#ffffff',
                      border: '1px solid var(--border-color)',
                      borderRadius: 'var(--radius-sm)',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                    }}
                  >
                    <div>
                      <div className="font-bold text-xs text-slate-900">{item.skill}</div>
                      <div className="text-xs text-muted" style={{ fontSize: '0.7rem' }}>
                        Job Standard: {formatLevel(item.required_level || item.level)}
                      </div>
                    </div>

                    {supported ? (
                      <button
                        type="button"
                        onClick={() => navigate(targetAssessmentPath(item.skill))}
                        className="btn btn-primary text-xs flex items-center gap-1"
                        style={{ padding: '0.3rem 0.75rem', fontSize: '0.75rem', fontWeight: 600 }}
                      >
                        <span>Take 5-Min Quiz</span>
                        <ArrowRight size={12} />
                      </button>
                    ) : (
                      <span className="text-xs text-muted italic" style={{ fontSize: '0.7rem' }}>
                        CV Evidenced Only
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* =========================================================================
          4. SECTION 2: SKILL MATCH TABLE
             (Same consistent table component used across Dashboard and Analysis)
         ========================================================================= */}
      <SkillMatchTable
        skills={skillsList}
        supportedSkills={supportedSkillsList}
        analysisId={activeAnalysisId}
        title="Skill Match Analysis"
        subtitle="Detailed alignment of your verified proof and quiz results against job requirements."
        icon={<Layers size={18} style={{ color: 'var(--primary-700)' }} />}
        className="mb-6"
      />

      {/* =========================================================================
          5. SECTION 3: STRATEGIC ACTION PLAN
         ========================================================================= */}
      <div className="card mb-6" style={{ padding: '1.5rem 1.75rem', backgroundColor: '#ffffff', border: '1px solid var(--border-color)' }}>
        <div className="mb-4">
          <div className="flex items-center gap-2 mb-0.5">
            <Lightbulb size={18} style={{ color: 'var(--primary-700)' }} />
            <h2 className="card-title text-lg font-bold" style={{ margin: 0 }}>
              Strategic Action Plan
            </h2>
          </div>
          <p className="text-xs text-muted" style={{ margin: 0 }}>
            Key priorities for technical practice, resume refinement, and interview prep.
          </p>
        </div>

        {/* Vertical Stack of Action Boxes */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {/* Box 1: Technical Practice */}
          <div
            style={{
              padding: '1.25rem 1.4rem',
              backgroundColor: '#ffffff',
              border: '1px solid #e2e8f0',
              borderRadius: 'var(--radius-sm)',
              boxShadow: '0 1px 3px rgba(0,0,0,0.02)',
            }}
          >
            <div className="flex justify-between items-center gap-2 mb-3">
              <div className="flex items-center gap-2.5">
                <span
                  className="badge badge-purple"
                  style={{
                    fontSize: '0.72rem',
                    fontWeight: 600,
                    padding: '0.2rem 0.55rem',
                    borderRadius: '6px',
                  }}
                >
                  1. Technical Practice
                </span>
                <span style={{ fontWeight: 600, fontSize: '0.88rem', color: '#0f172a' }}>Skills to Focus on First</span>
              </div>
              {interviewBlockers.length > 0 && (
                <span
                  className="badge"
                  style={{
                    backgroundColor: '#fff7ed',
                    color: '#c2410c',
                    border: '1px solid #ffedd5',
                    fontSize: '0.72rem',
                    fontWeight: 600,
                    padding: '0.2rem 0.55rem',
                  }}
                >
                  {interviewBlockers.length} {interviewBlockers.length === 1 ? 'Skill to Prioritize' : 'Skills to Prioritize'}
                </span>
              )}
            </div>

            {interviewBlockers.length > 0 ? (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '0.75rem' }}>
                {interviewBlockers.slice(0, 3).map((item, idx) => {
                  const supported = isSkillAvailable(item.skill);
                  const hasAttempt = Boolean(item.attempt_id);
                  return (
                    <div
                      key={idx}
                      style={{
                        padding: '0.85rem 1.15rem',
                        backgroundColor: '#f8fafc',
                        border: '1px solid #e2e8f0',
                        borderRadius: '8px',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        gap: '0.75rem',
                      }}
                    >
                      <div>
                        <div style={{ fontWeight: 600, fontSize: '0.92rem', color: '#0f172a', marginBottom: '2px' }}>
                          {item.skill}
                        </div>
                        <div className="text-xs text-muted">
                          Target: <span style={{ fontWeight: 600, color: '#334155' }}>{formatLevel(item.required_level || item.level)}</span>
                        </div>
                      </div>

                      {supported ? (
                        <button
                          type="button"
                          onClick={() => navigate(targetAssessmentPath(item.skill))}
                          className="btn btn-outline text-xs flex items-center gap-1.5"
                          style={{
                            padding: '0.35rem 0.75rem',
                            backgroundColor: '#ffffff',
                            borderColor: '#cbd5e1',
                            fontWeight: 600,
                            height: 32,
                            borderRadius: '6px',
                          }}
                        >
                          <RotateCcw size={12} />
                          <span>{hasAttempt ? 'Retake Quiz' : 'Take Quiz'}</span>
                        </button>
                      ) : (
                        <span
                          className="badge"
                          style={{
                            backgroundColor: '#ffffff',
                            color: '#64748b',
                            border: '1px solid #cbd5e1',
                            fontSize: '0.72rem',
                            padding: '0.35rem 0.75rem',
                            height: 32,
                            display: 'inline-flex',
                            alignItems: 'center',
                            borderRadius: '6px',
                            fontWeight: 500,
                          }}
                        >
                          Self-study
                        </span>
                      )}
                    </div>
                  );
                })}
              </div>
            ) : (
              <div
                style={{
                  padding: '0.85rem 1.15rem',
                  backgroundColor: '#f0fdf4',
                  border: '1px solid #bbf7d0',
                  borderRadius: '8px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                  fontSize: '0.82rem',
                  color: '#166534',
                }}
              >
                <CheckCircle2 size={16} className="text-emerald-600" />
                <span className="font-semibold">
                  All required technical skills meet or exceed the target level for this role.
                </span>
              </div>
            )}
          </div>

          {/* Box 2: Resume Optimization */}
          <div
            style={{
              padding: '1.25rem 1.4rem',
              backgroundColor: '#ffffff',
              border: '1px solid #e2e8f0',
              borderRadius: 'var(--radius-sm)',
              boxShadow: '0 1px 3px rgba(0,0,0,0.02)',
            }}
          >
            <div className="flex justify-between items-center gap-2 mb-3">
              <div className="flex items-center gap-2.5">
                <span
                  className="badge"
                  style={{
                    backgroundColor: '#ecfdf5',
                    color: '#047857',
                    border: '1px solid #a7f3d0',
                    fontSize: '0.72rem',
                    fontWeight: 600,
                    padding: '0.2rem 0.55rem',
                    borderRadius: '6px',
                  }}
                >
                  2. Resume Refinement
                </span>
                <span style={{ fontWeight: 600, fontSize: '0.88rem', color: '#0f172a' }}>CV Improvement Suggestions</span>
              </div>
            </div>

            {skillsWithCvFeedback.length > 0 ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                {skillsWithCvFeedback.slice(0, 2).map((item, idx) => {
                  const fb = item.actionable_feedback;
                  const isCopied = copiedKey === item.skill;
                  return (
                    <div
                      key={idx}
                      style={{
                        padding: '0.85rem 1.15rem',
                        backgroundColor: '#f8fafc',
                        border: '1px solid #e2e8f0',
                        borderRadius: '8px',
                      }}
                    >
                      <div className="flex justify-between items-center mb-1.5">
                        <span style={{ fontWeight: 600, fontSize: '0.82rem', color: '#0f172a' }}>
                          {item.skill} — Suggested CV Bullet:
                        </span>
                        {fb.suggested_wording && (
                          <button
                            type="button"
                            onClick={() => handleCopyText(item.skill, fb.suggested_wording)}
                            className="btn btn-outline text-xs flex items-center gap-1"
                            style={{
                              padding: '0.2rem 0.55rem',
                              fontSize: '0.68rem',
                              backgroundColor: '#ffffff',
                              borderColor: '#cbd5e1',
                              borderRadius: '4px',
                            }}
                          >
                            {isCopied ? <Check size={12} className="text-emerald-600" /> : <Copy size={12} />}
                            <span>{isCopied ? 'Copied!' : 'Copy Bullet'}</span>
                          </button>
                        )}
                      </div>
                      {fb.suggested_wording && (
                        <div
                          style={{
                            padding: '0.6rem 0.85rem',
                            backgroundColor: '#ffffff',
                            border: '1px solid #e2e8f0',
                            borderRadius: '6px',
                            fontSize: '0.78rem',
                            color: '#334155',
                            fontStyle: 'italic',
                            lineHeight: 1.5,
                          }}
                        >
                          "{fb.suggested_wording}"
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            ) : missingCvSkills.length > 0 ? (
              <div
                style={{
                  padding: '0.85rem 1.15rem',
                  backgroundColor: '#f8fafc',
                  border: '1px solid #e2e8f0',
                  borderRadius: '8px',
                  fontSize: '0.82rem',
                  color: '#334155',
                  lineHeight: 1.6,
                }}
              >
                Your resume does not explicitly highlight:{' '}
                <span style={{ fontWeight: 600, color: '#0f172a' }}>
                  {missingCvSkills.slice(0, 4).map((s) => s.skill).join(', ')}
                </span>.
                {' '}Consider adding project details or practical exposure for these skills to improve keyword matching.
              </div>
            ) : (
              <div
                style={{
                  padding: '0.85rem 1.15rem',
                  backgroundColor: '#f0fdf4',
                  border: '1px solid #bbf7d0',
                  borderRadius: '8px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                  fontSize: '0.82rem',
                  color: '#166534',
                }}
              >
                <CheckCircle2 size={16} className="text-emerald-600" />
                <span className="font-semibold">
                  Your resume covers all required competencies highlighted in this job description.
                </span>
              </div>
            )}
          </div>

          {/* Box 3: Interview Positioning */}
          <div
            style={{
              padding: '1.25rem 1.4rem',
              backgroundColor: '#ffffff',
              border: '1px solid #e2e8f0',
              borderRadius: 'var(--radius-sm)',
              boxShadow: '0 1px 3px rgba(0,0,0,0.02)',
            }}
          >
            <div className="flex justify-between items-center gap-2 mb-3">
              <div className="flex items-center gap-2.5">
                <span
                  className="badge"
                  style={{
                    backgroundColor: '#eff6ff',
                    color: '#1d4ed8',
                    border: '1px solid #bfdbfe',
                    fontSize: '0.72rem',
                    fontWeight: 600,
                    padding: '0.2rem 0.55rem',
                    borderRadius: '6px',
                  }}
                >
                  3. Interview Positioning
                </span>
                <span style={{ fontWeight: 600, fontSize: '0.88rem', color: '#0f172a' }}>Talking Points for Live Rounds</span>
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '0.85rem' }}>
              <div
                style={{
                  padding: '0.85rem 1.15rem',
                  backgroundColor: '#f8fafc',
                  border: '1px solid #e2e8f0',
                  borderRadius: '8px',
                }}
              >
                <div style={{ fontWeight: 600, fontSize: '0.82rem', color: '#0f172a', marginBottom: '0.35rem' }}>
                  Anchor on Verified Strengths
                </div>
                <div style={{ fontSize: '0.78rem', color: '#334155', lineHeight: 1.55 }}>
                  {verifiedStrengths.length > 0
                    ? `Lead technical discussions with concrete examples demonstrating your verified proficiency in ${verifiedStrengths.map((s) => s.skill).slice(0, 3).join(', ')}.`
                    : 'Anchor technical conversations on your strongest relevant engineering projects and system architecture.'}
                </div>
              </div>

              <div
                style={{
                  padding: '0.85rem 1.15rem',
                  backgroundColor: '#f8fafc',
                  border: '1px solid #e2e8f0',
                  borderRadius: '8px',
                }}
              >
                <div style={{ fontWeight: 600, fontSize: '0.82rem', color: '#0f172a', marginBottom: '0.35rem' }}>
                  Addressing Growth Areas
                </div>
                <div style={{ fontSize: '0.78rem', color: '#334155', lineHeight: 1.55 }}>
                  {interviewBlockers.length > 0
                    ? `For ${interviewBlockers.slice(0, 2).map((s) => s.skill).join(' and ')}, acknowledge your current depth transparently and emphasize your hands-on practice and fast ramp-up ability.`
                    : 'Speak with confidence on your core competencies and emphasize team collaboration, scalability, and impact.'}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* =========================================================================
          6. FOOTER NAVIGATION
         ========================================================================= */}
      <div className="flex justify-between items-center flex-wrap gap-4 pt-3" style={{ borderTop: '1px solid var(--border-color)' }}>
        <button
          onClick={() => navigate(activeAnalysisId ? `/dashboard?analysis_id=${activeAnalysisId}` : '/dashboard')}
          className="btn btn-outline flex items-center gap-2"
        >
          <ArrowLeft size={16} />
          <span>Back to Dashboard</span>
        </button>

        <div className="flex items-center gap-2 flex-wrap">
          <button
            onClick={() => navigate('/results')}
            className="btn btn-outline flex items-center gap-2"
          >
            <BookOpen size={16} />
            <span>Open Interview Prep Hub</span>
          </button>

          <button
            onClick={() => {
              clearAnalysis();
              navigate('/dashboard', { replace: true });
            }}
            className="btn btn-primary flex items-center gap-2"
          >
            <RefreshCw size={16} />
            <span>Analyze Another Job</span>
          </button>
        </div>
      </div>
    </div>
  );
}
