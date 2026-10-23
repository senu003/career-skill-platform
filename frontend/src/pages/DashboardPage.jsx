import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Upload, FileText, CheckCircle2, AlertCircle, AlertTriangle,
  ArrowRight, RefreshCw, Briefcase, ChevronDown, ChevronUp,
  Target, TrendingUp, Sparkles, HelpCircle
} from 'lucide-react';
import { fetchWithAuth } from '../api';
import { useAssessment } from '../context/AssessmentContext';
import { isSupportedSkill } from '../utils/supportedSkills';

export default function DashboardPage() {
  const navigate = useNavigate();
  const { analysisResult, setAnalysisResult, clearAnalysis } = useAssessment();
  const assessmentPath = (skillName) => {
    const path = `/assessment/${encodeURIComponent(skillName)}`;
    return analysisResult?.analysis_id
      ? `${path}?analysis_id=${encodeURIComponent(analysisResult.analysis_id)}`
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
    setJobDescription('');
    setExpandedEvidence({});
    setActiveFilter('All');
    setError(null);
  };

  // Format Helper: Capitalize text strings safely
  const formatLevel = (lvl) => {
    if (!lvl) return 'N/A';
    const s = String(lvl).trim();
    return s.charAt(0).toUpperCase() + s.slice(1).toLowerCase();
  };

  // Translate required level from JD — if unspecified, show "Any Level"
  const translateRequiredLevel = (level) => {
    if (!level) return 'Any Level';
    const clean = String(level).trim().toLowerCase();
    if (clean === 'unspecified' || clean === 'none' || clean === 'null') return 'Any Level';
    if (clean === 'basic') return 'Basic';
    if (clean === 'intermediate') return 'Intermediate';
    if (clean === 'advanced') return 'Advanced';
    return formatLevel(level);
  };

  // Translate CV Level
  // "unspecified" -> "Mentioned (level unclear)"
  // "not_found"   -> "Not in CV"
  const translateCvLevel = (cvLevel, isMatched) => {
    if (!cvLevel) {
      return isMatched ? 'Mentioned (level unclear)' : 'Not in CV';
    }
    const clean = String(cvLevel).trim().toLowerCase();
    if (clean === 'unspecified') return 'Mentioned (level unclear)';
    if (clean === 'not_found' || clean === 'null' || clean === 'none') return 'Not in CV';
    if (clean === 'basic') return 'Basic';
    if (clean === 'intermediate') return 'Intermediate';
    if (clean === 'advanced') return 'Advanced';
    return formatLevel(cvLevel);
  };

  const getLevelPillClass = (levelStr, isMissing) => {
    if (isMissing) return 'level-pill-missing';
    const s = String(levelStr || '').toLowerCase();
    if (s.includes('adv')) return 'level-pill-advanced';
    if (s.includes('inter')) return 'level-pill-intermediate';
    if (s.includes('bas')) return 'level-pill-basic';
    if (s.includes('not in cv') || s.includes('missing')) return 'level-pill-missing';
    return 'level-pill-any';
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

    // Totally missing: not found in CV at all
    if (cvStatus === 'Missing' || !item.matched || cvRaw === 'not_found') {
      return 'totally_missing';
    }

    const cvVal = LEVEL_MAP[cvRaw] || 0;
    const reqVal = LEVEL_MAP[reqRaw] || 0;

    // If either side has no numeric level (unspecified), check match status
    if (cvVal === 0 || reqVal === 0) {
      // Both unspecified but still matched — treat as meets
      if (cvStatus === 'Match') return 'meets';
      if (cvStatus === 'Needs Improvement') return 'level_gap';
      return 'meets'; // graceful fallback
    }

    // Override with assessed level if available
    const assRaw = String(item.assessed_level || '').trim().toLowerCase();
    const assVal = LEVEL_MAP[assRaw] || 0;
    const compareVal = assVal > 0 ? assVal : cvVal;

    if (compareVal < reqVal) return 'level_gap';
    if (compareVal > reqVal) return 'exceeds';
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

  // Status Helper: 4-tier classification with descriptive labels and color classes
  const getSkillStatus = (skillItem) => {
    const tier = getGapTier(skillItem);
    switch (tier) {
      case 'totally_missing':
        return { label: 'Totally Missing', className: 'status-badge-missing', tier };
      case 'level_gap':
        return { label: 'Level Gap', className: 'status-badge-needs-improvement', tier };
      case 'exceeds':
        return { label: 'Exceeds Required', className: 'status-badge-exceeds', tier };
      case 'meets':
      default:
        return { label: 'Meets Requirements', className: 'status-badge-strong', tier };
    }
  };

  // One-line explanation under each gap, aware of missing levels
  const getGapExplanation = (item) => {
    const reqRaw = String(item.required_level || item.level || '').trim().toLowerCase();
    const reqStr = translateRequiredLevel(reqRaw);
    const importanceLabel = (item.importance || 'required').toLowerCase() === 'preferred' ? 'Nice-to-have' : 'Required';
    const tier = getGapTier(item);

    if (tier === 'totally_missing') {
      return `${importanceLabel} skill — not found anywhere in your CV`;
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

  const preferredFoundCount = preferredSkills.filter(isMatchedSkill).length;
  const totalPreferredCount = preferredSkills.length;

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
  const readinessReasons = analysisResult?.readiness_reasons || [];
  const verdictTheme = getVerdictTheme(readinessVerdict);

  // Check if candidate has completed any assessment
  const hasAnyAssessments = skillsList.some(s => s.assessed_level !== null && s.assessed_level !== undefined);

  // Focus First list (Gaps ONLY, max 5, ordered Required before Preferred, then largest gap first)
  const focusFirstList = (() => {
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
        ? ((s.importance || 'required').toLowerCase() === 'preferred' ? 'Preferred skill missing from CV' : 'Required skill missing from CV')
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
  const showFooterCta = Boolean(firstGapWithAssessment);

  // Category counters
  const meetsCount = skillsList.filter(s => getGapTier(s) === 'meets' || getGapTier(s) === 'exceeds').length;
  const gapCount = skillsList.filter(s => getGapTier(s) === 'level_gap').length;
  const missingCount = skillsList.filter(s => getGapTier(s) === 'totally_missing').length;

  // Header display: never show placeholder like "dfgh at ghj"
  const displayJobTitle = jobTitle && jobTitle.trim() ? jobTitle.trim() : 'Your target job';
  const displayCompany = companyName && companyName.trim() ? ` at ${companyName.trim()}` : '';

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
          {/* 1. CLEAN TOP HEADER */}
          <div className="flex justify-between items-center mb-5 flex-wrap gap-4 pb-4" style={{ borderBottom: '1px solid var(--border-color)' }}>
            <div>
              <div className="flex items-center gap-2 mb-1">
                <span className="badge badge-purple" style={{ fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                  CV & Job Gap Analysis
                </span>
                <span className="text-xs text-muted">
                  Session ID #{analysisResult?.analysis_id || 'Active'}
                </span>
              </div>
              <h1 className="page-title text-2xl font-extrabold text-main" style={{ margin: 0 }}>
                {displayJobTitle}{displayCompany}
              </h1>
              <p className="text-xs text-muted mt-1">
                Matched against: <strong style={{ color: 'var(--text-main)' }}>{selectedFile?.name || savedCv?.file_name || 'Uploaded Resume'}</strong>
              </p>
            </div>

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

          {/* 2. CLEAN STATS BAR (Sleek, uncluttered, neutral color palette) */}
          <div
            className="card mb-6"
            style={{
              padding: '1.25rem 1.75rem',
              backgroundColor: '#ffffff',
              border: '1px solid var(--border-color)',
            }}
          >
            <div className="flex items-center justify-between gap-6 flex-wrap">
              {/* Overall Match */}
              <div>
                <div className="text-xs uppercase tracking-wider font-semibold text-muted">Overall Match</div>
                <div className="font-extrabold text-3xl text-main mt-0.5" style={{ color: 'var(--text-main)', letterSpacing: '-0.02em' }}>
                  {matchPercentage}%
                </div>
                <div className="text-xs text-muted mt-0.5">
                  {requiredFoundCount} of {totalRequiredCount} required skills found in CV
                </div>
              </div>

              {/* Readiness Verdict */}
              <div style={{ borderLeft: '1px solid var(--border-color)', paddingLeft: '1.5rem' }}>
                <div className="text-xs uppercase tracking-wider font-semibold text-muted">Candidate Readiness</div>
                <div className="font-bold text-lg text-main mt-0.5">
                  {readinessVerdict}
                </div>
                <div className="text-xs text-muted mt-0.5">
                  {gapCount + missingCount === 0 ? 'All required skills verified in CV' : `${gapCount + missingCount} skill gap${gapCount + missingCount > 1 ? 's' : ''} identified`}
                </div>
              </div>

              {/* Skill Count Summaries */}
              <div className="flex items-center gap-2 flex-wrap" style={{ borderLeft: '1px solid var(--border-color)', paddingLeft: '1.5rem' }}>
                <button
                  type="button"
                  onClick={() => setActiveFilter('Matched')}
                  className="badge"
                  style={{
                    padding: '0.45rem 0.85rem',
                    backgroundColor: activeFilter === 'Matched' ? '#f1f5f9' : '#ffffff',
                    color: '#166534',
                    border: '1px solid #bbf7d0',
                    fontWeight: 600,
                    cursor: 'pointer',
                  }}
                >
                  ✓ {meetsCount} Meets
                </button>
                <button
                  type="button"
                  onClick={() => setActiveFilter('Gaps')}
                  className="badge"
                  style={{
                    padding: '0.45rem 0.85rem',
                    backgroundColor: activeFilter === 'Gaps' ? '#f1f5f9' : '#ffffff',
                    color: '#9a3412',
                    border: '1px solid #fed7aa',
                    fontWeight: 600,
                    cursor: 'pointer',
                  }}
                >
                  ⚠ {gapCount} Level Gaps
                </button>
                <button
                  type="button"
                  onClick={() => setActiveFilter('Gaps')}
                  className="badge"
                  style={{
                    padding: '0.45rem 0.85rem',
                    backgroundColor: activeFilter === 'Gaps' ? '#f1f5f9' : '#ffffff',
                    color: '#991b1b',
                    border: '1px solid #fecaca',
                    fontWeight: 600,
                    cursor: 'pointer',
                  }}
                >
                  ✕ {missingCount} Missing
                </button>
              </div>
            </div>
          </div>

          {/* 3. INTERACTIVE SKILL MATRIX (GRID) */}
          <div className="card mb-6" style={{ padding: '1.25rem 1.5rem', backgroundColor: '#ffffff' }}>
            <div className="flex items-center justify-between mb-4 flex-wrap gap-3">
              <div>
                <h2 className="card-title mb-0.5 text-lg font-bold flex items-center gap-2">
                  <span>Skill Gap & Verification Matrix</span>
                </h2>
                <p className="text-muted text-xs">
                  Compare required job skills with extracted CV evidence and take assessments to verify each skill level.
                </p>
              </div>

              {/* Filter Tabs */}
              <div className="filter-chips" role="group" aria-label="Filter skills">
                {[
                  { id: 'All', label: 'All Skills', count: skillsList.length },
                  { id: 'Gaps', label: 'Gaps Only', count: allGapSkills.length },
                  { id: 'Matched', label: 'Meets / Exceeds', count: meetsCount },
                  { id: 'Required', label: 'Required', count: requiredSkills.length },
                  { id: 'Preferred', label: 'Nice to Have', count: preferredSkills.length },
                ].map((chip) => (
                  <button
                    key={chip.id}
                    type="button"
                    className={`filter-chip ${activeFilter === chip.id ? 'active' : ''}`}
                    onClick={() => setActiveFilter(chip.id)}
                  >
                    <span>{chip.label}</span>
                    <span className="filter-chip-count">{chip.count}</span>
                  </button>
                ))}
              </div>
            </div>

            {/* The Modern Grid Table */}
            <div className="skill-matrix-container">
              <table className="skill-matrix-table" aria-label="Skill Gap Analysis Matrix">
                <thead>
                  <tr>
                    <th style={{ width: '22%' }}>Skill</th>
                    <th style={{ width: '13%' }}>Importance</th>
                    <th style={{ width: '16%' }}>Job Requirement</th>
                    <th style={{ width: '17%' }}>Your CV Evidence</th>
                    <th style={{ width: '16%' }}>Match Status</th>
                    <th style={{ width: '16%', textAlign: 'right' }}>Assessment & Action</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredBreakdownSkills.length === 0 ? (
                    <tr>
                      <td colSpan={6} style={{ textAlign: 'center', padding: '2.5rem', color: 'var(--text-muted)' }}>
                        No skills match the selected "{activeFilter}" filter.
                      </td>
                    </tr>
                  ) : (
                    filteredBreakdownSkills.map((item, idx) => {
                      const status = getSkillStatus(item);
                      const isGap = isSkillGap(item);
                      const tier = status.tier;
                      const reqLvl = translateRequiredLevel(item.required_level || item.level);
                      const isNiceToHave = (item.importance || 'required').toLowerCase() === 'preferred';
                      const isAssessed = item.assessed_level !== null && item.assessed_level !== undefined;
                      const skillKey = item.skill || idx;
                      const isAvailable = isSkillAvailable(item.skill);
                      const cvLvlDisplay = translateCvLevel(item.cv_level, item.matched);
                      const isMissingInCv = cvLvlDisplay === 'Not in CV';

                      return (
                        <React.Fragment key={skillKey}>
                          <tr>
                            {/* 1. Skill Name */}
                            <td>
                              <div className="font-bold text-main flex items-center gap-1.5">
                                <span>{item.skill}</span>
                              </div>
                              <button
                                type="button"
                                onClick={() => toggleEvidence(skillKey)}
                                className="text-xs text-muted flex items-center gap-1 mt-1 hover:text-primary-600"
                                style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}
                              >
                                <FileText size={11} />
                                <span style={{ textDecoration: 'underline' }}>
                                  {expandedEvidence[skillKey] ? 'Hide CV quote' : 'View CV quote'}
                                </span>
                              </button>
                            </td>

                            {/* 2. Importance */}
                            <td>
                              <span
                                className="badge"
                                style={{
                                  fontSize: '0.72rem',
                                  fontWeight: 600,
                                  backgroundColor: isNiceToHave ? '#ffffff' : '#f1f5f9',
                                  color: isNiceToHave ? '#64748b' : '#1e293b',
                                  border: isNiceToHave ? '1px solid #e2e8f0' : '1px solid #cbd5e1',
                                }}
                              >
                                {isNiceToHave ? 'Nice to Have' : 'Required'}
                              </span>
                            </td>

                            {/* 3. Job Requirement Level */}
                            <td>
                              <span className={`level-pill ${getLevelPillClass(reqLvl, false)}`}>
                                {reqLvl}
                              </span>
                            </td>

                            {/* 4. CV Level */}
                            <td>
                              <span className={`level-pill ${getLevelPillClass(cvLvlDisplay, isMissingInCv)}`}>
                                {cvLvlDisplay}
                              </span>
                            </td>

                            {/* 5. Match Status Badge */}
                            <td>
                              <span className={`status-badge ${status.className}`} style={{ fontSize: '0.78rem' }}>
                                {status.label}
                              </span>
                            </td>

                            {/* 6. Assessment / Action */}
                            <td style={{ textAlign: 'right' }}>
                              {isAssessed ? (
                                <div className="flex flex-col items-end gap-1">
                                  <span
                                    className="badge"
                                    style={{
                                      backgroundColor: '#ecfdf5',
                                      color: '#059669',
                                      border: '1px solid #a7f3d0',
                                      fontWeight: 600,
                                      fontSize: '0.75rem',
                                    }}
                                  >
                                    Assessed: {formatLevel(item.assessed_level)}
                                  </span>
                                  {isAvailable && (
                                    <button
                                      type="button"
                                      onClick={() => navigate(assessmentPath(item.skill))}
                                      className="text-xs text-muted hover:text-primary-600"
                                      style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}
                                    >
                                      Retake test
                                    </button>
                                  )}
                                </div>
                              ) : isAvailable ? (
                                isGap ? (
                                  <button
                                    type="button"
                                    onClick={() => navigate(assessmentPath(item.skill))}
                                    className="btn btn-primary"
                                    style={{
                                      padding: '0.35rem 0.85rem',
                                      fontSize: '0.78rem',
                                      whiteSpace: 'nowrap',
                                    }}
                                  >
                                    Take Assessment →
                                  </button>
                                ) : (
                                  <button
                                    type="button"
                                    onClick={() => navigate(assessmentPath(item.skill))}
                                    className="btn btn-outline"
                                    style={{
                                      padding: '0.35rem 0.75rem',
                                      fontSize: '0.78rem',
                                      whiteSpace: 'nowrap',
                                    }}
                                  >
                                    Verify Level
                                  </button>
                                )
                              ) : (
                                <span className="text-xs text-muted" style={{ fontStyle: 'italic' }}>
                                  CV verified
                                </span>
                              )}
                            </td>
                          </tr>

                          {/* Expanded Evidence Accordion Row */}
                          {expandedEvidence[skillKey] && (
                            <tr style={{ backgroundColor: '#f8fafc' }}>
                              <td colSpan={6} style={{ padding: '0.75rem 1.25rem', borderBottom: '1px solid var(--border-color)' }}>
                                <div className="flex items-start gap-2">
                                  <span className="text-xs font-bold text-muted uppercase">CV Context:</span>
                                  <span className="text-xs text-main" style={{ fontStyle: 'italic', lineHeight: 1.5 }}>
                                    {item.evidence && item.evidence.trim() ? `"${item.evidence}"` : 'No direct mention found in CV text.'}
                                  </span>
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
