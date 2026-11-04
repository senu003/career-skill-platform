import React, { useState, useEffect, useMemo } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  Upload, FileText, CheckCircle2, AlertCircle, AlertTriangle,
  ArrowRight, RefreshCw, Briefcase,
  TrendingUp, Sparkles
} from 'lucide-react';
import { fetchWithAuth } from '../api';
import { useAssessment } from '../context/AssessmentContext';
import { isSupportedSkill } from '../utils/supportedSkills';
import SkillMatchTable from '../components/SkillMatchTable';
import {
  formatLevel,
  translateRequiredLevel,
  translateCvLevel,
  getLevelPillClass,
} from '../utils/formatters';


export default function DashboardPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { analysisResult, setAnalysisResult, clearAnalysis } = useAssessment();
  const urlAnalysisId = searchParams.get('analysis_id');
  const activeAnalysisId = urlAnalysisId || analysisResult?.analysis_id;

  const assessmentPath = (skillName) => {
    const path = `/assessment/${encodeURIComponent(skillName)}`;
    return activeAnalysisId
      ? `${path}?analysis_id=${encodeURIComponent(activeAnalysisId)}`
      : path;
  };

  // Intake Form State
  const [selectedFile, setSelectedFile] = useState(null);
  const [dragActive, setDragActive] = useState(false);
  const [jobTitle, setJobTitle] = useState('');
  const [companyName, setCompanyName] = useState('');
  const [jobDescription, setJobDescription] = useState('');

  // Saved CV State
  const [savedCv, setSavedCv] = useState(null);
  const [useSavedCv, setUseSavedCv] = useState(false);

  // UI Flow State
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [expandedEvidence, setExpandedEvidence] = useState({});
  const [activeFilter, setActiveFilter] = useState('All');
  const [supportedSkillsList, setSupportedSkillsList] = useState([]);
  const jobDescriptionWordCount = jobDescription.trim()
    ? jobDescription.trim().split(/\s+/).length
    : 0;

  const toggleEvidence = (skillKey) => {
    setExpandedEvidence((prev) => ({
      ...prev,
      [skillKey]: !prev[skillKey],
    }));
  };

  // Fetch supported assessment skills from /assessment/supported-skills
  useEffect(() => {
    let isMounted = true;
    const fetchSupportedSkills = async () => {
      try {
        const res = await fetchWithAuth('/assessment/supported-skills');
        if (isMounted && res && Array.isArray(res.supported_skills)) {
          setSupportedSkillsList(res.supported_skills);
        }
      } catch {
        // Fallback silently to predefined list
      }
    };
    fetchSupportedSkills();
    return () => {
      isMounted = false;
    };
  }, []);

  // Fetch last uploaded CV on mount
  useEffect(() => {
    let isMounted = true;
    const fetchSavedCv = async () => {
      try {
        const res = await fetchWithAuth('/cv/latest');
        if (isMounted && res && res.has_cv && res.cv) {
          setSavedCv(res.cv);
          setUseSavedCv(true);
        }
      } catch {
        // No saved CV found
      }
    };
    fetchSavedCv();
    return () => {
      isMounted = false;
    };
  }, []);

  // Sync session from URL if explicit analysis_id is provided
  useEffect(() => {
    let isCancelled = false;
    if (urlAnalysisId && String(analysisResult?.analysis_id) !== String(urlAnalysisId)) {
      const fetchSession = async () => {
        try {
          const res = await fetchWithAuth(`/cv/sessions/${urlAnalysisId}`);
          if (!isCancelled && res) {
            setAnalysisResult(res);
          }
        } catch (err) {
          console.warn('Failed to load session from analysis_id param:', err);
        }
      };
      fetchSession();
    }
    return () => {
      isCancelled = true;
    };
  }, [urlAnalysisId, analysisResult?.analysis_id, setAnalysisResult]);

  const isSkillAvailable = (skillName) => {
    return isSupportedSkill(skillName, supportedSkillsList);
  };

  // Drag and Drop Handlers
  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      validateAndSetFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      validateAndSetFile(e.target.files[0]);
    }
  };

  const validateAndSetFile = (file) => {
    setError(null);
    if (!file) return;

    if (file.type !== 'application/pdf' && !file.name.toLowerCase().endsWith('.pdf')) {
      setError('Please select a valid PDF document (.pdf).');
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      setError('File size exceeds 10MB limit. Please upload a smaller PDF.');
      return;
    }
    if (file.size === 0) {
      setError('The uploaded PDF appears empty or unreadable. Please ensure it contains readable text.');
      return;
    }

    setSelectedFile(file);
    setUseSavedCv(false);
  };

  const removeFile = () => {
    setSelectedFile(null);
    if (savedCv) {
      setUseSavedCv(true);
    }
  };

  // Form Submission & Analysis API Integration
  const handleAnalyze = async (e) => {
    if (e && e.preventDefault) e.preventDefault();
    setError(null);

    if (!selectedFile && !useSavedCv) {
      setError('Please upload your CV PDF or choose your saved CV.');
      return;
    }

    if (jobDescriptionWordCount < 10) {
      setError('Please paste a more detailed job description with at least 10 words so we can identify the required skills.');
      return;
    }

    setLoading(true);

    try {
      // 1. Extract requirements from job description using POST /requirements/analyze
      const reqRes = await fetchWithAuth('/requirements/analyze', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ text: jobDescription.trim() }),
      });

      const extractedRequirements = reqRes.requirements || [];

      if (!Array.isArray(extractedRequirements) || extractedRequirements.length === 0) {
        throw new Error('No skill requirements could be extracted from the job description. Please provide a more detailed description.');
      }

      // 2. Prepare multipart form data for POST /cv/analyze
      const formData = new FormData();
      if (selectedFile) {
        formData.append('file', selectedFile);
      } else if (savedCv) {
        formData.append('cv_id', savedCv.id);
      }
      formData.append('requirements', JSON.stringify(extractedRequirements));
      if (jobTitle.trim()) formData.append('job_title', jobTitle.trim());
      if (companyName.trim()) formData.append('company', companyName.trim());
      formData.append('include_prior_assessments', 'false');

      // 3. Analyze CV against requirements
      const cvRes = await fetchWithAuth('/cv/analyze', {
        method: 'POST',
        body: formData,
      });

      // 4. Save backend analysis response to AssessmentContext
      setAnalysisResult(cvRes);
    } catch (err) {
      if (err.status === 401 || (err.message && err.message.includes('401'))) {
        setError('Your session has expired. Redirecting to login page...');
        setTimeout(() => {
          navigate('/login');
        }, 1500);
      } else if (err.status === 502 || (err.message && err.message.includes('502'))) {
        setError('The AI analysis service is temporarily unavailable (502 Bad Gateway). Please try again shortly.');
      } else {
        setError(err.message || 'An error occurred while analyzing match. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleAnalyzeAnother = () => {
    clearAnalysis();
    setSelectedFile(null);
    setJobTitle('');
    setCompanyName('');
    setJobDescription('');
    setExpandedEvidence({});
    setActiveFilter('All');
    setError(null);
    navigate('/dashboard', { replace: true });
  };



  // Extract skills list safely from backend response
  const skillsList = analysisResult?.skills || [
    ...(analysisResult?.matched_skills || []),
    ...(analysisResult?.missing_skills || []),
  ];

  const LEVEL_MAP = { basic: 1, intermediate: 2, advanced: 3 };

  /**
   * 4-tier skill gap classification:
   *   totally_missing — skill name NOT found in CV at all
   *   level_gap       — skill found but CV level < required level
   *   meets           — CV level == required level (or both unspecified with match)
   *   exceeds         — CV level > required level
   */
  const getGapTier = (item) => {
    const cvStatus = item.cv_match_status || (item.matched ? 'Match' : 'Missing');
    const cvRaw = String(item.cv_level || '').trim().toLowerCase();
    const reqRaw = String(item.required_level || item.level || '').trim().toLowerCase();
    const reqVal = LEVEL_MAP[reqRaw] || 0;

    // 1. If candidate completed technical assessment, it is ground truth
    const assRaw = String(item.assessed_level || '').trim().toLowerCase();
    const assVal = LEVEL_MAP[assRaw] || 0;
    if (assVal > 0) {
      if (reqVal > 0) {
        if (assVal < reqVal) return 'level_gap';
        if (assVal > reqVal) return 'exceeds';
        return 'meets';
      }
      return 'meets';
    }

    // 2. Unassessed: check CV presence
    if (cvStatus === 'Missing' || !item.matched || cvRaw === 'not_found') {
      return 'totally_missing';
    }

    const cvVal = LEVEL_MAP[cvRaw] || 0;

    // If either side has no numeric level (unspecified), check match status
    if (cvVal === 0 || reqVal === 0) {
      if (cvStatus === 'Match') return 'meets';
      if (cvStatus === 'Needs Improvement') return 'level_gap';
      return 'meets';
    }

    if (cvVal < reqVal) return 'level_gap';
    if (cvVal > reqVal) return 'exceeds';
    return 'meets';
  };

  // Helper to determine if a skill is a GAP (totally missing OR level gap)
  const isSkillGap = (item) => {
    const tier = getGapTier(item);
    return tier === 'totally_missing' || tier === 'level_gap';
  };

  // Calculate numeric gap size for ordering
  const getGapSize = (item) => {
    if (item.level_gap !== null && item.level_gap !== undefined) {
      const val = Number(item.level_gap);
      if (!isNaN(val)) return val;
    }
    const reqStr = String(item.required_level || item.level || 'basic').toLowerCase().trim();
    const reqVal = LEVEL_MAP[reqStr] || 1;
    const cvStatus = item.cv_match_status || (item.matched ? 'Match' : 'Missing');
    if (cvStatus === 'Missing' || !item.matched) return reqVal;
    if (cvStatus === 'Needs Improvement') {
      const cvStr = String(item.cv_level || '').toLowerCase().trim();
      const cvVal = LEVEL_MAP[cvStr] || 0;
      return Math.max(1, reqVal - cvVal);
    }
    return 0;
  };

  // Status Helper: 4-tier evidence taxonomy
  const getSkillStatus = (skillItem) => {
    const isAssessed = skillItem.assessed_level !== null && skillItem.assessed_level !== undefined;
    const tier = getGapTier(skillItem);
    if (isAssessed) {
      if (tier === 'level_gap' || tier === 'totally_missing') {
        return { label: 'Verified Gap', className: 'status-badge-needs-improvement', tier };
      }
      return { label: 'Verified Mastered', className: 'status-badge-strong', tier };
    }
    // Unassessed states (strictly separate from verified mastery)
    if (tier === 'totally_missing') {
      return { label: 'Not on CV (Unverified)', className: 'status-badge-missing', tier };
    }
    if (tier === 'level_gap') {
      return { label: 'CV Level Gap (Unverified)', className: 'status-badge-needs-improvement', tier };
    }
    return { label: 'CV Evidenced (Unverified)', className: 'status-badge-strong', tier };
  };

  // One-line explanation under each gap, aware of missing levels
  const _getGapExplanation = (item) => {
    const reqRaw = String(item.required_level || item.level || '').trim().toLowerCase();
    const reqStr = translateRequiredLevel(reqRaw);
    const importanceLabel = (item.importance || 'required').toLowerCase() === 'preferred' ? 'Nice-to-have' : 'Required';
    const tier = getGapTier(item);

    if (tier === 'totally_missing') {
      return `${importanceLabel} skill — not mentioned in CV (unverified proficiency)`;
    }

    const cvRaw = String(item.cv_level || '').toLowerCase();
    const cvHasLevel = LEVEL_MAP[cvRaw] > 0;
    const reqHasLevel = LEVEL_MAP[reqRaw] > 0;

    if (tier === 'level_gap') {
      if (item.assessed_level && Number(item.level_gap) > 0) {
        return `${importanceLabel} — needs ${reqStr}; your assessment: ${formatLevel(item.assessed_level)}`;
      }
      if (cvHasLevel && reqHasLevel) {
        return `${importanceLabel} — needs ${reqStr}; your CV shows ${formatLevel(cvRaw)} level`;
      }
      if (!reqHasLevel) {
        return `${importanceLabel} — CV mentions the skill but evidence below expected level`;
      }
      return `${importanceLabel} — needs ${reqStr} level; CV evidence is insufficient`;
    }
    return null; // No explanation needed for meets/exceeds
  };

  // Required vs Preferred partitioning
  const requiredSkills = skillsList.filter(s => (s.importance || 'required').toLowerCase() !== 'preferred');
  const preferredSkills = skillsList.filter(s => (s.importance || '').toLowerCase() === 'preferred');

  const isMatchedSkill = (s) => (s.cv_match_status === 'Match' || (s.matched && s.cv_match_status !== 'Missing' && s.cv_match_status !== 'Needs Improvement'));

  const requiredFoundCount = requiredSkills.filter(isMatchedSkill).length;
  const totalRequiredCount = requiredSkills.length;

  const _preferredFoundCount = preferredSkills.filter(isMatchedSkill).length;
  const _totalPreferredCount = preferredSkills.length;

  // Match percentage: Count Required skills only (Do not mix Preferred into the percentage)
  const matchPercentage = totalRequiredCount > 0
    ? Math.round((requiredFoundCount / totalRequiredCount) * 100)
    : (skillsList.length > 0 ? Math.round((skillsList.filter(isMatchedSkill).length / skillsList.length) * 100) : 0);

  // Verdict Theme Helper
  const getVerdictTheme = (verdict) => {
    const v = (verdict || '').toLowerCase();
    if (v.includes('interview') || v.includes('ready')) {
      return {
        bg: '#ecfdf5',
        color: '#059669',
        border: '1px solid #a7f3d0',
        badgeClass: 'badge-success',
        icon: <CheckCircle2 size={24} style={{ color: '#059669' }} />
      };
    }
    if (v.includes('major') || v.includes('upskill')) {
      return {
        bg: '#fef2f2',
        color: '#dc2626',
        border: '1px solid #fecaca',
        badgeClass: 'status-badge-missing',
        icon: <AlertTriangle size={24} style={{ color: '#dc2626' }} />
      };
    }
    return {
      bg: '#fffbeb',
      color: '#b45309',
      border: '1px solid #fde68a',
      badgeClass: 'badge-warning',
      icon: <TrendingUp size={24} style={{ color: '#d97706' }} />
    };
  };

  const readinessVerdict = analysisResult?.readiness_verdict || analysisResult?.final_verdict || 'Evaluation Complete';
  const _readinessReasons = analysisResult?.readiness_reasons || [];
  const _verdictTheme = getVerdictTheme(readinessVerdict);

  // Check if candidate has completed any assessment
  const _hasAnyAssessments = skillsList.some(s => s.assessed_level !== null && s.assessed_level !== undefined);

  // Focus First list (Gaps ONLY, max 5, ordered Required before Preferred, then largest gap first)
  const _focusFirstList = (() => {
    // If backend provided priority_skills, ensure all items are strictly gaps
    if (analysisResult?.priority_skills && Array.isArray(analysisResult.priority_skills) && analysisResult.priority_skills.length > 0) {
      const gapPriority = analysisResult.priority_skills.filter(p => isSkillGap(p));
      if (gapPriority.length > 0) {
        return gapPriority.slice(0, 5);
      }
    }

    // Fallback: extract gaps from skillsList
    const gaps = skillsList.filter(s => isSkillGap(s));
    gaps.sort((a, b) => {
      // 1. Required before Preferred
      const aReq = (a.importance || 'required').toLowerCase() !== 'preferred' ? 0 : 1;
      const bReq = (b.importance || 'required').toLowerCase() !== 'preferred' ? 0 : 1;
      if (aReq !== bReq) return aReq - bReq;

      // 2. Largest gap first
      const aGap = getGapSize(a);
      const bGap = getGapSize(b);
      if (bGap !== aGap) return bGap - aGap;

      return (a.skill || '').localeCompare(b.skill || '');
    });

    return gaps.slice(0, 5).map(s => ({
      skill: s.skill,
      reason: s.cv_match_status === 'Missing' || !s.matched
        ? ((s.importance || 'required').toLowerCase() === 'preferred' ? 'Preferred skill not in CV (Unverified)' : 'Required skill not in CV (Unverified)')
        : (s.cv_match_status === 'Needs Improvement' ? 'Skill needs improvement based on CV evidence' : 'Skill gap identified below requirement'),
      required_level: s.required_level || s.level,
      importance: s.importance || 'required',
      level_gap: s.level_gap
    }));
  })();

  // Sort Skill Breakdown: gaps first (Missing, Needs Improvement), then Matched
  const sortedBreakdownSkills = [...skillsList].sort((a, b) => {
    const aIsGap = isSkillGap(a);
    const bIsGap = isSkillGap(b);
    if (aIsGap && !bIsGap) return -1;
    if (!aIsGap && bIsGap) return 1;

    // Within same category: Required before Preferred
    const aReq = (a.importance || 'required').toLowerCase() !== 'preferred' ? 0 : 1;
    const bReq = (b.importance || 'required').toLowerCase() !== 'preferred' ? 0 : 1;
    if (aReq !== bReq) return aReq - bReq;

    if (aIsGap && bIsGap) {
      const aGap = getGapSize(a);
      const bGap = getGapSize(b);
      if (bGap !== aGap) return bGap - aGap;
    }

    return (a.skill || '').localeCompare(b.skill || '');
  });

  // Filter chips: All / Gaps / Matched / Required / Preferred
  const filteredBreakdownSkills = sortedBreakdownSkills.filter(item => {
    if (activeFilter === 'All') return true;
    if (activeFilter === 'Gaps') return isSkillGap(item);
    if (activeFilter === 'Matched') return !isSkillGap(item);
    if (activeFilter === 'Required') return (item.importance || 'required').toLowerCase() !== 'preferred';
    if (activeFilter === 'Preferred') return (item.importance || '').toLowerCase() === 'preferred';
    return true;
  });

  // Footer CTA: Show "Continue to Assessment" only if at least one gap has an available assessment
  const allGapSkills = skillsList.filter(isSkillGap);
  const firstGapWithAssessment = allGapSkills.find(s => isSkillAvailable(s.skill));
  const _showFooterCta = Boolean(firstGapWithAssessment);

  // Category counters
  const meetsCount = skillsList.filter(s => getGapTier(s) === 'meets' || getGapTier(s) === 'exceeds').length;
  const gapCount = skillsList.filter(s => getGapTier(s) === 'level_gap').length;
  const missingCount = skillsList.filter(s => getGapTier(s) === 'totally_missing').length;
  const assessedCount = skillsList.filter(s => s.assessed_level !== null && s.assessed_level !== undefined).length;
  const isPreliminary = Boolean(analysisResult?.is_preliminary ?? (assessedCount === 0));

  // Filtered skills list driven by glance card filters
  const displayedSkillsList = useMemo(() => {
    if (activeFilter === 'Matched') {
      return skillsList.filter(s => getGapTier(s) === 'meets' || getGapTier(s) === 'exceeds');
    }
    if (activeFilter === 'LevelGaps' || activeFilter === 'Gaps') {
      return skillsList.filter(s => getGapTier(s) === 'level_gap');
    }
    if (activeFilter === 'Missing') {
      return skillsList.filter(s => getGapTier(s) === 'totally_missing');
    }
    return skillsList;
  }, [skillsList, activeFilter]);

  // Header display: never show placeholder like "dfgh at ghj"
  const displayJobTitle = (jobTitle && jobTitle.trim()) || analysisResult?.job_title || 'Your target job';
  const effectiveCompany = (companyName && companyName.trim()) || analysisResult?.company || '';
  const displayCompany = effectiveCompany ? ` at ${effectiveCompany}` : '';

  return (
    <div className="fade-in">
      {/* ERROR ALERT */}
      {error && (
        <div
          className="alert-error flex items-start gap-3 mb-4"
          role="alert"
          style={{
            padding: '1.1rem 1.25rem',
            borderRadius: 'var(--radius-sm)',
          }}
        >
          <AlertCircle size={20} style={{ flexShrink: 0, marginTop: '2px' }} />
          <div style={{ flex: 1 }}>
            <div className="font-bold text-sm mb-0.5">
              {error.includes('502') || error.toLowerCase().includes('bad gateway')
                ? 'AI Service Temporarily Unavailable'
                : 'Unable to Analyze Match'}
            </div>
            <div className="text-xs" style={{ lineHeight: 1.5, opacity: 0.95 }}>
              {error}
            </div>
            {(error.includes('502') || error.toLowerCase().includes('bad gateway')) && (
              <button
                type="button"
                onClick={handleAnalyze}
                className="btn btn-outline text-xs mt-2.5 flex items-center gap-1.5"
                style={{
                  padding: '0.35rem 0.75rem',
                  backgroundColor: '#ffffff',
                  borderColor: 'var(--danger-color)',
                  color: 'var(--danger-color)',
                }}
              >
                <RefreshCw size={13} />
                <span>Retry</span>
              </button>
            )}
          </div>
        </div>
      )}

      {/* LOADING STATE DURING ANALYSIS */}
      {loading ? (
        <div className="card text-center fade-in" style={{ padding: '3.5rem 2rem', margin: '1.5rem 0' }} role="status">
          <div
            className="spinner spinner-dark mb-4"
            style={{ width: 44, height: 44, borderWidth: 3, margin: '0 auto 1.5rem' }}
          ></div>
          <h2 className="card-title text-xl mb-2">Analyzing Job Match & CV Evidence</h2>
          <p className="text-muted text-sm mb-4" style={{ maxWidth: '520px', margin: '0 auto 1.5rem', lineHeight: 1.5 }}>
            Extracting skills from job description, comparing with your CV evidence, and synthesizing candidate readiness verdict...
          </p>
          <div className="flex justify-center items-center gap-2 text-xs text-muted flex-wrap">
            <span className="badge badge-purple">1. NLP Skill Extraction</span>
            <span>→</span>
            <span className="badge badge-purple">2. CV Evidence Matching</span>
            <span>→</span>
            <span className="badge badge-purple">3. Readiness & Priority Analysis</span>
          </div>
        </div>
      ) : !analysisResult ? (
        /* INTAKE FORM VIEW */
        <div>
          <div className="page-header">
            <h1 className="page-title">Find out how well you match this job</h1>
            <p className="page-subtitle">
              Upload your CV or choose your saved resume, and provide job requirements to calculate match compatibility.
            </p>
          </div>

          {/* Workflow Indicator */}
          <div className="workflow-steps">
            <div className={`workflow-step ${selectedFile || useSavedCv ? 'active' : ''}`}>
              <span className="workflow-step-num">1</span>
              <span>CV Selected</span>
            </div>
            <div className={`workflow-step-divider ${selectedFile || useSavedCv ? 'active' : ''}`} />
            <div className={`workflow-step ${jobDescription.trim() ? 'active' : ''}`}>
              <span className="workflow-step-num">2</span>
              <span>Provide Job</span>
            </div>
            <div className={`workflow-step-divider ${analysisResult ? 'active' : ''}`} />
            <div className={`workflow-step ${analysisResult ? 'active' : ''}`}>
              <span className="workflow-step-num">3</span>
              <span>Analyze Match</span>
            </div>
          </div>

          <form onSubmit={handleAnalyze} className="grid" style={{ gap: '1.5rem' }}>
            {/* CV UPLOAD / SAVED CV CARD */}
            <div className="card">
              <h2 className="card-title flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <FileText size={20} style={{ color: 'var(--primary-600)' }} />
                  <span>Your CV / Resume</span>
                </div>
                {savedCv && (
                  <button
                    type="button"
                    onClick={() => {
                      setUseSavedCv(!useSavedCv);
                      if (!useSavedCv) setSelectedFile(null);
                    }}
                    className="btn btn-outline text-xs"
                    style={{ padding: '0.3rem 0.65rem' }}
                  >
                    {useSavedCv ? 'Upload New File Instead' : 'Use Last Saved CV'}
                  </button>
                )}
              </h2>

              {useSavedCv && savedCv ? (
                <div className="file-preview" style={{ backgroundColor: 'var(--primary-50)', border: '1px solid var(--primary-200)' }}>
                  <div className="flex items-center gap-3">
                    <FileText size={24} style={{ color: 'var(--primary-600)' }} />
                    <div>
                      <div className="font-semibold text-sm text-main flex items-center gap-2">
                        <span>{savedCv.file_name}</span>
                        <span className="badge badge-purple">Saved Resume</span>
                      </div>
                      <div className="text-xs text-muted">
                        Uploaded on {new Date(savedCv.uploaded_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}
                      </div>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => setUseSavedCv(false)}
                    className="btn btn-outline"
                    style={{ padding: '0.3rem 0.6rem', fontSize: '0.8rem' }}
                  >
                    Replace File
                  </button>
                </div>
              ) : !selectedFile ? (
                <div>
                  {!savedCv && (
                    <p className="text-xs text-muted mb-2 font-medium" style={{ color: 'var(--primary-700)' }}>
                      Upload your CV to begin
                    </p>
                  )}
                  <div
                    className={`upload-zone ${dragActive ? 'dragging' : ''}`}
                    onDragEnter={handleDrag}
                    onDragOver={handleDrag}
                    onDragLeave={handleDrag}
                    onDrop={handleDrop}
                    onClick={() => document.getElementById('cv-file-input').click()}
                    tabIndex={0}
                    role="button"
                    aria-label="Upload your CV PDF document"
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        document.getElementById('cv-file-input').click();
                      }
                    }}
                  >
                    <input
                      id="cv-file-input"
                      type="file"
                      accept=".pdf,application/pdf"
                      onChange={handleFileChange}
                      style={{ display: 'none' }}
                    />
                    <Upload size={32} style={{ color: 'var(--primary-500)', marginBottom: '0.75rem' }} />
                    <p className="font-semibold text-main mb-1">
                      Drag and drop your CV PDF here, or <span style={{ color: 'var(--primary-600)', textDecoration: 'underline' }}>Browse</span>
                    </p>
                    <p className="text-xs text-muted">Supports PDF format up to 10MB</p>
                  </div>
                </div>
              ) : (
                <div className="file-preview">
                  <div className="flex items-center gap-3">
                    <FileText size={24} style={{ color: 'var(--primary-600)' }} />
                    <div>
                      <div className="font-semibold text-sm" style={{ color: 'var(--text-main)' }}>{selectedFile.name}</div>
                      <div className="text-xs text-muted">{(selectedFile.size / 1024).toFixed(1)} KB • PDF Document</div>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={removeFile}
                    className="btn btn-outline"
                    style={{ padding: '0.3rem 0.6rem', fontSize: '0.8rem' }}
                  >
                    Change File
                  </button>
                </div>
              )}
            </div>

            {/* JOB DETAILS CARD */}
            <div className="card">
              <h2 className="card-title flex items-center gap-2">
                <Briefcase size={20} style={{ color: 'var(--primary-600)' }} />
                <span>Job Details & Description</span>
              </h2>

              <div className="grid grid-cols-2" style={{ gap: '1rem', marginBottom: '1.25rem' }}>
                <div className="form-group" style={{ marginBottom: 0 }}>
                  <label htmlFor="job-title-input" className="form-label">Job Title <span className="text-muted font-normal">(Optional)</span></label>
                  <input
                    id="job-title-input"
                    type="text"
                    className="input"
                    placeholder="e.g. Senior Frontend Engineer"
                    value={jobTitle}
                    onChange={(e) => setJobTitle(e.target.value)}
                  />
                </div>

                <div className="form-group" style={{ marginBottom: 0 }}>
                  <label htmlFor="company-name-input" className="form-label">Company Name <span className="text-muted font-normal">(Optional)</span></label>
                  <input
                    id="company-name-input"
                    type="text"
                    className="input"
                    placeholder="e.g. TechCorp"
                    value={companyName}
                    onChange={(e) => setCompanyName(e.target.value)}
                  />
                </div>
              </div>

              <div className="form-group">
                <div className="flex items-center justify-between gap-2">
                  <label htmlFor="job-description-input" className="form-label">Job Description Text *</label>
                  <span
                    className="text-xs text-muted"
                    aria-live="polite"
                    style={{ color: jobDescriptionWordCount > 0 && jobDescriptionWordCount < 10 ? '#b45309' : undefined }}
                  >
                    {jobDescriptionWordCount} words
                  </span>
                </div>
                <textarea
                  id="job-description-input"
                  className="textarea"
                  rows={7}
                  placeholder="Paste the full job description here, including required skills, preferred skills, and responsibilities..."
                  value={jobDescription}
                  onChange={(e) => setJobDescription(e.target.value)}
                  aria-describedby="job-description-help"
                  required
                />
                <p id="job-description-help" className="text-xs text-muted mt-1" style={{ lineHeight: 1.45 }}>
                  Include at least 10 words. For best results, include specific technologies and expected experience levels.
                </p>
              </div>

              <div className="flex justify-between items-center mt-4 flex-wrap gap-2">
                <span className="text-xs text-muted">
                  Extracts skills and compares CV qualifications against job requirements.
                </span>
                <button
                  type="submit"
                  disabled={loading}
                  className="btn btn-primary"
                  style={{ padding: '0.75rem 1.75rem', fontSize: '0.95rem' }}
                >
                  {loading ? (
                    <>
                      <span className="spinner"></span>
                      <span>Analyzing Match...</span>
                    </>
                  ) : (
                    <>
                      <span>Analyze Match</span>
                      <ArrowRight size={18} />
                    </>
                  )}
                </button>
              </div>
            </div>
          </form>
        </div>
      ) : (
        /* ========================================================
           B. PAGE STRUCTURE (TOP TO BOTTOM) - RESULTS VIEW
           1. Header
           2. Summary card
           3. Focus First (gaps only, max 5)
           4. Skill breakdown
           5. Footer CTA "Continue to Assessment"
           ======================================================== */
        <div className="fade-in">
          {/* 1. TOP HEADER & MATCH AT A GLANCE (Consistent design with Interview Prep Hub) */}
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
            {/* Left Column: Icon + Header Info + Action Buttons */}
            <div style={{ display: 'flex', gap: '1rem', alignItems: 'flex-start', flex: '1 1 360px', minWidth: '300px' }}>
              <div className="prep-header-icon" style={{ marginTop: '0.2rem' }}>
                <Briefcase size={28} />
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.35rem', flexWrap: 'wrap' }}>
                  <span className="badge badge-purple" style={{ fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                    CV & Job Gap Analysis
                  </span>
                  <span className="text-xs text-muted">
                    Session ID #{analysisResult?.analysis_id || 'Active'}
                  </span>
                </div>
                <h1 className="page-title" style={{ fontSize: '1.75rem', fontWeight: 800, margin: '0 0 0.35rem 0', color: 'var(--text-main)', lineHeight: 1.25 }}>
                  {displayJobTitle}{displayCompany}
                </h1>
                <p className="page-subtitle" style={{ margin: '0 0 1rem 0', fontSize: '0.9rem', color: 'var(--text-muted)' }}>
                  Matched against: <strong style={{ color: 'var(--text-main)' }}>{selectedFile?.name || savedCv?.file_name || 'Uploaded Resume'}</strong>
                </p>

                <div className="flex items-center gap-2 flex-wrap">
                  <button
                    type="button"
                    onClick={handleAnalyzeAnother}
                    className="btn btn-outline flex items-center gap-1.5"
                    id="btn-analyze-another"
                    style={{ padding: '0.55rem 1rem', fontSize: '0.85rem' }}
                  >
                    <RefreshCw size={14} />
                    <span>Analyze Another Job</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      const analysisId = analysisResult?.analysis_id;
                      navigate(analysisId ? `/recommendation?analysis_id=${analysisId}` : '/recommendation');
                    }}
                    className="btn btn-primary flex items-center gap-1.5"
                    style={{ padding: '0.55rem 1.15rem', fontSize: '0.85rem', fontWeight: 600 }}
                  >
                    <Sparkles size={15} />
                    <span>View Full AI Report</span>
                  </button>
                </div>
              </div>
            </div>

            {/* Right Column: Match at a Glance Card */}
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
                  Your match at a glance
                </span>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                  <span
                    className="badge badge-purple"
                    style={{ fontSize: '0.72rem', fontWeight: 700, padding: '0.15rem 0.5rem' }}
                    title="Candidate readiness verdict"
                  >
                    {readinessVerdict}
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
                      title="Technical proficiency unverified (0 assessments completed)"
                    >
                      Preliminary
                    </span>
                  )}
                </div>
              </div>

              {/* 4 Stats Columns */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '0.75rem', textAlign: 'center' }}>
                <div
                  onClick={() => setActiveFilter('All')}
                  style={{
                    cursor: 'pointer',
                    padding: '0.25rem',
                    borderRadius: 'var(--radius-sm)',
                    backgroundColor: activeFilter === 'All' ? 'rgba(99, 102, 241, 0.08)' : 'transparent',
                    transition: 'background-color 0.15s ease',
                  }}
                  title="Show all skills"
                >
                  <div style={{ fontSize: '1.5rem', fontWeight: 800, color: 'var(--text-main)', letterSpacing: '-0.02em' }}>
                    {matchPercentage}%
                  </div>
                  <div className="text-xs text-muted">Overall Match</div>
                </div>

                <div
                  onClick={() => setActiveFilter(activeFilter === 'Matched' ? 'All' : 'Matched')}
                  style={{
                    cursor: 'pointer',
                    padding: '0.25rem',
                    borderRadius: 'var(--radius-sm)',
                    backgroundColor: activeFilter === 'Matched' ? 'rgba(34, 197, 94, 0.12)' : 'transparent',
                    transition: 'background-color 0.15s ease',
                  }}
                  title="Filter meets target skills"
                >
                  <div style={{ fontSize: '1.5rem', fontWeight: 800, color: 'var(--success-color)' }}>
                    {meetsCount}
                  </div>
                  <div className="text-xs text-muted">Meets</div>
                </div>

                <div
                  onClick={() => setActiveFilter(activeFilter === 'LevelGaps' ? 'All' : 'LevelGaps')}
                  style={{
                    cursor: 'pointer',
                    padding: '0.25rem',
                    borderRadius: 'var(--radius-sm)',
                    backgroundColor: activeFilter === 'LevelGaps' ? 'rgba(249, 115, 22, 0.12)' : 'transparent',
                    transition: 'background-color 0.15s ease',
                  }}
                  title="Filter level gap skills"
                >
                  <div style={{ fontSize: '1.5rem', fontWeight: 800, color: 'var(--warning-color)' }}>
                    {gapCount}
                  </div>
                  <div className="text-xs text-muted">Level Gaps</div>
                </div>

                <div
                  onClick={() => setActiveFilter(activeFilter === 'Missing' ? 'All' : 'Missing')}
                  style={{
                    cursor: 'pointer',
                    padding: '0.25rem',
                    borderRadius: 'var(--radius-sm)',
                    backgroundColor: activeFilter === 'Missing' ? 'rgba(239, 68, 68, 0.12)' : 'transparent',
                    transition: 'background-color 0.15s ease',
                  }}
                  title="Filter unverified skills"
                >
                  <div style={{ fontSize: '1.5rem', fontWeight: 800, color: '#ef4444' }}>
                    {missingCount}
                  </div>
                  <div className="text-xs text-muted">Unverified</div>
                </div>
              </div>

              {/* Subtitle / Explanatory footer inside card */}
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
                <span>{requiredFoundCount} of {totalRequiredCount} required skills in CV</span>
                <span>
                  {activeFilter !== 'All' ? (
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        setActiveFilter('All');
                      }}
                      style={{
                        background: 'none',
                        border: 'none',
                        color: 'var(--primary-color)',
                        cursor: 'pointer',
                        fontSize: '0.72rem',
                        padding: 0,
                        textDecoration: 'underline',
                        fontWeight: 600,
                      }}
                    >
                      Clear filter ({activeFilter === 'Matched' ? 'Meets' : activeFilter === 'LevelGaps' ? 'Level Gaps' : 'Unverified'})
                    </button>
                  ) : isPreliminary ? (
                    '0 quizzes completed'
                  ) : (
                    gapCount + missingCount === 0 ? 'All skills verified' : `${gapCount + missingCount} skill gap${gapCount + missingCount > 1 ? 's' : ''}`
                  )}
                </span>
              </div>
            </div>
          </div>

          {/* 2. SKILL MATCH TABLE */}
          <SkillMatchTable
            skills={displayedSkillsList}
            supportedSkills={supportedSkillsList}
            analysisId={activeAnalysisId}
            title="Skill match"
            className="mb-6"
          />

          {/* 4. FOOTER REPORT BAR */}
          <div
            className="card flex items-center justify-between flex-wrap gap-4"
            style={{
              padding: '1.25rem 1.5rem',
              backgroundColor: '#f8fafc',
              border: '1px solid var(--border-color)',
            }}
          >
            <div>
              <h3 className="font-bold text-main text-sm mb-0.5">Comprehensive Candidate Report Ready</h3>
              <p className="text-xs text-muted" style={{ margin: 0 }}>
                Review detailed skill explanations, ML readiness scoring, and tailored study recommendations.
              </p>
            </div>
            <button
              type="button"
              onClick={() => {
                const analysisId = analysisResult?.analysis_id;
                navigate(analysisId ? `/recommendation?analysis_id=${analysisId}` : '/recommendation');
              }}
              className="btn btn-primary flex items-center gap-2"
              style={{ padding: '0.65rem 1.5rem', fontSize: '0.875rem', fontWeight: 600 }}
            >
              <Sparkles size={16} />
              <span>Generate Full Report</span>
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
