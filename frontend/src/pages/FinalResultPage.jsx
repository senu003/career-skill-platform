import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { 
  CheckCircle2, 
  AlertCircle, 
  AlertTriangle, 
  TrendingUp, 
  Sparkles, 
  BookOpen, 
  ArrowLeft, 
  RefreshCw, 
  HelpCircle, 
  RotateCcw,
  Copy,
  Check,
  ChevronDown,
  ChevronUp,
  FileText,
  MessageSquare,
  Layers
} from 'lucide-react';
import { fetchWithAuth } from '../api';
import { useAssessment } from '../context/AssessmentContext';
import { isSupportedSkill } from '../utils/supportedSkills';

// Domain-specific technical study concept mappings for targeted preparation
const TECHNICAL_STUDY_CONCEPTS = {
  'javascript': {
    'advanced': ['Asynchronous Patterns (Promises, Async/Await, Microtasks)', 'Event Loop & Execution Context', 'Closures, Scope Chains & Lexical Environment', 'Prototypes, Classes, & Memory Management'],
    'intermediate': ['Array Methods (map, filter, reduce)', 'DOM Manipulation & Event Bubbling', 'Fetch API & JSON Handling', 'ES6+ Syntax & Destructuring'],
    'basic': ['Variables (let/const) & Data Types', 'Conditional Logic & Functions', 'Loops & Basic Arrays', 'Basic String & Number Methods'],
    'default': ['Asynchronous JavaScript & Event Loop', 'Core Language Mechanics & Scope', 'Modern ES6+ Syntax & Patterns']
  },
  'react': {
    'advanced': ['Component Lifecycle & Custom Hooks Design', 'Memoization & Rendering Performance (useMemo, useCallback)', 'State Architecture & Context Optimization', 'Concurrent Features & Code Splitting'],
    'intermediate': ['State & Props Management (useState, useEffect)', 'Controlled Forms & Form Validation', 'Component Composition & Reusability', 'Routing & API Integration'],
    'basic': ['JSX Syntax & Element Rendering', 'Functional Components', 'Basic Props & Event Handling', 'Simple State Updates'],
    'default': ['React Hooks & Performance Optimization', 'State Architecture & Component Patterns']
  },
  'typescript': {
    'advanced': ['Conditional & Mapped Types', 'Generics & Utility Types (Pick, Omit, Record)', 'Strict Null Checking & Type Narrowing', 'Type-Safe API Contracts & Decorators'],
    'intermediate': ['Interfaces vs Type Aliases', 'Union & Intersection Types', 'Typing React Components & Hooks', 'Enums & Type Assertions'],
    'basic': ['Primitive Types & Type Annotations', 'Basic Object & Array Typing', 'Function Parameter & Return Types'],
    'default': ['Generics & Advanced Type System', 'Type Narrowing & Interface Contracts']
  },
  'python': {
    'advanced': ['Metaclasses, Decorators, & Dunder Methods', 'Asyncio & Concurrency (Threads vs Processes)', 'Memory Profiling & Generator Pipelines', 'Packaging & Type Hinting (typing module)'],
    'intermediate': ['List/Dict Comprehensions & Generators', 'OOP: Inheritance & Polymorphism', 'Error Handling & Context Managers (with)', 'Virtual Environments & Dependencies'],
    'basic': ['Variables, Lists, Tuples & Dictionaries', 'Functions & Parameter Passing', 'Basic File I/O & String Operations'],
    'default': ['Pythonic Idioms & Data Structures', 'OOP, Generators, & Error Handling']
  },
  'postgresql': {
    'advanced': ['Query Plan Analysis (EXPLAIN ANALYZE)', 'Indexing Strategies (B-Tree, GIN, Partial Indexes)', 'Transactions & ACID Isolation Levels', 'Partitioning, Replication, & Connection Pooling'],
    'intermediate': ['Complex Joins (INNER, LEFT, FULL)', 'Aggregation & Window Functions', 'Foreign Keys, Constraints, & Cascades', 'Schema Migrations & Indexing Basics'],
    'basic': ['Basic CRUD Queries (SELECT, INSERT, UPDATE, DELETE)', 'WHERE Filters & ORDER BY', 'Basic Primary Keys & Tables'],
    'default': ['Indexing & Query Performance Tuning', 'Window Functions & Transaction Isolation']
  },
  'docker': {
    'default': ['Multi-Stage Dockerfiles for Production', 'Container Networking & Bridge Networks', 'Volume Persistence & Bind Mounts', 'Docker Compose Service Orchestration']
  },
  'aws': {
    'default': ['IAM Security Policies & Least Privilege Roles', 'S3 Bucket Configuration & CloudFront Distribution', 'EC2 / ECS Container Deployment', 'VPC Fundamentals & Security Groups']
  }
};

// Interview Question Forecast Generator based on skills & levels
const getInterviewQuestions = (skillsList, gapsList) => {
  const questions = [];

  // Question 1: Focused on confirmed gap or lowest scoring skill
  const primaryGap = gapsList[0] || skillsList.find(s => s.total_score !== null && s.total_score < 0.5) || skillsList[0];
  if (primaryGap) {
    const sName = primaryGap.skill.toLowerCase();
    if (sName.includes('javascript')) {
      questions.push({
        topic: 'JavaScript Mechanics (High Probability)',
        question: 'Can you explain the execution order between microtasks (Promises, queueMicrotask) and macrotasks (setTimeout, I/O) in the JavaScript event loop?',
        hint: 'Interviewers look for understanding of why Promise.then() runs before setTimeout(..., 0).'
      });
    } else if (sName.includes('react')) {
      questions.push({
        topic: 'React Architecture (High Probability)',
        question: 'How do you diagnose and prevent unnecessary re-renders in a deeply nested React component tree when using global state?',
        hint: 'Discuss useMemo, useCallback, React.memo, and state co-location.'
      });
    } else if (sName.includes('python')) {
      questions.push({
        topic: 'Python Concurrency (High Probability)',
        question: 'How does the Global Interpreter Lock (GIL) impact CPU-bound multi-threading in Python, and how would you bypass it for concurrent tasks?',
        hint: 'Mention multiprocessing, asyncio for I/O bound tasks, and native C extensions.'
      });
    } else {
      questions.push({
        topic: `${primaryGap.skill} Core Standard (High Probability)`,
        question: `How do you structure production-grade architecture and error-handling in ${primaryGap.skill} at an enterprise level?`,
        hint: 'Emphasize reliability, logging, clean interfaces, and edge-case handling.'
      });
    }
  }

  // Question 2: Focused on second key required skill or architecture
  const secondSkill = skillsList.find(s => s.skill.toLowerCase() !== primaryGap?.skill.toLowerCase() && (s.importance || 'required').toLowerCase() !== 'preferred') || skillsList[1];
  if (secondSkill) {
    const sName = secondSkill.skill.toLowerCase();
    if (sName.includes('typescript')) {
      questions.push({
        topic: 'TypeScript Type Safety',
        question: 'How do you type unknown external API responses safely using generics and type guards rather than resorting to any?',
        hint: 'Discuss the unknown type, Zod / custom type guards, and discriminated unions.'
      });
    } else if (sName.includes('postgres') || sName.includes('sql')) {
      questions.push({
        topic: 'Database Performance',
        question: 'When a critical query slows down under high traffic, what steps do you take with EXPLAIN ANALYZE to identify index bottlenecks?',
        hint: 'Look for Seq Scans vs Index Scans, cost estimates, and high row filter percentages.'
      });
    } else {
      questions.push({
        topic: `${secondSkill.skill} Best Practices`,
        question: `What patterns do you implement in ${secondSkill.skill} to ensure high testability, maintainability, and code quality?`,
        hint: 'Focus on separation of concerns, automated unit testing, and dependency injection.'
      });
    }
  }

  // Question 3: System Design / Practical Integration question
  questions.push({
    topic: 'Full-Stack Integration & Reliability',
    question: 'How do you handle graceful degradation and retry strategies when backend API services or database queries experience transient latency spikes?',
    hint: 'Mention exponential backoff with jitter, circuit breakers, optimistic UI updates, and caching.'
  });

  return questions;
};

// Helper to format level
const formatLevel = (lvl) => {
  if (!lvl) return 'N/A';
  const clean = String(lvl).trim().toLowerCase();
  if (clean === 'unspecified' || clean === 'none') return 'Any Level';
  return clean.charAt(0).toUpperCase() + clean.slice(1);
};

// Helper to format score
const formatScore = (score) => {
  if (score === null || score === undefined) return null;
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

export default function FinalResultPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { analysisResult, setAnalysisResult, clearAnalysis, refreshAnalysis, isRefreshing } = useAssessment();

  const urlAnalysisId = searchParams.get('analysis_id');
  const activeAnalysisId = urlAnalysisId || analysisResult?.analysis_id;

  const [aggregationData, setAggregationData] = useState(null);
  const [loadingAgg, setLoadingAgg] = useState(false);
  const [refreshError, setRefreshError] = useState(null);

  // Expandable state for CV suggestion drawer and interview questions
  const [expandedCvSuggest, setExpandedCvSuggest] = useState({});
  const [copiedKey, setCopiedKey] = useState(null);

  const toggleCvSuggest = (key) => {
    setExpandedCvSuggest(prev => ({ ...prev, [key]: !prev[key] }));
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

  // 1. VERIFIED STRENGTHS: Tested and scored >= 70% or met required level
  const verifiedStrengths = useMemo(() => skillsList.filter((s) => {
    const isAssessed = s.assessed_level !== null && s.assessed_level !== undefined;
    if (!isAssessed) return false;
    return !s.is_weakness && (s.level_gap === null || s.level_gap <= 0) && (s.total_score === null || s.total_score >= 0.50);
  }), [skillsList]);

  // 2. INTERVIEW BLOCKERS & GAPS: Confirmed quiz gaps or missing required qualifications
  const interviewBlockers = useMemo(() => skillsList.filter((s) => {
    const isAssessed = s.assessed_level !== null && s.assessed_level !== undefined;
    if (isAssessed) {
      return s.is_weakness || (s.level_gap !== null && s.level_gap > 0) || (s.total_score !== null && s.total_score < 0.50);
    }
    // Missing from CV or marked as missing
    return !s.matched || s.cv_match_status === 'Missing';
  }), [skillsList]);

  // 3. UNVERIFIED / SELF-REPORTED: Claimed in CV text but pending empirical test proof
  const unverifiedClaims = useMemo(() => skillsList.filter((s) => {
    const isAssessed = s.assessed_level !== null && s.assessed_level !== undefined;
    if (isAssessed) return false;
    return s.matched && s.cv_match_status !== 'Missing';
  }), [skillsList]);

  // Authoritative Verdict & Overall Status Resolution
  const finalVerdict = analysisResult?.readiness_verdict || analysisResult?.final_verdict || aggregationData?.readiness_verdict || aggregationData?.final_verdict || 'Evaluation Complete';
  const overallConfidenceDisplay = formatConfidence(aggregationData?.recommendation_confidence || analysisResult?.recommendation_confidence || 0.85);
  const assessedSkills = useMemo(() => skillsList.filter((s) => s.assessed_level !== null && s.assessed_level !== undefined), [skillsList]);
  const isPreliminary = Boolean(analysisResult?.is_preliminary ?? aggregationData?.is_preliminary ?? (assessedSkills.length === 0));

  const overallMatchScore = analysisResult?.score_data?.score !== undefined 
    ? `${Math.round(analysisResult.score_data.score)}%` 
    : (aggregationData?.overall_score !== null && aggregationData?.overall_score !== undefined 
        ? `${Math.round(aggregationData.overall_score * 100)}%` 
        : '67%');

  const totalSkillsCount = aggregationData?.total_skills || skillsList.length;

  // Forecasted interview questions based on active JD & candidates gaps
  const interviewQuestions = useMemo(() => {
    return getInterviewQuestions(skillsList, interviewBlockers);
  }, [skillsList, interviewBlockers]);

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
      gradient: 'linear-gradient(135deg, #3730a3 0%, #4f46e5 100%)',
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

  // Helper to extract study concepts
  const getStudyConceptsForSkill = (skillName, requiredLevel) => {
    const key = String(skillName || '').toLowerCase().trim();
    const lvl = String(requiredLevel || 'intermediate').toLowerCase().trim();
    if (TECHNICAL_STUDY_CONCEPTS[key]) {
      return TECHNICAL_STUDY_CONCEPTS[key][lvl] || TECHNICAL_STUDY_CONCEPTS[key]['default'] || TECHNICAL_STUDY_CONCEPTS[key]['intermediate'];
    }
    return [
      `Core language syntax & standard library in ${skillName}`,
      `Best practices, design patterns, & modular architecture`,
      `Common performance bottlenecks & memory profiling`,
      `Testing, edge-case coverage, & API integration`
    ];
  };

  // Loading Guard
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

  // Empty Analysis Guard
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

  return (
    <div
      className="fade-in"
      style={{
        maxWidth: '1000px',
        margin: '0 auto',
        paddingBottom: '3.5rem',
        width: '100%',
        boxSizing: 'border-box',
        overflowX: 'hidden'
      }}
    >
      {/* 1. PAGE HEADER & QUICK ACTIONS */}
      <div className="flex justify-between items-center mb-5 flex-wrap gap-4 pb-3" style={{ borderBottom: '1px solid var(--border-color)' }}>
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="badge badge-purple" style={{ fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
              Final Candidate Evaluation Dossier
            </span>
            {activeAnalysisId && (
              <span className="text-xs text-muted">
                Session #{activeAnalysisId}
              </span>
            )}
          </div>
          <h1 className="page-title text-2xl font-extrabold text-main" style={{ margin: 0 }}>
            Interview Readiness & Career Audit
          </h1>
          <p className="text-xs text-muted mt-1">
            Empirical synthesis of resume claims, real technical assessment performance, and hiring manager evaluation criteria.
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
            <span>{loadingAgg || isRefreshing ? 'Recalculating...' : 'Refresh'}</span>
          </button>
          <button
            type="button"
            onClick={() => navigate(activeAnalysisId ? `/dashboard?analysis_id=${activeAnalysisId}` : '/dashboard')}
            className="btn btn-outline flex items-center gap-1.5 text-xs"
            style={{ padding: '0.5rem 0.9rem' }}
          >
            <ArrowLeft size={13} />
            <span>Back to Dashboard</span>
          </button>
        </div>
      </div>

      {refreshError && (
        <div className="alert-error flex items-center gap-2 mb-4 p-3 rounded text-xs">
          <AlertCircle size={15} />
          <span>{refreshError}</span>
        </div>
      )}

      {/* 2. PILLAR 1: THE REALITY CHECK (CV Claims vs Empirical Truth Hero Card) */}
      <div
        className="card mb-6"
        style={{
          background: bannerTheme.gradient,
          borderRadius: 'var(--radius)',
          padding: '2rem',
          boxShadow: '0 8px 24px -4px rgba(0, 0, 0, 0.14)',
          border: 'none',
        }}
      >
        <div className="flex justify-between items-start gap-4 flex-wrap mb-4">
          <div style={{ flex: '1 1 340px' }}>
            <div className="flex items-center gap-2 mb-2 flex-wrap" style={{ opacity: 0.95, fontSize: '0.78rem', textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 700 }}>
              <div className="flex items-center gap-1.5">
                {bannerTheme.icon}
                <span>Authoritative Readiness Verdict</span>
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

            {/* Hiring Manager Executive Synthesis */}
            <p className="text-xs mt-2.5" style={{ opacity: 0.95, maxWidth: '640px', lineHeight: 1.6, color: 'rgba(255, 255, 255, 0.95)' }}>
              {isPreliminary
                ? 'Your resume presents a viable keyword match, but technical capability is completely unverified. Complete the priority assessments below to convert resume claims into verified strengths.'
                : interviewBlockers.length > 0
                ? `Initial screening confirms your profile aligns with ${overallMatchScore} of core requirements. However, technical testing revealed ${interviewBlockers.length} critical gap${interviewBlockers.length > 1 ? 's' : ''} that will raise red flags in technical interview rounds. Focused review on identified blocker topics is recommended prior to technical interviews.`
                : 'Candidate demonstrated verified proficiency across all tested job requirements. Technical assessment scores strongly confirm CV claims. Recommended to proceed to technical interview rounds with confidence.'}
            </p>
          </div>

          {/* Side-by-Side Reality Metrics */}
          <div className="flex items-center gap-3 flex-wrap">
            <div className="match-stat-item" style={{ backgroundColor: bannerTheme.badgeBg }}>
              <div className="text-xs" style={{ color: 'rgba(255,255,255,0.85)', fontSize: '0.72rem', textTransform: 'uppercase', fontWeight: 600 }}>
                Resume Claims
              </div>
              <div className="font-extrabold text-xl mt-0.5">{overallMatchScore} Match</div>
            </div>

            <div className="match-stat-item" style={{ backgroundColor: bannerTheme.badgeBg }}>
              <div className="text-xs" style={{ color: 'rgba(255,255,255,0.85)', fontSize: '0.72rem', textTransform: 'uppercase', fontWeight: 600 }}>
                Empirically Verified
              </div>
              <div className="font-extrabold text-xl mt-0.5">
                {verifiedStrengths.length} / {totalSkillsCount} Skills
              </div>
            </div>

            {overallConfidenceDisplay && (
              <div className="match-stat-item" style={{ backgroundColor: bannerTheme.badgeBg }}>
                <div className="text-xs" style={{ color: 'rgba(255,255,255,0.85)', fontSize: '0.72rem', textTransform: 'uppercase', fontWeight: 600 }}>
                  Model Confidence
                </div>
                <div className="font-extrabold text-xl mt-0.5">{overallConfidenceDisplay}</div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* 3. PILLAR 2: 3-BUCKET CANDIDATE COMPETENCY PROFILE (High Signal, No Duplicate Grid!) */}
      <div className="mb-6">
        <div className="mb-3">
          <h2 className="card-title text-lg font-bold flex items-center gap-2 mb-0.5" style={{ margin: 0 }}>
            <Layers size={18} style={{ color: 'var(--primary-700)' }} />
            <span>Candidate Competency Profile: Reality vs. Claims</span>
          </h2>
          <p className="text-xs text-muted" style={{ margin: 0 }}>
            Evaluated by combining your direct assessment quiz scores with verified resume evidence.
          </p>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(290px, 1fr))', gap: '1rem', width: '100%' }}>
          
          {/* BUCKET 1: VERIFIED STRENGTHS */}
          <div
            className="card"
            style={{
              padding: '1.25rem',
              margin: 0,
              backgroundColor: '#ffffff',
              border: '1px solid #bbf7d0',
              borderTop: '4px solid #10b981',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between',
            }}
          >
            <div>
              <div className="flex justify-between items-center mb-2">
                <span className="font-bold text-sm text-emerald-900 flex items-center gap-1.5">
                  <CheckCircle2 size={16} className="text-emerald-600" />
                  <span>Verified Strengths</span>
                </span>
                <span className="badge" style={{ backgroundColor: '#ecfdf5', color: '#059669', border: '1px solid #a7f3d0', fontSize: '0.68rem', fontWeight: 700 }}>
                  {verifiedStrengths.length} Confirmed
                </span>
              </div>
              <p className="text-xs text-muted mb-3" style={{ lineHeight: 1.4 }}>
                Skills where technical assessment scores empirically confirmed your proficiency at or above the job standard.
              </p>

              {verifiedStrengths.length === 0 ? (
                <div className="p-3 bg-slate-50 border border-slate-200 rounded text-xs text-muted italic text-center my-2">
                  No skills empirically confirmed yet. Take technical quizzes to build verified proof.
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                  {verifiedStrengths.map((item, idx) => (
                    <div
                      key={idx}
                      style={{
                        padding: '0.6rem 0.75rem',
                        backgroundColor: '#f0fdf4',
                        border: '1px solid #bbf7d0',
                        borderRadius: 'var(--radius-sm)',
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                      }}
                    >
                      <div>
                        <div className="font-bold text-xs text-emerald-950">{item.skill}</div>
                        <div className="text-xs text-emerald-700" style={{ fontSize: '0.7rem' }}>
                          Standard: {formatLevel(item.required_level || item.level)}
                        </div>
                      </div>
                      <span className="badge" style={{ backgroundColor: '#dcfce7', color: '#15803d', fontSize: '0.7rem', fontWeight: 700 }}>
                        Score: {formatScore(item.total_score) || 'Passed'}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="mt-3 pt-2 text-xs text-emerald-800" style={{ borderTop: '1px dashed #bbf7d0', fontSize: '0.72rem' }}>
              ✓ Safe to anchor on as core technical talking points in interviews.
            </div>
          </div>

          {/* BUCKET 2: INTERVIEW BLOCKERS & CRITICAL GAPS */}
          <div
            className="card"
            style={{
              padding: '1.25rem',
              margin: 0,
              backgroundColor: '#ffffff',
              border: '1px solid #fecaca',
              borderTop: '4px solid #ef4444',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between',
            }}
          >
            <div>
              <div className="flex justify-between items-center mb-2">
                <span className="font-bold text-sm text-rose-950 flex items-center gap-1.5">
                  <AlertTriangle size={16} className="text-rose-600" />
                  <span>Interview Blockers</span>
                </span>
                <span className="badge" style={{ backgroundColor: '#fef2f2', color: '#dc2626', border: '1px solid #fecaca', fontSize: '0.68rem', fontWeight: 700 }}>
                  {interviewBlockers.length} Red Flags
                </span>
              </div>
              <p className="text-xs text-muted mb-3" style={{ lineHeight: 1.4 }}>
                Failed assessments, low quiz scores, or critical required skills missing from your CV. These will disqualify you in technical rounds.
              </p>

              {interviewBlockers.length === 0 ? (
                <div className="p-3 bg-emerald-50 border border-emerald-200 rounded text-xs text-emerald-800 font-medium text-center my-2">
                  ✓ Zero critical interview blockers identified!
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                  {interviewBlockers.map((item, idx) => {
                    const supported = isSupportedSkill(item.skill);
                    const isAssessed = item.assessed_level !== null && item.assessed_level !== undefined;
                    return (
                      <div
                        key={idx}
                        style={{
                          padding: '0.6rem 0.75rem',
                          backgroundColor: '#fef2f2',
                          border: '1px solid #fecaca',
                          borderRadius: 'var(--radius-sm)',
                        }}
                      >
                        <div className="flex justify-between items-start gap-2 mb-1">
                          <span className="font-bold text-xs text-rose-950">{item.skill}</span>
                          <span className="badge" style={{ backgroundColor: '#fee2e2', color: '#b91c1c', fontSize: '0.65rem', fontWeight: 700 }}>
                            {isAssessed ? `Score: ${formatScore(item.total_score)}` : 'Missing in CV'}
                          </span>
                        </div>
                        <div className="text-xs text-rose-800" style={{ fontSize: '0.7rem', lineHeight: 1.3 }}>
                          {isAssessed
                            ? `Demonstrated ${formatLevel(item.assessed_level)} vs Required ${formatLevel(item.required_level || item.level)}`
                            : 'Required qualification not evidenced in your resume text'}
                        </div>
                        {supported && (
                          <div className="mt-2 text-right">
                            <button
                              type="button"
                              onClick={() => navigate(targetAssessmentPath(item.skill))}
                              className="btn btn-primary text-xs"
                              style={{ padding: '0.2rem 0.6rem', fontSize: '0.68rem', backgroundColor: '#dc2626', borderColor: '#b91c1c' }}
                            >
                              <span>{isAssessed ? 'Retake Quiz' : 'Take 5-Min Quiz'}</span>
                            </button>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            <div className="mt-3 pt-2 text-xs text-rose-800" style={{ borderTop: '1px dashed #fecaca', fontSize: '0.72rem' }}>
              ⚠ Prioritize fixing these before submitting job applications.
            </div>
          </div>

          {/* BUCKET 3: SELF-REPORTED (AWAITING PROOF) */}
          <div
            className="card"
            style={{
              padding: '1.25rem',
              margin: 0,
              backgroundColor: '#ffffff',
              border: '1px solid #bae6fd',
              borderTop: '4px solid #0284c7',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between',
            }}
          >
            <div>
              <div className="flex justify-between items-center mb-2">
                <span className="font-bold text-sm text-sky-950 flex items-center gap-1.5">
                  <FileText size={16} className="text-sky-600" />
                  <span>Claimed in CV</span>
                </span>
                <span className="badge" style={{ backgroundColor: '#f0f9ff', color: '#0369a1', border: '1px solid #bae6fd', fontSize: '0.68rem', fontWeight: 700 }}>
                  {unverifiedClaims.length} Unassessed
                </span>
              </div>
              <p className="text-xs text-muted mb-3" style={{ lineHeight: 1.4 }}>
                Skills detected in your CV text that have not yet been empirically tested. Employers treat these as unverified claims.
              </p>

              {unverifiedClaims.length === 0 ? (
                <div className="p-3 bg-slate-50 border border-slate-200 rounded text-xs text-muted italic text-center my-2">
                  All CV skills have been evaluated.
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', maxHeight: '230px', overflowY: 'auto' }}>
                  {unverifiedClaims.map((item, idx) => {
                    const supported = isSupportedSkill(item.skill);
                    return (
                      <div
                        key={idx}
                        style={{
                          padding: '0.5rem 0.75rem',
                          backgroundColor: '#f0f9ff',
                          border: '1px solid #e0f2fe',
                          borderRadius: 'var(--radius-sm)',
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center',
                        }}
                      >
                        <div>
                          <div className="font-semibold text-xs text-sky-950">{item.skill}</div>
                          <div className="text-xs text-sky-700" style={{ fontSize: '0.68rem' }}>
                            CV Level: {formatLevel(item.cv_level)}
                          </div>
                        </div>
                        {supported ? (
                          <button
                            type="button"
                            onClick={() => navigate(targetAssessmentPath(item.skill))}
                            className="btn btn-outline text-xs"
                            style={{ padding: '0.2rem 0.55rem', fontSize: '0.68rem', borderColor: '#bae6fd', color: '#0369a1' }}
                          >
                            Verify
                          </button>
                        ) : (
                          <span className="text-muted" style={{ fontSize: '0.65rem', fontStyle: 'italic' }}>
                            CV Evidence Only
                          </span>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            <div className="mt-3 pt-2 text-xs text-sky-800" style={{ borderTop: '1px dashed #bae6fd', fontSize: '0.72rem' }}>
              ℹ An interviewer will test whether your real depth matches your CV text.
            </div>
          </div>
        </div>
      </div>

      {/* 4. PILLAR 3: TARGETED STUDY ROADMAP & CONCEPT PINPOINTING (Based on Quiz Mistakes) */}
      {interviewBlockers.length > 0 && (
        <div className="card mb-6" style={{ padding: '1.5rem', backgroundColor: '#ffffff', border: '1px solid var(--border-color)' }}>
          <div className="mb-4">
            <h2 className="card-title text-lg font-bold flex items-center gap-2 mb-0.5" style={{ margin: 0 }}>
              <BookOpen size={18} style={{ color: 'var(--primary-700)' }} />
              <span>Targeted Technical Study Roadmap</span>
            </h2>
            <p className="text-xs text-muted" style={{ margin: 0 }}>
              Specific core concepts identified by your test evaluation that you must master to satisfy the job requirements.
            </p>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', width: '100%' }}>
            {interviewBlockers.slice(0, 3).map((item, idx) => {
              const concepts = getStudyConceptsForSkill(item.skill, item.required_level || item.level);
              const supported = isSupportedSkill(item.skill);

              return (
                <div
                  key={idx}
                  style={{
                    backgroundColor: '#fafafa',
                    border: '1px solid var(--border-color)',
                    borderRadius: 'var(--radius-sm)',
                    padding: '1.25rem',
                  }}
                >
                  <div className="flex justify-between items-start gap-3 flex-wrap mb-2">
                    <div>
                      <div className="flex items-center gap-2 mb-1 flex-wrap">
                        <span className="font-bold text-main text-base">{item.skill}</span>
                        <span className="badge" style={{ fontSize: '0.68rem', backgroundColor: '#eff6ff', color: '#1e40af', border: '1px solid #bfdbfe' }}>
                          Target Standard: {formatLevel(item.required_level || item.level)}
                        </span>
                        <span className="badge" style={{ fontSize: '0.68rem', backgroundColor: '#fef2f2', color: '#dc2626', border: '1px solid #fecaca' }}>
                          Estimated Prep: 3–5 Days
                        </span>
                      </div>
                      <div className="text-xs text-muted">
                        Focus your study on these specific high-weight interview topics:
                      </div>
                    </div>

                    {supported && (
                      <button
                        type="button"
                        onClick={() => navigate(targetAssessmentPath(item.skill))}
                        className="btn btn-outline text-xs flex items-center gap-1.5"
                        style={{ padding: '0.35rem 0.8rem' }}
                      >
                        <RotateCcw size={13} />
                        <span>Retake Skill Quiz</span>
                      </button>
                    )}
                  </div>

                  {/* Bulleted High-Impact Concepts */}
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '0.5rem', marginTop: '0.75rem' }}>
                    {concepts.map((concept, cIdx) => (
                      <div
                        key={cIdx}
                        style={{
                          padding: '0.5rem 0.75rem',
                          backgroundColor: '#ffffff',
                          border: '1px solid #e2e8f0',
                          borderRadius: '4px',
                          fontSize: '0.78rem',
                          color: '#334155',
                          display: 'flex',
                          alignItems: 'flex-start',
                          gap: '0.5rem',
                        }}
                      >
                        <span style={{ color: 'var(--primary-600)', fontWeight: 700, fontSize: '0.9rem', lineHeight: 1 }}>•</span>
                        <span>{concept}</span>
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* 5. PILLAR 4: TECHNICAL INTERVIEW QUESTION FORECAST */}
      <div className="card mb-6" style={{ padding: '1.5rem', backgroundColor: '#ffffff', border: '1px solid var(--border-color)' }}>
        <div className="mb-4">
          <div className="flex items-center gap-2 mb-0.5">
            <MessageSquare size={18} style={{ color: 'var(--primary-700)' }} />
            <h2 className="card-title text-lg font-bold" style={{ margin: 0 }}>
              Technical Interview Question Forecast
            </h2>
          </div>
          <p className="text-xs text-muted" style={{ margin: 0 }}>
            High-probability questions hiring teams will ask based on this job description and your identified skill profile.
          </p>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem', width: '100%' }}>
          {interviewQuestions.map((q, idx) => (
            <div
              key={idx}
              style={{
                backgroundColor: '#f8fafc',
                border: '1px solid #e2e8f0',
                borderRadius: 'var(--radius-sm)',
                padding: '1rem 1.25rem',
              }}
            >
              <div className="flex items-center gap-2 mb-1.5 flex-wrap">
                <span className="badge" style={{ backgroundColor: '#e0e7ff', color: '#4338ca', border: '1px solid #c7d2fe', fontSize: '0.68rem', fontWeight: 700 }}>
                  Question {idx + 1}
                </span>
                <span className="text-xs font-bold text-slate-700">{q.topic}</span>
              </div>

              <div className="font-semibold text-main text-sm mb-2" style={{ lineHeight: 1.4 }}>
                "{q.question}"
              </div>

              <div className="text-xs text-muted p-2 rounded bg-white border border-slate-200" style={{ fontStyle: 'italic', lineHeight: 1.4 }}>
                <span className="font-semibold text-slate-600 not-italic">Interviewer Expectation: </span>
                {q.hint}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 6. PILLAR 5: RESUME OPTIMIZATION & COPYABLE BULLET POINTS */}
      {skillsList.some(s => s.actionable_feedback) && (
        <div className="card mb-6" style={{ padding: '1.5rem', backgroundColor: '#ffffff', border: '1px solid var(--border-color)' }}>
          <div className="mb-4">
            <div className="flex items-center gap-2 mb-0.5">
              <Sparkles size={18} style={{ color: 'var(--primary-700)' }} />
              <h2 className="card-title text-lg font-bold" style={{ margin: 0 }}>
                Resume Optimization: Ready-to-Copy Bullets
              </h2>
            </div>
            <p className="text-xs text-muted" style={{ margin: 0 }}>
              Enhance how your skills are presented on your resume before submitting to this hiring manager.
            </p>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', width: '100%' }}>
            {skillsList.filter(s => s.actionable_feedback).map((item, idx) => {
              const fb = item.actionable_feedback;
              const isCopied = copiedKey === item.skill;
              const isExpanded = Boolean(expandedCvSuggest[item.skill]);

              return (
                <div
                  key={idx}
                  style={{
                    backgroundColor: '#fafafa',
                    border: '1px solid var(--border-color)',
                    borderRadius: 'var(--radius-sm)',
                    padding: '1.15rem 1.25rem',
                  }}
                >
                  <div className="flex justify-between items-center mb-2 flex-wrap gap-2">
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-main text-sm">{item.skill}</span>
                      <span className="badge" style={{ backgroundColor: '#f1f5f9', color: '#475569', fontSize: '0.68rem', border: '1px solid #cbd5e1' }}>
                        Section: {fb.section || 'Experience'}
                      </span>
                    </div>

                    {fb.suggested_wording && (
                      <button
                        type="button"
                        onClick={() => handleCopyText(item.skill, fb.suggested_wording)}
                        className="btn btn-outline text-xs flex items-center gap-1.5"
                        style={{ padding: '0.25rem 0.65rem', color: '#059669', borderColor: '#a7f3d0', backgroundColor: '#ffffff' }}
                      >
                        {isCopied ? <Check size={12} /> : <Copy size={12} />}
                        <span>{isCopied ? 'Copied to Clipboard!' : 'Copy Text'}</span>
                      </button>
                    )}
                  </div>

                  <div className="text-xs text-muted mb-2">
                    {fb.explanation}
                  </div>

                  {fb.suggested_wording ? (
                    <blockquote
                      style={{
                        margin: '0.5rem 0 0 0',
                        padding: '0.65rem 0.85rem',
                        backgroundColor: '#f0fdf4',
                        borderLeft: '3px solid #10b981',
                        fontSize: '0.825rem',
                        color: '#1e293b',
                        lineHeight: 1.5,
                        borderRadius: '0 4px 4px 0',
                      }}
                    >
                      "{fb.suggested_wording}"
                    </blockquote>
                  ) : null}

                  {fb.original_text && (
                    <div className="mt-2 text-right">
                      <button
                        type="button"
                        onClick={() => toggleCvSuggest(item.skill)}
                        style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '0.72rem', color: 'var(--primary-600)', display: 'inline-flex', alignItems: 'center', gap: '0.2rem' }}
                      >
                        <span>{isExpanded ? 'Hide original wording' : 'View original wording'}</span>
                        {isExpanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                      </button>

                      {isExpanded && (
                        <div className="text-left text-xs text-muted mt-1 p-2 bg-white rounded border border-slate-200 italic">
                          Current text: "{fb.original_text}"
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* 7. FOOTER NAVIGATION */}
      <div className="flex justify-between items-center flex-wrap gap-4 pt-3" style={{ borderTop: '1px solid var(--border-color)' }}>
        <button
          onClick={() => navigate(activeAnalysisId ? `/dashboard?analysis_id=${activeAnalysisId}` : '/dashboard')}
          className="btn btn-outline flex items-center gap-2"
        >
          <ArrowLeft size={16} />
          <span>Back to Skill Matrix</span>
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
